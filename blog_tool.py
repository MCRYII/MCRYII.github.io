import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk, filedialog
import subprocess
import datetime
import os
import re
import shutil
import webbrowser
import json
from pathlib import Path
from PIL import Image, ImageTk

# ================== 配置区域 ==================
BLOG_ROOT = r"D:\Downloads\Programs\myblog-new"   # 请修改为你的博客根目录
POSTS_BASE = os.path.join(BLOG_ROOT, "content", "posts")
IMAGES_DIR = os.path.join(BLOG_ROOT, "static", "images")
# =============================================

class TagInputWidget(tk.Frame):
    # ... (保持原有代码不变，省略以节省篇幅，实际使用时请保留完整)
    def __init__(self, master, title="", **kwargs):
        super().__init__(master, **kwargs)
        self.title = title
        self.tags = []
        self.init_ui()

    def init_ui(self):
        tk.Label(self, text=self.title, anchor="w").pack(fill=tk.X, pady=(0,5))
        input_frame = tk.Frame(self)
        input_frame.pack(fill=tk.X, pady=(0,8))
        self.entry = tk.Entry(input_frame, width=30)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry.bind("<Return>", self.add_tag_from_entry)
        self.tags_frame = tk.Frame(self, bg=self.cget("bg"))
        self.tags_frame.pack(fill=tk.X, anchor="w")
        self.refresh_tags_display()

    def add_tag_from_entry(self, event=None):
        text = self.entry.get().strip()
        if text and text not in self.tags:
            self.tags.append(text)
            self.entry.delete(0, tk.END)
            self.refresh_tags_display()
        return "break"

    def remove_tag(self, tag):
        if tag in self.tags:
            self.tags.remove(tag)
            self.refresh_tags_display()

    def refresh_tags_display(self):
        for widget in self.tags_frame.winfo_children():
            widget.destroy()
        for tag in self.tags:
            tag_frame = tk.Frame(self.tags_frame, bg="#e0e0e0", relief=tk.FLAT, bd=1)
            tag_frame.pack(side=tk.LEFT, padx=2, pady=2, anchor="w")
            label = tk.Label(tag_frame, text=tag, bg="#e0e0e0", fg="black", padx=5, pady=2)
            label.pack(side=tk.LEFT)
            del_btn = tk.Button(tag_frame, text="✕", bg="#e0e0e0", fg="red", bd=0,
                                cursor="hand2", command=lambda t=tag: self.remove_tag(t))
            del_btn.pack(side=tk.RIGHT, padx=(0,3))
        if not self.tags:
            tip = tk.Label(self.tags_frame, text="（点击输入框，输入后按回车添加）", fg="gray", bg=self.cget("bg"))
            tip.pack(side=tk.LEFT, padx=5)

    def get_tags(self):
        return self.tags

    def set_tags(self, tag_list):
        self.tags = tag_list.copy() if tag_list else []
        self.refresh_tags_display()

