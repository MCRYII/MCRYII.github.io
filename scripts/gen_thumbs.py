# -*- coding: utf-8 -*-
"""为 static/images 下的图片生成 640px 宽缩略图到 static/images/thumbs/（统一转 JPG）。
构建前运行一次即可；已存在且比原图新的缩略图会跳过。"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGES_DIR = os.path.join(ROOT, "static", "images")
THUMBS_DIR = os.path.join(IMAGES_DIR, "thumbs")
WIDTH = 640
QUALITY = 82
EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")


def main():
    if not os.path.isdir(IMAGES_DIR):
        print("static/images 不存在，跳过")
        return
    os.makedirs(THUMBS_DIR, exist_ok=True)
    made = skipped = failed = 0
    for name in sorted(os.listdir(IMAGES_DIR)):
        src = os.path.join(IMAGES_DIR, name)
        if not os.path.isfile(src):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext not in EXTS:
            continue
        stem = os.path.splitext(name)[0]
        dst = os.path.join(THUMBS_DIR, stem + ".jpg")
        if os.path.isfile(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
            skipped += 1
            continue
        try:
            img = Image.open(src)
            img.load()
        except Exception as e:
            print(f"跳过无法读取的图片 {name}: {e}")
            failed += 1
            continue
        try:
            if img.width > WIDTH:
                img = img.resize((WIDTH, round(img.height * WIDTH / img.width)), Image.LANCZOS)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            img.save(dst, "JPEG", quality=QUALITY, optimize=True, progressive=True)
            made += 1
        except Exception as e:
            print(f"缩略图生成失败 {name}: {e}")
            failed += 1
    print(f"缩略图：新增 {made} 张，跳过 {skipped} 张，失败 {failed} 张")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
