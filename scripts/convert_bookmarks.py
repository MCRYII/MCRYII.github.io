#!/usr/bin/env python3
"""把浏览器导出的书签 HTML 转换为 Hugo data/bookmarks.json

用法:
    python scripts/convert_bookmarks.py [书签文件路径] [输出路径]
默认读取桌面 favorites_2026_7_31.html，输出到 data/bookmarks.json
"""
import json
import os
import sys
from html.parser import HTMLParser

DEFAULT_SRC = r"C:\Users\MCRYII\Desktop\favorites_2026_7_31.html"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(PROJECT_ROOT, "data", "bookmarks.json")
STATIC_OUT = os.path.join(PROJECT_ROOT, "static", "bookmarks.json")


class BookmarkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.folder_stack = []
        self.categories = []
        self.orphans = []
        self.buf = []
        self.mode = None
        self.cur_a = None

    def handle_starttag(self, tag, attrs):
        if tag == "h3":
            self.mode = "h3"
            self.buf = []
        elif tag == "a":
            attrs = dict(attrs)
            self.mode = "a"
            self.buf = []
            self.cur_a = {"href": attrs.get("href", "")}

    def handle_data(self, data):
        if self.mode in ("h3", "a"):
            self.buf.append(data)

    def handle_endtag(self, tag):
        if tag == "h3" and self.mode == "h3":
            name = "".join(self.buf).strip()
            self.folder_stack.append({"name": name, "links": []})
            self.mode = None
        elif tag == "a" and self.mode == "a":
            title = "".join(self.buf).strip() or self.cur_a["href"]
            item = {"title": title, "url": self.cur_a["href"]}
            if self.folder_stack:
                self.folder_stack[-1]["links"].append(item)
            else:
                self.orphans.append(item)
            self.mode = None
        elif tag == "dl":
            if self.folder_stack:
                done = self.folder_stack.pop()
                if self.folder_stack:
                    if "children" not in self.folder_stack[-1]:
                        self.folder_stack[-1]["children"] = []
                    self.folder_stack[-1]["children"].append(done)
                else:
                    self.categories.append(done)


def collect_links(folder):
    links = list(folder.get("links", []))
    for child in folder.get("children", []):
        links.extend(collect_links(child))
    return links


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC
    out = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT

    parser = BookmarkParser()
    with open(src, encoding="utf-8") as f:
        parser.feed(f.read())

    cats = []
    toolbar = next((c for c in parser.categories if c.get("name") == "收藏夹栏"), None)
    if toolbar:
        # 收藏夹栏下的子分类提升为一级分类
        for child in toolbar.get("children", []):
            cats.append({"name": child["name"], "links": collect_links(child)})
        if toolbar.get("links"):
            cats.append({"name": "常用", "links": toolbar["links"]})
    for c in parser.categories:
        if c is not toolbar:
            cats.append({"name": c["name"], "links": collect_links(c)})
    if parser.orphans:
        cats.append({"name": "常用", "links": parser.orphans})

    # 单分类内去重，过滤空分类
    out_cats = []
    for c in cats:
        seen = set()
        uniq = []
        for link in c["links"]:
            if link["url"] not in seen:
                seen.add(link["url"])
                uniq.append(link)
        if uniq:
            out_cats.append({"name": c["name"], "links": uniq})

    # 分类排序：常用 / ai / UT / 工具 / STEAM / 游戏资源 / 其它资源 / ACG / 呃呃
    ORDER = ["常用", "ai", "UT", "工具", "STEAM", "游戏资源", "其它资源", "ACG", "呃呃"]
    out_cats.sort(key=lambda c: ORDER.index(c["name"]) if c["name"] in ORDER else 999)

    total = sum(len(c["links"]) for c in out_cats)
    payload = {"categories": out_cats, "total": total}

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    # 同时输出一份到 static，供网站导航页验证后拉取
    with open(STATIC_OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    print("categories:", len(out_cats))
    print("total links:", total)
    print("static copy saved to", STATIC_OUT)
    for c in out_cats:
        print("-", c["name"], len(c["links"]))
    print("saved to", out)


if __name__ == "__main__":
    main()
