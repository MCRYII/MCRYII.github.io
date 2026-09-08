# -*- coding: utf-8 -*-
"""自动拉取 B 站个人空间最新投稿视频并生成博客文章。

功能：
1. 请求 B 站个人空间投稿列表接口（默认 UID: 678345234）。
2. 检测 content/posts/ 中是否已存在对应 BV 号的文章（bili-<bvid>.md）。
3. 发现新视频时，下载封面图片至 static/images/。
4. 按既有模板格式在 content/posts/ 生成 Markdown 文章。
5. 自动调用 scripts/gen_thumbs.py 生成 640px 缩略图。
"""
import datetime
import json
import os
import re
import subprocess
import sys
import urllib.request

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS_DIR = os.path.join(ROOT, "content", "posts")
IMAGES_DIR = os.path.join(ROOT, "static", "images")
THUMBS_SCRIPT = os.path.join(ROOT, "scripts", "gen_thumbs.py")

DEFAULT_MID = "678345234"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": f"https://space.bilibili.com/{DEFAULT_MID}",
}


def fetch_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download_file(url, dest_path):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
    with open(dest_path, "wb") as f:
        f.write(data)


def extract_tags(title):
    tags = ["新视频", "游戏"]
    t_lower = title.lower()
    if "鬼泣" in title or "维吉尔" in title or "但丁" in title or "dmd" in t_lower or "hah" in t_lower:
        tags.append("鬼泣5")
    if "维吉尔" in title:
        tags.append("维吉尔")
    if "质量效应" in title:
        tags.append("质量效应")
    if "底特律" in title:
        tags.append("底特律")
    if "死亡搁浅" in title:
        tags.append("死亡搁浅")
    if "生化危机" in title:
        tags.append("生化危机")
    if "开拓者" in title:
        tags.append("开拓者")
    if "全流程" in title or "流程" in title or "最终决战" in title:
        tags.append("流程记录")
    # 去重且保序
    seen = set()
    result = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            result.append(tag)
    return result


def format_desc(desc):
    if not desc or not desc.strip():
        return "> {{< icon \"pen\" >}} 视频简介：暂无简介\n"
    lines = [l.strip() for l in desc.strip().splitlines() if l.strip()]
    if not lines:
        return "> {{< icon \"pen\" >}} 视频简介：暂无简介\n"
    result = []
    for i, line in enumerate(lines):
        is_last = (i == len(lines) - 1)
        suffix = "" if is_last else "\\\n"
        if i == 0:
            result.append(f"> {{{{< icon \"pen\" >}}}} 视频简介：{line}{suffix}")
        else:
            result.append(f"> {line}{suffix}")
    return "".join(result) + "\n"


