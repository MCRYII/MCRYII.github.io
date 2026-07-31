# -*- coding: utf-8 -*-
"""MCRYII 博客写作助手（现代化重构版）

功能：文章管理 / 封面编辑 / Markdown 预览 / 图片插入 / 本地预览 / 一键推送
"""
import datetime
import json
import os
import re
import shutil
import socket
import subprocess
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, scrolledtext, ttk

from PIL import Image, ImageTk

# ==================== 配置 ====================
BLOG_ROOT = r"D:\Downloads\Programs\myblog-new"
POSTS_BASE = os.path.join(BLOG_ROOT, "content", "posts")
IMAGES_DIR = os.path.join(BLOG_ROOT, "static", "images")
DEFAULT_COVER = os.path.join(IMAGES_DIR, "default-cover.png")

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

        self._setup_style()
        self._build_ui()
        self._bind_shortcuts()
        self.refresh_article_list()
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
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        self._build_edit_tab(edit_tab)
        self._build_preview_tab(preview_tab)

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
    def _scan_posts(self):
        out = []
        for root, _, files in os.walk(POSTS_BASE):
            for f in files:
                if f.endswith(".md"):
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, POSTS_BASE)
                    out.append((rel, full))
        return out

    def _parse_front(self, content):
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
            data["categories"] = self._parse_list(c.group(1))
        if g:
            data["tags"] = self._parse_list(g.group(1))
        if cv:
            data["cover"] = cv.group(1).strip()
        return data

    @staticmethod
    def _parse_list(raw):
        try:
            return json.loads(f"[{raw}]")
        except Exception:
            return [x.strip().strip("\"'") for x in raw.split(",") if x.strip()]

    def refresh_article_list(self):
        self.tree.delete(*self.tree.get_children())
        self._tree_imgs.clear()
        items = []
        for rel, full in self._scan_posts():
            try:
                with open(full, encoding="utf-8") as f:
                    content = f.read()
            except OSError:
                continue
            data = self._parse_front(content)
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
        data = self._parse_front(content)
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
        cats = json.dumps(self.cats.get_tags(), ensure_ascii=False)
        tags = json.dumps(self.tags.get_tags(), ensure_ascii=False)

        lines = ["---", f'title: "{title}"', f"date: {date}",
                 f"categories: {cats}", f"tags: {tags}",
                 f"draft: {str(self.draft_var.get()).lower()}"]
        if self.cover_path:
            lines.append("cover:")
            lines.append(f'  image: "{self.cover_path}"')
        lines.append("---")
        front = "\n".join(lines) + "\n\n"

        if self.current_file_path and os.path.exists(self.current_file_path):
            filepath = self.current_file_path
        else:
            safe = re.sub(r'[\\/:*?"<>|]', "", title).replace(" ", "-")
            filepath = os.path.join(POSTS_BASE, safe + ".md")
            if os.path.exists(filepath):
                filepath = os.path.join(POSTS_BASE, safe + f"-{int(datetime.datetime.now().timestamp())}.md")
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(front + body)
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


def main():
    if not os.path.isdir(BLOG_ROOT):
        print(f"错误：博客目录不存在 - {BLOG_ROOT}")
        input("按 Enter 退出...")
        return
    os.makedirs(POSTS_BASE, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)
    root = tk.Tk()
    BlogTool(root)
    root.mainloop()


if __name__ == "__main__":
    main()
