#!/usr/bin/env bash
# ==============================================================================
# MCRYII 博客 WSL 启动与运行脚本
# ==============================================================================
set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

PORT=1313
URL="http://localhost:$PORT/"

echo "=== [1/4] 终止历史 Hugo 进程 ==="
pkill -f "hugo server" 2>/dev/null || true

echo "=== [2/4] 生成缩略图 ==="
python3 scripts/gen_thumbs.py 2>/dev/null || true

echo "=== [3/4] 检查 assetsVersion 版本号 ==="
python3 scripts/bump_version.py 2>/dev/null || true

# 检查搜索索引时效
INDEX_FILE="$BASE_DIR/public/index.json"
if [ -f "$INDEX_FILE" ]; then
    INDEX_TIME=$(stat -c %Y "$INDEX_FILE" 2>/dev/null || echo 0)
    NEWER_CONTENT=$(find "$BASE_DIR/content" -type f -newermt "@$INDEX_TIME" 2>/dev/null | head -n 1 || true)
    if [ -n "$NEWER_CONTENT" ]; then
        echo "[提醒] content/ 有更新的文件，搜索索引可能过期，建议重新构建 (hugo --minify)"
    fi
fi

echo "=== [4/4] 启动 Hugo 本地预览服务 ==="
echo "博客服务地址: $URL"

if [ "$1" = "--daemon" ]; then
    nohup hugo server -D --port "$PORT" --bind 0.0.0.0 > /tmp/hugo_blog.log 2>&1 &
    echo "Hugo 已在后台启动 (日志: /tmp/hugo_blog.log)"
    for i in $(seq 1 20); do
        if curl -s -o /dev/null --max-time 1 "$URL"; then
            echo "Hugo 本地服务启动成功: $URL"
            break
        fi
        sleep 0.5
    done
    exit 0
else
    exec hugo server -D --port "$PORT" --bind 0.0.0.0
fi
