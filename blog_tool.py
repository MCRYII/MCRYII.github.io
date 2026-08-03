# -*- coding: utf-8 -*-
"""MCRYII 博客写作助手（现代化重构版）

功能：文章管理 / 封面编辑 / Markdown 预览 / 图片插入 / 本地预览 / 一键推送
网页版：python blog_tool.py --web 后浏览器打开 http://127.0.0.1:8777/
"""
import base64
import datetime
import io
import json
import mimetypes
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk

from PIL import Image, ImageTk

# ==================== 配置 ====================
BLOG_ROOT = r"D:\Downloads\Programs\myblog-new"
POSTS_BASE = os.path.join(BLOG_ROOT, "content", "posts")
IMAGES_DIR = os.path.join(BLOG_ROOT, "static", "images")
DEFAULT_COVER = os.path.join(IMAGES_DIR, "default-cover.png")
MOMENTS_FILE = os.path.join(BLOG_ROOT, "data", "moments.json")
MOMENTS_IMAGES_DIR = os.path.join(IMAGES_DIR, "moments")
MUSIC_DIR = os.path.join(BLOG_ROOT, "static", "music")
MUSIC_DATA_FILE = os.path.join(BLOG_ROOT, "data", "music.json")
MUSIC_EXTS = (".mp3", ".m4a", ".ogg", ".flac", ".wav")
WEB_UPLOAD_MAX_MB = 20  # 网页版上传上限（base64 会放大内存占用，大文件请用桌面版）
FILES_DIR = os.path.join(BLOG_ROOT, "static", "files")
COMFY_ROOT = r"D:\Downloads\Programs\ComfyUI-aki-v3\ComfyUI"
COMFY_PYTHON = r"D:\Downloads\Programs\ComfyUI-aki-v3\python\python.exe"
COMFY_OUTPUT_DIR = os.path.join(COMFY_ROOT, "output")
COMFY_HOST = "127.0.0.1"
COMFY_PORT = 8188
COMFY_API_URL = "http://{}:{}".format(COMFY_HOST, COMFY_PORT)
COMFY_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
AI_DEFAULT_NEGATIVE = "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry"

# ==================== 配色（深色 + 金色，与博客一致） ====================
COL_BG = "#16161a"
COL_PANEL = "#202024"
COL_PANEL2 = "#26262c"
COL_BORDER = "#34343c"
COL_TEXT = "#e8e8e8"
COL_MUTED = "#8f8f98"
COL_GOLD = "#d4af37"
COL_GOLD_DARK = "#a8872a"
COL_SELECT = "#3a3522"
COL_GREEN = "#6fbf73"
COL_RED = "#e5484d"
COL_INPUT = "#1b1b1f"

FONT = "微软雅黑"
FONT_MONO = "Consolas"


def is_git_repo():
    return os.path.isdir(os.path.join(BLOG_ROOT, ".git"))


def load_moments():
    """读取动态列表，文件不存在或损坏时返回空列表"""
    try:
        with open(MOMENTS_FILE, "r", encoding="utf-8") as f:
            entries = json.load(f).get("moments", [])
    except (OSError, ValueError):
        return []
    changed = False
    for i, e in enumerate(entries):
        if not e.get("id"):
            e["id"] = "m{}{}".format(datetime.datetime.now().strftime("%Y%m%d%H%M%S"), i)
            changed = True
    if changed:
        save_moments(entries)
    return entries


def save_moments(entries):
    os.makedirs(os.path.dirname(MOMENTS_FILE), exist_ok=True)
    with open(MOMENTS_FILE, "w", encoding="utf-8") as f:
        json.dump({"moments": entries}, f, ensure_ascii=False, indent=2)
        f.write("\n")


def load_music_data():
    """读取歌单配置；文件不存在或损坏时返回默认（仅"全部"歌单）"""
    try:
        with open(MUSIC_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict) or "playlists" not in data:
        data = {"playlists": [{"name": "全部", "order": []}]}
    if not any(p.get("name") == "全部" for p in data["playlists"]):
        data["playlists"].insert(0, {"name": "全部", "order": []})
    return data


def save_music_data(data):
    normalize_music_all(data)
    os.makedirs(os.path.dirname(MUSIC_DATA_FILE), exist_ok=True)
    with open(MUSIC_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def scan_music_files():
    """扫描 static/music/ 下所有音频文件，按文件名排序"""
    out = []
    if os.path.isdir(MUSIC_DIR):
        for f in sorted(os.listdir(MUSIC_DIR)):
            if f.lower().endswith(MUSIC_EXTS):
                out.append(f)
    return out


def normalize_music_all(data):
    """让"全部"歌单的 order 与 static/music 实际文件同步（保留已有顺序）"""
    files = scan_music_files()
    if not isinstance(data, dict):
        data = {}
    if not isinstance(data.get("playlists"), list):
        data["playlists"] = []
    if not any(p.get("name") == "全部" for p in data["playlists"]):
        data["playlists"].insert(0, {"name": "全部", "order": []})
    pl = next(p for p in data["playlists"] if p.get("name") == "全部")
    order = pl.setdefault("order", [])
    if not isinstance(order, list):
        order = pl["order"] = []
    for stale in [n for n in order if n not in files]:
        order.remove(stale)
    for f in files:
        if f not in order:
            order.append(f)
    return data


def parse_music_name(fname):
    """从 '作者 - 歌名.mp3' 解析作者和歌名"""
    base = os.path.splitext(fname)[0]
    if " - " in base:
        artist, title = base.split(" - ", 1)
        return artist.strip(), title.strip()
    return "", base


def scan_posts():
    """扫描 content/posts 下所有 markdown，返回 (相对路径, 绝对路径) 列表"""
    out = []
    for root, _, files in os.walk(POSTS_BASE):
        for f in files:
            if f.endswith(".md"):
                full = os.path.join(root, f)
                out.append((os.path.relpath(full, POSTS_BASE), full))
    return out


def parse_list(raw):
    try:
        return json.loads(f"[{raw}]")
    except Exception:
        return [x.strip().strip("\"'") for x in raw.split(",") if x.strip()]


def parse_front(content):
    """解析文章 front matter，返回 dict（title/date/categories/tags/draft/cover）"""
    data = {"title": None, "date": None, "categories": [], "tags": [],
            "draft": False, "cover": None}
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not m:
        return data
    yaml_text = m.group(1)
    t = re.search(r"title:\s*[\"']?(.*?)[\"']?\s*$", yaml_text, re.MULTILINE)
    d = re.search(r"date:\s*(\S+)", yaml_text)
    dr = re.search(r"draft:\s*(true|false)", yaml_text)
    c = re.search(r"categories:\s*\[(.*?)\]", yaml_text)
    g = re.search(r"tags:\s*\[(.*?)\]", yaml_text)
    cv = re.search(r"cover:\s*\n\s+image:\s*[\"']?(.+?)[\"']?\s*$", yaml_text, re.MULTILINE)
    if t:
        data["title"] = t.group(1).strip("\"' ")
    if d:
        data["date"] = d.group(1).strip()
    if dr:
        data["draft"] = dr.group(1) == "true"
    if c:
        data["categories"] = parse_list(c.group(1))
    if g:
        data["tags"] = parse_list(g.group(1))
    if cv:
        data["cover"] = cv.group(1).strip()
    return data


def build_article_front(title, date, cats, tags, draft, cover):
    """组装文章 front matter 文本"""
    lines = ["---", f'title: "{title}"', f"date: {date}",
             f"categories: {json.dumps(cats or [], ensure_ascii=False)}",
             f"tags: {json.dumps(tags or [], ensure_ascii=False)}",
             f"draft: {str(bool(draft)).lower()}"]
    if cover:
        lines.append("cover:")
        lines.append(f'  image: "{cover}"')
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def save_article_file(filepath, title, date, cats, tags, draft, cover, body):
    """写入文章文件；新文章自动生成文件名，返回最终路径"""
    if not filepath or not os.path.exists(filepath):
        safe = re.sub(r'[\\/:*?"<>|]', "", title).replace(" ", "-")
        filepath = os.path.join(POSTS_BASE, safe + ".md")
        if os.path.exists(filepath):
            filepath = os.path.join(POSTS_BASE, safe + f"-{int(datetime.datetime.now().timestamp())}.md")
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(build_article_front(title, date, cats, tags, draft, cover) + body)
    return filepath


def fmt_size(n):
    """文件大小转可读文本（B / KB / MB / GB）"""
    if n >= 1073741824:
        return f"{n / 1073741824:.2f} GB"
    if n >= 1048576:
        return f"{n / 1048576:.1f} MB"
    if n >= 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n} B"


class TagInputWidget(tk.Frame):
    """分类 / 标签输入组件"""

    def __init__(self, master, title="", **kw):
        super().__init__(master, bg=COL_PANEL, **kw)
        self.title = title
        self.tags = []
        self._build()

    def _build(self):
        tk.Label(self, text=self.title, anchor="w", bg=COL_PANEL, fg=COL_MUTED,
                 font=(FONT, 9)).pack(fill=tk.X, pady=(0, 4))
        row = tk.Frame(self, bg=COL_PANEL)
        row.pack(fill=tk.X, pady=(0, 6))
        self.entry = tk.Entry(row, bg=COL_INPUT, fg=COL_TEXT, insertbackground=COL_GOLD,
                              relief=tk.FLAT, font=(FONT, 10), highlightthickness=1,
                              highlightbackground=COL_BORDER, highlightcolor=COL_GOLD)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        self.entry.bind("<Return>", self.add_tag)
        self.entry.bind("<KP_Enter>", self.add_tag)
        self.tags_frame = tk.Frame(self, bg=COL_PANEL)
        self.tags_frame.pack(fill=tk.X, anchor="w")
        self._refresh()

    def add_tag(self, _=None):
        text = self.entry.get().strip()
        if text and text not in self.tags:
            self.tags.append(text)
            self.entry.delete(0, tk.END)
            self._refresh()
        return "break"

    def remove_tag(self, tag):
        if tag in self.tags:
            self.tags.remove(tag)
            self._refresh()

    def _refresh(self):
        for w in self.tags_frame.winfo_children():
            w.destroy()
        if not self.tags:
            tk.Label(self.tags_frame, text="输入后回车添加", fg="#5c5c66",
                     bg=COL_PANEL, font=(FONT, 9)).pack(side=tk.LEFT, padx=4)
            return
        for tag in self.tags:
            chip = tk.Frame(self.tags_frame, bg=COL_SELECT, highlightthickness=1,
                            highlightbackground=COL_GOLD_DARK)
            chip.pack(side=tk.LEFT, padx=3, pady=2)
            tk.Label(chip, text=tag, bg=COL_SELECT, fg=COL_GOLD,
                     font=(FONT, 9)).pack(side=tk.LEFT, padx=(8, 2), pady=3)
            tk.Label(chip, text="x", bg=COL_SELECT, fg=COL_RED, cursor="hand2",
                     font=(FONT, 9)).pack(side=tk.LEFT, padx=(2, 7))
            chip.winfo_children()[-1].bind("<Button-1>", lambda e, t=tag: self.remove_tag(t))

    def get_tags(self):
        return self.tags

    def set_tags(self, tag_list):
        self.tags = list(tag_list or [])
        self._refresh()


