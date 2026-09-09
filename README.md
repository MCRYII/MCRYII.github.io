# MCRYII 的个人博客

<p align="center">
  <a href="https://www.mcryii.fun/"><img src="https://img.shields.io/badge/Website-www.mcryii.fun-4A90E2?style=flat-square&logo=googlechrome&logoColor=white" alt="Website"></a>
  <a href="https://github.com/MCRYII/MCRYII.github.io/actions/workflows/hugo.yml"><img src="https://img.shields.io/github/actions/workflow/status/MCRYII/MCRYII.github.io/hugo.yml?branch=master&label=Deploy&style=flat-square" alt="Build Status"></a>
  <a href="https://gohugo.io/"><img src="https://img.shields.io/badge/Hugo-Extended_0.162.1-FF4088?style=flat-square&logo=hugo&logoColor=white" alt="Hugo"></a>
  <a href="https://github.com/adityatelange/hugo-PaperMod"><img src="https://img.shields.io/badge/Theme-PaperMod_Enhanced-1E88E5?style=flat-square" alt="Theme"></a>
</p>

基于 [Hugo Extended](https://gohugo.io/) 构建、以 [PaperMod](https://github.com/adityatelange/hugo-PaperMod) 为基底进行深度定制自研的现代化个人博客站点。  
已通过 GitHub Actions 持续集成自动构建并部署至 GitHub Pages，绑定独立域名：[www.mcryii.fun](https://www.mcryii.fun/)。

---

## ✨ 站点特色与功能

- 🎨 **主题配色调色板**：内置 6 套精心配色主题，支持深浅模式与全站强调色联动，本地持久化记忆，全局色彩无刷新热切换。
- 🎮 **首页彩蛋小游戏宇宙**：
  - 首页下滑航程抵达底部展开像素跑道，顺势助跑起跳展开全屏游戏层；
  - 内置 **3 款原生 Canvas 小游戏**，左上角胶囊按钮（`#dino-switch`）无缝即时轮转切换：
    1. **飞行猫避障**：类 Flappy 风格横版飞行，支持动态仰角、喷流粒子顺应与柱/鸟混合障碍；
    2. **恐龙跑酷**：经典像素跑道越障，支持跳跃、下蹲与自适应速度；
    3. **喵喵打地鼠**：3×3 九宫格地洞、时间奖惩与动态难度提速算法、Combo 连击加成，支持触控轻打、鼠标小木锤下砸残影与键盘双布局快捷键（`1~9` / `QWE·ASD·ZXC`）；
  - **吉祥物统一眩晕表情**：三款游戏统一接入痛痛眼（`> <`）与金色旋转碎星受击表现；支持跟随主题色板实时换色。
- 🎵 **全屏沉浸式音乐台**：支持实时音频频谱绘制、同步滚动歌词、自适应音频封面解析与全站常驻迷你播放器。
- 🔍 **高效本地搜索**：基于 Fuse.js 深度定制，支持文章/笔记/动态联合搜索、类型徽标与中英文单词快速检索。
- 💬 **轻量无感知评论**：集成 Cusdis 开源自托管式评论组件，无需复杂授权即可畅所欲言。
- 🖼️ **全套高清图标体系**：全站 UI 统一为金色自绘 SVG 矢量图标；配套带版本防缓存的多分辨率 Favicon 套件（.ico / 16px / 32px / Apple Touch Icon）与微留白吉祥物头像。
- 📱 **多端全方位自适应**：深度优化移动端交互动力学（顺势上滑助跑冲刺、触底防抖浮动容差与响应式提示胶囊）。

---

## 🛠️ 技术栈

| 模块 | 技术选型 | 说明 |
|---|---|---|
| **静态生成器** | [Hugo Extended](https://gohugo.io/) `0.162.1` | 高效极速渲染，支持 SCSS/WebP/资源合并 |
| **主题基底** | [PaperMod](https://github.com/adityatelange/hugo-PaperMod) | 作为 submodule 引入，在上层做全量自定义覆写 |
| **开发环境** | WSL2 (Ubuntu 24.04 Linux) | 原生 Linux 工具链与脚本环境 |
| **本地工具** | Python 3 + Bash | 桌面/网页版写作助手、自动化缩略图生成、B站投稿同步 |
| **部署环境** | GitHub Actions + GitHub Pages | push 到 `master` 自动触发自动化工作流 |

---

## 🚀 本地开发与综合管理（WSL 原生）

项目主目录位于 WSL2 Linux 原生环境（`/home/mcryii/myblog-new`）。推荐在 WSL 环境下通过综合管理脚本进行运维：

```bash
# 启动本地实时热重载开发服务器（默认端口 1313，含草稿）
./manage.sh serve
# 或
./run.sh

# 生产环境完整构建（输出至 public/）
./manage.sh build

# 为 static/images/ 批量生成 640px 缩略图
./manage.sh thumbs

# 自动拉取 B 站个人空间最新投稿并转化为博文
./manage.sh sync-bili

# 生成指定年份农历节日数据（如 2027 年）
./manage.sh lunar 2027

# 启动本地写作助手网页版
./manage.sh tool
```

> [!TIP]
> **Windows 快捷启动**：
> 在 Windows 宿主下可直接双击项目根目录的 `打开博客.bat` 或 `打开博客.ps1`，将自动在后台唤起 WSL 环境启动 Hugo 并自动探测网络健康后唤起默认浏览器。

---

## 📂 目录结构概览

```text
myblog-new/
├── .github/workflows/       # GitHub Actions 持续部署配置 (hugo.yml)
├── content/                 # 博客 Markdown 源文件
│   ├── posts/               # 正式博文
│   ├── notes/               # 便签与笔记本
│   └── dynamic/             # 个人短动态
├── data/                    # 数据驱动源文件 (JSON)
│   ├── changelog.json       # 站内更新日志
│   ├── friends.json         # 友链列表
│   └── planning.json        # 年度规划看板
├── layouts/                 # 页面结构覆写与自定义模板
│   ├── partials/            # 顶栏、底栏、扩展头部 (extend_head.html) 等
│   └── _default/            # 音乐页、更新日志、404 等独立页面模板
├── static/                  # 静态资源文件 (原样复制到发布根目录)
│   ├── images/              # 文章插图、头像及封面
│   ├── js/                  # 核心脚本 (dino-game.js, fly-game.js, mole-game.js 等)
│   └── favicon*             # 多分辨率 Favicon 套件
├── scripts/                 # 辅助与自动化工具集
│   ├── sync_bili_posts.py   # B 站动态/投稿自动同步脚本
│   ├── gen_thumbs.py        # 封面缩略图生成工具
│   └── bump_version.py      # 缓存版本号自增工具
├── manage.sh                # WSL 原生综合管理脚本
├── run.sh                   # WSL 原生启动运行脚本
├── blog_tool.py             # 桌面/网页版写作助手
├── hugo.yaml                # 站点主配置文件
└── README.md                # 仓库说明文档
```

---

## 📝 贡献与维护准则

1. **更新日志优先**：依据站点发布规范，每次向 `master` 分支推送更新前，需在 `data/changelog.json` 的 `entries` 顶部同步追加当次更新记录条目。
2. **规范与文档同步**：完成功能或模板调整后，及时更新本地专享的《指南.md》备忘手册，确保文档始终与当前站点架构真实对应。
3. **安全与本地优先**：所有功能与改动本地验证无误后，再明确执行 Git 提交与远程推送。
