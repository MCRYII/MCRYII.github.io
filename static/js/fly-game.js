/* =========================================================
 * 飞行猫避障小游戏（Flappy Cat）
 * 玩法：猫在空中飞行，支持键盘 ↑↓ / W/S 控制上下移动，或鼠标直接跟随
 * 障碍物：上下立柱（中间留缝隙）+ 飞行翼龙，撞击即死
 * 颜色全部跟随站点 CSS 变量与明暗主题
 * ========================================================= */
(function () {
    'use strict';

    var HI_KEY = 'mcryii-fly-hi';

    var canvas, ctx, W, H, dpr, raf = 0, lastTs = 0, pal = null;
    var cat, obstacles, clouds, particles, speed, score, hi, gameOver, running, spawnTimer, frameCount;
    var keys = { up: false, down: false };
    var isPointerActive = false;
    var pointerTargetY = 0;

    function getShared() {
        return window.__dinoShared || {};
    }

    // ---------- 专属空中飞行形态（苍彼原版萌猫 · 收爪悬浮与扇翅姿态） ----------
    // 100% 保持原版圆滚滚经典体态，去除非飞行模式下的地面迈步踏地，小脚丫整齐收拢悬空
    var CAT_FLY_UP = [
        '......WW........WW......',
        '.....WWWW.....WWWW......',
        '.....WWWWWWWWWWWWWW.....',
        '...wWWWWWWWWWWWWWWWWW...',
        '..wwWWWWWWWWWWWWWWWWW...',
        '.wwwWkkWWeWWWWWeWWkkW...',
        'wwwwWWWWWeWWWWWeWWWWW...',
        'wwwwWWWbbWWWWWWWbbWWW...',
        'wwwWWWWWWWmWmWmWWWWWW...',
        '...WWWWWWWWmmmWWWWWWW...',
        '...WWWWWWWWWWWWWWWWWW...',
        '...WWWWWWWWWWWWWWWWWW...',
        '...WWWWWWWWWWWWWWWWWW...',
        '...WWWWWWWWWWWWWWWWWW...',
        '.....WWWWWWWWWWWWWW.....',
        '......WWWWWWWWWWWW......',
        '........WW....WW........',
        '........................'
    ];

    var CAT_FLY_DOWN = [
        '......WW........WW......',
        '.....WWWW.....WWWW......',
        '.....WWWWWWWWWWWWWW.....',
        '....WWWWWWWWWWWWWWWWW...',
        '....WWWWWWWWWWWWWWWWW...',
        '....WkkWWeWWWWWeWWkkW...',
        '....WWWWWeWWWWWeWWWWW...',
        '....WWWbbWWWWWWWbbWWW...',
        '...WWWWWWWmWmWmWWWWWW...',
        'wwwwWWWWWWWmmmWWWWWWW...',
        'wwwwWWWWWWWWWWWWWWWWW...',
        'wwwwWWWWWWWWWWWWWWWWW...',
        'wwwWWWWWWWWWWWWWWWWWW...',
        '.wwWWWWWWWWWWWWWWWWWW...',
        '.....WWWWWWWWWWWWWW.....',
        '......WWWWWWWWWWWW......',
        '........WW....WW........',
        '........................'
    ];

    function resetGame() {
        var scale = Math.max(1.8, Math.min(3.2, Math.round(H * 0.0038 * 2.2 * 10) / 10));
        var catW = 24 * scale;
        var catH = 18 * scale;
        var startY = Math.round(H * 0.45);

        cat = {
            x: Math.max(40, Math.round(W * 0.16)),
            y: startY,
            targetY: startY,
            vy: 0,
            w: catW,
            h: catH,
            scale: scale,
            tilt: 0
        };

        obstacles = [];
        particles = [];
        clouds = [];
        speed = 4.6;
        score = 0;
        gameOver = false;
        running = false;
        spawnTimer = 40;
        frameCount = 0;
        isPointerActive = false;
        pointerTargetY = startY;

        for (var i = 0; i < 4; i++) {
            clouds.push({
                x: Math.random() * W,
                y: H * (0.08 + Math.random() * 0.75),
                s: 0.7 + Math.random() * 0.7
            });
        }
    }

    function spawnObstacle() {
        var shared = getShared();
        // 分数达标后 28% 几率刷出移动翼龙
        var spawnPtero = score >= 12 && Math.random() < 0.28;

        if (spawnPtero) {
            var pteroH = 28;
            var minY = Math.round(H * 0.12);
            var maxY = Math.round(H * 0.82);
            var py = minY + Math.random() * (maxY - minY);
            obstacles.push({
                type: 'ptero',
                x: W + 50,
                y: py,
                baseY: py,
                w: 48,
                h: pteroH,
                frame: 0,
                wave: Math.random() * Math.PI * 2,
                passed: false
            });
            return;
        }

        // 立柱障碍（上下留缝隙）
        var pillarW = Math.max(48, Math.min(74, Math.round(W * 0.052)));
        // 缝隙高度：初始为猫身高的 3.4 倍，随分数平滑收紧至 2.45 倍
        var gapH = Math.max(cat.h * 2.45, cat.h * (3.4 - Math.min(0.95, score * 0.02)));
        var padY = Math.round(H * 0.12);
        var gapY = padY + Math.random() * (H - padY * 2 - gapH);

        obstacles.push({
            type: 'pillar',
            x: W + 50,
            w: pillarW,
            gapY: gapY,
            gapH: gapH,
            passed: false
        });
    }

    function update(f) {
        frameCount++;
        if (gameOver || !running) {
            // 待机轻微浮动
            if (!gameOver && cat) {
                cat.y = cat.targetY + Math.sin(frameCount * 0.06) * 6;
                cat.tilt = Math.sin(frameCount * 0.06) * 0.06;
            }
            return;
        }

        // 难度平缓递增
        speed = Math.min(10.5, 4.6 + score * 0.08);

        // ---------- 猫运动学 ----------
        if (isPointerActive) {
            // 鼠标跟随模式：柔和逼近目标 Y 并计算瞬时速度
            var dy = pointerTargetY - cat.y;
            var oldY = cat.y;
            cat.y += dy * 0.16;
            cat.vy = (cat.y - oldY) / Math.max(0.1, f);
        } else {
            // 键盘控制模式
            var moveSpeed = 6.8;
            if (keys.up && !keys.down) {
                cat.vy = -moveSpeed;
            } else if (keys.down && !keys.up) {
                cat.vy = moveSpeed;
            } else {
                cat.vy *= 0.65;
            }
            cat.y += cat.vy * f;
        }

        // 动态飞行仰角（向上爬升仰头，向下俯冲低头，最大 ±18 度）
        var targetTilt = Math.max(-0.32, Math.min(0.32, cat.vy * 0.045));
        cat.tilt = (cat.tilt || 0) + (targetTilt - (cat.tilt || 0)) * 0.22;

        // 边界限制（不可超出天空和地面，保留边距）
        var minY = 14;
        var maxY = H - cat.h - 14;
        if (cat.y < minY) { cat.y = minY; cat.vy = 0; }
        if (cat.y > maxY) { cat.y = maxY; cat.vy = 0; }

        // ---------- 尾部金色粒子喷射（根据身体倾角动态顺应后方） ----------
        if (frameCount % 2 === 0) {
            var cosT = Math.cos(cat.tilt);
            var sinT = Math.sin(cat.tilt);
            var mcx = cat.x + cat.w / 2;
            var mcy = cat.y + cat.h / 2;
            var lx = -cat.w * 0.42;
            var ly = cat.h * 0.10 + (Math.random() - 0.5) * 6;
            var px = mcx + lx * cosT - ly * sinT;
            var py = mcy + lx * sinT + ly * cosT;

            particles.push({
                x: px,
                y: py,
                vx: -speed * 0.45 * cosT - Math.random() * 1.5,
                vy: -speed * 0.45 * sinT + (Math.random() - 0.5) * 1.5,
                life: 1.0,
                size: 2.2 + Math.random() * 2.5
            });
        }
        for (var pIdx = particles.length - 1; pIdx >= 0; pIdx--) {
            var pt = particles[pIdx];
            pt.x += pt.vx;
            pt.y += pt.vy;
            pt.life -= 0.05;
            if (pt.life <= 0) particles.splice(pIdx, 1);
        }

        // ---------- 障碍物生成与移动 ----------
        spawnTimer -= f;
        if (spawnTimer <= 0) {
            spawnObstacle();
            // 柱间距随速度动态调整，确保始终有充足反应距离
            spawnTimer = (120 + Math.random() * 60) - Math.min(45, (speed - 4.6) * 5);
        }

        for (var i = obstacles.length - 1; i >= 0; i--) {
            var ob = obstacles[i];
            ob.x -= speed * f;

            if (ob.type === 'ptero') {
                ob.y = ob.baseY + Math.sin(frameCount * 0.08 + ob.wave) * 22;
                if (frameCount % 12 === 0) ob.frame = 1 - ob.frame;
            }

            // 得分判定（通过障碍物）
            if (!ob.passed && ob.x + ob.w < cat.x) {
                ob.passed = true;
                score++;
                if (score > hi) {
                    hi = score;
                    localStorage.setItem(HI_KEY, String(hi));
                }
            }

            if (ob.x + ob.w < -60) {
                obstacles.splice(i, 1);
            }
        }

        // ---------- 云层流动 ----------
        clouds.forEach(function (c) {
            c.x -= speed * 0.22 * f;
            if (c.x < -80) {
                c.x = W + 40 + Math.random() * W * 0.4;
                c.y = H * (0.08 + Math.random() * 0.75);
            }
        });

        // ---------- 碰撞判定（AABB + 边缘宽容度） ----------
        var pad = 4;
        var catBox = {
            x: cat.x + pad + 2,
            y: cat.y + pad,
            w: cat.w - (pad + 2) * 2,
            h: cat.h - pad * 2
        };

        for (var k = 0; k < obstacles.length; k++) {
            var o = obstacles[k];
            if (o.type === 'pillar') {
                // 上立柱
                if (aabb(catBox, { x: o.x, y: 0, w: o.w, h: o.gapY })) {
                    gameOver = true;
                    break;
                }
                // 下立柱
                if (aabb(catBox, { x: o.x, y: o.gapY + o.gapH, w: o.w, h: H - (o.gapY + o.gapH) })) {
                    gameOver = true;
                    break;
                }
            } else if (o.type === 'ptero') {
                if (aabb(catBox, { x: o.x + 6, y: o.y + 4, w: o.w - 12, h: o.h - 8 })) {
                    gameOver = true;
                    break;
                }
            }
        }
    }

    function aabb(r1, r2) {
        return r1.x < r2.x + r2.w &&
               r1.x + r1.w > r2.x &&
               r1.y < r2.y + r2.h &&
               r1.y + r1.h > r2.y;
    }

    // ---------- 绘制 ----------
    function drawPillar(o) {
        var capH = 14;
        var capOver = 4;

        // 顶部立柱
        var topH = o.gapY;
        if (topH > 0) {
            // 柱体
            ctx.fillStyle = 'rgba(' + pal.rgb + ', 0.12)';
            ctx.fillRect(o.x, 0, o.w, topH);
            ctx.strokeStyle = 'rgba(' + pal.rgb + ', 0.65)';
            ctx.lineWidth = 2;
            ctx.strokeRect(o.x, -2, o.w, topH + 2);

            // 柱头端帽
            ctx.fillStyle = pal.accent;
            ctx.fillRect(o.x - capOver, topH - capH, o.w + capOver * 2, capH);
        }

        // 底部立柱
        var botY = o.gapY + o.gapH;
        var botH = H - botY;
        if (botH > 0) {
            // 柱体
            ctx.fillStyle = 'rgba(' + pal.rgb + ', 0.12)';
            ctx.fillRect(o.x, botY, o.w, botH);
            ctx.strokeStyle = 'rgba(' + pal.rgb + ', 0.65)';
            ctx.lineWidth = 2;
            ctx.strokeRect(o.x, botY, o.w, botH + 2);

            // 柱头端帽
            ctx.fillStyle = pal.accent;
            ctx.fillRect(o.x - capOver, botY, o.w + capOver * 2, capH);
        }
    }

    function draw() {
        var shared = getShared();
        if (!ctx || !pal) return;

        // 动态跟随全局深浅主题与色板切换
        var curThemeKey = (document.documentElement.dataset.theme || 'light') + '|' + (document.documentElement.dataset.palette || 'gold');
        if ((!pal || curThemeKey !== pal.themeKey) && shared.readColors) {
            pal = shared.readColors();
            var bgLayer = document.getElementById('dino-layer');
            if (bgLayer) bgLayer.style.background = pal.bg;
        }

        ctx.clearRect(0, 0, W, H);

        // 背景云层
        if (shared.drawCloud) {
            clouds.forEach(function (c) { shared.drawCloud(c, ctx, pal); });
        }

        // 天空/地面边界能量弱虚线
        ctx.strokeStyle = 'rgba(' + pal.rgb + ', 0.22)';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([8, 8]);
        ctx.beginPath();
        ctx.moveTo(0, 12);
        ctx.lineTo(W, 12);
        ctx.moveTo(0, H - 12);
        ctx.lineTo(W, H - 12);
        ctx.stroke();
        ctx.setLineDash([]);

        // 障碍物
        obstacles.forEach(function (o) {
            if (o.type === 'pillar') {
                drawPillar(o);
            } else if (o.type === 'ptero' && shared.drawPtero) {
                shared.drawPtero(o, ctx, pal);
            }
        });

        // 飞行金色粒子
        particles.forEach(function (pt) {
            ctx.fillStyle = 'rgba(' + pal.rgb + ', ' + (pt.life * 0.7).toFixed(2) + ')';
            ctx.fillRect(pt.x, pt.y, pt.size, pt.size);
        });

        // 吉祥物飞行猫（专属飞行形态：收拢后肢滑翔 + 大翅膀上下扇动 + 动态俯仰倾角）
        if (cat && shared.drawMascot) {
            var grid;
            if (gameOver && shared.CAT_FLY_HIT) {
                grid = shared.CAT_FLY_HIT;
            } else {
                grid = (frameCount % 14 < 7) ? CAT_FLY_UP : CAT_FLY_DOWN;
            }
            var cx = cat.x + cat.w / 2;
            var cy = cat.y + cat.h / 2;
            ctx.save();
            ctx.translate(cx, cy);
            ctx.rotate(cat.tilt || 0);
            shared.drawMascot(ctx, grid, -cat.w / 2, -cat.h / 2, cat.scale, pal);
            ctx.restore();
        }

        // 分数（右上角，避开右上角关闭/主题按钮）
        var pad = Math.max(14, Math.round(W * 0.02));
        var scoreStr = String(score).padStart(5, '0');
        var hiStr = String(hi).padStart(5, '0');
        if (shared.drawText) {
            shared.drawText('HI ' + hiStr + '  ' + scoreStr, W - pad - 110, pad + 20, Math.max(14, Math.min(18, W * 0.014)), 'right', 'rgba(' + pal.rgb + ', 0.85)', ctx);
        }

        // 待机未开始提示
        if (!running && !gameOver && shared.drawText) {
            shared.drawText('按 ↑ / ↓ 或 移动鼠标控制飞行', W / 2, H / 2, Math.max(16, Math.min(22, W * 0.018)), 'center', pal.accent, ctx);
            shared.drawText('点击屏幕 / 按空格 开始游戏', W / 2, H / 2 + 32, Math.max(13, Math.min(16, W * 0.013)), 'center', 'rgba(' + pal.rgb + ', 0.85)', ctx);
        }

        // Game Over 界面
        if (gameOver && shared.drawText) {
            var cx = W / 2, cy = H / 2;
            shared.drawText('G A M E   O V E R', cx, cy - 22, Math.max(22, Math.min(40, W * 0.035)), 'center', pal.accent, ctx);
            shared.drawText('得分：' + score + '  ·  最高纪录：' + hi, cx, cy + 18, Math.max(14, Math.min(18, W * 0.014)), 'center', 'rgba(' + pal.rgb + ', 0.9)', ctx);
            shared.drawText('点击屏幕 / 按空格 重新开始 · Esc 退出', cx, cy + 46, Math.max(12, Math.min(15, W * 0.012)), 'center', 'rgba(' + pal.rgb + ', 0.7)', ctx);

            // 重新开始环形图标（精准咬合的顺时针循环箭头）
            var arcCx = cx;
            var arcCy = cy + 88;
            var arcR = 15;
            var startA = Math.PI * 0.25;
            var endA = Math.PI * 1.82;

            ctx.strokeStyle = pal.accent;
            ctx.lineWidth = 3;
            ctx.lineCap = 'round';
            ctx.beginPath();
            ctx.arc(arcCx, arcCy, arcR, startA, endA, false);
            ctx.stroke();

            // 终点切线方向动态对接三角形箭头
            var endX = arcCx + arcR * Math.cos(endA);
            var endY = arcCy + arcR * Math.sin(endA);
            var tangent = endA + Math.PI / 2;
            var tipX = endX + 8 * Math.cos(tangent);
            var tipY = endY + 8 * Math.sin(tangent);
            var leftX = endX + 5.5 * Math.cos(tangent - Math.PI * 0.72);
            var leftY = endY + 5.5 * Math.sin(tangent - Math.PI * 0.72);
            var rightX = endX + 5.5 * Math.cos(tangent + Math.PI * 0.72);
            var rightY = endY + 5.5 * Math.sin(tangent + Math.PI * 0.72);

            ctx.fillStyle = pal.accent;
            ctx.beginPath();
            ctx.moveTo(tipX, tipY);
            ctx.lineTo(leftX, leftY);
            ctx.lineTo(rightX, rightY);
            ctx.closePath();
            ctx.fill();
        }
    }

    function loop(ts) {
        if (!raf) return;
        if (!lastTs) lastTs = ts;
        var dt = Math.min(34, ts - lastTs);
        lastTs = ts;
        update(dt / 16.7);
        draw();
        raf = requestAnimationFrame(loop);
    }

    // ---------- 对外接口 ----------
    var flyGame = {
        name: '飞行猫',
        start: function (cv, cx, p) {
            canvas = cv;
            ctx = cx;
            pal = p;
            hi = parseInt(localStorage.getItem(HI_KEY) || '0', 10) || 0;
            W = window.innerWidth;
            H = window.innerHeight;
            resetGame();
            lastTs = 0;
            if (raf) cancelAnimationFrame(raf);
            raf = requestAnimationFrame(loop);
        },
        stop: function () {
            if (raf) cancelAnimationFrame(raf);
            raf = 0;
            keys.up = false;
            keys.down = false;
            isPointerActive = false;
        },
        resize: function (newW, newH) {
            W = newW;
            H = newH;
            if (cat) {
                var scale = Math.max(1.8, Math.min(3.2, Math.round(H * 0.0038 * 2.2 * 10) / 10));
                cat.scale = scale;
                cat.w = 24 * scale;
                cat.h = 18 * scale;
                cat.x = Math.max(40, Math.round(W * 0.16));
            }
        },
        setPal: function (p) {
            pal = p;
        },
        pressAction: function () {
            if (gameOver) {
                resetGame();
                running = true;
                return;
            }
            if (!running) {
                running = true;
            }
        },
        onKeyDown: function (e) {
            if (e.code === 'ArrowUp' || e.code === 'KeyW') {
                e.preventDefault();
                keys.up = true;
                isPointerActive = false;
                if (!running && !gameOver) running = true;
            } else if (e.code === 'ArrowDown' || e.code === 'KeyS') {
                e.preventDefault();
                keys.down = true;
                isPointerActive = false;
                if (!running && !gameOver) running = true;
            } else if (e.code === 'Space') {
                e.preventDefault();
                this.pressAction();
            }
        },
        onKeyUp: function (e) {
            if (e.code === 'ArrowUp' || e.code === 'KeyW') {
                keys.up = false;
            } else if (e.code === 'ArrowDown' || e.code === 'KeyS') {
                keys.down = false;
            }
        },
        onPointerMove: function (e) {
            isPointerActive = true;
            if (cat) {
                pointerTargetY = e.clientY - cat.h / 2;
            }
        },
        setPal: function (p) {
            pal = p;
            var bgLayer = document.getElementById('dino-layer');
            if (bgLayer) bgLayer.style.background = pal.bg;
        },
        onPointerLeave: function () {
            isPointerActive = false;
        }
    };

    window.__flyGame = flyGame;

    // 注册到通用游戏管理器
    window.__gameManager = window.__gameManager || {
        gameList: ['fly', 'dino', 'mole'],
        games: {},
        current: 'fly',
        register: function (id, gameObj) {
            this.games[id] = gameObj;
            if (this.gameList.indexOf(id) === -1) this.gameList.push(id);
        }
    };
    window.__gameManager.register('fly', flyGame);
})();