class CoverCropDialog(tk.Toplevel):
    """封面裁剪编辑器：锁定 5:3 比例，支持拖动选区、移动选区、缩放选区"""

    RATIO = 5 / 3

    def __init__(self, master, image_path):
        super().__init__(master)
        self.title("调整封面裁剪（5:3）")
        self.configure(bg=COL_PANEL)
        self.resizable(False, False)
        self.transient(master)
        self.result = None

        self.img = Image.open(image_path).convert("RGB")
        self.iw, self.ih = self.img.size

        cw, ch = 780, 560
        self.scale = min(cw / self.iw, ch / self.ih)
        self.dw = max(1, int(self.iw * self.scale))
        self.dh = max(1, int(self.ih * self.scale))
        self.ox = (cw - self.dw) // 2
        self.oy = (ch - self.dh) // 2

        self.canvas = tk.Canvas(self, width=cw, height=ch, bg="#0f0f12",
                                highlightthickness=0, cursor="crosshair")
        self.canvas.pack(padx=12, pady=(12, 6))
        self.photo = ImageTk.PhotoImage(
            self.img.resize((self.dw, self.dh), Image.LANCZOS))

        self._init_rect()
        self.mode = None
        self.drag = None
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        bar = tk.Frame(self, bg=COL_PANEL)
        bar.pack(fill=tk.X, padx=12, pady=(0, 12))
        tk.Label(bar, text="拖动框可移动 · 右下角金块可缩放 · 空白处拖动新建选区",
                 bg=COL_PANEL, fg=COL_MUTED, font=(FONT, 9)).pack(side=tk.LEFT)
        btn_reset = tk.Button(bar, text="重置", command=self._reset,
                              bg=COL_PANEL2, fg=COL_TEXT, relief=tk.FLAT,
                              activebackground=COL_SELECT, activeforeground=COL_GOLD,
                              font=(FONT, 10), cursor="hand2", padx=12, pady=4)
        btn_reset.pack(side=tk.RIGHT, padx=4)
        btn_cancel = tk.Button(bar, text="取消", command=self._cancel,
                               bg="#3a2023", fg=COL_RED, relief=tk.FLAT,
                               activebackground="#4a262a", activeforeground="#ff7a80",
                               font=(FONT, 10), cursor="hand2", padx=12, pady=4)
        btn_cancel.pack(side=tk.RIGHT, padx=4)
        btn_ok = tk.Button(bar, text="确认裁剪", command=self._confirm,
                           bg=COL_GOLD, fg="#1b1405", relief=tk.FLAT,
                           activebackground="#e0bc4e", activeforeground="#1b1405",
                           font=(FONT, 10, "bold"), cursor="hand2", padx=16, pady=4)
        btn_ok.pack(side=tk.RIGHT, padx=4)
        self._draw()

    def _init_rect(self):
        w = min(self.iw, int(self.ih * self.RATIO))
        h = int(w / self.RATIO)
        self.rect = [(self.iw - w) // 2, (self.ih - h) // 2, w, h]

    def _reset(self):
        self._init_rect()
        self._draw()

    def _cancel(self):
        self.result = None
        self.destroy()

    def _confirm(self):
        x, y, w, h = self.rect
        if w < 20 or h < 20:
            return
        self.result = self.img.crop((x, y, x + w, y + h))
        self.destroy()

    def _to_canvas(self, x, y):
        return self.ox + x * self.scale, self.oy + y * self.scale

    def _to_img(self, cx, cy):
        return (cx - self.ox) / self.scale, (cy - self.oy) / self.scale

    def _draw(self):
        self.canvas.delete("all")
        self.canvas.create_image(self.ox, self.oy, image=self.photo, anchor="nw")
        x, y, w, h = self.rect
        cx, cy = self._to_canvas(x, y)
        cw2, ch2 = w * self.scale, h * self.scale
        self.canvas.create_rectangle(cx, cy, cx + cw2, cy + ch2,
                                     outline=COL_GOLD, width=2)
        self.canvas.create_rectangle(cx + cw2 - 10, cy + ch2 - 10,
                                     cx + cw2 + 2, cy + ch2 + 2,
                                     fill=COL_GOLD, outline="")
        self.canvas.create_text(cx + 4, cy - 6, text=f"{w} × {h}",
                                anchor="sw", fill=COL_GOLD, font=(FONT, 9))

    def _on_press(self, e):
        x, y = self._to_img(e.x, e.y)
        x = max(0, min(self.iw, x))
        y = max(0, min(self.ih, y))
        rx, ry, rw, rh = self.rect
        if rx + rw - 14 <= x <= rx + rw + 2 and ry + rh - 14 <= y <= ry + rh + 2:
            self.mode = "resize"
            self.drag = (x, y)
        elif rx <= x <= rx + rw and ry <= y <= ry + rh:
            self.mode = "move"
            self.drag = (x - rx, y - ry)
        else:
            self.mode = "new"
            self.drag = (x, y)

    def _on_drag(self, e):
        x, y = self._to_img(e.x, e.y)
        x = max(0, min(self.iw, x))
        y = max(0, min(self.ih, y))
        if self.mode == "move":
            dx, dy = self.drag
            nx = max(0, min(self.iw - self.rect[2], x - dx))
            ny = max(0, min(self.ih - self.rect[3], y - dy))
            self.rect[0], self.rect[1] = int(nx), int(ny)
        elif self.mode == "resize":
            rx, ry = self.rect[0], self.rect[1]
            w = max(40, min(self.iw - rx, x - rx))
            h = w / self.RATIO
            if ry + h > self.ih:
                h = self.ih - ry
                w = h * self.RATIO
            self.rect[2], self.rect[3] = int(w), int(h)
        elif self.mode == "new":
            sx, sy = self.drag
            w = max(40, min(self.iw - sx, x - sx))
            h = w / self.RATIO
            if sy + h > self.ih:
                h = self.ih - sy
                w = h * self.RATIO
            self.rect = [int(sx), int(sy), int(w), int(h)]
        self._draw()

    def _on_release(self, _=None):
        self.mode = None


class BlogTool:
    def __init__(self, root):
        self.root = root
        self.root.title("MCRYII 博客写作助手")
        self.root.geometry("1320x880")
        self.root.minsize(1100, 700)
        self.root.configure(bg=COL_BG)

        self.current_file_path = None
        self.current_title = ""
        self.cover_path = None
        self.auto_cover = None
        self.dirty = False
        self._img_refs = []
        self._tree_imgs = {}
        self._preview_imgs = []
        self.moment_images = []
        self.moment_entries = []

        self._setup_style()
        self._build_ui()
        self._bind_shortcuts()
        self.refresh_article_list()
        self.refresh_moment_list()
        self.refresh_download_list()
        self._update_server_status()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------- 样式 ----------------
    def _setup_style(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=COL_PANEL)
        style.configure("TLabel", background=COL_PANEL, foreground=COL_TEXT, font=(FONT, 10))
        style.configure("Treeview",
                        background=COL_INPUT, fieldbackground=COL_INPUT, foreground=COL_TEXT,
                        borderwidth=0, rowheight=52, font=(FONT, 10))
        style.configure("Treeview.Heading",
                        background=COL_PANEL2, foreground=COL_GOLD, borderwidth=0,
                        font=(FONT, 9, "bold"), padding=(8, 6))
        style.map("Treeview",
                  background=[("selected", COL_SELECT)],
                  foreground=[("selected", COL_GOLD)])
        style.map("Treeview.Heading", background=[("active", COL_PANEL2)])
        style.configure("TNotebook", background=COL_PANEL, borderwidth=0)
        style.configure("TNotebook.Tab",
                        background=COL_PANEL2, foreground=COL_MUTED, padding=(18, 8),
                        font=(FONT, 10))
        style.map("TNotebook.Tab",
                  background=[("selected", COL_PANEL)],
                  foreground=[("selected", COL_GOLD)])
        style.configure("TScrollbar", background=COL_PANEL2, troughcolor=COL_BG,
                        arrowcolor=COL_MUTED, bordercolor=COL_PANEL2)

    def _btn(self, parent, text, command, kind="ghost", width=None):
        cfg = {
            "ghost": dict(bg=COL_PANEL2, fg=COL_TEXT, activebackground=COL_SELECT,
                          activeforeground=COL_GOLD, highlightbackground=COL_BORDER),
            "gold": dict(bg=COL_GOLD, fg="#1b1405", activebackground="#e0bc4e",
                         activeforeground="#1b1405", highlightbackground=COL_GOLD),
            "danger": dict(bg="#3a2023", fg=COL_RED, activebackground="#4a262a",
                           activeforeground="#ff7a80", highlightbackground="#5a2c30"),
        }[kind]
        return tk.Button(parent, text=text, command=command, relief=tk.FLAT,
                         font=(FONT, 10), cursor="hand2", padx=14, pady=6,
                         highlightthickness=1, width=width, **cfg)

    # ---------------- 界面 ----------------
    def _build_ui(self):
        # 顶栏
        header = tk.Frame(self.root, bg=COL_PANEL, height=58)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="MCRYII 博客写作助手", bg=COL_PANEL, fg=COL_GOLD,
                 font=(FONT, 14, "bold")).pack(side=tk.LEFT, padx=18)
        self.server_label = tk.Label(header, text="服务器检测中", bg=COL_PANEL,
                                     fg=COL_MUTED, font=(FONT, 9))
        self.server_label.pack(side=tk.LEFT, padx=10)
        self.git_label = tk.Label(header, text="Git: -", bg=COL_PANEL, fg=COL_MUTED,
                                  font=(FONT, 9))
        self.git_label.pack(side=tk.LEFT, padx=10)
        for text, cmd, kind in (
            ("预览网站", self.preview_site, "gold"),
            ("推送到 GitHub", self.push_to_github, "ghost"),
            ("Git 状态", self._update_git_status, "ghost"),
        ):
            self._btn(header, text, cmd, kind).pack(side=tk.RIGHT, padx=6, pady=10)

        # 主体
        main = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg=COL_BG,
                              sashwidth=5, sashrelief=tk.FLAT)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 左侧：文章列表
        left = tk.Frame(main, bg=COL_PANEL)
        main.add(left, width=330, minsize=260)
        bar = tk.Frame(left, bg=COL_PANEL)
        bar.pack(fill=tk.X, padx=10, pady=(10, 6))
        tk.Label(bar, text="已有文章", bg=COL_PANEL, fg=COL_TEXT,
                 font=(FONT, 11, "bold")).pack(side=tk.LEFT)
        self._btn(bar, "＋ 新建", self.new_article, "gold").pack(side=tk.RIGHT)
        self.tree = ttk.Treeview(left, columns=("date",), show="tree headings",
                                 selectmode="browse")
        self.tree.heading("#0", text="文章", anchor="w")
        self.tree.heading("date", text="日期", anchor="w")
        self.tree.column("#0", width=210, anchor="w")
        self.tree.column("date", width=82, anchor="w")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10)
        self.tree.bind("<Double-Button-1>", self.load_selected)
        self.tree.bind("<Return>", self.load_selected)
        bottom = tk.Frame(left, bg=COL_PANEL)
        bottom.pack(fill=tk.X, padx=10, pady=8)
        self._btn(bottom, "删除", self.delete_article, "danger").pack(side=tk.LEFT)
        self._btn(bottom, "刷新", self.refresh_article_list).pack(side=tk.RIGHT)

        # 右侧：编辑 / 预览
        right = tk.Frame(main, bg=COL_PANEL)
        main.add(right, width=940)
        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        edit_tab = tk.Frame(self.notebook, bg=COL_PANEL)
        self.notebook.add(edit_tab, text="编辑")
        preview_tab = tk.Frame(self.notebook, bg=COL_PANEL)
        self.notebook.add(preview_tab, text="预览")
        moments_tab = tk.Frame(self.notebook, bg=COL_PANEL)
        self.notebook.add(moments_tab, text="动态")
        downloads_tab = tk.Frame(self.notebook, bg=COL_PANEL)
        self.notebook.add(downloads_tab, text="下载")
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        self._build_edit_tab(edit_tab)
        self._build_preview_tab(preview_tab)
        self._build_moments_tab(moments_tab)
        self._build_downloads_tab(downloads_tab)

        # 状态栏
        status = tk.Frame(self.root, bg=COL_PANEL2, height=30)
        status.pack(fill=tk.X)
        status.pack_propagate(False)
        self.status_var = tk.StringVar(value="就绪")
        tk.Label(status, textvariable=self.status_var, bg=COL_PANEL2, fg=COL_MUTED,
                 font=(FONT, 9)).pack(side=tk.LEFT, padx=14)
        self.count_var = tk.StringVar(value="字数：0")
        tk.Label(status, textvariable=self.count_var, bg=COL_PANEL2, fg=COL_GOLD,
                 font=(FONT, 9)).pack(side=tk.RIGHT, padx=14)

    def _build_edit_tab(self, parent):
        meta = tk.LabelFrame(parent, text=" 文章信息 ", bg=COL_PANEL, fg=COL_GOLD,
                             font=(FONT, 10, "bold"), bd=0, highlightthickness=1,
                             highlightbackground=COL_BORDER)
        meta.pack(fill=tk.X, padx=12, pady=(12, 6))
        meta.columnconfigure(1, weight=1)

        tk.Label(meta, text="标题", bg=COL_PANEL, fg=COL_MUTED,
                 font=(FONT, 9)).grid(row=0, column=0, sticky="w", padx=(12, 8), pady=6)
        self.title_entry = self._entry(meta)
        self.title_entry.grid(row=0, column=1, columnspan=3, sticky="ew", padx=(0, 12), pady=6)

        tk.Label(meta, text="日期", bg=COL_PANEL, fg=COL_MUTED,
                 font=(FONT, 9)).grid(row=1, column=0, sticky="w", padx=(12, 8), pady=6)
        self.date_entry = self._entry(meta)
        self.date_entry.grid(row=1, column=1, sticky="ew", padx=(0, 6), pady=6)
        self._btn(meta, "现在", lambda: self.date_entry.delete(0, tk.END) or
                  self.date_entry.insert(0, self._now_str()), "ghost").grid(
            row=1, column=2, padx=2, pady=6)

        self.cats = TagInputWidget(meta, title="分类")
        self.cats.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=4)
        self.tags = TagInputWidget(meta, title="标签")
        self.tags.grid(row=2, column=2, columnspan=2, sticky="ew", padx=12, pady=4)

        self.draft_var = tk.BooleanVar(value=False)
        tk.Checkbutton(meta, text="草稿模式（不发布）", variable=self.draft_var,
                       bg=COL_PANEL, fg=COL_MUTED, selectcolor=COL_INPUT,
                       activebackground=COL_PANEL, activeforeground=COL_GOLD,
                       font=(FONT, 9), highlightthickness=0).grid(
            row=3, column=0, columnspan=2, sticky="w", padx=12, pady=6)

        # 封面行
        cover_row = tk.Frame(meta, bg=COL_PANEL)
        cover_row.grid(row=3, column=2, columnspan=2, sticky="ew", padx=12, pady=6)
        tk.Label(cover_row, text="封面", bg=COL_PANEL, fg=COL_MUTED,
                 font=(FONT, 9)).pack(side=tk.LEFT)
        self.cover_canvas = tk.Label(cover_row, text="无封面", bg=COL_INPUT, fg=COL_MUTED,
                                     width=16, height=3, relief=tk.FLAT)
        self.cover_canvas.pack(side=tk.LEFT, padx=8)
        self._btn(cover_row, "编辑封面", self.edit_cover, "ghost").pack(side=tk.LEFT, padx=3)
        self._btn(cover_row, "选择封面", self.choose_cover, "ghost").pack(side=tk.LEFT, padx=3)
        self._btn(cover_row, "清除", self.clear_cover, "danger").pack(side=tk.LEFT, padx=3)

        # 工具栏
        tools = tk.Frame(parent, bg=COL_PANEL)
        tools.pack(fill=tk.X, padx=12, pady=6)
        self._btn(tools, "保存 (Ctrl+S)", self.save_article, "gold").pack(side=tk.LEFT)
        self._btn(tools, "插入图片", self.insert_image).pack(side=tk.LEFT, padx=4)
        self._btn(tools, "清空编辑区", self._clear_editor).pack(side=tk.LEFT, padx=4)
        tk.Label(tools, text="Ctrl+N 新建 · F5 刷新 · Ctrl+K 预览", bg=COL_PANEL,
                 fg="#5c5c66", font=(FONT, 9)).pack(side=tk.RIGHT)

        # 正文
        tk.Label(parent, text="正文（Markdown）", bg=COL_PANEL, fg=COL_MUTED,
                 font=(FONT, 9)).pack(anchor="w", padx=14)
        self.text_area = scrolledtext.ScrolledText(
            parent, wrap=tk.WORD, undo=True, bg=COL_INPUT, fg=COL_TEXT,
            insertbackground=COL_GOLD, font=(FONT, 11), relief=tk.FLAT,
            highlightthickness=1, highlightbackground=COL_BORDER, highlightcolor=COL_GOLD,
            selectbackground=COL_SELECT, selectforeground=COL_GOLD)
        self.text_area.pack(fill=tk.BOTH, expand=True, padx=12, pady=(4, 12))
        self.text_area.bind("<<Modified>>", self._on_modified)

    def _build_preview_tab(self, parent):
        tk.Label(parent, text="Markdown 预览（自动渲染，图片缩略显示）", bg=COL_PANEL,
                 fg=COL_MUTED, font=(FONT, 9)).pack(anchor="w", padx=14, pady=(12, 4))
        self.preview_text = tk.Text(
            parent, wrap=tk.WORD, bg=COL_INPUT, fg=COL_TEXT, relief=tk.FLAT,
            font=(FONT, 11), padx=16, pady=12, cursor="arrow",
            highlightthickness=1, highlightbackground=COL_BORDER)
        self.preview_text.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        self.preview_text.config(state=tk.DISABLED)
        self.preview_text.tag_configure("h1", font=(FONT, 20, "bold"), foreground=COL_GOLD,
                                        spacing3=8)
        self.preview_text.tag_configure("h2", font=(FONT, 16, "bold"), foreground=COL_GOLD,
                                        spacing3=6)
        self.preview_text.tag_configure("h3", font=(FONT, 13, "bold"), foreground="#f0d98c")
        self.preview_text.tag_configure("bold", font=(FONT, 11, "bold"))
        self.preview_text.tag_configure("italic", font=(FONT, 11, "italic"))
        self.preview_text.tag_configure("code", font=(FONT_MONO, 10), background="#2a2a30",
                                        foreground="#f2b8a0")
        self.preview_text.tag_configure("quote", foreground=COL_MUTED, font=(FONT, 10, "italic"),
                                        lmargin1=16, lmargin2=16)
        self.preview_text.tag_configure("link", foreground="#7fb3ff", underline=1)
        self.preview_text.tag_configure("list", lmargin1=8, lmargin2=24)
        self.preview_text.tag_configure("muted", foreground="#6a6a72")

    def _entry(self, parent):
        return tk.Entry(parent, bg=COL_INPUT, fg=COL_TEXT, insertbackground=COL_GOLD,
                        relief=tk.FLAT, font=(FONT, 10), highlightthickness=1,
                        highlightbackground=COL_BORDER, highlightcolor=COL_GOLD)

    # ---------------- 快捷键 / 事件 ----------------
    def _bind_shortcuts(self):
        self.root.bind("<Control-s>", lambda e: self.save_article())
        self.root.bind("<Control-n>", lambda e: self.new_article())
        self.root.bind("<Control-k>", lambda e: self._show_preview())
        self.root.bind("<F5>", lambda e: self.refresh_article_list())

    def _on_modified(self, _=None):
        if self.text_area.edit_modified():
            self.dirty = True
            self.text_area.edit_modified(False)
            self._update_count()

    def _on_tab_changed(self, _=None):
        if self.notebook.index(self.notebook.select()) == 1:
            self._show_preview()

    def _on_close(self):
        if self.dirty and not messagebox.askyesno("未保存", "有未保存的修改，确定退出？"):
            return
        self.root.destroy()

    def _now_str(self):
        return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")

    # ---------------- 文章列表 ----------------
    def refresh_article_list(self):
        self.tree.delete(*self.tree.get_children())
        self._tree_imgs.clear()
        items = []
        for rel, full in scan_posts():
            try:
                with open(full, encoding="utf-8") as f:
                    content = f.read()
            except OSError:
                continue
            data = parse_front(content)
            title = data["title"] or os.path.splitext(os.path.basename(full))[0]
            date = (data["date"] or "")[:10]
            mtime = os.path.getmtime(full)
            items.append((mtime, rel, full, title, date, data["cover"]))
        items.sort(key=lambda x: x[0], reverse=True)
        for _, rel, full, title, date, cover in items:
            thumb = self._make_thumb(cover, full)
            opts = {"text": f"  {title}", "values": (date,)}
            if thumb:
                opts["image"] = thumb
            iid = self.tree.insert("", tk.END, **opts)
            if thumb:
                self._tree_imgs[iid] = thumb
            self.tree.item(iid, tags=(rel,))
        self.status_var.set(f"共 {len(items)} 篇文章")

    def _make_thumb(self, cover, md_path):
        """封面缩略图：优先 front matter cover，其次正文第一张图"""
        path = None
        if cover:
            path = os.path.join(BLOG_ROOT, "static", cover.lstrip("/"))
        if not path or not os.path.exists(path):
            try:
                with open(md_path, encoding="utf-8") as f:
                    body = f.read()
                m = re.search(r"!\[[^\]]*\]\((/images/[^)]+)\)", body)
                if m:
                    path = os.path.join(BLOG_ROOT, "static", m.group(1).lstrip("/"))
            except OSError:
                path = None
        if path and os.path.exists(path):
            try:
                img = Image.open(path)
                img.thumbnail((54, 40))
                return ImageTk.PhotoImage(img)
            except Exception:
                pass
        return None

    def load_selected(self, _=None):
        sel = self.tree.selection()
        if not sel:
            return
        rel = self.tree.item(sel[0], "tags")[0]
        full = os.path.join(POSTS_BASE, rel)
        if self.dirty and not messagebox.askyesno("未保存", "切换文章会丢失未保存修改，继续？"):
            return
        try:
            with open(full, encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            messagebox.showerror("错误", f"读取失败：{e}")
            return
        data = parse_front(content)
        m = re.match(r"^---\s*\n.*?\n---\s*\n", content, re.DOTALL)
        body = content[m.end():].strip() if m else content.strip()
        self.title_entry.delete(0, tk.END)
        self.title_entry.insert(0, data["title"] or "")
        self.date_entry.delete(0, tk.END)
        self.date_entry.insert(0, data["date"] or self._now_str())
        self.cats.set_tags(data["categories"])
        self.tags.set_tags(data["tags"])
        self.draft_var.set(data["draft"])
        self.cover_path = data["cover"]
        self.auto_cover = self._find_auto_cover(full)
        self._update_cover_preview()
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert("1.0", body)
        self.current_file_path = full
        self.current_title = data["title"] or ""
        self.dirty = False
        if not self.cover_path and self.auto_cover:
            self.status_var.set(f"已打开：{rel}（封面来自正文图片，可点\"编辑封面\"裁剪）")
        else:
            self.status_var.set(f"已打开：{rel}")
        self._update_count()

    # ---------------- 新建 / 保存 / 删除 ----------------
    def new_article(self):
        if self.dirty and not messagebox.askyesno("未保存", "有未保存的修改，新建会丢失，继续？"):
            return
        self.title_entry.delete(0, tk.END)
        self.date_entry.delete(0, tk.END)
        self.date_entry.insert(0, self._now_str())
        self.cats.set_tags([])
        self.tags.set_tags([])
        self.draft_var.set(False)
        self.cover_path = None
        self.auto_cover = None
        self._update_cover_preview()
        self.text_area.delete("1.0", tk.END)
        self.current_file_path = None
        self.current_title = ""
        self.dirty = False
        self.status_var.set("新建文章，填写后保存")
        self.title_entry.focus_set()
        self.notebook.select(0)
        self._update_count()

    def save_article(self):
        title = self.title_entry.get().strip()
        if not title:
            messagebox.showwarning("提示", "标题不能为空")
            return
        date = self.date_entry.get().strip() or self._now_str()
        if not re.match(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}\+08:00)?$", date):
            messagebox.showwarning("提示", "日期格式应为 2026-06-06 或 2026-06-06T21:24:37+08:00")
            return
        if re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            date += "T00:00:00+08:00"
        body = self.text_area.get("1.0", tk.END).rstrip()
        try:
            filepath = save_article_file(
                self.current_file_path, title, date,
                self.cats.get_tags(), self.tags.get_tags(),
                self.draft_var.get(), self.cover_path, body)
        except OSError as e:
            messagebox.showerror("错误", f"保存失败：{e}")
            return
        self.current_file_path = filepath
        self.current_title = title
        self.dirty = False
        rel = os.path.relpath(filepath, POSTS_BASE)
        self.status_var.set(f"已保存：{rel}")
        self.refresh_article_list()
        messagebox.showinfo("成功", f"文章已保存\n{filepath}")

    def delete_article(self):
        if not self.current_file_path or not os.path.exists(self.current_file_path):
            messagebox.showwarning("提示", "没有打开的文章可删除")
            return
        rel = os.path.relpath(self.current_file_path, POSTS_BASE)
        if messagebox.askyesno("确认删除", f"永久删除\n{rel}\n？此操作不可恢复！"):
            try:
                os.remove(self.current_file_path)
                self.new_article()
                self.refresh_article_list()
                self.status_var.set(f"已删除：{rel}")
            except OSError as e:
                messagebox.showerror("错误", f"删除失败：{e}")

    def _clear_editor(self):
        if messagebox.askyesno("清空", "清空编辑区（不保存）？"):
            self.text_area.delete("1.0", tk.END)
            self.dirty = True
            self._update_count()

    # ---------------- 动态 ----------------
    def _build_moments_tab(self, parent):
        pad = {"padx": 14, "pady": 6}
        tk.Label(parent, text="写下此刻（Ctrl+Enter 发布，会显示在 /dynamic/ 动态页）", anchor="w",
                 bg=COL_PANEL, fg=COL_TEXT, font=(FONT, 11, "bold")).pack(fill=tk.X, **pad)
        self.moment_text = tk.Text(parent, height=5, bg=COL_INPUT, fg=COL_TEXT,
                                   insertbackground=COL_GOLD, relief=tk.FLAT, wrap=tk.WORD,
                                   highlightthickness=1, highlightbackground=COL_BORDER,
                                   highlightcolor=COL_GOLD, font=(FONT, 11))
        self.moment_text.pack(fill=tk.X, **pad)
        self.moment_text.bind("<Control-Return>", lambda e: self.publish_moment())

        imgs_row = tk.Frame(parent, bg=COL_PANEL)
        imgs_row.pack(fill=tk.X, **pad)
        self._btn(imgs_row, "添加图片", self._pick_moment_images, width=10).pack(side=tk.LEFT)
        self._btn(imgs_row, "移除选中", self._remove_moment_images, "danger",
                  width=10).pack(side=tk.LEFT, padx=8)
        self.moment_imgs_list = tk.Listbox(parent, height=3, bg=COL_INPUT, fg=COL_TEXT,
                                           relief=tk.FLAT, highlightthickness=1,
                                           highlightbackground=COL_BORDER,
                                           selectbackground=COL_SELECT,
                                           selectforeground=COL_GOLD, font=(FONT, 9))
        self.moment_imgs_list.pack(fill=tk.X, **pad)

        link_row = tk.Frame(parent, bg=COL_PANEL)
        link_row.pack(fill=tk.X, **pad)
        tk.Label(link_row, text="链接（可选）", bg=COL_PANEL, fg=COL_MUTED,
                 font=(FONT, 9)).pack(side=tk.LEFT)
        self.moment_link_entry = tk.Entry(link_row, bg=COL_INPUT, fg=COL_TEXT,
                                          insertbackground=COL_GOLD, relief=tk.FLAT,
                                          highlightthickness=1, highlightbackground=COL_BORDER,
                                          highlightcolor=COL_GOLD, font=(FONT, 10))
        self.moment_link_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4, padx=(8, 0))

        self._btn(parent, "发布动态", self.publish_moment, "gold").pack(anchor="w", **pad)

        tk.Label(parent, text="已有动态", anchor="w", bg=COL_PANEL, fg=COL_TEXT,
                 font=(FONT, 11, "bold")).pack(fill=tk.X, **pad)
        self.moment_tree = ttk.Treeview(parent, columns=("text",), show="tree headings",
                                        selectmode="browse")
        self.moment_tree.heading("#0", text="时间", anchor="w")
        self.moment_tree.heading("text", text="内容", anchor="w")
        self.moment_tree.column("#0", width=150, anchor="w")
        self.moment_tree.column("text", width=520, anchor="w")
        self.moment_tree.pack(fill=tk.BOTH, expand=True, **pad)
        tree_bottom = tk.Frame(parent, bg=COL_PANEL)
        tree_bottom.pack(fill=tk.X, **pad)
        self._btn(tree_bottom, "删除选中", self.delete_moment, "danger").pack(side=tk.LEFT)
        self._btn(tree_bottom, "刷新", self.refresh_moment_list).pack(side=tk.RIGHT)

    def _pick_moment_images(self):
        paths = filedialog.askopenfilenames(
            title="选择动态图片（可多选）",
            filetypes=[("图片", "*.png *.jpg *.jpeg *.gif *.webp *.avif")])
        for p in paths:
            if p not in self.moment_images:
                self.moment_images.append(p)
        self._refresh_moment_imgs()

    def _remove_moment_images(self):
        for i in reversed(self.moment_imgs_list.curselection()):
            self.moment_images.pop(i)
        self._refresh_moment_imgs()

    def _refresh_moment_imgs(self):
        self.moment_imgs_list.delete(0, tk.END)
        for p in self.moment_images:
            self.moment_imgs_list.insert(tk.END, os.path.basename(p))

    def _copy_to_moments(self, src):
        os.makedirs(MOMENTS_IMAGES_DIR, exist_ok=True)
        name = "{}-{}".format(datetime.datetime.now().strftime("%Y%m%d%H%M%S"),
                              os.path.basename(src))
        try:
            shutil.copy(src, os.path.join(MOMENTS_IMAGES_DIR, name))
        except OSError as e:
            messagebox.showerror("错误", f"复制图片失败：{e}")
            return None
        return "/images/moments/" + name

    def publish_moment(self):
        text = self.moment_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("提示", "动态内容不能为空")
            return
        entry = {
            "date": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "text": text,
        }
        images = [url for url in (self._copy_to_moments(p) for p in self.moment_images) if url]
        if images:
            entry["images"] = images
        link = self.moment_link_entry.get().strip()
        if link:
            entry["link"] = link
        entries = load_moments()
        entries.insert(0, entry)
        save_moments(entries)
        self.moment_text.delete("1.0", tk.END)
        self.moment_images = []
        self.moment_link_entry.delete(0, tk.END)
        self._refresh_moment_imgs()
        self.refresh_moment_list()
        self.status_var.set("动态已发布，重新构建后即可在 /dynamic/ 看到")
        messagebox.showinfo("成功", "动态已发布\n重新构建网站后可在 /dynamic/ 查看")

    def refresh_moment_list(self):
        self.moment_tree.delete(*self.moment_tree.get_children())
        self.moment_entries = sorted(load_moments(),
                                     key=lambda e: e.get("date", ""), reverse=True)
        for i, e in enumerate(self.moment_entries):
            date = e.get("date", "")[:16].replace("T", " ")
            text = e.get("text", "").replace("\n", " ")
            if len(text) > 40:
                text = text[:40] + "…"
            self.moment_tree.insert("", tk.END, iid=str(i), text=date, values=(text,))

    def delete_moment(self):
        sel = self.moment_tree.selection()
        if not sel:
            messagebox.showwarning("提示", "请先选中要删除的动态")
            return
        idx = int(sel[0])
        entry = self.moment_entries[idx]
        preview = entry.get("text", "")[:30].replace("\n", " ")
        if not messagebox.askyesno("确认删除", f"删除这条动态？\n{preview}\n（关联的图片会一并删除）"):
            return
        for url in entry.get("images", []):
            rel = url.replace("/images/moments/", "", 1) if url.startswith("/images/moments/") \
                else os.path.basename(url)
            if ".." in rel or not rel:
                continue
            img_path = os.path.join(MOMENTS_IMAGES_DIR, rel)
            if os.path.isfile(img_path):
                try:
                    os.remove(img_path)
                except OSError:
                    pass
        self.moment_entries.pop(idx)
        save_moments(self.moment_entries)
        self.refresh_moment_list()
        self.status_var.set("已删除动态")

    # ---------------- 下载文件管理 ----------------
    def _build_downloads_tab(self, parent):
        bar = tk.Frame(parent, bg=COL_PANEL)
        bar.pack(fill=tk.X, padx=12, pady=(12, 6))
        self._btn(bar, "添加文件", self._add_download_files, "gold").pack(side=tk.LEFT)
        self._btn(bar, "新建分类", self._new_download_category).pack(side=tk.LEFT, padx=8)
        self._btn(bar, "重命名", self._rename_download_category).pack(side=tk.LEFT, padx=8)
        self._btn(bar, "外链", self._set_download_external).pack(side=tk.LEFT, padx=8)
        self._btn(bar, "删除选中", self._delete_download_file, "danger").pack(side=tk.LEFT)
        self._btn(bar, "刷新", self.refresh_download_list).pack(side=tk.RIGHT)
        tk.Label(parent, text="选择分类后点「添加文件」，文件会复制到 static/files/<分类>/，重新构建后出现在 /downloads/",
                 anchor="w", bg=COL_PANEL, fg=COL_MUTED, font=(FONT, 9)).pack(fill=tk.X, padx=12)
        self.download_tree = ttk.Treeview(parent, columns=("size",), show="tree headings",
                                          selectmode="browse")
        self.download_tree.heading("#0", text="分类 / 文件", anchor="w")
        self.download_tree.heading("size", text="大小", anchor="w")
        self.download_tree.column("#0", width=430, anchor="w")
        self.download_tree.column("size", width=120, anchor="w")
        self.download_tree.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

    def refresh_download_list(self):
        self.download_tree.delete(*self.download_tree.get_children())
        if not os.path.isdir(FILES_DIR):
            self.status_var.set("static/files/ 目录不存在")
            return
        total = 0
        for name in sorted(os.listdir(FILES_DIR)):
            cat_dir = os.path.join(FILES_DIR, name)
            if not os.path.isdir(cat_dir):
                continue
            cat_iid = f"cat:{name}"
            self.download_tree.insert("", tk.END, iid=cat_iid, text=f"  {name}", open=True)
            for fname in sorted(os.listdir(cat_dir)):
                full = os.path.join(cat_dir, fname)
                if os.path.isfile(full):
                    self.download_tree.insert(cat_iid, tk.END, iid=f"file:{name}:{fname}",
                                              text=f"  {fname}",
                                              values=(fmt_size(os.path.getsize(full)),))
                    total += 1
        self.status_var.set(f"共 {len(self.download_tree.get_children())} 个分类、{total} 个文件")

    def _selected_download_cat(self):
        sel = self.download_tree.selection()
        if not sel:
            return None
        iid = sel[0]
        if iid.startswith("cat:"):
            return iid[4:]
        if iid.startswith("file:"):
            return iid.split(":", 2)[1]
        return None

    def _add_download_files(self):
        cat = self._selected_download_cat()
        if not cat:
            messagebox.showwarning("提示", "请先在列表中选择一个分类（或先点「新建分类」）")
            return
        paths = filedialog.askopenfilenames(title="选择要添加的文件（可多选）")
        if not paths:
            return
        os.makedirs(os.path.join(FILES_DIR, cat), exist_ok=True)
        ok = 0
        for p in paths:
            try:
                shutil.copy(p, os.path.join(FILES_DIR, cat, os.path.basename(p)))
                ok += 1
            except OSError as e:
                messagebox.showerror("错误", f"复制失败：{os.path.basename(p)}\n{e}")
        self.refresh_download_list()
        if ok:
            self.status_var.set(f"已添加 {ok} 个文件，重新构建后可在 /downloads/ 看到")
            messagebox.showinfo("成功", f"已添加 {ok} 个文件\n重新构建网站后即可在 /downloads/ 看到")

    def _new_download_category(self):
        name = simpledialog.askstring("新建分类", "输入分类名（字母/数字/-/_，将作为文件夹名）：",
                                      parent=self.root)
        if not name:
            return
        name = name.strip()
        if not re.match(r"^[A-Za-z0-9_-]+$", name):
            messagebox.showwarning("提示", "分类名只能包含字母、数字、- 和 _")
            return
        os.makedirs(os.path.join(FILES_DIR, name), exist_ok=True)
        self.refresh_download_list()
        self.status_var.set(f"已创建分类 {name}")

    def _rename_download_category(self):
        cat = self._selected_download_cat()
        if not cat:
            messagebox.showwarning("提示", "请先选择一个分类")
            return
        name = simpledialog.askstring("重命名分类", "新的分类名（字母/数字/-/_）：",
                                      parent=self.root, initialvalue=cat)
        if not name:
            return
        name = name.strip()
        if not re.match(r"^[A-Za-z0-9_-]+$", name):
            messagebox.showwarning("提示", "分类名只能包含字母、数字、- 和 _")
            return
        if name == cat:
            return
        old = os.path.join(FILES_DIR, cat)
        new = os.path.join(FILES_DIR, name)
        if os.path.exists(new):
            messagebox.showwarning("提示", f"分类 {name} 已存在")
            return
        try:
            os.rename(old, new)
        except OSError as e:
            messagebox.showerror("错误", str(e))
            return
        self.refresh_download_list()
        self.status_var.set(f"已重命名 {cat} -> {name}")

    def _set_download_external(self):
        """给选中文件配置外链（网盘/对象存储直链），空值清除外链"""
        sel = self.download_tree.selection()
        if not sel:
            return
        iid = sel[0]
        if not iid.startswith("file:"):
            messagebox.showwarning("提示", "请先选择一个【文件】")
            return
        _, cat, fname = iid.split(":", 2)
        key = f"{cat}/{fname}"
        cfg_file = os.path.join(BLOG_ROOT, "data", "downloads.json")
        cfg = {}
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except (OSError, ValueError):
            cfg = {}
        if not isinstance(cfg, dict) or not isinstance(cfg.get("files"), dict):
            cfg = {"files": {}}
        cur = cfg["files"].get(key, "")
        url = simpledialog.askstring("设置外链", f"{key}\n输入网盘/对象存储直链（留空清除）：",
                                     parent=self.root, initialvalue=cur)
        if url is None:
            return
        url = url.strip()
        if url:
            cfg["files"][key] = url
        else:
            cfg["files"].pop(key, None)
        os.makedirs(os.path.dirname(cfg_file), exist_ok=True)
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        self.status_var.set(f"外链已更新：{key}")

    def _delete_download_file(self):
        sel = self.download_tree.selection()
        if not sel:
            return
        iid = sel[0]
        if not iid.startswith("file:"):
            messagebox.showwarning("提示", "请选择要删除的【文件】（空分类文件夹可手动清理）")
            return
        _, cat, fname = iid.split(":", 2)
        if not messagebox.askyesno("确认删除", f"删除文件？\n{cat}/{fname}\n（删除后不可恢复）"):
            return
        try:
            os.remove(os.path.join(FILES_DIR, cat, fname))
        except OSError as e:
            messagebox.showerror("错误", str(e))
            return
        self.refresh_download_list()
        self.status_var.set(f"已删除 {cat}/{fname}")

    # ---------------- 图片 / 封面 ----------------
    def insert_image(self):
        os.makedirs(IMAGES_DIR, exist_ok=True)
        path = filedialog.askopenfilename(
            title="选择图片",
            filetypes=[("图片", "*.png *.jpg *.jpeg *.gif *.webp *.avif")])
        if not path:
            return
        dest = self._copy_to_images(path)
        if not dest:
            return
        alt = os.path.splitext(os.path.basename(dest))[0]
        self.text_area.insert(tk.INSERT, f"![{alt}]({dest})\n\n")
        self.text_area.edit_modified(True)
        self._on_modified()
        self.status_var.set(f"已插入图片：{dest}")

    def choose_cover(self):
        os.makedirs(IMAGES_DIR, exist_ok=True)
        path = filedialog.askopenfilename(
            title="选择封面图片",
            filetypes=[("图片", "*.png *.jpg *.jpeg *.webp *.avif")])
        if not path:
            return
        dlg = CoverCropDialog(self.root, path)
        self.root.wait_window(dlg)
        cropped = dlg.result
        if cropped is None:
            self.status_var.set("已取消选择封面")
            return
        saved = self._save_cropped(cropped, path)
        if not saved:
            return
        self.cover_path = saved
        self._update_cover_preview()
        self.dirty = True
        self.status_var.set(f"封面已裁剪并设置：{self.cover_path}")

    def edit_cover(self):
        """编辑当前封面：优先已保存的 cover，其次正文自动封面"""
        full = self._current_cover_full()
        if not full or not os.path.exists(full):
            messagebox.showinfo("提示", "当前文章没有封面图，请先点\"选择封面\"")
            return
        dlg = CoverCropDialog(self.root, full)
        self.root.wait_window(dlg)
        cropped = dlg.result
        if cropped is None:
            self.status_var.set("已取消编辑封面")
            return
        saved = self._save_cropped(cropped, full)
        if not saved:
            return
        self.cover_path = saved
        self._update_cover_preview()
        self.dirty = True
        self.status_var.set(f"封面已裁剪保存：{self.cover_path}")

    def _save_cropped(self, cropped, src_path):
        base = re.sub(r'[\\/:*?"<>|]', "", os.path.splitext(os.path.basename(src_path))[0])
        base = base or "cover"
        ext = os.path.splitext(src_path)[1].lower() or ".jpg"
        out = os.path.join(IMAGES_DIR, f"{base}-cover{ext}")
        i = 1
        while os.path.exists(out):
            out = os.path.join(IMAGES_DIR, f"{base}-cover-{i}{ext}")
            i += 1
        try:
            if ext in (".jpg", ".jpeg"):
                cropped.save(out, quality=92)
            else:
                cropped.save(out)
        except OSError as e:
            messagebox.showerror("错误", f"保存封面失败：{e}")
            return None
        return f"/images/{os.path.basename(out)}"

    def _find_auto_cover(self, md_full):
        """默认封面：正文第一张图片；正文无图则用全局默认封面图"""
        try:
            with open(md_full, encoding="utf-8") as f:
                body = f.read()
        except OSError:
            return DEFAULT_COVER if os.path.exists(DEFAULT_COVER) else None
        m = re.search(r"!\[[^\]]*\]\((/images/[^)]+)\)", body)
        if m:
            p = os.path.join(BLOG_ROOT, "static", m.group(1).lstrip("/"))
            if os.path.exists(p):
                return p
        return DEFAULT_COVER if os.path.exists(DEFAULT_COVER) else None

    def _current_cover_full(self):
        if self.cover_path:
            p = os.path.join(BLOG_ROOT, "static", self.cover_path.lstrip("/"))
            if os.path.exists(p):
                return p
        if self.auto_cover:
            return self.auto_cover
        return None

    def clear_cover(self):
        self.cover_path = None
        self._update_cover_preview()
        self.dirty = True
        self.status_var.set("封面已清除")

    def _copy_to_images(self, src):
        name = os.path.basename(src)
        dest = os.path.join(IMAGES_DIR, name)
        if os.path.exists(dest):
            base, ext = os.path.splitext(name)
            i = 1
            while os.path.exists(os.path.join(IMAGES_DIR, f"{base}_{i}{ext}")):
                i += 1
            dest = os.path.join(IMAGES_DIR, f"{base}_{i}{ext}")
        try:
            shutil.copy2(src, dest)
            return f"/images/{os.path.basename(dest)}"
        except OSError as e:
            messagebox.showerror("错误", f"复制图片失败：{e}")
            return None

    def _update_cover_preview(self):
        for w in self.cover_canvas.winfo_children():
            w.destroy()
        full = self._current_cover_full()
        if not full:
            self.cover_canvas.config(text="无封面", image="")
            return
        if not os.path.exists(full):
            self.cover_canvas.config(text="图片丢失", image="")
            return
        try:
            img = Image.open(full)
            img.thumbnail((110, 66))
            photo = ImageTk.PhotoImage(img)
            self._img_refs.append(photo)
            self.cover_canvas.config(text="", image=photo)
        except Exception:
            self.cover_canvas.config(text="无法预览", image="")

    # ---------------- 预览 / 字数 ----------------
    def _update_count(self):
        body = self.text_area.get("1.0", tk.END).strip()
        self.count_var.set(f"字数：{len(body)}")

    def _show_preview(self):
        body = self.text_area.get("1.0", tk.END).rstrip()
        self.preview_text.config(state=tk.NORMAL)
        self.preview_text.delete("1.0", tk.END)
        self._preview_imgs.clear()
        self._render_markdown(body)
        self.preview_text.config(state=tk.DISABLED)

    def _render_markdown(self, md):
        lines = md.splitlines()
        code_block = False
        for line in lines:
            s = line.strip()
            if s.startswith("```"):
                code_block = not code_block
                self.preview_text.insert(tk.END, "\n")
                continue
            if code_block:
                self.preview_text.insert(tk.END, line + "\n", "code")
                continue
            if not s:
                self.preview_text.insert(tk.END, "\n")
                continue
            if s.startswith("### "):
                self._insert_inline(s[4:], "h3")
                self.preview_text.insert(tk.END, "\n")
            elif s.startswith("## "):
                self._insert_inline(s[3:], "h2")
                self.preview_text.insert(tk.END, "\n")
            elif s.startswith("# "):
                self._insert_inline(s[2:], "h1")
                self.preview_text.insert(tk.END, "\n")
            elif s.startswith("> "):
                self.preview_text.insert(tk.END, s[2:] + "\n", "quote")
            elif s.startswith(("- ", "* ")):
                self._insert_inline("• " + s[2:], "list")
                self.preview_text.insert(tk.END, "\n")
            elif re.match(r"^\d+\.\s", s):
                self._insert_inline(s, "list")
                self.preview_text.insert(tk.END, "\n")
            elif s.startswith("![") :
                self._insert_image(s)
            else:
                self._insert_inline(s, None)
                self.preview_text.insert(tk.END, "\n")

    def _insert_image(self, line):
        m = re.search(r"!\[([^\]]*)\]\(([^)]+)\)", line)
        if not m:
            self.preview_text.insert(tk.END, line + "\n", "muted")
            return
        alt, url = m.group(1), m.group(2)
        full = None
        if url.startswith("/images/"):
            full = os.path.join(BLOG_ROOT, "static", url.lstrip("/"))
        elif re.match(r"^[a-zA-Z]:", url):
            full = url
        if full and os.path.exists(full):
            try:
                img = Image.open(full)
                img.thumbnail((420, 300))
                photo = ImageTk.PhotoImage(img)
                self._preview_imgs.append(photo)
                self.preview_text.image_create(tk.END, image=photo)
                self.preview_text.insert(tk.END, "\n")
                return
            except Exception:
                pass
        self.preview_text.insert(tk.END, f"[图片] {alt or url}\n", "muted")

    def _insert_inline(self, text, tag):
        # 行内：**粗体** *斜体* `代码` [链接](url)
        pattern = r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\))"
        pos = 0
        for m in re.finditer(pattern, text):
            if m.start() > pos:
                self.preview_text.insert(tk.END, text[pos:m.start()], tag)
            seg = m.group(1)
            if seg.startswith("**"):
                self.preview_text.insert(tk.END, seg[2:-2], (tag, "bold") if tag else "bold")
            elif seg.startswith("*"):
                self.preview_text.insert(tk.END, seg[1:-1], (tag, "italic") if tag else "italic")
            elif seg.startswith("`"):
                self.preview_text.insert(tk.END, seg[1:-1], "code")
            else:
                lm = re.match(r"\[([^\]]+)\]\(([^)]+)\)", seg)
                self.preview_text.insert(tk.END, lm.group(1), (tag, "link") if tag else "link")
            pos = m.end()
        if pos < len(text):
            self.preview_text.insert(tk.END, text[pos:], tag)

    # ---------------- 网站 / Git ----------------
    def _server_running(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            return s.connect_ex(("127.0.0.1", 1314)) == 0
        finally:
            s.close()

    def _update_server_status(self):
        if self._server_running():
            self.server_label.config(text="本地服务器运行中", fg=COL_GREEN)
        else:
            self.server_label.config(text="本地服务器未启动", fg=COL_MUTED)
        self.root.after(5000, self._update_server_status)

    def preview_site(self):
        if not self._server_running():
            subprocess.Popen(
                ["hugo", "server", "-D", "--port", "1314", "--bind", "127.0.0.1"],
                cwd=BLOG_ROOT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.status_var.set("正在启动本地服务器...")
            self.root.after(2500, lambda: webbrowser.open("http://localhost:1314"))
        else:
            webbrowser.open("http://localhost:1314")
        self._update_server_status()

    def _update_git_status(self):
        if not is_git_repo():
            self.git_label.config(text="Git: 非仓库", fg=COL_RED)
            return
        try:
            r = subprocess.run(["git", "status", "--porcelain"], cwd=BLOG_ROOT,
                               capture_output=True, text=True, encoding="utf-8")
            n = len([x for x in r.stdout.splitlines() if x.strip()])
            self.git_label.config(text=f"Git: {n} 个未提交改动",
                                  fg=COL_GOLD if n else COL_GREEN)
        except Exception:
            self.git_label.config(text="Git: 无法读取", fg=COL_RED)

    def push_to_github(self):
        if not is_git_repo():
            messagebox.showerror("错误", "当前目录不是 Git 仓库")
            return
        r = subprocess.run(["git", "status", "--porcelain"], cwd=BLOG_ROOT,
                           capture_output=True, text=True, encoding="utf-8")
        if not r.stdout.strip():
            messagebox.showinfo("提示", "没有需要推送的改动")
            return
        title = self.title_entry.get().strip()
        msg = f"更新文章: {title}" if title else "更新文章"
        if not messagebox.askyesno("确认推送", f"提交信息：\n{msg}\n\n确定提交并推送到 GitHub？"):
            return
        steps = [
            ("git", "add", "-A"),
            ("git", "commit", "-m", msg),
            ("git", "push"),
        ]
        try:
            for cmd in steps:
                p = subprocess.run(cmd, cwd=BLOG_ROOT, capture_output=True,
                                   text=True, encoding="utf-8")
                if p.returncode != 0:
                    err = (p.stderr or p.stdout or "").strip()
                    if "nothing to commit" in err:
                        break
                    messagebox.showerror("推送失败", err[-500:])
                    return
            self.status_var.set("推送成功，等待 GitHub Actions 构建")
            messagebox.showinfo("成功", "已推送到 GitHub，稍后网站自动更新")
            self._update_git_status()
        except Exception as e:
            messagebox.showerror("错误", str(e))


# ==================== 网页版（python blog_tool.py --web） ====================
WEB_PORT = 8777

WEB_UI_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>博客写作助手 · 网页版</title>
<style>
:root { --bg:#16161a; --panel:#202024; --panel2:#26262c; --border:#34343c; --text:#e8e8e8; --muted:#8f8f98; --gold:#d4af37; --gold-dark:#a8872a; --red:#e5484d; --input:#1b1b1f; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--text); font-family:"Microsoft YaHei",system-ui,sans-serif; }
header { display:flex; align-items:center; gap:14px; padding:14px 20px; background:var(--panel); border-bottom:1px solid var(--border); position:sticky; top:0; z-index:10; }
h1 { font-size:1.05rem; color:var(--gold); margin:0; }
#status { font-size:.8rem; color:var(--muted); }
.tabs { display:flex; gap:8px; margin-left:auto; }
.tab-btn { background:var(--panel2); color:var(--muted); border:1px solid var(--border); border-radius:10px; padding:8px 18px; cursor:pointer; font-size:.9rem; font-family:inherit; }
.tab-btn.active { background:#3a3522; color:var(--gold); border-color:var(--gold-dark); }
.view { display:none; }
.view.active { display:flex; }
#art-list-pane { width:280px; border-right:1px solid var(--border); background:var(--panel); overflow-y:auto; height:calc(100vh - 58px); flex-shrink:0; }
#art-list { list-style:none; margin:0; padding:8px; }
#art-list li { padding:10px 12px; border-radius:10px; cursor:pointer; border:1px solid transparent; }
#art-list li:hover { background:var(--panel2); }
#art-list li.sel { background:#3a3522; border-color:var(--gold-dark); }
#art-list .a-title { font-size:.88rem; font-weight:700; }
#art-list .a-meta { font-size:.7rem; color:var(--muted); margin-top:3px; }
#art-list .draft-tag { color:var(--red); }
#art-form { flex:1; padding:16px 20px; overflow-y:auto; height:calc(100vh - 58px); }
.row { margin-bottom:12px; display:flex; gap:12px; align-items:center; }
.row label { width:64px; color:var(--muted); font-size:.85rem; flex-shrink:0; }
input[type=text], textarea { background:var(--input); color:var(--text); border:1px solid var(--border); border-radius:8px; padding:8px 10px; font-size:.9rem; font-family:inherit; }
input[type=text]:focus, textarea:focus { outline:none; border-color:var(--gold); }
textarea#f-body { width:100%; height:44vh; font-family:Consolas,monospace; font-size:.88rem; line-height:1.6; resize:vertical; }
.btn { background:var(--panel2); color:var(--text); border:1px solid var(--border); border-radius:10px; padding:8px 16px; cursor:pointer; font-size:.88rem; font-family:inherit; }
.btn:hover { background:var(--panel); }
.btn.gold { background:var(--gold); color:#1b1405; border-color:var(--gold); font-weight:700; }
.btn.gold:hover { background:#e0bc4e; }
.btn.danger { background:#3a2023; color:var(--red); border-color:#5a2c30; }
.btn.sm { padding:4px 10px; font-size:.78rem; }
.pv-img-err { display: block; color: var(--red); font-size: .78rem; padding: 6px 0; }
.chipbox {
    flex: 1;
    position: relative;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    background: var(--input);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 6px 8px;
}
.chipbox:focus-within { border-color: var(--gold); }
.chipbox input {
    flex: 1;
    min-width: 120px;
    background: transparent;
    border: none;
    color: var(--text);
    font-size: .85rem;
    outline: none;
    padding: 4px;
}
.chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: #3a3522;
    color: var(--gold);
    border: 1px solid var(--gold-dark);
    border-radius: 999px;
    padding: 3px 8px 3px 10px;
    font-size: .78rem;
}
.chip-x { cursor: pointer; color: var(--red); font-size: .82rem; line-height: 1; }
.chip-x:hover { color: #ff7a80; }
.chip-drop {
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    right: 0;
    background: var(--panel2);
    border: 1px solid var(--border);
    border-radius: 10px;
    max-height: 220px;
    overflow-y: auto;
    z-index: 20;
    box-shadow: 0 8px 20px rgba(0, 0, 0, .4);
}
.chip-drop div { padding: 7px 12px; font-size: .82rem; cursor: pointer; color: var(--text); }
.chip-drop div:hover { background: #3a3522; color: var(--gold); }
#pv { background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:14px 16px; margin-top:12px; display:none; font-size:.88rem; line-height:1.7; }
#pv h1,#pv h2,#pv h3 { color:var(--gold); }
#pv img { display:block; max-width:360px; max-height:240px; object-fit:contain; border-radius:8px; border:1px solid var(--border); }
.pv-img-wrap { position:relative; display:inline-block; margin:6px 0; }
.pv-img-x { display:none; position:absolute; top:-8px; right:-8px; width:20px; height:20px; line-height:20px; text-align:center; border-radius:50%; background:var(--red); color:#fff; cursor:pointer; font-size:.72rem; box-shadow:0 1px 4px rgba(0,0,0,.4); }
.pv-img-wrap:hover .pv-img-x { display:block; }
#pv a { color:#7fb3ff; }
#pv code { background:#2a2a30; border-radius:4px; padding:1px 6px; }
#pv pre { background:#2a2a30; padding:10px; border-radius:8px; overflow-x:auto; }
#pv blockquote { border-left:3px solid var(--gold-dark); margin:0; padding-left:12px; color:var(--muted); }
#mom-pane { flex:1; padding:16px 20px; overflow-y:auto; height:calc(100vh - 58px); display:flex; gap:20px; }
#mom-form { width:420px; flex-shrink:0; }
#mom-form textarea { width:100%; height:120px; resize:vertical; }
#mom-imgs { list-style:none; margin:8px 0; padding:0; }
#mom-imgs li { display:flex; align-items:center; gap:8px; font-size:.8rem; color:var(--muted); padding:4px 0; }
#mom-list { flex:1; min-width:0; }
#mom-items { list-style:none; margin:0; padding:0; }
#mom-items li { background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:10px 12px; margin-bottom:8px; font-size:.85rem; line-height:1.6; white-space:pre-wrap; word-break:break-word; }
#mom-items li.hl { border-color:var(--gold); background:#2c2618; }
#dl-pane { flex:1; padding:16px 20px; overflow-y:auto; height:calc(100vh - 58px); display:flex; gap:20px; }
#dl-form { width:420px; flex-shrink:0; }
select { background:var(--input); color:var(--text); border:1px solid var(--border); border-radius:8px; padding:8px 10px; font-size:.9rem; font-family:inherit; }
select:focus { outline:none; border-color:var(--gold); }
#dl-list { flex:1; min-width:0; }
#dl-items { list-style:none; margin:0; padding:0; }
#dl-items li { display:flex; align-items:center; gap:10px; background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:8px 12px; margin-bottom:6px; font-size:.85rem; }
#dl-items .dl-name { flex:1; min-width:0; word-break:break-all; }
#dl-items .dl-size { color:var(--muted); font-size:.75rem; white-space:nowrap; }
.mom-meta { font-size:.72rem; color:var(--muted); margin-bottom:4px; display:flex; gap:10px; align-items:center; }
.mom-del { margin-left:auto; }
.small { font-size:.75rem; color:var(--muted); }
.hidden-file { display:none; }
#music-pane { flex:1; padding:16px 20px; overflow-y:auto; height:calc(100vh - 58px); display:flex; gap:20px; }
#music-pls { width:220px; flex-shrink:0; }
#music-pls-list { list-style:none; margin:8px 0; padding:0; }
#music-pls-list li { display:flex; align-items:center; gap:8px; padding:8px 10px; border-radius:8px; cursor:pointer; font-size:.85rem; color:var(--text); }
#music-pls-list li:hover { background:var(--panel2); }
#music-pls-list li.sel { background:#3a3522; color:var(--gold); }
#music-pls-list li .pl-del { margin-left:auto; }
#music-files { flex:1; min-width:0; }
#music-items { list-style:none; margin:8px 0 0; padding:0; }
#music-items li { display:flex; align-items:center; gap:8px; background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:8px 12px; margin-bottom:6px; font-size:.85rem; }
#music-items .mu-idx { color:var(--muted); font-size:.75rem; width:22px; text-align:right; flex-shrink:0; }
#music-items .mu-name { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
#music-items .mu-size { color:var(--muted); font-size:.75rem; flex-shrink:0; }
.mu-btn { flex-shrink:0; }
.mu-grip { color:var(--muted); cursor:grab; flex-shrink:0; padding:2px 4px; user-select:none; }
.mu-grip:active { cursor:grabbing; }
#music-items li.mu-dragging { opacity:.45; }
#music-items li.mu-drag-over { outline:1px dashed var(--gold); }
.ic { width:15px; height:15px; stroke:currentColor; fill:none; stroke-width:1.8; stroke-linecap:round; stroke-linejoin:round; vertical-align:-2px; margin-right:5px; flex-shrink:0; }
.ic-sm { width:12px; height:12px; margin:0 3px 0 0; vertical-align:-1px; }
.list-bar { display:flex; align-items:center; justify-content:space-between; padding:10px 12px 4px; color:var(--muted); font-size:.85rem; font-weight:700; }
#art-list-pane { position:relative; }
#art-list-pane.collapsed { width:28px !important; overflow:visible; }
#art-list-pane.collapsed .list-bar,
#art-list-pane.collapsed #art-list { display:none; }
#btn-expand {
    display:none;
    position:absolute;
    top:50%;
    left:50%;
    transform:translate(-50%, -50%);
    width:24px;
    height:36px;
    padding:0;
    border-radius:8px;
}
#art-list-pane.collapsed #btn-expand { display:block; }
#btn-expand .ic { margin:0; }
#art-filter { display:flex; align-items:center; gap:6px; padding:6px 10px 2px; }
#art-filter input[type=text] {
    flex:1; min-width:0; background:var(--input); color:var(--text);
    border:1px solid var(--border); border-radius:8px; padding:6px 8px 6px 26px;
    font-size:.8rem; outline:none; font-family:inherit;
}
#art-filter input[type=text]:focus { border-color:var(--gold); }
#art-filter .search-wrap { position:relative; flex:1; min-width:0; }
#art-filter .search-wrap .ic { position:absolute; left:7px; top:7px; margin:0; color:var(--muted); width:13px; height:13px; }
#art-filter label { display:flex; align-items:center; gap:4px; color:var(--muted); font-size:.75rem; cursor:pointer; white-space:nowrap; }
#art-filter input[type=checkbox] { accent-color:var(--gold); }
.crop-overlay {
    display:none; position:fixed; inset:0; z-index:9999; background:rgba(0,0,0,.7);
    align-items:center; justify-content:center;
}
.crop-overlay.open { display:flex; }
.crop-box { background:var(--panel); border:1px solid var(--border); border-radius:14px; padding:16px 20px; box-shadow:0 12px 40px rgba(0,0,0,.5); }
.crop-box h3 { margin:0 0 10px; font-size:.95rem; color:var(--gold); }
#crop-canvas { display:block; background:#000; border-radius:8px; cursor:move; }
.crop-tools { display:flex; align-items:center; gap:8px; margin-top:12px; }
.crop-tools .btn { padding:6px 12px; }
#ai-pane { flex:1; padding:16px 20px; overflow-y:auto; height:calc(100vh - 58px); display:flex; gap:20px; }
#ai-form { width:360px; flex-shrink:0; }
#ai-form textarea { width:100%; height:100px; resize:vertical; }
#ai-status-line { font-size:.88rem; color:var(--text); margin-bottom:8px; }
#ai-grid { flex:1; min-width:0; }
#ai-items { list-style:none; margin:0; padding:0; display:grid; grid-template-columns:repeat(auto-fill,minmax(180px,1fr)); gap:10px; }
#ai-items li { background:var(--panel); border:1px solid var(--border); border-radius:8px; padding:8px; }
#ai-items img { width:100%; height:150px; object-fit:cover; border-radius:6px; background:#000; }
#ai-items .ai-name { display:block; font-size:.72rem; color:var(--muted); margin-top:6px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.ai-actions { display:flex; gap:6px; margin-top:8px; flex-wrap:wrap; }
.ai-progress { width:100%; height:6px; background:var(--input); border-radius:4px; overflow:hidden; margin-top:10px; }
.ai-progress > div { height:100%; background:var(--gold); width:0; transition:width .2s; }
.img-picker-overlay { display:none; position:fixed; inset:0; z-index:9999; background:rgba(0,0,0,.75); align-items:center; justify-content:center; }
.img-picker-overlay.open { display:flex; }
.img-picker { width:min(760px,92vw); max-height:86vh; background:var(--panel); border:1px solid var(--border); border-radius:14px; padding:16px 20px; overflow-y:auto; }
.img-picker-tabs { display:flex; gap:6px; margin-bottom:10px; }
#pick-ai-items { list-style:none; display:grid; grid-template-columns:repeat(auto-fill,minmax(120px,1fr)); gap:8px; margin:8px 0; padding:0; }
#pick-ai-items li { cursor:pointer; border:2px solid transparent; border-radius:8px; overflow:hidden; background:var(--panel2); }
#pick-ai-items li.sel { border-color:var(--gold); }
#pick-ai-items img { width:100%; height:100px; object-fit:cover; display:block; }
#pick-ai-items .pick-ai-name { display:block; font-size:.68rem; color:var(--muted); padding:4px 6px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
#pick-gen-prompt { width:100%; height:90px; resize:vertical; }
#pick-gen-preview { display:none; max-width:100%; margin-top:8px; border-radius:8px; }
</style>
</head>
<body>
<svg xmlns="http://www.w3.org/2000/svg" style="display:none" aria-hidden="true">
  <symbol id="ic-doc" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6"/></symbol>
  <symbol id="ic-chat" viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2Z"/></symbol>
  <symbol id="ic-box" viewBox="0 0 24 24"><path d="M21 8 12 3 3 8v8l9 5 9-5Z"/><path d="M3 8l9 5 9-5"/><path d="M12 13v8"/></symbol>
  <symbol id="ic-pen" viewBox="0 0 24 24"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></symbol>
  <symbol id="ic-save" viewBox="0 0 24 24"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2Z"/><path d="M17 21v-8H7v8"/><path d="M7 3v5h8"/></symbol>
  <symbol id="ic-trash" viewBox="0 0 24 24"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M10 11v6"/><path d="M14 11v6"/></symbol>
  <symbol id="ic-image" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/></symbol>
  <symbol id="ic-eye" viewBox="0 0 24 24"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></symbol>
  <symbol id="ic-plus" viewBox="0 0 24 24"><path d="M12 5v14"/><path d="M5 12h14"/></symbol>
  <symbol id="ic-upload" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5"/><path d="M12 3v12"/></symbol>
  <symbol id="ic-folder" viewBox="0 0 24 24"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2Z"/></symbol>
  <symbol id="ic-link" viewBox="0 0 24 24"><path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/></symbol>
  <symbol id="ic-send" viewBox="0 0 24 24"><path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4Z"/></symbol>
  <symbol id="ic-left" viewBox="0 0 24 24"><path d="m15 18-6-6 6-6"/></symbol>
  <symbol id="ic-right" viewBox="0 0 24 24"><path d="m9 18 6-6-6-6"/></symbol>
  <symbol id="ic-x" viewBox="0 0 24 24"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></symbol>
  <symbol id="ic-music" viewBox="0 0 24 24"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></symbol>
  <symbol id="ic-up" viewBox="0 0 24 24"><path d="m18 15-6-6-6 6"/></symbol>
  <symbol id="ic-down" viewBox="0 0 24 24"><path d="m6 9 6 6 6-6"/></symbol>
  <symbol id="ic-grip" viewBox="0 0 24 24"><path d="M9 6h1M15 6h1M9 12h1M15 12h1M9 18h1M15 18h1"/></symbol>
  <symbol id="ic-search" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></symbol>
  <symbol id="ic-crop" viewBox="0 0 24 24"><path d="M6 2v14a2 2 0 0 0 2 2h14"/><path d="M18 22V8a2 2 0 0 0-2-2H2"/></symbol>
  <symbol id="ic-zoomin" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/><path d="M11 8v6"/><path d="M8 11h6"/></symbol>
  <symbol id="ic-zoomout" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/><path d="M8 11h6"/></symbol>
  <symbol id="ic-check" viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5"/></symbol>
  <symbol id="ic-spark" viewBox="0 0 24 24"><path d="M12 2 14.2 8.8 21 11l-6.8 2.2L12 20l-2.2-6.8L3 11l6.8-2.2Z"/><path d="M19 3v4"/><path d="M21 5h-4"/></symbol>
</svg>
<header>
  <h1>博客写作助手 · 网页版</h1>
  <span id="status">就绪</span>
  <div class="tabs">
    <button class="tab-btn active" id="tab-articles"><svg class="ic"><use href="#ic-doc"/></svg>文章</button>
    <button class="tab-btn" id="tab-moments"><svg class="ic"><use href="#ic-chat"/></svg>动态</button>
    <button class="tab-btn" id="tab-ai"><svg class="ic"><use href="#ic-spark"/></svg>AI 图库</button>
    <button class="tab-btn" id="tab-music"><svg class="ic"><use href="#ic-music"/></svg>音乐</button>
    <button class="tab-btn" id="tab-downloads"><svg class="ic"><use href="#ic-box"/></svg>下载</button>
  </div>
</header>
<main>
  <section class="view active" id="view-articles">
    <div id="art-list-pane">
      <div class="list-bar"><span>文章</span><button class="btn sm" id="btn-collapse" title="收起列表"><svg class="ic ic-sm"><use href="#ic-left"/></svg></button></div>
      <ul id="art-list"></ul>
      <button class="btn sm" id="btn-expand" title="展开列表"><svg class="ic"><use href="#ic-right"/></svg></button>
    </div>
    <div id="art-form">
      <input type="hidden" id="f-file">
      <div class="row"><label>标题</label><input type="text" id="f-title" style="flex:1"></div>
      <div class="row"><label>日期</label><input type="text" id="f-date" placeholder="2026-08-01 或 2026-08-01T21:24:37+08:00" style="flex:1"></div>
      <div class="row"><label>分类</label>
        <div class="chipbox" id="cat-box">
          <div class="chips" id="cat-chips"></div>
          <input type="text" id="f-cats" placeholder="输入筛选或新建，回车确认" autocomplete="off">
          <div class="chip-drop" id="cat-drop" style="display:none"></div>
        </div>
      </div>
      <div class="row"><label>标签</label>
        <div class="chipbox" id="tag-box">
          <div class="chips" id="tag-chips"></div>
          <input type="text" id="f-tags" placeholder="输入后回车添加" autocomplete="off">
        </div>
      </div>
      <div class="row">
        <label>封面</label><input type="text" id="f-cover" placeholder="/images/xxx.jpg" style="flex:1">
        <input type="file" id="f-cover-file" class="hidden-file" accept="image/*">
        <button class="btn sm" id="btn-cover-up"><svg class="ic ic-sm"><use href="#ic-upload"/></svg>上传封面</button>
        <label style="width:auto; display:flex; align-items:center; gap:6px; color:var(--muted); font-size:.85rem; cursor:pointer;"><input type="checkbox" id="f-draft"> 草稿</label>
      </div>
      <div class="row" style="align-items:flex-start;">
        <label>正文</label>
        <div style="flex:1">
          <textarea id="f-body" placeholder="Markdown 正文"></textarea>
          <div style="margin-top:8px; display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
            <button class="btn gold" id="btn-save"><svg class="ic"><use href="#ic-save"/></svg>保存</button>
            <button class="btn" id="btn-new"><svg class="ic"><use href="#ic-plus"/></svg>新建</button>
            <button class="btn danger" id="btn-del"><svg class="ic"><use href="#ic-trash"/></svg>删除</button>
            <input type="file" id="f-img-file" class="hidden-file" accept="image/*">
            <button class="btn" id="btn-img-up"><svg class="ic"><use href="#ic-image"/></svg>插入图片</button>
            <button class="btn" id="btn-pv"><svg class="ic"><use href="#ic-eye"/></svg>预览</button>
          </div>
          <div id="pv"></div>
        </div>
      </div>
    </div>
  </section>
  <section class="view" id="view-moments">
    <div id="mom-pane">
      <div id="mom-form">
        <div class="small" style="margin-bottom:8px">写下此刻（发布到博客 /dynamic/ 动态页）</div>
        <textarea id="m-text" placeholder="随便写点什么…"></textarea>
        <div class="row" style="margin-top:10px">
          <input type="file" id="m-img-file" class="hidden-file" accept="image/*" multiple>
          <button class="btn sm" id="btn-m-img"><svg class="ic ic-sm"><use href="#ic-image"/></svg>添加图片</button>
        </div>
        <ul id="mom-imgs"></ul>
        <div class="row"><label>链接（可选）</label><input type="text" id="m-link" placeholder="https://..." style="flex:1"></div>
        <div style="display:flex; gap:8px;">
        <button class="btn gold" id="btn-m-save"><svg class="ic"><use href="#ic-send"/></svg>发布动态</button>
          <button class="btn" id="btn-m-cancel" style="display:none">取消编辑</button>
        </div>
      </div>
      <div id="mom-list">
        <div class="small" style="margin-bottom:8px">已有动态</div>
        <ul id="mom-items"></ul>
      </div>
    </div>
  </section>
  <section class="view" id="view-ai">
    <div id="ai-pane">
      <div id="ai-form">
        <div class="small" style="margin-bottom:8px">ComfyUI 状态</div>
        <div id="ai-status-line">检测中...</div>
        <div style="display:flex; gap:8px; margin-bottom:12px;">
          <button class="btn sm" id="btn-ai-start"><svg class="ic ic-sm"><use href="#ic-spark"/></svg>启动</button>
          <button class="btn sm" id="btn-ai-refresh"><svg class="ic ic-sm"><use href="#ic-upload"/></svg>刷新</button>
        </div>
        <div class="small" style="margin-bottom:6px">一句话生成</div>
        <textarea id="ai-prompt" placeholder="例如：一只金色机械猫坐在电路板上，赛博朋克风格"></textarea>
        <div class="row" style="margin-top:8px"><label style="width:56px">模型</label><select id="ai-model" style="flex:1"></select></div>
        <div class="row"><label style="width:56px">尺寸</label><select id="ai-size" style="flex:1">
          <option value="832x1216">竖版 832x1216</option>
          <option value="1024x1024" selected>方图 1024x1024</option>
          <option value="1216x832">横版 1216x832</option>
        </select></div>
        <button class="btn gold" id="btn-ai-gen"><svg class="ic"><use href="#ic-spark"/></svg>生成</button>
        <div class="ai-progress" id="ai-progress"><div></div></div>
        <div class="small" id="ai-gen-status"></div>
      </div>
      <div id="ai-grid">
        <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
          <span class="small">ComfyUI 最近生成</span>
          <button class="btn sm" id="btn-ai-grid-refresh"><svg class="ic ic-sm"><use href="#ic-upload"/></svg>刷新</button>
        </div>
        <ul id="ai-items"></ul>
      </div>
    </div>
  </section>
  <section class="view" id="view-downloads">
    <div id="dl-pane">
      <div id="dl-form">
          <div class="row">
            <label>分类</label>
            <select id="dl-cat" style="flex:1"></select>
            <button class="btn sm" id="btn-dl-rencat"><svg class="ic ic-sm"><use href="#ic-pen"/></svg>重命名</button>
            <button class="btn sm" id="btn-dl-newcat"><svg class="ic ic-sm"><use href="#ic-plus"/></svg>新建</button>
          </div>
        <div class="row">
          <input type="file" id="dl-file" class="hidden-file" multiple>
          <button class="btn gold" id="btn-dl-upload"><svg class="ic"><use href="#ic-upload"/></svg>添加文件</button>
        </div>
        <div class="small">文件复制到 static/files/&lt;分类&gt;/，重新构建后出现在 /downloads/。大文件建议用桌面版。</div>
      </div>
      <div id="dl-list">
        <div class="small" style="margin-bottom:8px">已有文件（可删除）</div>
        <ul id="dl-items"></ul>
      </div>
    </div>
  </section>
  <section class="view" id="view-music">
    <div id="music-pane">
      <div id="music-pls">
        <div class="small" style="margin-bottom:8px">歌单</div>
        <ul id="music-pls-list"></ul>
        <div style="display:flex; gap:6px; margin-top:10px;">
          <input type="text" id="m-pls-name" placeholder="新歌单名" style="flex:1; min-width:0;">
          <button class="btn sm" id="btn-pls-new"><svg class="ic ic-sm"><use href="#ic-plus"/></svg>新建</button>
        </div>
      </div>
      <div id="music-files">
        <div style="display:flex; gap:8px; align-items:center; margin-bottom:8px; flex-wrap:wrap;">
          <input type="file" id="m-music-file" class="hidden-file" accept="audio/*">
          <button class="btn gold" id="btn-music-up"><svg class="ic"><use href="#ic-upload"/></svg>上传音乐</button>
          <select id="m-pls-add" style="display:none; background:var(--input); color:var(--text); border:1px solid var(--border); border-radius:8px; padding:6px 8px; max-width:260px;"></select>
          <button class="btn sm" id="btn-pls-add" style="display:none"><svg class="ic ic-sm"><use href="#ic-plus"/></svg>加入歌单</button>
          <span class="small" id="m-music-tip" style="margin-left:auto">文件名用"作者 - 歌名.mp3"格式</span>
        </div>
        <ul id="music-items"></ul>
      </div>
    </div>
  </section>
</main>
<div class="img-picker-overlay" id="img-picker">
  <div class="img-picker">
    <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
      <span class="small" id="img-picker-title">选择图片</span>
      <button class="btn sm" id="btn-picker-close" style="margin-left:auto"><svg class="ic ic-sm"><use href="#ic-x"/></svg></button>
    </div>
    <div class="img-picker-tabs">
      <button class="tab-btn active" id="pick-tab-local">本地上传</button>
      <button class="tab-btn" id="pick-tab-gallery">AI 图库</button>
      <button class="tab-btn" id="pick-tab-gen">AI 生成</button>
    </div>
    <div id="pick-local">
      <input type="file" id="pick-file" class="hidden-file" accept="image/*">
      <button class="btn gold" id="btn-pick-file"><svg class="ic"><use href="#ic-upload"/></svg>选择本地图片</button>
      <div class="small">选完会自动上传并插入</div>
    </div>
    <div id="pick-gallery" style="display:none">
      <div style="display:flex; gap:8px; align-items:center; margin-bottom:6px;">
        <button class="btn sm" id="btn-pick-ai-refresh"><svg class="ic ic-sm"><use href="#ic-upload"/></svg>刷新</button>
        <span class="small" id="pick-ai-tip"></span>
      </div>
      <ul id="pick-ai-items"></ul>
      <button class="btn gold" id="btn-pick-ai-use" disabled><svg class="ic"><use href="#ic-check"/></svg>使用此图</button>
    </div>
    <div id="pick-gen" style="display:none">
      <textarea id="pick-gen-prompt" placeholder="一句话描述要生成的图片"></textarea>
      <div class="row" style="margin-top:8px"><label style="width:56px">模型</label><select id="pick-gen-model" style="flex:1"></select></div>
      <button class="btn gold" id="btn-pick-gen"><svg class="ic"><use href="#ic-spark"/></svg>生成</button>
      <div class="ai-progress" id="pick-gen-progress"><div></div></div>
      <div class="small" id="pick-gen-status"></div>
      <img id="pick-gen-preview" alt="">
      <button class="btn gold" id="btn-pick-gen-use" style="display:none"><svg class="ic"><use href="#ic-check"/></svg>使用此图</button>
    </div>
  </div>
</div>
<script>
(function () {
    var $ = function (id) { return document.getElementById(id); };
    var state = { articles: [], curFile: null, moments: [], momImgs: [], editingId: null,
                  catChips: [], tagChips: [], allCats: [], musicFiles: [], musicPls: [], musicCur: '全部',
                  ai: { models: [], images: [], pickImages: [], taskId: null,
                        picker: { context: null, cb: null, selected: null, genName: null, genTask: null } } };
    var pendingMomentId = null;

    function api(path, opts) {
        opts = opts || {};
        opts.headers = Object.assign({}, opts.headers || {}, { 'Content-Type': 'application/json' });
        return fetch(path, opts).then(function (r) { return r.json(); });
    }
    function setStatus(t) { $('status').textContent = t; }
    function esc(s) { var d = document.createElement('div'); d.textContent = s == null ? '' : String(s); return d.innerHTML; }
    function renderChips(boxId, chips) {
        var list = $(boxId).querySelector('.chips');
        list.innerHTML = '';
        chips.forEach(function (c, i) {
            var el = document.createElement('span');
            el.className = 'chip';
            el.innerHTML = '<span>' + esc(c) + '</span><span class="chip-x" title="删除"><svg class="ic ic-sm"><use href="#ic-x"/></svg></span>';
            el.querySelector('.chip-x').addEventListener('click', function () {
                chips.splice(i, 1);
                renderChips(boxId, chips);
            });
            list.appendChild(el);
        });
    }
    function addChip(chips, boxId, inputId) {
        var v = $(inputId).value.trim();
        if (v && chips.indexOf(v) < 0) chips.push(v);
        $(inputId).value = '';
        renderChips(boxId, chips);
        $(inputId).focus();
    }
    function updateCatDrop() {
        var q = $('f-cats').value.trim();
        var list = state.allCats.filter(function (c) {
            return state.catChips.indexOf(c) < 0 && (!q || c.indexOf(q) >= 0);
        });
        var drop = $('cat-drop');
        if (!list.length) { drop.style.display = 'none'; return; }
        drop.innerHTML = '';
        list.forEach(function (c) {
            var el = document.createElement('div');
            el.textContent = c;
            el.addEventListener('click', function () {
                if (state.catChips.indexOf(c) < 0) state.catChips.push(c);
                $('f-cats').value = '';
                renderChips('cat-box', state.catChips);
                updateCatDrop();
            });
            drop.appendChild(el);
        });
        drop.style.display = 'block';
    }

    // ---- 页签 ----
    function showTab(name) {
        $('view-articles').classList.toggle('active', name === 'articles');
        $('view-moments').classList.toggle('active', name === 'moments');
        $('view-ai').classList.toggle('active', name === 'ai');
        $('view-downloads').classList.toggle('active', name === 'downloads');
        $('view-music').classList.toggle('active', name === 'music');
        $('tab-articles').classList.toggle('active', name === 'articles');
        $('tab-moments').classList.toggle('active', name === 'moments');
        $('tab-ai').classList.toggle('active', name === 'ai');
        $('tab-downloads').classList.toggle('active', name === 'downloads');
        $('tab-music').classList.toggle('active', name === 'music');
    }
    $('tab-articles').addEventListener('click', function () { showTab('articles'); });
    $('tab-moments').addEventListener('click', function () { showTab('moments'); });
    $('tab-ai').addEventListener('click', function () { showTab('ai'); loadAiState(); });
    $('tab-downloads').addEventListener('click', function () { showTab('downloads'); });
    $('tab-music').addEventListener('click', function () { showTab('music'); loadMusic(); });

    // ---- AI 图库 / 图片来源 ----
    function aiImgUrl(name, subfolder, thumb) {
        return '/comfy-image?name=' + encodeURIComponent(name) +
            (subfolder ? '&subfolder=' + encodeURIComponent(subfolder) : '') +
            '&thumb=' + (thumb ? '1' : '0');
    }
    function loadAiState() {
        api('/api/comfy/state').then(function (s) {
            var running = !!s.running;
            $('ai-status-line').textContent = running ? 'ComfyUI 已运行' : 'ComfyUI 未运行';
            $('btn-ai-start').disabled = running;
            state.ai.models = running ? (s.models || []) : [];
            fillAiModels();
            if (running) loadAiGallery();
        });
    }
    function fillAiModels() {
        var opts = state.ai.models.map(function (m) {
            return '<option value="' + esc(m) + '">' + esc(m) + '</option>';
        }).join('');
        if (!opts) opts = '<option value="">无模型</option>';
        $('ai-model').innerHTML = opts;
        $('pick-gen-model').innerHTML = opts;
    }
    function startComfy() {
        $('ai-status-line').textContent = '正在启动 ComfyUI...';
        api('/api/comfy/start', { method: 'POST', body: '{}' }).then(function (r) {
            if (r.error) { alert(r.error); $('ai-status-line').textContent = '启动失败'; return; }
            pollComfyReady(0);
        });
    }
    function pollComfyReady(n) {
        if (n > 120) { $('ai-status-line').textContent = '启动超时，请检查 ComfyUI'; return; }
        api('/api/comfy/state').then(function (s) {
            if (s.running) { loadAiState(); $('ai-gen-status').textContent = 'ComfyUI 已就绪'; return; }
            setTimeout(function () { pollComfyReady(n + 1); }, 1000);
        });
    }
    function loadAiGallery() {
        api('/api/comfy/images').then(function (d) {
            state.ai.images = d.images || [];
            renderAiGallery();
        });
    }
    function renderAiGallery() {
        var ul = $('ai-items');
        ul.innerHTML = '';
        if (!state.ai.images.length) {
            ul.innerHTML = '<li class="small" style="border:none;background:none;">暂无 AI 图片</li>';
            return;
        }
        state.ai.images.forEach(function (it) {
            var li = document.createElement('li');
            li.innerHTML = '<img src="' + aiImgUrl(it.name, '', 1) + '" loading="lazy" alt="">' +
                '<span class="ai-name">' + esc(it.name) + '</span>' +
                '<div class="ai-actions">' +
                '<button class="btn sm" data-act="post">插入正文</button>' +
                '<button class="btn sm" data-act="cover">封面</button>' +
                '<button class="btn sm" data-act="moment">动态</button>' +
                '</div>';
            li.querySelectorAll('button').forEach(function (b) {
                b.addEventListener('click', function () {
                    useAiImage(it.name, b.getAttribute('data-act'));
                });
            });
            ul.appendChild(li);
        });
    }
    function useAiImage(name, action, cb) {
        var target = action === 'moment' ? 'moment' : 'post';
        api('/api/comfy/import', {
            method: 'POST',
            body: JSON.stringify({ name: name, target: target })
        }).then(function (r) {
            if (r.error) { alert(r.error); return; }
            if (cb) { cb(r.url); return; }
            applyAiUrl(r.url, action);
        });
    }
    function applyAiUrl(url, action) {
        if (action === 'cover') {
            $('f-cover').value = url;
            showTab('articles');
        } else if (action === 'moment') {
            state.momImgs.push(url);
            renderMomImgs();
            showTab('moments');
        } else {
            var ta = $('f-body');
            var p = ta.selectionStart || ta.value.length;
            ta.value = ta.value.slice(0, p) + '![](' + url + ')\\n\\n' + ta.value.slice(p);
            showTab('articles');
        }
        setStatus('AI 图片已导入：' + url);
    }
    function openImagePicker(context, cb) {
        state.ai.picker = { context: context, cb: cb, selected: null, genName: null, genTask: null };
        $('btn-pick-ai-use').disabled = true;
        $('img-picker').classList.add('open');
        $('img-picker-title').textContent = context === 'moment' ? '添加动态图片' :
            (context === 'cover' ? '设置封面' : '插入正文图片');
        setPickerTab('local');
        $('pick-file').value = '';
        loadPickAiGallery();
        resetPickGen();
    }
    function closePicker() {
        $('img-picker').classList.remove('open');
    }
    function setPickerTab(name) {
        $('pick-local').style.display = name === 'local' ? '' : 'none';
        $('pick-gallery').style.display = name === 'gallery' ? '' : 'none';
        $('pick-gen').style.display = name === 'gen' ? '' : 'none';
        ['pick-tab-local', 'pick-tab-gallery', 'pick-tab-gen'].forEach(function (id) {
            $(id).classList.toggle('active', id === 'pick-tab-' + name);
        });
    }
    function loadPickAiGallery() {
        api('/api/comfy/images').then(function (d) {
            state.ai.pickImages = d.images || [];
            renderPickAiGallery();
        });
    }
    function renderPickAiGallery() {
        var ul = $('pick-ai-items');
        ul.innerHTML = '';
        state.ai.pickImages.forEach(function (it) {
            var li = document.createElement('li');
            if (state.ai.picker.selected === it.name) li.className = 'sel';
            li.innerHTML = '<img src="' + aiImgUrl(it.name, '', 1) + '" loading="lazy" alt="">' +
                '<span class="pick-ai-name">' + esc(it.name) + '</span>';
            li.addEventListener('click', function () {
                state.ai.picker.selected = it.name;
                renderPickAiGallery();
                $('btn-pick-ai-use').disabled = false;
            });
            ul.appendChild(li);
        });
        if (!state.ai.pickImages.length) {
            $('pick-ai-tip').textContent = '暂无 AI 图片';
        } else {
            $('pick-ai-tip').textContent = '点击选择图片';
        }
    }
    function resetPickGen() {
        $('pick-gen-prompt').value = '';
        $('pick-gen-progress').firstElementChild.style.width = '0%';
        $('pick-gen-status').textContent = '';
        $('pick-gen-preview').style.display = 'none';
        $('pick-gen-preview').removeAttribute('src');
        $('btn-pick-gen-use').style.display = 'none';
    }
    function startGenerate(target) {
        var promptEl = target === 'picker' ? $('pick-gen-prompt') : $('ai-prompt');
        var modelEl = target === 'picker' ? $('pick-gen-model') : $('ai-model');
        var prompt = promptEl.value.trim();
        if (!prompt) { alert('请输入提示词'); return; }
        if (!modelEl.value) { alert('请先启动 ComfyUI 并选择模型'); return; }
        var size = ($('ai-size').value || '1024x1024').split('x');
        var payload = {
            prompt: prompt, model: modelEl.value,
            width: size[0], height: size[1], steps: 20, cfg: 7
        };
        var statusEl = target === 'picker' ? $('pick-gen-status') : $('ai-gen-status');
        var progressEl = target === 'picker' ?
            $('pick-gen-progress').firstElementChild : $('ai-progress').firstElementChild;
        statusEl.textContent = '提交中...';
        progressEl.style.width = '0%';
        api('/api/comfy/generate', { method: 'POST', body: JSON.stringify(payload) }).then(function (r) {
            if (r.error) { alert(r.error); statusEl.textContent = '生成失败'; return; }
            pollAiTask(r.prompt_id, statusEl, progressEl, function (img) {
                if (target === 'picker') {
                    state.ai.picker.genName = img.filename;
                    $('pick-gen-preview').src = aiImgUrl(img.filename, img.subfolder || '', 0);
                    $('pick-gen-preview').style.display = '';
                    $('btn-pick-gen-use').style.display = '';
                } else {
                    setStatus('AI 图片已生成');
                    loadAiGallery();
                }
            });
        });
    }
    function pollAiTask(taskId, statusEl, progressEl, onDone) {
        api('/api/comfy/task?prompt_id=' + encodeURIComponent(taskId)).then(function (t) {
            var pct = 0, text = '';
            if (t.status === 'queued') {
                text = '排队中...';
            } else if (t.status === 'running') {
                if (t.max) pct = Math.min(99, Math.round((t.value || 0) / t.max * 100));
                text = '生成中 ' + pct + '%';
            } else if (t.status === 'done') {
                pct = 100;
                text = '生成完成';
                progressEl.style.width = '100%';
                statusEl.textContent = text;
                if (onDone && t.images && t.images[0]) onDone(t.images[0]);
                return;
            } else if (t.status === 'error') {
                text = '生成失败';
                statusEl.textContent = text;
                return;
            } else {
                text = '等待任务开始...';
            }
            progressEl.style.width = pct + '%';
            statusEl.textContent = text;
            setTimeout(function () { pollAiTask(taskId, statusEl, progressEl, onDone); }, 1000);
        });
    }
    $('btn-ai-start').addEventListener('click', startComfy);
    $('btn-ai-refresh').addEventListener('click', loadAiState);
    $('btn-ai-grid-refresh').addEventListener('click', loadAiGallery);
    $('btn-ai-gen').addEventListener('click', function () { startGenerate('tab'); });
    $('btn-picker-close').addEventListener('click', closePicker);
    $('btn-pick-file').addEventListener('click', function () { $('pick-file').click(); });
    $('pick-file').addEventListener('change', function () {
        var f = this.files && this.files[0];
        if (!f) return;
        uploadImg(this, state.ai.picker.context === 'moment' ? 'moment' : 'post', function (url) {
            state.ai.picker.cb(url);
            closePicker();
        });
    });
    $('pick-tab-local').addEventListener('click', function () { setPickerTab('local'); });
    $('pick-tab-gallery').addEventListener('click', function () { setPickerTab('gallery'); });
    $('pick-tab-gen').addEventListener('click', function () { setPickerTab('gen'); });
    $('btn-pick-ai-refresh').addEventListener('click', loadPickAiGallery);
    $('btn-pick-ai-use').addEventListener('click', function () {
        var name = state.ai.picker.selected;
        if (!name) return;
        useAiImage(name, state.ai.picker.context, function (url) {
            state.ai.picker.cb(url);
            closePicker();
        });
    });
    $('btn-pick-gen').addEventListener('click', function () { startGenerate('picker'); });
    $('btn-pick-gen-use').addEventListener('click', function () {
        var name = state.ai.picker.genName;
        if (!name) return;
        useAiImage(name, state.ai.picker.context, function (url) {
            state.ai.picker.cb(url);
            closePicker();
        });
    });

    $('btn-collapse').addEventListener('click', function () {
        $('art-list-pane').classList.add('collapsed');
    });
    $('btn-expand').addEventListener('click', function () {
        $('art-list-pane').classList.remove('collapsed');
    });

    // ---- 文章 ----
    function renderArtList() {
        var ul = $('art-list');
        ul.innerHTML = '';
        state.articles.forEach(function (a) {
            var li = document.createElement('li');
            li.className = a.file === state.curFile ? 'sel' : '';
            li.innerHTML = '<div class="a-title">' + (a.draft ? '<span class="draft-tag">[草稿] </span>' : '') + esc(a.title) + '</div>' +
                '<div class="a-meta">' + esc(a.date || '') + '</div>';
            li.addEventListener('click', function () { loadArticle(a.file); });
            ul.appendChild(li);
        });
    }
    function loadArticles() {
        api('/api/articles').then(function (list) {
            state.articles = list;
            state.allCats = [];
            list.forEach(function (a) {
                (a.categories || []).forEach(function (c) {
                    if (state.allCats.indexOf(c) < 0) state.allCats.push(c);
                });
            });
            renderArtList();
            if (!state.curFile && list.length) loadArticle(list[0].file);
        });
    }
    function loadArticle(file) {
        state.curFile = file;
        api('/api/article?file=' + encodeURIComponent(file)).then(function (d) {
            $('f-file').value = d.file || '';
            $('f-title').value = d.title || '';
            $('f-date').value = d.date || '';
            state.catChips = (d.categories || []).slice();
            state.tagChips = (d.tags || []).slice();
            renderChips('cat-box', state.catChips);
            renderChips('tag-box', state.tagChips);
            $('f-cover').value = d.cover || '';
            $('f-draft').checked = !!d.draft;
            $('f-body').value = d.body || '';
            $('pv').style.display = 'none';
            $('pv').innerHTML = '';
            renderArtList();
            setStatus('已打开：' + file);
        }).catch(function () { setStatus('打开失败'); });
    }
    function saveArticle() {
        var payload = {
            file: $('f-file').value || null,
            title: $('f-title').value,
            date: $('f-date').value,
            categories: state.catChips,
            tags: state.tagChips,
            draft: $('f-draft').checked,
            cover: $('f-cover').value,
            body: $('f-body').value.replace(/\\s+$/, '')
        };
        api('/api/article', { method: 'POST', body: JSON.stringify(payload) }).then(function (r) {
            if (r.error) { alert(r.error); return; }
            setStatus('已保存：' + r.file);
            loadArticles();
        });
    }
    function newArticle() {
        state.curFile = null;
        $('f-file').value = '';
        $('f-title').value = '';
        $('f-date').value = '';
        state.catChips = [];
        state.tagChips = [];
        renderChips('cat-box', state.catChips);
        renderChips('tag-box', state.tagChips);
        $('f-cover').value = '';
        $('f-draft').checked = false;
        $('f-body').value = '';
        renderArtList();
        $('f-title').focus();
    }
    function delArticle() {
        if (!state.curFile || !confirm('确定删除这篇文件？\\n' + state.curFile)) return;
        api('/api/article?file=' + encodeURIComponent(state.curFile), { method: 'DELETE' }).then(function (r) {
            if (r.error) { alert(r.error); return; }
            state.curFile = null;
            newArticle();
            loadArticles();
            setStatus('已删除');
        });
    }
    function uploadImg(input, target, done) {
        var f = input.files && input.files[0];
        if (!f) return;
        if (f.size > 20 * 1024 * 1024) { alert('文件超过 20MB，请使用桌面版上传'); return; }
        var reader = new FileReader();
        reader.onload = function () {
            api('/api/upload', { method: 'POST', body: JSON.stringify({ name: f.name, data: reader.result, target: target }) })
                .then(function (r) { if (r.error) { alert(r.error); return; } done(r.url); });
        };
        reader.readAsDataURL(f);
    }
    $('btn-save').addEventListener('click', saveArticle);
    $('btn-new').addEventListener('click', newArticle);
    $('btn-del').addEventListener('click', delArticle);
    $('btn-img-up').addEventListener('click', function () {
        openImagePicker('post', function (url) {
            var ta = $('f-body');
            var p = ta.selectionStart || ta.value.length;
            ta.value = ta.value.slice(0, p) + '![](' + url + ')\\n\\n' + ta.value.slice(p);
            ta.focus();
            ta.selectionStart = ta.selectionEnd = p + url.length + 5;
        });
    });
    $('f-img-file').addEventListener('change', function () {
        uploadImg(this, 'post', function (url) {
            var ta = $('f-body');
            var p = ta.selectionStart || ta.value.length;
            ta.value = ta.value.slice(0, p) + '![](' + url + ')\\n\\n' + ta.value.slice(p);
            ta.focus();
            ta.selectionStart = ta.selectionEnd = p + url.length + 5;
        });
    });
    $('btn-cover-up').addEventListener('click', function () {
        openImagePicker('cover', function (url) { $('f-cover').value = url; });
    });
    $('f-cover-file').addEventListener('change', function () {
        uploadImg(this, 'post', function (url) { $('f-cover').value = url; });
    });
    $('btn-pv').addEventListener('click', function () {
        var pv = $('pv');
        pv.style.display = pv.style.display === 'none' ? 'block' : 'none';
        if (pv.style.display === 'block') renderPreview();
    });
    function renderPreview() {
        var pv = $('pv');
        pv.innerHTML = mdRender($('f-body').value);
        var idx = 0;
        pv.querySelectorAll('img').forEach(function (img) {
            var wrap = document.createElement('span');
            wrap.className = 'pv-img-wrap';
            img.parentNode.insertBefore(wrap, img);
            wrap.appendChild(img);
            var x = document.createElement('span');
            x.className = 'pv-img-x';
            x.innerHTML = '<svg class="ic ic-sm"><use href="#ic-x"/></svg>';
            x.title = '从正文删除这张图片';
            x.addEventListener('click', (function (n) {
                return function () {
                    if (confirm('从正文中删除这张图片？')) removeImageLine(n);
                };
            })(idx));
            wrap.appendChild(x);
            idx++;
        });
    }
    function removeImageLine(n) {
        var ta = $('f-body');
        var lines = ta.value.split('\\n');
        var cnt = 0;
        for (var i = 0; i < lines.length; i++) {
            if (/!\\[[^\\]]*\\]\\([^)]+\\)/.test(lines[i])) {
                if (cnt === n) {
                    lines.splice(i, 1);
                    ta.value = lines.join('\\n').replace(/\\n{3,}/g, '\\n\\n');
                    renderPreview();
                    return;
                }
                cnt++;
            }
        }
    }
    $('pv').addEventListener('error', function (e) {
        var img = e.target;
        if (img && img.tagName === 'IMG' && !img.dataset.err) {
            img.dataset.err = '1';
            var oldSrc = img.getAttribute('src') || img.src;
            var tip = document.createElement('span');
            tip.className = 'pv-img-err';
            tip.textContent = '图片加载失败：' + oldSrc;
            img.parentNode.insertBefore(tip, img);
            img.style.display = 'none';
        }
    }, true);
    $('f-cats').addEventListener('input', updateCatDrop);
    $('f-cats').addEventListener('focus', updateCatDrop);
    $('f-cats').addEventListener('blur', function () {
        setTimeout(function () { $('cat-drop').style.display = 'none'; }, 150);
    });
    $('f-cats').addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            addChip(state.catChips, 'cat-box', 'f-cats');
            updateCatDrop();
        }
        if (e.key === 'Escape') { $('cat-drop').style.display = 'none'; }
    });
    $('f-tags').addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            addChip(state.tagChips, 'tag-box', 'f-tags');
        }
    });

    // ---- 动态 ----
    function loadMoments() {
        api('/api/moments').then(function (list) {
            state.moments = list;
            var ul = $('mom-items');
            ul.innerHTML = '';
            list.forEach(function (m, i) {
                var li = document.createElement('li');
                if (state.editingId && m.id === state.editingId) li.className = 'hl';
                li.innerHTML = '<div class="mom-meta"><span>' + esc((m.date || '').slice(0, 16).replace('T', ' ')) + '</span>' +
                (m.images && m.images.length ? '<span><svg class="ic ic-sm"><use href="#ic-image"/></svg>' + m.images.length + '</span>' : '') +
                '<button class="btn sm mom-edit"><svg class="ic ic-sm"><use href="#ic-pen"/></svg>编辑</button>' +
                '<button class="btn sm danger mom-del"><svg class="ic ic-sm"><use href="#ic-trash"/></svg>删除</button></div>' +
                    '<div>' + esc(m.text) + '</div>';
                li.querySelector('.mom-edit').addEventListener('click', function () { loadMomentToEdit(i); });
                li.querySelector('.mom-del').addEventListener('click', function () { delMoment(m.id); });
                ul.appendChild(li);
            });
            if (pendingMomentId) {
                var idx = list.findIndex(function (m) { return m.id === pendingMomentId; });
                if (idx >= 0) {
                    loadMomentToEdit(idx);
                    if (ul.children[idx]) ul.children[idx].scrollIntoView({ block: 'center' });
                }
                pendingMomentId = null;
            }
        });
    }
    function loadMomentToEdit(i) {
        var m = state.moments[i];
        if (!m) return;
        state.editingId = m.id;
        $('m-text').value = m.text || '';
        $('m-link').value = m.link || '';
        state.momImgs = (m.images || []).slice();
        renderMomImgs();
        $('btn-m-save').innerHTML = '<svg class="ic"><use href="#ic-save"/></svg>保存修改';
        $('btn-m-cancel').style.display = '';
        setStatus('正在编辑动态，发布时间保持不变');
        loadMoments();
    }
    function resetMomentForm() {
        state.editingId = null;
        $('m-text').value = '';
        $('m-link').value = '';
        state.momImgs = [];
        renderMomImgs();
        $('btn-m-save').innerHTML = '<svg class="ic"><use href="#ic-send"/></svg>发布动态';
        $('btn-m-cancel').style.display = 'none';
    }
    function delMoment(id) {
        if (!confirm('删除这条动态？关联图片也会删除。')) return;
        api('/api/moment?id=' + encodeURIComponent(id), { method: 'DELETE' }).then(function (r) {
            if (r.error) { alert(r.error); return; }
            if (state.editingId === id) resetMomentForm();
            loadMoments();
        });
    }
    function renderMomImgs() {
        var ul = $('mom-imgs');
        ul.innerHTML = '';
        state.momImgs.forEach(function (u, i) {
            var li = document.createElement('li');
            li.innerHTML = esc(u) + ' <button class="btn sm danger"><svg class="ic ic-sm"><use href="#ic-x"/></svg></button>';
            li.querySelector('button').addEventListener('click', function () { state.momImgs.splice(i, 1); renderMomImgs(); });
            ul.appendChild(li);
        });
    }
    $('btn-m-img').addEventListener('click', function () {
        openImagePicker('moment', function (url) {
            state.momImgs.push(url);
            renderMomImgs();
        });
    });
    $('m-img-file').addEventListener('change', function () {
        Array.prototype.forEach.call(this.files, function (f) {
            if (f.size > 20 * 1024 * 1024) { alert('文件超过 20MB，请使用桌面版上传'); return; }
            var reader = new FileReader();
            reader.onload = function () {
                api('/api/upload', { method: 'POST', body: JSON.stringify({ name: f.name, data: reader.result, target: 'moment' }) })
                    .then(function (r) { if (r.error) { alert(r.error); return; } state.momImgs.push(r.url); renderMomImgs(); });
            };
            reader.readAsDataURL(f);
        });
        this.value = '';
    });
    $('btn-m-save').addEventListener('click', function () {
        var text = $('m-text').value.trim();
        if (!text) { alert('动态内容不能为空'); return; }
        var payload = { text: text, images: state.momImgs, link: $('m-link').value.trim() };
        var isEdit = !!state.editingId;
        if (isEdit) payload.id = state.editingId;
        api('/api/moment', { method: 'POST', body: JSON.stringify(payload) })
            .then(function (r) {
                if (r.error) { alert(r.error); return; }
                resetMomentForm();
                loadMoments();
            setStatus(isEdit ? '动态已更新' : '动态已发布');
            });
    });
    $('btn-m-cancel').addEventListener('click', function () {
        resetMomentForm();
        loadMoments();
        setStatus('已取消编辑');
    });

    // ---- 音乐 ----
    function loadMusic() {
        api('/api/music').then(function (data) {
            state.musicFiles = data.files || [];
            state.musicPls = data.playlists || [];
            if (!state.musicPls.some(function (x) { return x.name === state.musicCur; })) {
                state.musicCur = '全部';
            }
            renderMusicPls();
            renderMusicFiles();
        });
    }
    function renderMusicPls() {
        var ul = $('music-pls-list');
        ul.innerHTML = '';
        state.musicPls.forEach(function (pl) {
            var li = document.createElement('li');
            li.className = pl.name === state.musicCur ? 'sel' : '';
            li.innerHTML = '<span>' + esc(pl.name) + ' (' + (pl.order || []).length + ')</span>';
            if (pl.name !== '全部') {
                var del = document.createElement('button');
                del.className = 'btn sm danger pl-del';
                del.innerHTML = '<svg class="ic ic-sm"><use href="#ic-trash"/></svg>';
                del.title = '删除歌单';
                del.addEventListener('click', function (e) {
                    e.stopPropagation();
                    if (confirm('删除歌单「' + pl.name + '」？歌曲文件不会删除。')) {
                        api('/api/music', { method: 'POST', body: JSON.stringify({ action: 'playlist_delete', name: pl.name }) }).then(function (r) {
                            if (r.error) { alert(r.error); return; }
                            if (state.musicCur === pl.name) state.musicCur = '全部';
                            loadMusic();
                        });
                    }
                });
                li.appendChild(del);
            }
            li.addEventListener('click', function () {
                state.musicCur = pl.name;
                renderMusicPls();
                renderMusicFiles();
            });
            ul.appendChild(li);
        });
        var sel = $('m-pls-add');
        var addBtn = $('btn-pls-add');
        if (state.musicCur === '全部') {
            sel.style.display = 'none';
            addBtn.style.display = 'none';
        } else {
            sel.style.display = '';
            addBtn.style.display = '';
            var cur = state.musicPls.filter(function (x) { return x.name === state.musicCur; })[0];
            var curOrder = (cur && cur.order) || [];
            sel.innerHTML = '<option value="">选择歌曲…</option>';
            state.musicFiles.forEach(function (f) {
                if (curOrder.indexOf(f.name) < 0) {
                    var o = document.createElement('option');
                    o.value = f.name;
                    o.textContent = f.name;
                    sel.appendChild(o);
                }
            });
        }
    }
    function fmtSize(n) {
        if (!n) return '';
        if (n > 1048576) return (n / 1048576).toFixed(1) + ' MB';
        return Math.ceil(n / 1024) + ' KB';
    }
    function renderMusicFiles() {
        var ul = $('music-items');
        ul.innerHTML = '';
        var pl = state.musicPls.filter(function (x) { return x.name === state.musicCur; })[0];
        var order = (pl && pl.order) || [];
        var isAll = state.musicCur === '全部';
        var list = order.map(function (n) {
            return state.musicFiles.filter(function (f) { return f.name === n; })[0];
        }).filter(Boolean);
        if (isAll && !list.length) list = state.musicFiles;
        if (!list.length) {
            var empty = document.createElement('li');
            empty.className = 'small';
            empty.style.cssText = 'border:none; background:none;';
            empty.textContent = isAll ? '歌单为空，点上方「上传音乐」添加' : '歌单为空，切到「全部」选择歌曲加入';
            ul.appendChild(empty);
            return;
        }
        var dragSong = null;
        list.forEach(function (f, i) {
            var li = document.createElement('li');
            li.innerHTML = '<span class="mu-grip" draggable="true" title="拖动排序"><svg class="ic ic-sm"><use href="#ic-grip"/></svg></span>' +
                '<span class="mu-idx">' + (i + 1) + '</span>' +
                '<span class="mu-name">' + esc((f.artist ? f.artist + ' - ' : '') + f.title) + '</span>' +
                '<span class="mu-size">' + fmtSize(f.size) + '</span>';
            var grip = li.querySelector('.mu-grip');
            grip.addEventListener('dragstart', function (e) {
                dragSong = f.name;
                li.classList.add('mu-dragging');
                if (e.dataTransfer) {
                    e.dataTransfer.effectAllowed = 'move';
                    e.dataTransfer.setData('text/plain', f.name);
                }
            });
            li.addEventListener('dragover', function (e) {
                if (dragSong && dragSong !== f.name) {
                    e.preventDefault();
                    li.classList.add('mu-drag-over');
                }
            });
            li.addEventListener('dragleave', function (e) {
                if (!li.contains(e.relatedTarget)) {
                    li.classList.remove('mu-drag-over');
                }
            });
            li.addEventListener('drop', function (e) {
                e.preventDefault();
                li.classList.remove('mu-drag-over');
                if (dragSong && dragSong !== f.name) {
                    moveMusicTo(dragSong, i);
                }
            });
            li.addEventListener('dragend', function () {
                li.classList.remove('mu-dragging');
                li.classList.remove('mu-drag-over');
            });
            var up = document.createElement('button');
            up.className = 'btn sm mu-btn';
            up.title = '上移';
            up.innerHTML = '<svg class="ic ic-sm"><use href="#ic-up"/></svg>';
            up.addEventListener('click', function () { moveMusic(f.name, 'up'); });
            li.appendChild(up);
            var down = document.createElement('button');
            down.className = 'btn sm mu-btn';
            down.title = '下移';
            down.innerHTML = '<svg class="ic ic-sm"><use href="#ic-down"/></svg>';
            down.addEventListener('click', function () { moveMusic(f.name, 'down'); });
            li.appendChild(down);
            if (isAll) {
                var del = document.createElement('button');
                del.className = 'btn sm danger mu-btn';
                del.title = '删除文件';
                del.innerHTML = '<svg class="ic ic-sm"><use href="#ic-trash"/></svg>';
                del.addEventListener('click', function () {
                    if (confirm('删除音乐文件「' + f.name + '」？会从所有歌单移除。')) {
                        api('/api/music?name=' + encodeURIComponent(f.name), { method: 'DELETE' }).then(function (r) {
                            if (r.error) { alert(r.error); return; }
                            loadMusic();
                        });
                    }
                });
                li.appendChild(del);
            } else {
                var rm = document.createElement('button');
                rm.className = 'btn sm danger mu-btn';
                rm.title = '移出歌单';
                rm.innerHTML = '<svg class="ic ic-sm"><use href="#ic-x"/></svg>';
                rm.addEventListener('click', function () { musicPlsOp('playlist_remove', f.name); });
                li.appendChild(rm);
            }
            ul.appendChild(li);
        });
    }
    function moveMusic(song, dir) {
        api('/api/music', { method: 'POST', body: JSON.stringify({ action: 'move', name: state.musicCur, song: song, dir: dir }) }).then(function (r) {
            if (r.error) { alert(r.error); return; }
            loadMusic();
        });
    }
    function moveMusicTo(song, to) {
        api('/api/music', { method: 'POST', body: JSON.stringify({ action: 'move_to', name: state.musicCur, song: song, to: to }) }).then(function (r) {
            if (r.error) { alert(r.error); return; }
            loadMusic();
        });
    }
    function musicPlsOp(action, song) {
        api('/api/music', { method: 'POST', body: JSON.stringify({ action: action, name: state.musicCur, song: song }) }).then(function (r) {
            if (r.error) { alert(r.error); return; }
            loadMusic();
        });
    }
    $('btn-pls-new').addEventListener('click', function () {
        var name = $('m-pls-name').value.trim();
        if (!name) { alert('请输入歌单名'); return; }
        api('/api/music', { method: 'POST', body: JSON.stringify({ action: 'playlist_create', name: name }) }).then(function (r) {
            if (r.error) { alert(r.error); return; }
            $('m-pls-name').value = '';
            loadMusic();
        });
    });
    $('btn-pls-add').addEventListener('click', function () {
        var song = $('m-pls-add').value;
        if (!song) { alert('请选择歌曲'); return; }
        musicPlsOp('playlist_add', song);
    });
    $('btn-music-up').addEventListener('click', function () { $('m-music-file').click(); });
    $('m-music-file').addEventListener('change', function () {
        var f = this.files[0];
        if (!f) return;
        if (!/\\.(mp3|m4a|ogg|flac|wav)$/i.test(f.name)) { alert('只支持音频文件'); this.value = ''; return; }
        if (f.size > 20 * 1024 * 1024) { alert('文件超过 20MB，请使用桌面版上传'); this.value = ''; return; }
        var reader = new FileReader();
        reader.onload = function () {
            api('/api/music', { method: 'POST', body: JSON.stringify({ action: 'upload', name: f.name, data: reader.result }) }).then(function (r) {
                if (r.error) { alert(r.error); return; }
                loadMusic();
                setStatus('已上传 ' + f.name + '，重新构建后出现在播放器');
            });
        };
        reader.readAsDataURL(f);
        this.value = '';
    });

    // ---- 下载文件 ----
    function loadDownloads() {
        api('/api/files').then(function (data) {
            state.cats = data.categories || [];
            var sel = $('dl-cat');
            var cur = sel.value;
            sel.innerHTML = '';
            if (!state.cats.length) {
                var o = document.createElement('option');
                o.value = '';
                o.textContent = '（暂无分类，请先新建）';
                sel.appendChild(o);
            }
            state.cats.forEach(function (c) {
                var o = document.createElement('option');
                o.value = c.name;
                o.textContent = c.name + '（' + c.files.length + ' 个文件）';
                sel.appendChild(o);
            });
            if (cur && state.cats.some(function (c) { return c.name === cur; })) sel.value = cur;
            renderDlItems();
        });
    }
    function renderDlItems() {
        var ul = $('dl-items');
        ul.innerHTML = '';
        var cat = $('dl-cat').value;
        var c = state.cats.filter(function (x) { return x.name === cat; })[0];
        if (!c) return;
        c.files.forEach(function (f) {
            var li = document.createElement('li');
              li.innerHTML = '<span class="dl-name"><svg class="ic ic-sm"><use href="#ic-doc"/></svg>' + esc(f.name) + '</span>' +
                  '<span class="dl-size">' + esc(f.sizeText) + '</span>' +
                  '<button class="btn sm">外链</button>' +
                  '<button class="btn sm danger">删除</button>';
              li.querySelectorAll('button')[0].addEventListener('click', function () {
                  var url = prompt('外链 URL（网盘/对象存储直链，留空清除）：');
                  if (url === null) return;
                  api('/api/files', { method: 'POST', body: JSON.stringify({
                      action: 'external', cat: cat, name: f.name, url: url.trim()
                  }) }).then(function (r) {
                      if (r.error) { alert(r.error); return; }
                      loadDownloads();
                      setStatus('外链已更新：' + cat + '/' + f.name);
                  });
              });
              li.querySelectorAll('button')[1].addEventListener('click', function () { delDlFile(cat, f.name); });
              ul.appendChild(li);
        });
    }
    function delDlFile(cat, name) {
        if (!confirm('删除文件？\\n' + cat + '/' + name + '\\n（删除后不可恢复）')) return;
        api('/api/files?cat=' + encodeURIComponent(cat) + '&name=' + encodeURIComponent(name),
            { method: 'DELETE' })
            .then(function (r) {
                if (r.error) { alert(r.error); return; }
                loadDownloads();
                setStatus('已删除 ' + cat + '/' + name);
            });
    }
    $('dl-cat').addEventListener('change', renderDlItems);
    $('btn-dl-upload').addEventListener('click', function () { $('dl-file').click(); });
    $('dl-file').addEventListener('change', function () {
        var cat = $('dl-cat').value;
        if (!cat) { alert('请先新建/选择分类'); this.value = ''; return; }
        var files = Array.prototype.slice.call(this.files);
        var done = 0;
        files.forEach(function (f) {
            if (f.size > 20 * 1024 * 1024) { alert('文件超过 20MB，请使用桌面版上传'); return; }
            var reader = new FileReader();
            reader.onload = function () {
                api('/api/files', { method: 'POST', body: JSON.stringify({
                    action: 'upload', cat: cat, name: f.name, data: reader.result
                }) })
                      .then(function (r) {
                          if (r.error) { alert(r.error); }
                          done++;
                          if (done === files.length) {
                              loadDownloads();
                              setStatus('已上传 ' + done + '/' + files.length + ' 个文件，重新构建后生效');
                          }
                      });
            };
            reader.readAsDataURL(f);
        });
        this.value = '';
    });
    $('btn-dl-newcat').addEventListener('click', function () {
        var name = prompt('输入分类名（字母/数字/-/_，将作为文件夹名）：');
        if (!name) return;
        api('/api/files', { method: 'POST', body: JSON.stringify({ action: 'mkdir', name: name.trim() }) })
            .then(function (r) {
                if (r.error) { alert(r.error); return; }
                loadDownloads();
                setStatus('已创建分类 ' + name.trim());
            });
    });
    $('btn-dl-rencat').addEventListener('click', function () {
        var cat = $('dl-cat').value;
        if (!cat) { alert('请先选择分类'); return; }
        var name = prompt('新的分类名（字母/数字/-/_）：', cat);
        if (!name || name.trim() === cat) return;
        api('/api/files', { method: 'POST', body: JSON.stringify({ action: 'rename', cat: cat, name: name.trim() }) })
            .then(function (r) {
                if (r.error) { alert(r.error); return; }
                loadDownloads();
                setStatus('已重命名 ' + cat + ' -> ' + name.trim());
            });
    });

    // ---- 迷你 Markdown 渲染（仅预览用） ----
    function mdEscape(s) { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
    function mdInline(s) {
        s = mdEscape(s);
        s = s.replace(/!\\[([^\\]]*)\\]\\(([^)]+)\\)/g, '<img src="$2" alt="$1">');
        s = s.replace(/\\[([^\\]]+)\\]\\(([^)]+)\\)/g, '<a href="$2" target="_blank">$1</a>');
        s = s.replace(/\\*\\*([^*]+)\\*\\*/g, '<b>$1</b>');
        s = s.replace(/\\*([^*]+)\\*/g, '<i>$1</i>');
        s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
        return s;
    }
    function mdRender(src) {
        var out = [], code = false, block = [], buf = [];
        function flush() {
            if (buf.length) { out.push('<p>' + buf.join('<br>') + '</p>'); buf = []; }
        }
        src.split('\\n').forEach(function (line) {
            var s = line.trim();
            if (s.indexOf('```') === 0) {
                flush();
                if (code) { out.push('<pre>' + mdEscape(block.join('\\n')) + '</pre>'); }
                block = [];
                code = !code;
                return;
            }
            if (code) { block.push(line); return; }
            if (!s) { flush(); return; }
            var h = s.match(/^(#{1,3})\\s/);
            if (h) { flush(); var n = h[1].length; out.push('<h' + n + '>' + mdInline(s.slice(n + 1)) + '</h' + n + '>'); return; }
            if (s.indexOf('> ') === 0) { buf.push('<blockquote>' + mdInline(s.slice(2)) + '</blockquote>'); return; }
            if (/^[-*]\\s/.test(s)) { buf.push('• ' + mdInline(s.slice(2))); return; }
            buf.push(mdInline(s));
        });
        if (code) { out.push('<pre>' + mdEscape(block.join('\\n')) + '</pre>'); }
        flush();
        return out.join('\\n');
    }

    // ---- 初始化 ----
    loadArticles();
    loadMoments();
    loadDownloads();
    loadMusic();
    loadAiState();
    var q = new URLSearchParams(location.search);
    if (q.get('new') === '1') { newArticle(); showTab('articles'); }
    else if (q.get('file')) { loadArticle(q.get('file')); showTab('articles'); }
    else if (q.get('tab') === 'ai') { showTab('ai'); }
    else if (q.get('tab') === 'music') { showTab('music'); }
    else if (q.get('tab') === 'moments' || q.get('id')) { showTab('moments'); }
    else if (q.get('tab') === 'downloads') { showTab('downloads'); }
    if (q.get('id')) pendingMomentId = q.get('id');
})();
</script>
</body>
</html>
"""


def _safe_join(base, rel):
    """把相对路径安全拼到 base 下，越界返回 None"""
    base = os.path.normpath(base)
    full = os.path.normpath(os.path.join(base, rel))
    if os.path.commonpath([base, full]) != base:
        return None
    return full


_COMFY_PROCESS = None
_COMFY_PROCESS_LOCK = threading.Lock()


def _comfy_http_json(method, path, data=None, timeout=5):
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(
        COMFY_API_URL + path, data=body, method=method,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _comfy_running():
    try:
        with urllib.request.urlopen(COMFY_API_URL + "/system_stats", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def _comfy_start():
    global _COMFY_PROCESS
    with _COMFY_PROCESS_LOCK:
        if _comfy_running():
            return {"started": False}
        if _COMFY_PROCESS is not None and _COMFY_PROCESS.poll() is None:
            return {"started": False}
        if not os.path.isfile(COMFY_PYTHON) or not os.path.isfile(os.path.join(COMFY_ROOT, "main.py")):
            raise OSError("ComfyUI 路径不存在，请检查配置")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        _COMFY_PROCESS = subprocess.Popen(
            [COMFY_PYTHON, "-s", "main.py", "--port", str(COMFY_PORT),
             "--disable-auto-launch", "--dont-print-server"],
            cwd=COMFY_ROOT, creationflags=flags,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"started": True}


def _comfy_models():
    try:
        info = _comfy_http_json("GET", "/object_info/CheckpointLoaderSimple", timeout=5)
        raw = info.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name")
        if isinstance(raw, list) and raw and isinstance(raw[0], list):
            return [str(x) for x in raw[0]]
    except Exception:
        pass
    return []


def _build_comfy_workflow(p):
    model = (p.get("model") or "").strip()
    prompt = (p.get("prompt") or "").strip()
    negative = (p.get("negative") or "").strip() or AI_DEFAULT_NEGATIVE
    if not model or not prompt:
        raise ValueError("模型和提示词不能为空")
    try:
        width = max(256, min(2048, int(p.get("width") or 1024)))
        height = max(256, min(2048, int(p.get("height") or 1024)))
        width = max(64, round(width / 8) * 8)
        height = max(64, round(height / 8) * 8)
        steps = max(1, min(100, int(p.get("steps") or 20)))
        cfg = max(1.0, min(30.0, float(p.get("cfg") or 7)))
        seed = int(p.get("seed") or 0)
    except (TypeError, ValueError):
        raise ValueError("生成参数无效")
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": model}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {
            "width": width, "height": height, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0],
            "latent_image": ["4", 0], "seed": seed, "steps": steps,
            "cfg": cfg, "sampler_name": "euler", "scheduler": "normal", "denoise": 1}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "blog_ai"}},
    }


def _comfy_generate(p):
    if not _comfy_running():
        raise OSError("ComfyUI 未运行，请先在 AI 图库页启动")
    workflow = _build_comfy_workflow(p)
    resp = _comfy_http_json("POST", "/prompt", {
        "prompt": workflow, "client_id": "blog-tool"}, timeout=10)
    pid = resp.get("prompt_id")
    if not pid:
        raise OSError(str(resp.get("error") or resp.get("node_errors") or resp)[:500])
    return pid


def _recv_exact(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            return None
        data += chunk
    return data


def _comfy_ws_progress(prompt_id, timeout=1.0):
    try:
        s = socket.create_connection((COMFY_HOST, COMFY_PORT), timeout=timeout)
    except OSError:
        return None
    try:
        s.settimeout(timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            "GET /ws?clientId=blog-tool HTTP/1.1\r\n"
            "Host: {}:{}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: {}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ).format(COMFY_HOST, COMFY_PORT, key)
        s.sendall(req.encode("ascii"))
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = s.recv(4096)
            if not chunk:
                return None
            head += chunk
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            return None
        deadline = time.time() + timeout
        while time.time() < deadline:
            hdr = _recv_exact(s, 2)
            if hdr is None:
                return None
            opcode = hdr[0] & 0x0f
            length = hdr[1] & 0x7f
            if length == 126:
                ext = _recv_exact(s, 2)
                if ext is None:
                    return None
                length = int.from_bytes(ext, "big")
            elif length == 127:
                ext = _recv_exact(s, 8)
                if ext is None:
                    return None
                length = int.from_bytes(ext, "big")
            if hdr[1] & 0x80:
                mask = _recv_exact(s, 4)
                if mask is None:
                    return None
            payload = b""
            while len(payload) < length:
                chunk = s.recv(min(65536, length - len(payload)))
                if not chunk:
                    return None
                payload += chunk
            if opcode == 1:
                try:
                    msg = json.loads(payload.decode("utf-8", "replace"))
                except Exception:
                    continue
                if msg.get("type") == "progress":
                    data = msg.get("data") or {}
                    if data.get("prompt_id") == prompt_id:
                        return (data.get("value") or 0, data.get("max") or 0)
                elif msg.get("type") == "executing":
                    data = msg.get("data") or {}
                    if data.get("prompt_id") == prompt_id and data.get("node") is None:
                        return None
                elif msg.get("type") == "execution_error":
                    data = msg.get("data") or {}
                    if data.get("prompt_id") == prompt_id:
                        return None
            elif opcode == 8:
                return None
    finally:
        s.close()
    return None


def _comfy_history_images(history):
    out = []
    for node_id, node_output in (history.get("outputs") or {}).items():
        for im in (node_output.get("images") or []):
            if im.get("filename"):
                out.append({
                    "filename": im["filename"],
                    "subfolder": im.get("subfolder", ""),
                    "type": im.get("type", "output"),
                })
    return out


def _comfy_task_status(prompt_id):
    try:
        history = _comfy_http_json(
            "GET", "/history/" + urllib.parse.quote(prompt_id, safe=""), timeout=5)
        if prompt_id in history:
            h = history[prompt_id]
            status = h.get("status") or {}
            images = _comfy_history_images(h)
            if status.get("status_str") == "error":
                return {"status": "error", "message": "ComfyUI 生成失败", "images": images}
            if status.get("completed") or images:
                return {"status": "done", "images": images}
            return {"status": "running"}
    except Exception:
        pass
    try:
        queue = _comfy_http_json("GET", "/queue", timeout=5)
    except Exception:
        return {"status": "not_found"}
    for item in queue.get("queue_pending", []):
        if len(item) > 1 and item[1] == prompt_id:
            return {"status": "queued"}
    for item in queue.get("queue_running", []):
        if len(item) > 1 and item[1] == prompt_id:
            progress = _comfy_ws_progress(prompt_id, timeout=1.0)
            return {
                "status": "running",
                "value": progress[0] if progress else 0,
                "max": progress[1] if progress else 0,
            }
    return {"status": "not_found"}


def _safe_comfy_path(name, subfolder=""):
    name = os.path.basename(name or "")
    if not name or ".." in name:
        return None
    subfolder = (subfolder or "").replace("\\", "/").strip("/")
    if not subfolder:
        base = COMFY_OUTPUT_DIR
    elif ".." in subfolder.split("/") or os.path.isabs(subfolder):
        return None
    else:
        base = os.path.join(COMFY_OUTPUT_DIR, subfolder)
    base = os.path.normpath(base)
    full = _safe_join(base, name)
    if full and os.path.isfile(full) and os.path.splitext(name)[1].lower() in COMFY_IMAGE_EXTS:
        return full
    return None


def _comfy_list_images(limit=100):
    out = []
    if not os.path.isdir(COMFY_OUTPUT_DIR):
        return out
    for name in sorted(os.listdir(COMFY_OUTPUT_DIR)):
        full = os.path.join(COMFY_OUTPUT_DIR, name)
        if not os.path.isfile(full) or os.path.splitext(name)[1].lower() not in COMFY_IMAGE_EXTS:
            continue
        st = os.stat(full)
        out.append({"name": name, "size": st.st_size, "mtime": st.st_mtime})
    out.sort(key=lambda x: x["mtime"], reverse=True)
    return out[:limit]


def _comfy_image_bytes(name, subfolder="", thumb=False):
    full = _safe_comfy_path(name, subfolder)
    if not full:
        return None, None
    if not thumb:
        with open(full, "rb") as f:
            return f.read(), mimetypes.guess_type(full)[0] or "image/png"
    with Image.open(full) as img:
        img.thumbnail((480, 480))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=82, optimize=True)
        return buf.getvalue(), "image/jpeg"


def _unique_blog_path(dest_dir, stem, ext):
    i = 0
    while True:
        name = stem + (("-" + str(i)) if i else "") + ext
        full = os.path.join(dest_dir, name)
        if not os.path.exists(full):
            return full
        i += 1


def _optimize_blog_image(src):
    with open(src, "rb") as f:
        orig = f.read()
    with Image.open(src) as img:
        img.load()
        has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
        if has_alpha:
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            buf = io.BytesIO()
            img.save(buf, "PNG", optimize=True)
            data, ext = buf.getvalue(), ".png"
        else:
            rgb = img.convert("RGB")
            buf = io.BytesIO()
            rgb.save(buf, "JPEG", quality=85, optimize=True, progressive=True)
            data, ext = buf.getvalue(), ".jpg"
    if len(data) >= len(orig):
        return orig, os.path.splitext(src)[1].lower() or ext
    return data, ext


def _import_comfy_image(name, target):
    src = _safe_comfy_path(name)
    if not src:
        raise ValueError("ComfyUI 图片不存在")
    dest_dir = MOMENTS_IMAGES_DIR if target == "moment" else IMAGES_DIR
    os.makedirs(dest_dir, exist_ok=True)
    data, ext = _optimize_blog_image(src)
    stem = datetime.datetime.now().strftime("%Y%m%d%H%M%S") + "-" + os.path.splitext(os.path.basename(name))[0]
    dest = _unique_blog_path(dest_dir, stem, ext)
    with open(dest, "wb") as f:
        f.write(data)
    return "/images/" + os.path.relpath(dest, IMAGES_DIR).replace("\\", "/")


class BlogWebHandler(BaseHTTPRequestHandler):
    server_version = "BlogToolWeb/1.0"

    def log_message(self, fmt, *args):
        pass

    def _reply(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, code=200):
        self._reply(code, json.dumps(obj, ensure_ascii=False))

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _content_file(self, rel):
        """content 目录下的文件绝对路径；非法路径返回 None"""
        rel = (rel or "").replace("\\", "/")
        if not rel or ".." in rel.split("/"):
            return None
        if rel.startswith("content/"):
            rel = rel[len("content/"):]
        return _safe_join(os.path.join(BLOG_ROOT, "content"), rel)

    def _serve_static(self, url_path):
        """把 /images/、/files/ 等路径映射到博客 static/ 目录，供网页版预览显示图片"""
        rel = url_path.lstrip("/")
        full = _safe_join(os.path.join(BLOG_ROOT, "static"), rel)
        if full and os.path.isfile(full):
            ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
            try:
                with open(full, "rb") as f:
                    data = f.read()
            except OSError as e:
                self._json({"error": str(e)}, 500)
                return
            self._reply(200, data, ctype)
        else:
            self._json({"error": "not found"}, 404)

    def _get_comfy_image(self, qs):
        name = qs.get("name", [""])[0]
        sub = qs.get("subfolder", [""])[0]
        thumb = qs.get("thumb", ["0"])[0] in ("1", "true", "True")
        data, ctype = _comfy_image_bytes(name, sub, thumb)
        if data is None:
            self._json({"error": "not found"}, 404)
            return
        self._reply(200, data, ctype)

    def _post_comfy_import(self, p):
        target = p.get("target") or "post"
        if target not in ("post", "moment"):
            target = "post"
        try:
            url = _import_comfy_image(p.get("name") or "", target)
        except Exception as e:
            self._json({"error": str(e)}, 400)
            return
        self._json({"ok": True, "url": url})

    def _post_comfy_generate(self, p):
        try:
            pid = _comfy_generate(p)
        except Exception as e:
            code = 503 if "未运行" in str(e) else 400
            self._json({"error": str(e)}, code)
            return
        self._json({"ok": True, "prompt_id": pid})

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        try:
            if parsed.path == "/":
                self._reply(200, WEB_UI_HTML, "text/html; charset=utf-8")
            elif parsed.path.startswith(("/images/", "/files/")):
                self._serve_static(parsed.path)
            elif parsed.path == "/comfy-image":
                self._get_comfy_image(qs)
            elif parsed.path == "/api/ping":
                self._json({"ok": True})
            elif parsed.path == "/api/comfy/state":
                running = _comfy_running()
                self._json({
                    "running": running,
                    "models": _comfy_models() if running else [],
                })
            elif parsed.path == "/api/comfy/models":
                self._json({"models": _comfy_models()})
            elif parsed.path == "/api/comfy/images":
                self._json({"images": _comfy_list_images()})
            elif parsed.path == "/api/comfy/task":
                pid = qs.get("prompt_id", [""])[0]
                if not pid:
                    self._json({"error": "缺少 prompt_id"}, 400)
                    return
                self._json(_comfy_task_status(pid))
            elif parsed.path == "/api/articles":
                items = []
                for rel, full in scan_posts():
                    try:
                        with open(full, encoding="utf-8") as f:
                            data = parse_front(f.read())
                    except OSError:
                        continue
                    items.append({
                        "file": "content/posts/" + rel.replace("\\", "/"),
                        "title": data["title"] or os.path.splitext(os.path.basename(full))[0],
                        "date": (data["date"] or "")[:10],
                        "draft": data["draft"],
                        "categories": data["categories"],
                    })
                items.sort(key=lambda x: x["date"], reverse=True)
                self._json(items)
            elif parsed.path == "/api/article":
                full = self._content_file(qs.get("file", [""])[0])
                if not full or not os.path.isfile(full):
                    self._json({"error": "文件不存在"}, 404)
                    return
                with open(full, encoding="utf-8") as f:
                    content = f.read()
                data = parse_front(content)
                m = re.match(r"^---\s*\n.*?\n---\s*\n", content, re.DOTALL)
                data["body"] = content[m.end():].strip() if m else content.strip()
                data["file"] = os.path.relpath(full, os.path.join(BLOG_ROOT, "content")).replace("\\", "/")
                self._json(data)
            elif parsed.path == "/api/moments":
                self._json(sorted(load_moments(), key=lambda e: e.get("date", ""), reverse=True))
            elif parsed.path == "/api/files":
                self._json(self._list_files())
            elif parsed.path == "/api/music":
                music_data = load_music_data()
                normalize_music_all(music_data)
                files = []
                for f in scan_music_files():
                    artist, title = parse_music_name(f)
                    size = 0
                    try:
                        size = os.path.getsize(os.path.join(MUSIC_DIR, f))
                    except OSError:
                        pass
                    files.append({"name": f, "artist": artist, "title": title or f, "size": size})
                self._json({"files": files, "playlists": music_data["playlists"]})
            else:
                self._json({"error": "not found"}, 404)
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        try:
            payload = self._read_json()
        except Exception:
            self._json({"error": "请求体不是合法 JSON"}, 400)
            return
        try:
            if parsed.path == "/api/article":
                self._post_article(payload)
            elif parsed.path == "/api/moment":
                self._post_moment(payload)
            elif parsed.path == "/api/upload":
                self._post_upload(payload)
            elif parsed.path == "/api/comfy/start":
                self._json(_comfy_start())
            elif parsed.path == "/api/comfy/import":
                self._post_comfy_import(payload)
            elif parsed.path == "/api/comfy/generate":
                self._post_comfy_generate(payload)
            elif parsed.path == "/api/files":
                self._post_files(payload)
            elif parsed.path == "/api/music":
                self._post_music(payload)
            else:
                self._json({"error": "not found"}, 404)
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def _post_article(self, p):
        title = (p.get("title") or "").strip()
        if not title:
            self._json({"error": "标题不能为空"}, 400)
            return
        date = (p.get("date") or "").strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}\+08:00)?$", date):
            self._json({"error": "日期格式应为 2026-06-06 或 2026-06-06T21:24:37+08:00"}, 400)
            return
        if re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            date += "T00:00:00+08:00"
        rel = (p.get("file") or "").strip()
        full = self._content_file(rel) if rel else None
        if rel and (not full or os.path.isdir(full)):
            self._json({"error": "非法文件路径"}, 400)
            return
        body = (p.get("body") or "").rstrip()
        saved = save_article_file(full, title, date, p.get("categories") or [],
                                  p.get("tags") or [], bool(p.get("draft")),
                                  (p.get("cover") or "").strip() or None, body)
        rel_saved = os.path.relpath(saved, POSTS_BASE).replace("\\", "/")
        self._json({"ok": True, "file": "content/posts/" + rel_saved})

    def _post_moment(self, p):
        text = (p.get("text") or "").strip()
        if not text:
            self._json({"error": "动态内容不能为空"}, 400)
            return
        images = [u for u in (p.get("images") or [])
                  if isinstance(u, str) and u.startswith("/images/moments/")]
        link = (p.get("link") or "").strip()
        entries = load_moments()
        eid = (p.get("id") or "").strip()
        if eid:
            entry = next((e for e in entries if e.get("id") == eid), None)
            if entry is None:
                self._json({"error": "动态不存在"}, 404)
                return
            for url in entry.get("images", []):
                if url not in images:
                    self._remove_moment_image(url)
            entry["text"] = text
            if images:
                entry["images"] = images
            else:
                entry.pop("images", None)
            if link:
                entry["link"] = link
            else:
                entry.pop("link", None)
            save_moments(entries)
            self._json({"ok": True, "id": eid})
        else:
            entry = {
                "id": "m{}{}".format(datetime.datetime.now().strftime("%Y%m%d%H%M%S"), len(entries)),
                "date": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
                "text": text,
            }
            if images:
                entry["images"] = images
            if link:
                entry["link"] = link
            entries.insert(0, entry)
            save_moments(entries)
            self._json({"ok": True, "id": entry["id"]})

    def _remove_moment_image(self, url):
        """删除一条动态图片文件（只在 URL 属于动态图片目录时）"""
        rel = url.replace("/images/moments/", "", 1) if url.startswith("/images/moments/") \
            else os.path.basename(url)
        if ".." in rel or not rel:
            return
        img_path = os.path.join(MOMENTS_IMAGES_DIR, rel)
        if os.path.isfile(img_path):
            try:
                os.remove(img_path)
            except OSError:
                pass

    def _post_upload(self, p):
        raw = p.get("data") or ""
        try:
            blob = base64.b64decode(raw.split(",", 1)[-1])
        except Exception:
            self._json({"error": "图片数据无效"}, 400)
            return
        if not blob:
            self._json({"error": "图片数据为空"}, 400)
            return
        if len(blob) > WEB_UPLOAD_MAX_MB * 1024 * 1024:
            self._json({"error": f"文件超过 {WEB_UPLOAD_MAX_MB}MB，请使用桌面版上传"}, 400)
            return
        name = os.path.basename(p.get("name") or "upload.png")
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)
        sub = "moments" if p.get("target") == "moment" else ""
        dest_dir = os.path.join(IMAGES_DIR, sub)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, "{}-{}".format(
            datetime.datetime.now().strftime("%Y%m%d%H%M%S"), safe))
        with open(dest, "wb") as f:
            f.write(blob)
        url = "/images/" + (sub + "/" if sub else "") + os.path.basename(dest)
        self._json({"ok": True, "url": url})

    def _files_dir(self, cat):
        """校验分类名并返回 static/files 下的目录，非法返回 None"""
        cat = (cat or "").strip()
        if not cat or "/" in cat or "\\" in cat or ".." in cat or cat in (".", ".."):
            return None
        return os.path.join(FILES_DIR, cat)

    def _list_files(self):
        """扫描 static/files，返回分类及文件列表"""
        cats = []
        if os.path.isdir(FILES_DIR):
            for name in sorted(os.listdir(FILES_DIR)):
                cat_dir = os.path.join(FILES_DIR, name)
                if not os.path.isdir(cat_dir):
                    continue
                files = []
                for fname in sorted(os.listdir(cat_dir)):
                    full = os.path.join(cat_dir, fname)
                    if os.path.isfile(full):
                        files.append({"name": fname, "size": os.path.getsize(full),
                                      "sizeText": fmt_size(os.path.getsize(full))})
                cats.append({"name": name, "files": files})
        return {"categories": cats}

    def _post_files(self, p):
        action = p.get("action")
        if action == "mkdir":
            name = (p.get("name") or "").strip()
            if not re.match(r"^[A-Za-z0-9_-]+$", name):
                self._json({"error": "分类名只能包含字母、数字、- 和 _"}, 400)
                return
            os.makedirs(os.path.join(FILES_DIR, name), exist_ok=True)
            self._json({"ok": True, "name": name})
        elif action == "upload":
            cat_dir = self._files_dir(p.get("cat"))
            if not cat_dir:
                self._json({"error": "非法分类名"}, 400)
                return
            raw = p.get("data") or ""
            try:
                blob = base64.b64decode(raw.split(",", 1)[-1])
            except Exception:
                self._json({"error": "文件数据无效"}, 400)
                return
            if not blob:
                self._json({"error": "文件数据为空"}, 400)
                return
            if len(blob) > WEB_UPLOAD_MAX_MB * 1024 * 1024:
                self._json({"error": f"文件超过 {WEB_UPLOAD_MAX_MB}MB，请使用桌面版上传"}, 400)
                return
            name = os.path.basename(p.get("name") or "file.bin")
            safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)
            os.makedirs(cat_dir, exist_ok=True)
            with open(os.path.join(cat_dir, safe), "wb") as f:
                f.write(blob)
            self._json({"ok": True, "name": safe})
        elif action == "rename":
            cat_dir = self._files_dir(p.get("cat"))
            name = (p.get("name") or "").strip()
            if not cat_dir or not re.match(r"^[A-Za-z0-9_-]+$", name):
                self._json({"error": "非法分类名"}, 400)
                return
            new_dir = os.path.join(FILES_DIR, name)
            if os.path.exists(new_dir):
                self._json({"error": f"分类 {name} 已存在"}, 400)
                return
            try:
                os.rename(cat_dir, new_dir)
            except OSError as e:
                self._json({"error": str(e)}, 500)
                return
            self._json({"ok": True, "name": name})
        elif action == "external":
            cat_dir = self._files_dir(p.get("cat"))
            fname = os.path.basename(p.get("name") or "")
            if not cat_dir or not fname or not os.path.isfile(os.path.join(cat_dir, fname)):
                self._json({"error": "文件不存在"}, 404)
                return
            key = f"{p.get('cat')}/{fname}"
            cfg_file = os.path.join(BLOG_ROOT, "data", "downloads.json")
            cfg = {}
            try:
                with open(cfg_file, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            except (OSError, ValueError):
                cfg = {}
            if not isinstance(cfg, dict) or not isinstance(cfg.get("files"), dict):
                cfg = {"files": {}}
            url = (p.get("url") or "").strip()
            if url:
                cfg["files"][key] = url
            else:
                cfg["files"].pop(key, None)
            os.makedirs(os.path.dirname(cfg_file), exist_ok=True)
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            self._json({"ok": True})
        else:
            self._json({"error": "未知操作"}, 400)

    def _post_music(self, p):
        action = p.get("action")
        if action == "upload":
            name = os.path.basename((p.get("name") or "").strip())
            if not name.lower().endswith(MUSIC_EXTS):
                self._json({"error": "只支持 mp3 / m4a / ogg / flac / wav"}, 400)
                return
            if not re.match(r"^[^\\/:*?\"<>|]+$", name):
                self._json({"error": "文件名包含非法字符"}, 400)
                return
            raw = p.get("data") or ""
            try:
                blob = base64.b64decode(raw.split(",", 1)[-1])
            except Exception:
                self._json({"error": "音频数据无效"}, 400)
                return
            if not blob:
                self._json({"error": "音频数据为空"}, 400)
                return
            if len(blob) > WEB_UPLOAD_MAX_MB * 1024 * 1024:
                self._json({"error": f"文件超过 {WEB_UPLOAD_MAX_MB}MB，请使用桌面版上传"}, 400)
                return
            os.makedirs(MUSIC_DIR, exist_ok=True)
            dest = os.path.join(MUSIC_DIR, name)
            if os.path.exists(dest):
                self._json({"error": "同名文件已存在"}, 400)
                return
            with open(dest, "wb") as f:
                f.write(blob)
            data = load_music_data()
            for pl in data["playlists"]:
                if pl.get("name") == "全部":
                    if name not in pl["order"]:
                        pl["order"].append(name)
                    break
            save_music_data(data)
            self._json({"ok": True})
        elif action == "playlist_create":
            name = (p.get("name") or "").strip()
            if not name or name == "全部":
                self._json({"error": "歌单名不能为空且不能叫\"全部\""}, 400)
                return
            data = load_music_data()
            if any(pl.get("name") == name for pl in data["playlists"]):
                self._json({"error": "歌单已存在"}, 400)
                return
            data["playlists"].append({"name": name, "order": []})
            save_music_data(data)
            self._json({"ok": True})
        elif action == "playlist_delete":
            name = (p.get("name") or "").strip()
            data = load_music_data()
            data["playlists"] = [pl for pl in data["playlists"] if pl.get("name") != name]
            if not any(pl.get("name") == "全部" for pl in data["playlists"]):
                data["playlists"].insert(0, {"name": "全部", "order": []})
            save_music_data(data)
            self._json({"ok": True})
        elif action == "playlist_add":
            name = (p.get("name") or "").strip()
            song = (p.get("song") or "").strip()
            data = load_music_data()
            pl = next((x for x in data["playlists"] if x.get("name") == name), None)
            if pl is None:
                self._json({"error": "歌单不存在"}, 404)
                return
            if song and song not in pl["order"]:
                pl["order"].append(song)
            save_music_data(data)
            self._json({"ok": True})
        elif action == "playlist_remove":
            name = (p.get("name") or "").strip()
            song = (p.get("song") or "").strip()
            data = load_music_data()
            pl = next((x for x in data["playlists"] if x.get("name") == name), None)
            if pl is None:
                self._json({"error": "歌单不存在"}, 404)
                return
            if song in pl["order"]:
                pl["order"].remove(song)
            save_music_data(data)
            self._json({"ok": True})
        elif action == "move":
            name = (p.get("name") or "").strip()
            song = (p.get("song") or "").strip()
            d = p.get("dir")
            data = load_music_data()
            pl = next((x for x in data["playlists"] if x.get("name") == name), None)
            if pl is None:
                self._json({"error": "歌单不存在"}, 404)
                return
            normalize_music_all(data)
            order = pl["order"]
            try:
                i = order.index(song)
            except ValueError:
                self._json({"error": "歌曲不在歌单中"}, 400)
                return
            j = i - 1 if d == "up" else i + 1
            if 0 <= j < len(order):
                order[i], order[j] = order[j], order[i]
            save_music_data(data)
            self._json({"ok": True})
        elif action == "move_to":
            name = (p.get("name") or "").strip()
            song = (p.get("song") or "").strip()
            data = load_music_data()
            pl = next((x for x in data["playlists"] if x.get("name") == name), None)
            if pl is None:
                self._json({"error": "歌单不存在"}, 404)
                return
            normalize_music_all(data)
            order = pl["order"]
            try:
                i = order.index(song)
            except ValueError:
                self._json({"error": "歌曲不在歌单中"}, 400)
                return
            try:
                to = int(p.get("to"))
            except (TypeError, ValueError):
                self._json({"error": "目标位置无效"}, 400)
                return
            if not 0 <= to < len(order):
                self._json({"error": "目标位置无效"}, 400)
                return
            order.insert(to, order.pop(i))
            save_music_data(data)
            self._json({"ok": True})
        else:
            self._json({"error": "未知操作"}, 400)

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        try:
            if parsed.path == "/api/article":
                full = self._content_file(qs.get("file", [""])[0])
                posts_base = os.path.join(BLOG_ROOT, "content", "posts")
                if not full or not os.path.isfile(full) or \
                        os.path.commonpath([posts_base, full]) != os.path.normpath(posts_base):
                    self._json({"error": "非法文件路径"}, 400)
                    return
                os.remove(full)
                self._json({"ok": True})
            elif parsed.path == "/api/moment":
                eid = qs.get("id", [""])[0]
                entries = load_moments()
                target = next((e for e in entries if e.get("id") == eid), None)
                if target is None:
                    self._json({"error": "动态不存在"}, 404)
                    return
                entries = [e for e in entries if e.get("id") != eid]
                for url in target.get("images", []):
                    self._remove_moment_image(url)
                save_moments(entries)
                self._json({"ok": True})
            elif parsed.path == "/api/files":
                cat_dir = self._files_dir(qs.get("cat", [""])[0])
                name = os.path.basename(qs.get("name", [""])[0])
                full = os.path.join(cat_dir, name) if cat_dir else None
                if not full or not os.path.isfile(full) or \
                        os.path.dirname(full) != os.path.normpath(cat_dir):
                    self._json({"error": "非法文件路径"}, 400)
                    return
                os.remove(full)
                self._json({"ok": True})
            elif parsed.path == "/api/music":
                name = os.path.basename(qs.get("name", [""])[0])
                full = os.path.join(MUSIC_DIR, name)
                if not name or not os.path.isfile(full):
                    self._json({"error": "文件不存在"}, 404)
                    return
                os.remove(full)
                data = load_music_data()
                for pl in data["playlists"]:
                    if name in pl.get("order", []):
                        pl["order"].remove(name)
                save_music_data(data)
                self._json({"ok": True})
            else:
                self._json({"error": "not found"}, 404)
        except Exception as e:
            self._json({"error": str(e)}, 500)


def _parse_web_params(raw_url):
    """解析 blogtool://edit?file=xxx 形式的外部调用参数，失败返回 None"""
    try:
        parts = urllib.parse.urlparse(raw_url or "")
        qs = urllib.parse.parse_qs(parts.query)
        params = {k: v[0] for k, v in qs.items()}
        if parts.netloc == "new":
            params["new"] = "1"
        return params
    except Exception:
        return None


