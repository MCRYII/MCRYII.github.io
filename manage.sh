#!/usr/bin/env bash
# ==============================================================================
# MCRYII 博客 WSL 综合管理脚本
# ==============================================================================
set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

show_help() {
    echo "MCRYII 博客管理工具 (WSL Linux 原生)"
    echo "用法: ./manage.sh [命令]"
    echo ""
    echo "可用命令:"
    echo "  serve | s        启动本地预览服务器 (含草稿、自动刷新，默认端口 1313)"
    echo "  build | b        生产环境构建 (产物输出至 public/)"
    echo "  thumbs           为 static/images 生成 640px 缩略图"
    echo "  sync-bili        自动拉取 B 站个人空间最新投稿并生成博客文章"
    echo "  lunar [年份]     生成农历节日数据 (例: ./manage.sh lunar 2027)"
    echo "  tool             启动写作助手网页版 (blog_tool.py --web)"
    echo "  status           查看当前 Hugo 运行状态与 Git 状态"
    echo "  help             显示此帮助信息"
    echo ""
}

case "$1" in
    serve|s)
        shift
        exec ./run.sh "$@"
        ;;
    build|b)
        echo "=== 生成缩略图 ==="
        python3 scripts/gen_thumbs.py
        echo "=== 正在构建生产站点 (hugo --minify) ==="
        hugo --minify
        echo "=== 构建完成！产物位于 public/ ==="
        ;;
    thumbs)
        python3 scripts/gen_thumbs.py
        ;;
    sync-bili)
        python3 scripts/sync_bili_posts.py
        ;;
    lunar)
        shift
        python3 scripts/gen_lunar_events.py "$@"
        ;;
    tool)
        echo "正在启动写作工具网页版..."
        python3 blog_tool.py --web
        ;;
    status)
        echo "=== Hugo 运行进程 ==="
        pgrep -a hugo || echo "Hugo 当前未运行"
        echo ""
        echo "=== Git 状态 ==="
        git status -s
        ;;
    help|--help|-h|"")
        show_help
        ;;
    *)
        echo "未知命令: $1"
        show_help
        exit 1
        ;;
esac
