#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查核心 JS 文件的修改时间，若新于 hugo.yaml 则自动递增 assetsVersion。"""
import datetime
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HUGO_YAML = os.path.join(ROOT, "hugo.yaml")
JS_FILES = [
    os.path.join(ROOT, "static", "js", "nav.js"),
    os.path.join(ROOT, "static", "js", "global-nav.js"),
    os.path.join(ROOT, "static", "js", "scroll-effects.js"),
    os.path.join(ROOT, "static", "js", "dino-game.js"),
]


def main():
    if not os.path.isfile(HUGO_YAML):
        return
    yaml_mtime = os.path.getmtime(HUGO_YAML)
    existing_js = [f for f in JS_FILES if os.path.isfile(f)]
    if not existing_js:
        return
    latest_js_mtime = max(os.path.getmtime(f) for f in existing_js)
    if latest_js_mtime <= yaml_mtime:
        return

    with open(HUGO_YAML, "r", encoding="utf-8") as f:
        content = f.read()

    today = datetime.datetime.now().strftime("%Y%m%d")
    match = re.search(r"assetsVersion:\s*['\"]" + today + r"-(\d+)['\"]", content)
    if match:
        new_ver = f"{today}-{int(match.group(1)) + 1}"
    else:
        new_ver = f"{today}-1"

    new_content = re.sub(r"assetsVersion:\s*['\"][^'\"]+['\"]", f"assetsVersion: '{new_ver}'", content)
    if new_content != content:
        with open(HUGO_YAML, "w", encoding="utf-8", newline="\n") as f:
            f.write(new_content)
        print(f"[assetsVersion] 已自动递增更新为: {new_ver}")


if __name__ == "__main__":
    main()
