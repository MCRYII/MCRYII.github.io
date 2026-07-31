# MCRYII 的博客

基于 [Hugo](https://gohugo.io/) + [PaperMod](https://github.com/adityatelange/hugo-PaperMod) 主题的个人博客，部署在 GitHub Pages，绑定域名 [www.mcryii.fun](https://www.mcryii.fun/)。

## 技术栈

- Hugo（extended 版，版本见 `.github/workflows/hugo.yml`）
- PaperMod 主题（git submodule）
- 本地写作工具：`blog_tool.py`（Tkinter 桌面应用）

## 本地开发

```powershell
# 启动本地预览（含草稿），默认 http://localhost:1313
hugo server -D

# 构建生产站点到 public/
hugo --minify
```

## 部署流程

推送到 `master` 分支后，GitHub Actions 会自动构建并发布到 GitHub Pages：

```powershell
git add .
git commit -m "更新文章: xxx"
git push
```

也可以在写作工具里点击"🚀 推送到 GitHub"完成以上操作。

## 目录说明

```text
content/posts/    文章（Markdown + Front Matter）
layouts/          主题覆盖与自定义（播放器、搜索、背景、评论等）
static/images/    文章图片
static/music/     播放器音乐
static/files/     下载页文件（按目录自动列出）
public/           构建产物（已 gitignore，无需手动提交）
```

## 写作提示

- 新文章放在 `content/posts/`，Front Matter 包含 `title`、`date`、`categories`、`tags`、`draft`
- 图片放到 `static/images/` 后，用 `![](/images/文件名)` 引用
- 下载页会自动列出 `static/files/` 下所有文件，新增文件后重新构建即可