class HugoBlogTool:
    def __init__(self, root):
        self.root = root
        self.root.title("Hugo 博客写作助手 - MCRYII")
        self.root.geometry("1200x900")
        self.root.resizable(True, True)

        self.current_file_path = None
        self.preview_process = None
        self.image_preview_cache = {}

        self.create_widgets()
        self.refresh_article_list()
        self.text_area.bind("<<Modified>>", self.on_text_modified)
        self.after_id = None

    def create_widgets(self):
        # 主布局
        main_pane = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=6)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 左侧：文章列表
        left_frame = tk.Frame(main_pane, width=250)
        main_pane.add(left_frame, width=250)
        tk.Label(left_frame, text="已有文章", font=("微软雅黑", 12, "bold")).pack(anchor="w", pady=5)
        self.article_listbox = tk.Listbox(left_frame, font=("Consolas", 10))
        self.article_listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scrollbar = tk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.article_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.article_listbox.config(yscrollcommand=scrollbar.set)
        self.article_listbox.bind("<Double-Button-1>", self.load_selected_article)

        # 右侧垂直分割
        right_pane = tk.PanedWindow(main_pane, orient=tk.VERTICAL, sashrelief=tk.RAISED, sashwidth=6)
        main_pane.add(right_pane, width=800)

        top_frame = tk.Frame(right_pane)
        right_pane.add(top_frame, height=500)

        # 文章元数据
        meta_frame = tk.LabelFrame(top_frame, text="文章元数据", padx=10, pady=10)
        meta_frame.pack(fill=tk.X, pady=5)

        # 第0行：标题
        tk.Label(meta_frame, text="标题:").grid(row=0, column=0, sticky="w", pady=2)
        self.title_entry = tk.Entry(meta_frame, width=60)
        self.title_entry.grid(row=0, column=1, padx=5, pady=2, sticky="ew", columnspan=3)

        # 第1行：发布日期（新增）
        tk.Label(meta_frame, text="发布日期:", anchor="w").grid(row=1, column=0, sticky="w", pady=2)
        self.date_entry = tk.Entry(meta_frame, width=30)
        self.date_entry.grid(row=1, column=1, sticky="w", padx=5, pady=2)
        tk.Label(meta_frame, text="格式: 2026-06-06T21:24:37+08:00 (留空则自动生成当前时间)", fg="gray", font=("微软雅黑", 8)).grid(row=1, column=2, columnspan=2, sticky="w", padx=5)

        # 第2行：分类组件
        self.categories_widget = TagInputWidget(meta_frame, title="分类（回车添加）")
        self.categories_widget.grid(row=2, column=0, columnspan=4, sticky="ew", pady=5)

        # 第3行：标签组件
        self.tags_widget = TagInputWidget(meta_frame, title="标签（回车添加）")
        self.tags_widget.grid(row=3, column=0, columnspan=4, sticky="ew", pady=5)

        # 第4行：草稿标记
        self.draft_var = tk.BooleanVar()
        tk.Checkbutton(meta_frame, text="草稿（draft: true）", variable=self.draft_var).grid(row=4, column=0, columnspan=4, sticky="w", pady=5)

        meta_frame.columnconfigure(1, weight=1)

        # 工具栏
        tool_frame = tk.Frame(top_frame)
        tool_frame.pack(fill=tk.X, pady=5)

        btn_new = tk.Button(tool_frame, text="📄 新建文章", command=self.new_article, bg="#2196F3", fg="white")
        btn_new.pack(side=tk.LEFT, padx=2)
        btn_img = tk.Button(tool_frame, text="📂 插入图片", command=self.insert_image, bg="#e0e0e0")
        btn_img.pack(side=tk.LEFT, padx=2)
        btn_save = tk.Button(tool_frame, text="💾 保存到本地", command=self.save_article, bg="#4CAF50", fg="white")
        btn_save.pack(side=tk.LEFT, padx=2)
        btn_preview = tk.Button(tool_frame, text="🌐 预览网站", command=self.preview_site, bg="#2196F3", fg="white")
        btn_preview.pack(side=tk.LEFT, padx=2)
        btn_push = tk.Button(tool_frame, text="🚀 推送到 GitHub", command=self.push_to_github, bg="#FF9800", fg="white")
        btn_push.pack(side=tk.LEFT, padx=2)
        btn_del = tk.Button(tool_frame, text="🗑️ 删除当前文章", command=self.delete_article, bg="#f44336", fg="white")
        btn_del.pack(side=tk.LEFT, padx=2)
        btn_refresh = tk.Button(tool_frame, text="🔄 刷新列表", command=self.refresh_article_list)
        btn_refresh.pack(side=tk.LEFT, padx=2)

        # 正文标签
        tk.Label(top_frame, text="正文（Markdown格式）:", anchor="w").pack(fill=tk.X, pady=(10,0))
        self.text_area = scrolledtext.ScrolledText(top_frame, wrap=tk.WORD, height=15, font=("Consolas", 11))
        self.text_area.pack(fill=tk.BOTH, expand=True, pady=5)

        # 图片预览区
        bottom_frame = tk.LabelFrame(right_pane, text="📷 文章图片预览（点击路径可复制）", padx=5, pady=5)
        right_pane.add(bottom_frame, height=200)

        self.preview_canvas = tk.Canvas(bottom_frame, bg="#f0f0f0")
        scrollbar_x = tk.Scrollbar(bottom_frame, orient=tk.HORIZONTAL, command=self.preview_canvas.xview)
        scrollbar_y = tk.Scrollbar(bottom_frame, orient=tk.VERTICAL, command=self.preview_canvas.yview)
        self.preview_canvas.configure(xscrollcommand=scrollbar_x.set, yscrollcommand=scrollbar_y.set)
        self.preview_inner = tk.Frame(self.preview_canvas)
        self.preview_canvas.create_window((0,0), window=self.preview_inner, anchor="nw")

        self.preview_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        self.preview_inner.bind("<Configure>", lambda e: self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all")))

        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def on_text_modified(self, event=None):
        self.text_area.edit_modified(False)
        if self.after_id:
            self.root.after_cancel(self.after_id)
        self.after_id = self.root.after(500, self.update_image_preview)

    def update_image_preview(self):
        for widget in self.preview_inner.winfo_children():
            widget.destroy()
        content = self.text_area.get("1.0", tk.END)
        pattern = r'!\[.*?\]\((.*?)\)'
        image_urls = re.findall(pattern, content)
        if not image_urls:
            tip = tk.Label(self.preview_inner, text="（当前文章中没有图片，使用“插入图片”按钮添加）", fg="gray")
            tip.pack(padx=10, pady=10)
            return

        for url in image_urls:
            frame = tk.Frame(self.preview_inner, relief=tk.RAISED, bd=1)
            frame.pack(side=tk.LEFT, padx=5, pady=5, anchor="n")
            # 加载缩略图
            thumb = None
            if url.startswith('/images/'):
                local_path = os.path.join(BLOG_ROOT, "static", url[1:])
                if os.path.exists(local_path):
                    try:
                        pil_img = Image.open(local_path)
                        pil_img.thumbnail((100, 100))
                        thumb = ImageTk.PhotoImage(pil_img)
                    except:
                        pass
            if thumb:
                img_label = tk.Label(frame, image=thumb)
                img_label.image = thumb
                img_label.pack(padx=2, pady=2)
            else:
                tk.Label(frame, text="⚠️ 无法预览", bg="#ddd", width=10, height=4).pack(padx=2, pady=2)
            # 路径
            path_short = url if len(url) < 40 else url[:37] + "..."
            lbl_path = tk.Label(frame, text=path_short, fg="blue", cursor="hand2", font=("Consolas", 8))
            lbl_path.pack(pady=2)
            lbl_path.bind("<Button-1>", lambda e, u=url: self.copy_image_path(u))
            # 删除按钮
            del_btn = tk.Button(frame, text="删除", fg="red", command=lambda u=url: self.remove_image_from_text(u))
            del_btn.pack(pady=2)

        self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all"))

    def copy_image_path(self, url):
        self.root.clipboard_clear()
        self.root.clipboard_append(url)
        self.status_var.set(f"已复制图片路径: {url}")

    def remove_image_from_text(self, url):
        content = self.text_area.get("1.0", tk.END)
        pattern = r'!\[.*?\]\(' + re.escape(url) + r'\)'
        new_content = re.sub(pattern, '', content, count=1)
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert("1.0", new_content)
        self.status_var.set(f"已删除图片: {url}")
        self.update_image_preview()

    # ------------------ 新增日期相关 ------------------
    def get_current_time_str(self):
        """返回当前时间的 Hugo 格式字符串"""
        return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")

    def validate_date(self, date_str):
        """简单验证日期格式是否符合 Hugo 要求，不符合则返回当前时间"""
        if not date_str:
            return self.get_current_time_str()
        # 尝试解析常见格式（允许用户输入 YYYY-MM-DD 自动补充时间）
        if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            date_str = date_str + "T00:00:00+08:00"
        # 验证完整格式
        pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+08:00$'
        if re.match(pattern, date_str):
            return date_str
        else:
            # 格式错误，提示并使用当前时间
            messagebox.showwarning("日期格式错误", f"日期格式不正确，已使用当前时间。\n正确格式: 2026-06-06T21:24:37+08:00 或 2026-06-06")
            return self.get_current_time_str()

    # ------------------ 新建文章 ------------------
    def new_article(self):
        self.title_entry.delete(0, tk.END)
        self.date_entry.delete(0, tk.END)
        self.date_entry.insert(0, self.get_current_time_str())
        self.categories_widget.set_tags([])
        self.tags_widget.set_tags([])
        self.draft_var.set(False)
        self.text_area.delete("1.0", tk.END)
        self.current_file_path = None
        self.status_var.set("新建文章，填写内容后保存即可")
        self.title_entry.focus_set()
        self.update_image_preview()

    # ------------------ 文章列表扫描 ------------------
    def get_all_md_files(self):
        md_files = []
        if not os.path.isdir(POSTS_BASE):
            return md_files
        for root, dirs, files in os.walk(POSTS_BASE):
            for file in files:
                if file.endswith(".md"):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, POSTS_BASE)
                    md_files.append(rel_path)
        md_files.sort(key=lambda rel: os.path.getmtime(os.path.join(POSTS_BASE, rel)), reverse=True)
        return md_files

    def refresh_article_list(self):
        self.article_listbox.delete(0, tk.END)
        for rel in self.get_all_md_files():
            self.article_listbox.insert(tk.END, rel)

    # ------------------ 加载文章 ------------------
    def load_selected_article(self, event=None):
        selection = self.article_listbox.curselection()
        if not selection:
            return
        rel_path = self.article_listbox.get(selection[0])
        full_path = os.path.join(POSTS_BASE, rel_path)
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            messagebox.showerror("错误", f"读取文件失败: {e}")
            return

        front_match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', content, re.DOTALL)
        if front_match:
            yaml_text = front_match.group(1)
            body = front_match.group(2)
            # 提取各个字段
            title_match = re.search(r'title:\s*["\']?(.*?)["\']?\s*$', yaml_text, re.MULTILINE)
            date_match = re.search(r'date:\s*(.*?)\s*$', yaml_text, re.MULTILINE)
            categories_match = re.search(r'categories:\s*\[(.*?)\]', yaml_text)
            tags_match = re.search(r'tags:\s*\[(.*?)\]', yaml_text)
            draft_match = re.search(r'draft:\s*(true|false)', yaml_text)

            if title_match:
                self.title_entry.delete(0, tk.END)
                self.title_entry.insert(0, title_match.group(1).strip('"\' '))
            if date_match:
                self.date_entry.delete(0, tk.END)
                self.date_entry.insert(0, date_match.group(1).strip())
            else:
                self.date_entry.delete(0, tk.END)
                self.date_entry.insert(0, self.get_current_time_str())
            if categories_match:
                cats_str = categories_match.group(1)
                try:
                    cats = json.loads(f"[{cats_str}]") if cats_str.strip() else []
                except:
                    cats = [c.strip().strip('"') for c in cats_str.split(",") if c.strip()]
                self.categories_widget.set_tags(cats)
            else:
                self.categories_widget.set_tags([])
            if tags_match:
                tags_str = tags_match.group(1)
                try:
                    tags = json.loads(f"[{tags_str}]") if tags_str.strip() else []
                except:
                    tags = [t.strip().strip('"') for t in tags_str.split(",") if t.strip()]
                self.tags_widget.set_tags(tags)
            else:
                self.tags_widget.set_tags([])
            if draft_match:
                self.draft_var.set(draft_match.group(1).lower() == "true")
        else:
            body = content
            self.categories_widget.set_tags([])
            self.tags_widget.set_tags([])
            self.draft_var.set(False)
            self.date_entry.delete(0, tk.END)
            self.date_entry.insert(0, self.get_current_time_str())

        self.text_area.delete("1.0", tk.END)
        self.text_area.insert("1.0", body.strip())
        self.current_file_path = full_path
        self.status_var.set(f"已加载: {rel_path}")
        self.update_image_preview()

    # ------------------ 生成 Front Matter ------------------
    def generate_front_matter(self, title, date_str, categories, tags, draft):
        # 如果用户没有输入日期，自动生成当前时间
        if not date_str:
            date_str = self.get_current_time_str()
        else:
            date_str = self.validate_date(date_str)
        cat_yaml = json.dumps(categories, ensure_ascii=False)
        tag_yaml = json.dumps(tags, ensure_ascii=False)
        draft_str = "true" if draft else "false"
        return f"""---
title: "{title}"
date: {date_str}
categories: {cat_yaml}
tags: {tag_yaml}
draft: {draft_str}
---

"""

    # ------------------ 保存文章 ------------------
    def save_article(self):
        title = self.title_entry.get().strip()
        if not title:
            messagebox.showwarning("提示", "标题不能为空")
            return
        date_str = self.date_entry.get().strip()
        categories = self.categories_widget.get_tags()
        tags = self.tags_widget.get_tags()
        draft = self.draft_var.get()
        body = self.text_area.get("1.0", tk.END).rstrip()

        if self.current_file_path and os.path.exists(self.current_file_path):
            filepath = self.current_file_path
        else:
            safe_title = re.sub(r'[\\/*?:"<>|]', '', title)
            filename = safe_title.replace(' ', '-') + ".md"
            filepath = os.path.join(POSTS_BASE, filename)

        front = self.generate_front_matter(title, date_str, categories, tags, draft)
        full_content = front + body

        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(full_content)
            self.current_file_path = filepath
            rel = os.path.relpath(filepath, POSTS_BASE)
            self.status_var.set(f"已保存: {rel}")
            self.refresh_article_list()
            messagebox.showinfo("成功", f"文章已保存到\n{filepath}")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")

    # ------------------ 插入图片 ------------------
    def insert_image(self):
        if not os.path.isdir(IMAGES_DIR):
            os.makedirs(IMAGES_DIR, exist_ok=True)
        img_path = filedialog.askopenfilename(title="选择图片", filetypes=[("图片文件", "*.png *.jpg *.jpeg *.gif *.webp")])
        if not img_path:
            return
        basename = os.path.basename(img_path)
        dest_path = os.path.join(IMAGES_DIR, basename)
        if os.path.exists(dest_path):
            name, ext = os.path.splitext(basename)
            counter = 1
            while os.path.exists(os.path.join(IMAGES_DIR, f"{name}_{counter}{ext}")):
                counter += 1
            dest_path = os.path.join(IMAGES_DIR, f"{name}_{counter}{ext}")
        shutil.copy2(img_path, dest_path)
        rel_path = f"/images/{os.path.basename(dest_path)}"
        alt = os.path.splitext(basename)[0]
        img_md = f"![{alt}]({rel_path})\n\n"
        self.text_area.insert(tk.INSERT, img_md)
        self.status_var.set("图片已复制并插入")
        self.update_image_preview()

    # ------------------ 预览网站 ------------------
    def preview_site(self):
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', 1314))
        if result == 0:
            answer = messagebox.askyesno("端口占用", "本地 1314 端口已被占用，可能已有 hugo server 在运行。\n是否强制关闭现有进程并重新启动？")
            if answer:
                subprocess.run("taskkill /F /IM hugo.exe", shell=True, capture_output=True)
                self.status_var.set("已终止现有 hugo 进程")
            else:
                webbrowser.open("http://localhost:1314")
                return
        cmd = f'start cmd /k "cd /d {BLOG_ROOT} && hugo server -D --port 1314"'
        subprocess.Popen(cmd, shell=True)
        self.status_var.set("预览服务器已启动，等待几秒后自动打开浏览器...")
        self.root.after(3000, lambda: webbrowser.open("http://localhost:1314"))

    # ------------------ 推送到 GitHub ------------------
    def push_to_github(self):
        if not messagebox.askyesno("确认推送", "确定要将所有本地更改推送到 GitHub 吗？\n请确保预览无误后再操作。"):
            return
        try:
            os.chdir(BLOG_ROOT)
            if not os.path.isdir(".git"):
                self.status_var.set("错误：当前目录不是 Git 仓库")
                return
            subprocess.run(["git", "add", "."], check=True, capture_output=True, text=True)
            commit_msg = "更新文章"
            if self.current_file_path:
                title = self.title_entry.get().strip()
                if title:
                    commit_msg = f"更新文章: {title}"
            subprocess.run(["git", "commit", "-m", commit_msg], check=True, capture_output=True, text=True)
            subprocess.run(["git", "push"], check=True, capture_output=True, text=True)
            self.status_var.set("✅ 推送成功！")
            messagebox.showinfo("成功", "已推送到 GitHub，稍等片刻在线网站将更新。")
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            self.status_var.set("推送失败")
            messagebox.showerror("Git 错误", f"执行 Git 命令失败:\n{error_msg}")
        except Exception as e:
            self.status_var.set("未知错误")
            messagebox.showerror("错误", str(e))

    # ------------------ 删除当前文章 ------------------
    def delete_article(self):
        if not self.current_file_path or not os.path.exists(self.current_file_path):
            messagebox.showwarning("提示", "没有打开的文章可删除")
            return
        rel = os.path.relpath(self.current_file_path, POSTS_BASE)
        if messagebox.askyesno("确认删除", f"确定要永久删除文章\n{rel} 吗？\n此操作不可恢复！"):
            try:
                os.remove(self.current_file_path)
                self.status_var.set(f"已删除: {rel}")
                self.new_article()
                self.refresh_article_list()
                messagebox.showinfo("成功", "文章已删除")
            except Exception as e:
                messagebox.showerror("错误", f"删除失败: {e}")

if __name__ == "__main__":
    if not os.path.isdir(BLOG_ROOT):
        print(f"错误：博客目录不存在 - {BLOG_ROOT}")
        print("请修改代码中的 BLOG_ROOT 变量")
        input("按 Enter 退出...")
        exit(1)
    os.makedirs(POSTS_BASE, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)

    root = tk.Tk()
    app = HugoBlogTool(root)
    root.mainloop()