def sync_videos(mid=DEFAULT_MID, limit=20):
    os.makedirs(POSTS_DIR, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)

    list_url = f"https://api.bilibili.com/x/v2/medialist/resource/list?mobi_app=web&type=1&biz_id={mid}&ps={limit}"
    print(f"正在获取 B 站个人空间投稿 (UID: {mid})...")
    try:
        list_data = fetch_json(list_url)
    except Exception as e:
        print(f"获取投稿列表失败: {e}")
        return 1

    items = list_data.get("data", {}).get("media_list", [])
    if not items:
        print("未获取到任何投稿视频。")
        return 0

    new_posts = []
    # 查找本地已收录的最新视频发布时间
    latest_existing_ts = 0
    sync_all = "--all" in sys.argv
    if not sync_all and os.path.exists(POSTS_DIR):
        for f in os.listdir(POSTS_DIR):
            if f.startswith("bili-") and f.endswith(".md"):
                try:
                    with open(os.path.join(POSTS_DIR, f), "r", encoding="utf-8") as fp:
                        for line in fp:
                            if line.startswith("date:"):
                                date_str_val = line.split(":", 1)[1].strip()
                                dt_val = datetime.datetime.fromisoformat(date_str_val)
                                if dt_val.timestamp() > latest_existing_ts:
                                    latest_existing_ts = dt_val.timestamp()
                                break
                except Exception:
                    pass

    # 按照发布时间从旧到新处理
    for it in reversed(items):
        bvid = it.get("bv_id")
        if not bvid:
            continue
        pubtime_ts = it.get("pubtime", 0)
        if not sync_all and latest_existing_ts > 0 and pubtime_ts <= latest_existing_ts:
            continue

        post_filename = f"bili-{bvid.lower()}.md"
        post_path = os.path.join(POSTS_DIR, post_filename)
        if os.path.exists(post_path):
            continue

        print(f"\n发现新视频: {bvid} - {it.get('title')}")
        # 获取详情
        detail_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        try:
            d_json = fetch_json(detail_url)
            d = d_json.get("data", {})
        except Exception as e:
            print(f"获取视频详情失败 ({bvid}): {e}")
            d = it

        title = d.get("title", it.get("title", "")).strip()
        pubdate_ts = d.get("pubdate") or it.get("pubtime", 0)
        dt = datetime.datetime.fromtimestamp(pubdate_ts)
        date_iso = dt.strftime("%Y-%m-%dT%H:%M:00+08:00")
        date_str = dt.strftime("%Y-%m-%d")
        pub_str = dt.strftime("%Y-%m-%d %H:%M")

        duration_sec = d.get("duration") or it.get("duration", 0)
        mins = duration_sec // 60
        secs = duration_sec % 60
        dur_str = f"{mins}:{secs:02d}"

        views = d.get("stat", {}).get("view", 0)
        tname = d.get("tname") or "生活"
        pic_url = d.get("pic") or it.get("cover")
        desc = d.get("desc", "")

        # 下载封面图
        cover_filename = f"bili-{bvid.lower()}-cover.jpg"
        cover_path = os.path.join(IMAGES_DIR, cover_filename)
        if pic_url:
            print(f"正在下载封面: {pic_url} -> {cover_filename}")
            try:
                download_file(pic_url, cover_path)
            except Exception as e:
                print(f"封面下载失败: {e}")

        # 格式化标题
        display_title = title if (title.startswith("《") and title.endswith("》")) else f"《{title}》"
        tags = extract_tags(title)
        tags_yaml = ", ".join(f'"{t}"' for t in tags)
        desc_block = format_desc(desc)

        md_content = f"""---
title: "{date_str} 新视频发布"
date: {date_iso}
categories: ["MCRYII"]
tags: [{tags_yaml}]
draft: false
cover:
  image: "/images/{cover_filename}"
---

![{display_title} 封面](/images/{cover_filename})

MCRYII 的新视频发布啦！本期视频是 **{display_title}**。

| 项目 | 信息 |
| --- | --- |
| {{{{< icon "calendar" >}}}} 发布时间 | {pub_str} |
| {{{{< icon "clock" >}}}} 视频时长 | {dur_str} |
| {{{{< icon "eye" >}}}} 播放量 | {views} |
| {{{{< icon "video" >}}}} 分区 | {tname} |
| {{{{< icon "link" >}}}} 视频链接 | https://www.bilibili.com/video/{bvid} |

{desc_block}
[{{{{< icon "play" >}}}} 前往 B 站观看完整视频](https://www.bilibili.com/video/{bvid})

---

*本文章由 B 站新视频自动整理生成。*
"""
        with open(post_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"已创建文章: content/posts/{post_filename}")
        new_posts.append(post_filename)

    if new_posts:
        print(f"\n成功创建 {len(new_posts)} 篇新文章！")
        if os.path.exists(THUMBS_SCRIPT):
            print("正在调用缩略图生成脚本...")
            subprocess.run([sys.executable, THUMBS_SCRIPT], cwd=ROOT)
    else:
        print("\n所有视频已在博客中收录，无需更新。")

    return 0


if __name__ == "__main__":
    sys.exit(sync_videos())
