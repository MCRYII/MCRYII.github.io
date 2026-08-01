# -*- coding: utf-8 -*-
"""MCRYII 博客写作助手（现代化重构版）

功能：文章管理 / 封面编辑 / Markdown 预览 / 图片插入 / 本地预览 / 一键推送
网页版：python blog_tool.py --web 后浏览器打开 http://127.0.0.1:8777/
"""
import base64
import datetime
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import tkinter as tk
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from tkinter import filedialog, messagebox, scrolledtext, ttk

from PIL import Image, ImageTk

# ==================== 配置 ====================
BLOG_ROOT = r"D:\Downloads\Programs\myblog-new"
POSTS_BASE = os.path.join(BLOG_ROOT, "content", "posts")
IMAGES_DIR = os.path.join(BLOG_ROOT, "static", "images")
DEFAULT_COVER = os.path.join(IMAGES_DIR, "default-cover.png")
MOMENTS_FILE = os.path.join(BLOG_ROOT, "data", "moments.json")
MOMENTS_IMAGES_DIR = os.path.join(IMAGES_DIR, "moments")

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
            tk.Label(chip, text="✕", bg=COL_SELECT, fg=COL_RED, cursor="hand2",
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
        btn_reset = tk.Button(bar, text="↺ 重置", command=self._reset,
                              bg=COL_PANEL2, fg=COL_TEXT, relief=tk.FLAT,
                              activebackground=COL_SELECT, activeforeground=COL_GOLD,
                              font=(FONT, 10), cursor="hand2", padx=12, pady=4)
        btn_reset.pack(side=tk.RIGHT, padx=4)
        btn_cancel = tk.Button(bar, text="取消", command=self._cancel,
                               bg="#3a2023", fg=COL_RED, relief=tk.FLAT,
                               activebackground="#4a262a", activeforeground="#ff7a80",
                               font=(FONT, 10), cursor="hand2", padx=12, pady=4)
        btn_cancel.pack(side=tk.RIGHT, padx=4)
        btn_ok = tk.Button(bar, text="✓ 确认裁剪", command=self._confirm,
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
        tk.Label(header, text="✒ MCRYII 博客写作助手", bg=COL_PANEL, fg=COL_GOLD,
                 font=(FONT, 14, "bold")).pack(side=tk.LEFT, padx=18)
        self.server_label = tk.Label(header, text="● 服务器检测中", bg=COL_PANEL,
                                     fg=COL_MUTED, font=(FONT, 9))
        self.server_label.pack(side=tk.LEFT, padx=10)
        self.git_label = tk.Label(header, text="Git: -", bg=COL_PANEL, fg=COL_MUTED,
                                  font=(FONT, 9))
        self.git_label.pack(side=tk.LEFT, padx=10)
        for text, cmd, kind in (
            ("🌐 预览网站", self.preview_site, "gold"),
            ("🚀 推送到 GitHub", self.push_to_github, "ghost"),
            ("🔄 Git 状态", self._update_git_status, "ghost"),
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
        tk.Label(bar, text="📚 已有文章", bg=COL_PANEL, fg=COL_TEXT,
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
        self._btn(bottom, "🗑 删除", self.delete_article, "danger").pack(side=tk.LEFT)
        self._btn(bottom, "🔄 刷新", self.refresh_article_list).pack(side=tk.RIGHT)

        # 右侧：编辑 / 预览
        right = tk.Frame(main, bg=COL_PANEL)
        main.add(right, width=940)
        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        edit_tab = tk.Frame(self.notebook, bg=COL_PANEL)
        self.notebook.add(edit_tab, text="✏ 编辑")
        preview_tab = tk.Frame(self.notebook, bg=COL_PANEL)
        self.notebook.add(preview_tab, text="👁 预览")
        moments_tab = tk.Frame(self.notebook, bg=COL_PANEL)
        self.notebook.add(moments_tab, text="💬 动态")
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        self._build_edit_tab(edit_tab)
        self._build_preview_tab(preview_tab)
        self._build_moments_tab(moments_tab)

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
        self._btn(meta, "📅 现在", lambda: self.date_entry.delete(0, tk.END) or
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
        self._btn(cover_row, "✏ 编辑封面", self.edit_cover, "ghost").pack(side=tk.LEFT, padx=3)
        self._btn(cover_row, "🖼 选择封面", self.choose_cover, "ghost").pack(side=tk.LEFT, padx=3)
        self._btn(cover_row, "✕ 清除", self.clear_cover, "danger").pack(side=tk.LEFT, padx=3)

        # 工具栏
        tools = tk.Frame(parent, bg=COL_PANEL)
        tools.pack(fill=tk.X, padx=12, pady=6)
        self._btn(tools, "💾 保存 (Ctrl+S)", self.save_article, "gold").pack(side=tk.LEFT)
        self._btn(tools, "🖼 插入图片", self.insert_image).pack(side=tk.LEFT, padx=4)
        self._btn(tools, "📋 清空编辑区", self._clear_editor).pack(side=tk.LEFT, padx=4)
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
        self.status_var.set(f"✅ 已保存：{rel}")
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
        self._btn(imgs_row, "🖼 添加图片", self._pick_moment_images, width=10).pack(side=tk.LEFT)
        self._btn(imgs_row, "🗑 移除选中", self._remove_moment_images, "danger",
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

        self._btn(parent, "📌 发布动态", self.publish_moment, "gold").pack(anchor="w", **pad)

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
        self._btn(tree_bottom, "🗑 删除选中", self.delete_moment, "danger").pack(side=tk.LEFT)
        self._btn(tree_bottom, "🔄 刷新", self.refresh_moment_list).pack(side=tk.RIGHT)

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
        self.status_var.set("📌 动态已发布，重新构建后即可在 /dynamic/ 看到")
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
            self.server_label.config(text="● 本地服务器运行中", fg=COL_GREEN)
        else:
            self.server_label.config(text="○ 本地服务器未启动", fg=COL_MUTED)
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
            self.status_var.set("✅ 推送成功，等待 GitHub Actions 构建")
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
#pv { background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:14px 16px; margin-top:12px; display:none; font-size:.88rem; line-height:1.7; }
#pv h1,#pv h2,#pv h3 { color:var(--gold); }
#pv img { max-width:100%; border-radius:8px; }
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
.mom-meta { font-size:.72rem; color:var(--muted); margin-bottom:4px; display:flex; gap:10px; align-items:center; }
.mom-del { margin-left:auto; }
.small { font-size:.75rem; color:var(--muted); }
.hidden-file { display:none; }
</style>
</head>
<body>
<header>
  <h1>✒ 博客写作助手 · 网页版</h1>
  <span id="status">就绪</span>
  <div class="tabs">
    <button class="tab-btn active" id="tab-articles">📝 文章</button>
    <button class="tab-btn" id="tab-moments">💬 动态</button>
  </div>
</header>
<main>
  <section class="view active" id="view-articles">
    <div id="art-list-pane"><ul id="art-list"></ul></div>
    <div id="art-form">
      <input type="hidden" id="f-file">
      <div class="row"><label>标题</label><input type="text" id="f-title" style="flex:1"></div>
      <div class="row"><label>日期</label><input type="text" id="f-date" placeholder="2026-08-01 或 2026-08-01T21:24:37+08:00" style="flex:1"></div>
      <div class="row"><label>分类</label><input type="text" id="f-cats" placeholder="逗号分隔" style="flex:1"></div>
      <div class="row"><label>标签</label><input type="text" id="f-tags" placeholder="逗号分隔" style="flex:1"></div>
      <div class="row">
        <label>封面</label><input type="text" id="f-cover" placeholder="/images/xxx.jpg" style="flex:1">
        <input type="file" id="f-cover-file" class="hidden-file" accept="image/*">
        <button class="btn sm" id="btn-cover-up">上传封面</button>
        <label style="width:auto; display:flex; align-items:center; gap:6px; color:var(--muted); font-size:.85rem; cursor:pointer;"><input type="checkbox" id="f-draft"> 草稿</label>
      </div>
      <div class="row" style="align-items:flex-start;">
        <label>正文</label>
        <div style="flex:1">
          <textarea id="f-body" placeholder="Markdown 正文"></textarea>
          <div style="margin-top:8px; display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
            <button class="btn gold" id="btn-save">💾 保存</button>
            <button class="btn" id="btn-new">＋ 新建</button>
            <button class="btn danger" id="btn-del">🗑 删除</button>
            <input type="file" id="f-img-file" class="hidden-file" accept="image/*">
            <button class="btn" id="btn-img-up">🖼 插入图片</button>
            <button class="btn" id="btn-pv">👁 预览</button>
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
          <button class="btn sm" id="btn-m-img">🖼 添加图片</button>
        </div>
        <ul id="mom-imgs"></ul>
        <div class="row"><label>链接（可选）</label><input type="text" id="m-link" placeholder="https://..." style="flex:1"></div>
        <div style="display:flex; gap:8px;">
          <button class="btn gold" id="btn-m-save">📌 发布动态</button>
          <button class="btn" id="btn-m-cancel" style="display:none">取消编辑</button>
        </div>
      </div>
      <div id="mom-list">
        <div class="small" style="margin-bottom:8px">已有动态</div>
        <ul id="mom-items"></ul>
      </div>
    </div>
  </section>
</main>
<script>
(function () {
    var $ = function (id) { return document.getElementById(id); };
    var state = { articles: [], curFile: null, moments: [], momImgs: [], editingId: null };
    var pendingMomentId = null;

    function api(path, opts) {
        opts = opts || {};
        opts.headers = Object.assign({}, opts.headers || {}, { 'Content-Type': 'application/json' });
        return fetch(path, opts).then(function (r) { return r.json(); });
    }
    function setStatus(t) { $('status').textContent = t; }
    function esc(s) { var d = document.createElement('div'); d.textContent = s == null ? '' : String(s); return d.innerHTML; }
    function splitList(s) { return s.split(/[,，]/).map(function (x) { return x.trim(); }).filter(Boolean); }

    // ---- 页签 ----
    function showTab(name) {
        $('view-articles').classList.toggle('active', name === 'articles');
        $('view-moments').classList.toggle('active', name === 'moments');
        $('tab-articles').classList.toggle('active', name === 'articles');
        $('tab-moments').classList.toggle('active', name === 'moments');
    }
    $('tab-articles').addEventListener('click', function () { showTab('articles'); });
    $('tab-moments').addEventListener('click', function () { showTab('moments'); });

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
            $('f-cats').value = (d.categories || []).join(', ');
            $('f-tags').value = (d.tags || []).join(', ');
            $('f-cover').value = d.cover || '';
            $('f-draft').checked = !!d.draft;
            $('f-body').value = d.body || '';
            renderArtList();
            setStatus('已打开：' + file);
        }).catch(function () { setStatus('打开失败'); });
    }
    function saveArticle() {
        var payload = {
            file: $('f-file').value || null,
            title: $('f-title').value,
            date: $('f-date').value,
            categories: splitList($('f-cats').value),
            tags: splitList($('f-tags').value),
            draft: $('f-draft').checked,
            cover: $('f-cover').value,
            body: $('f-body').value.replace(/\\s+$/, '')
        };
        api('/api/article', { method: 'POST', body: JSON.stringify(payload) }).then(function (r) {
            if (r.error) { alert(r.error); return; }
            setStatus('✅ 已保存：' + r.file);
            loadArticles();
        });
    }
    function newArticle() {
        state.curFile = null;
        $('f-file').value = '';
        $('f-title').value = '';
        $('f-date').value = '';
        $('f-cats').value = '';
        $('f-tags').value = '';
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
    $('btn-img-up').addEventListener('click', function () { $('f-img-file').click(); });
    $('f-img-file').addEventListener('change', function () {
        uploadImg(this, 'post', function (url) {
            var ta = $('f-body');
            var p = ta.selectionStart || ta.value.length;
            ta.value = ta.value.slice(0, p) + '![](' + url + ')\\n\\n' + ta.value.slice(p);
            ta.focus();
            ta.selectionStart = ta.selectionEnd = p + url.length + 5;
        });
    });
    $('btn-cover-up').addEventListener('click', function () { $('f-cover-file').click(); });
    $('f-cover-file').addEventListener('change', function () {
        uploadImg(this, 'post', function (url) { $('f-cover').value = url; });
    });
    $('btn-pv').addEventListener('click', function () {
        var pv = $('pv');
        pv.style.display = pv.style.display === 'none' ? 'block' : 'none';
        pv.innerHTML = mdRender($('f-body').value);
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
                    (m.images && m.images.length ? '<span>🖼 ' + m.images.length + '</span>' : '') +
                    '<button class="btn sm mom-edit">编辑</button>' +
                    '<button class="btn sm danger mom-del">删除</button></div>' +
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
        $('btn-m-save').textContent = '💾 保存修改';
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
        $('btn-m-save').textContent = '📌 发布动态';
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
            li.innerHTML = esc(u) + ' <button class="btn sm danger">✕</button>';
            li.querySelector('button').addEventListener('click', function () { state.momImgs.splice(i, 1); renderMomImgs(); });
            ul.appendChild(li);
        });
    }
    $('btn-m-img').addEventListener('click', function () { $('m-img-file').click(); });
    $('m-img-file').addEventListener('change', function () {
        Array.prototype.forEach.call(this.files, function (f) {
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
                setStatus(isEdit ? '✅ 动态已更新' : '📌 动态已发布');
            });
    });
    $('btn-m-cancel').addEventListener('click', function () {
        resetMomentForm();
        loadMoments();
        setStatus('已取消编辑');
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
            if (buf.length) { out.push('<p>' + buf.map(mdInline).join('<br>') + '</p>'); buf = []; }
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
    var q = new URLSearchParams(location.search);
    if (q.get('new') === '1') { newArticle(); showTab('articles'); }
    else if (q.get('file')) { loadArticle(q.get('file')); showTab('articles'); }
    else if (q.get('tab') === 'moments' || q.get('id')) { showTab('moments'); }
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

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        try:
            if parsed.path == "/":
                self._reply(200, WEB_UI_HTML, "text/html; charset=utf-8")
            elif parsed.path == "/api/ping":
                self._json({"ok": True})
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
    _safe_print(f"✒ 博客写作助手网页版已启动：{target}")
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