def _safe_print(*args):
    """控制台可能不存在（pythonw）或编码不支持特殊字符，输出失败时静默"""
    try:
        print(*args)
    except Exception:
        pass


def _port_in_use(host, port):
    """探测本地端口是否已有服务在监听"""
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def run_web_server(host="127.0.0.1", port=WEB_PORT, web_params=None):
    """启动本地网页版写作工具（仅本机可访问）；已运行时只跳转不重复启动"""
    os.makedirs(POSTS_BASE, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    target = f"http://{host}:{port}/"
    if web_params:
        target += "?" + urllib.parse.urlencode(web_params)
    if _port_in_use(host, port):
        webbrowser.open(target)  # 工具已在运行，直接跳到目标页
        return
    try:
        server = ThreadingHTTPServer((host, port), BlogWebHandler)
    except OSError as e:
        _safe_print(f"启动失败：{e}")
        return
    _safe_print(f"博客写作助手网页版已启动：{target}")
    _safe_print("按 Ctrl+C 停止服务。")
    webbrowser.open(target)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main():
    if not os.path.isdir(BLOG_ROOT):
        print(f"错误：博客目录不存在 - {BLOG_ROOT}")
        input("按 Enter 退出...")
        return
    if "--web" in sys.argv:
        extra = [a for a in sys.argv[1:] if a != "--web"]
        web_params = _parse_web_params(extra[0]) if extra else None
        run_web_server(web_params=web_params)
        return
    os.makedirs(POSTS_BASE, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)
    root = tk.Tk()
    BlogTool(root)
    root.mainloop()


if __name__ == "__main__":
    main()
