/* =========================================================
 * 主页彩蛋：下滑进入上色版小恐龙游戏
 * 颜色全部取自站点 CSS 变量（--accent 等），自动跟随色板与明暗主题
 * 触发：主页滚轮累计下滚 / 手机下拉 → 先提示一次，再滑一次进入游戏
 * ========================================================= */
(function () {
    'use strict';

    if (window.__dinoGameBound) return;
    window.__dinoGameBound = true;

    var WHEEL_THRESHOLD = 220;   // 滚轮累计下滑量（px）
    var TOUCH_THRESHOLD = 70;    // 手指下拉距离（px）
    var HI_KEY = 'mcryii-dino-hi';

    var state = 'closed';        // closed | opening | open | closing
    var hintShown = false;
    var wheelAccum = 0;
    var wheelTimer = null;
    var touchStartY = 0;
    var lastPoint = null;

    function isHome() {
        return window.location.pathname === '/' || window.location.pathname === '/index.html';
    }

    // 主页内容可滚动，须先滚到底部，继续下滑才算触发手势
    function atBottom() {
        var max = document.documentElement.scrollHeight - window.innerHeight;
        return max <= 0 || window.scrollY >= max - 5;
    }

    function readColors() {
        var cs = getComputedStyle(document.documentElement);
        var dark = document.documentElement.dataset.theme === 'dark';
        return {
            accent: cs.getPropertyValue('--accent').trim() || '#d4af37',
            deep: cs.getPropertyValue('--accent-deep').trim() || '#7a5c00',
            contrast: cs.getPropertyValue('--accent-contrast').trim() || '#241a02',
            rgb: cs.getPropertyValue('--accent-rgb').trim() || '212, 175, 55',
            bg: (dark ? cs.getPropertyValue('--card-bg-dark') : cs.getPropertyValue('--card-bg')).trim() || '#fff',
            dark: dark
        };
    }

    // ---------- 打开 / 关闭（圆形扩散过渡） ----------
    function openGame(x, y) {
        var layer = document.getElementById('dino-layer');
        if (!layer || state !== 'closed') return;
        state = 'opening';
        lastPoint = { x: x, y: y };
        var c = readColors();
        layer.style.background = c.bg;
        document.body.style.overflow = 'hidden';
        layer.hidden = false;
        layer.style.clipPath = 'circle(0px at ' + x + 'px ' + y + 'px)';
        // 强制一次回流，让初始 clip-path 先生效再过渡
        void layer.offsetWidth;
        layer.style.transition = 'clip-path 0.55s cubic-bezier(0.22, 0.61, 0.36, 1)';
        layer.style.clipPath = 'circle(142vmax at ' + x + 'px ' + y + 'px)';
        // 展开动画期间就接好输入，避免玩家点了没反应
        layer.onpointerdown = function (e) {
            if (e.target.closest('#dino-close') || e.target.closest('#dino-theme')) return;
            pressAction();
        };
        var closeBtn = document.getElementById('dino-close');
        if (closeBtn) closeBtn.onclick = function (e) { e.stopPropagation(); closeGame(); };
        var themeBtn = document.getElementById('dino-theme');
        if (themeBtn) themeBtn.onclick = function (e) {
            e.stopPropagation();
            var headerToggle = document.getElementById('theme-toggle');
            if (headerToggle) headerToggle.click();
            pal = readColors(); // 立即换色，下一帧重绘
            layer.style.background = pal.bg;
        };
        setTimeout(function () {
            if (state !== 'opening') return;
            state = 'open';
            layer.style.clipPath = '';
            layer.style.transition = '';
            startGame();
        }, 600);
    }

    function closeGame() {
        var layer = document.getElementById('dino-layer');
        if (!layer || state !== 'open') return;
        state = 'closing';
        stopGame();
        var p = lastPoint || { x: window.innerWidth / 2, y: window.innerHeight / 2 };
        layer.style.transition = 'clip-path 0.45s cubic-bezier(0.4, 0, 1, 1)';
        layer.style.clipPath = 'circle(142vmax at ' + p.x + 'px ' + p.y + 'px)';
        void layer.offsetWidth;
        layer.style.clipPath = 'circle(0px at ' + p.x + 'px ' + p.y + 'px)';
        setTimeout(function () {
            if (state !== 'closing') return;
            layer.hidden = true;
            layer.style.clipPath = '';
            layer.style.transition = '';
            document.body.style.overflow = '';
            state = 'closed';
        }, 500);
    }

    // ---------- 触发提示 ----------
    function showHint() {
        var hint = document.getElementById('dino-hint');
        if (!hint || hint.classList.contains('show')) return;
        hint.classList.add('show');
        setTimeout(function () { hint.classList.remove('show'); }, 2200);
    }

    function trigger(x, y) {
        if (state !== 'closed' || !isHome()) return;
        if (!document.getElementById('dino-layer')) return;
        if (!hintShown) {
            hintShown = true;
            showHint();
            return;
        }
        openGame(x, y);
    }

    // ---------- 手势检测 ----------
    document.addEventListener('wheel', function (e) {
        if (e.ctrlKey || state !== 'closed' || !isHome()) return;
        if (!atBottom()) { wheelAccum = 0; return; }
        if (e.deltaY <= 0) { wheelAccum = 0; return; }
        wheelAccum += e.deltaY;
        if (wheelTimer) clearTimeout(wheelTimer);
        wheelTimer = setTimeout(function () { wheelAccum = 0; }, 500);
        if (wheelAccum >= WHEEL_THRESHOLD) {
            wheelAccum = 0;
            trigger(e.clientX, e.clientY);
        }
    }, { passive: true });

    document.addEventListener('touchstart', function (e) {
        if (state !== 'closed' || !isHome()) return;
        if (!atBottom()) return;
        touchStartY = e.touches[0].clientY;
    }, { passive: true });

    document.addEventListener('touchmove', function (e) {
        if (state !== 'closed' || !isHome() || !touchStartY) return;
        var dy = e.touches[0].clientY - touchStartY;
        if (dy >= TOUCH_THRESHOLD) {
            touchStartY = 0;
            trigger(e.touches[0].clientX, e.touches[0].clientY);
        }
    }, { passive: true });

    document.addEventListener('keydown', function (e) {
        if (state !== 'open' && state !== 'opening') return;
        if (e.code === 'Escape') { e.preventDefault(); closeGame(); return; }
        if (e.code === 'Space' || e.code === 'ArrowUp') { e.preventDefault(); pressAction(); return; }
        if (e.code === 'ArrowDown') { e.preventDefault(); setDuck(true); return; }
    });
    document.addEventListener('keyup', function (e) {
        if (state !== 'open' && state !== 'opening') return;
        if (e.code === 'ArrowDown') setDuck(false);
    });

    // ---------- 游戏本体 ----------
    var GRAVITY = 0.62;   // 重力加速度（px/帧²，按 60fps 归一化）
    var JUMP_V = -12.5;   // 起跳初速度（px/帧）
    var canvas, ctx, W, H, dpr, raf = 0, lastTs = 0, pal = null;
    var dino, obstacles, clouds, dashes, groundY, speed, distance, score, hi, gameOver, running, spawnTimer, pteroTimer, frameCount;

    // ---------- 吉祥物像素画（苍之彼方的四重奏 ω 猫）----------
    // W=白色身体 w=蝙蝠翅膀(主题色) e=眼 m=ω嘴；描边由代码按主题色勾出
    var CAT_A = [
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
        '........WW....WW........'
    ];
    var CAT_B = [
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
        '.........WW....WW.......',
        '........WWW...WWW.......'
    ];
    var CAT_DUCK_A = [
        '.........WW........WW.........',
        '......WWWWWWWWWWWWWWWWWW......',
        '....WWWWWWWWWWWWWWWWWWWWWW....',
        '.wwwWWWWWWWWWWWWWWWWWWWWWW....',
        'wwwwWWWWkkWWeWWWWWeWWkkWWW....',
        'wwwwWWWWWWWWeWWWWWeWWWWWWW....',
        'www.WWWWWWbbWmWmWmWbbWWWWW....',
        '....WWWWWWWWWWmmmWWWWWWWWW....',
        '....WWWWWWWWWWWWWWWWWWWWWW....',
        '......WWWWWWWWWWWWWWWWWW......',
        '..........WW......WW..........',
        '..........WW......WW..........'
    ];
    var CAT_DUCK_B = [
        '.........WW........WW.........',
        '......WWWWWWWWWWWWWWWWWW......',
        '....WWWWWWWWWWWWWWWWWWWWWW....',
        '....WWWWWWWWWWWWWWWWWWWWWW....',
        '....WWWWkkWWeWWWWWeWWkkWWW....',
        '....WWWWWWWWeWWWWWeWWWWWWW....',
        'wwwwWWWWWWbbWmWmWmWbbWWWWW....',
        'wwwwWWWWWWWWWWmmmWWWWWWWWW....',
        'www.WWWWWWWWWWWWWWWWWWWWWW....',
        '......WWWWWWWWWWWWWWWWWW......',
        '...........WW......WW.........',
        '..........WWW.....WWW.........'
    ];

    function startGame() {
        canvas = document.getElementById('dino-canvas');
        var layer = document.getElementById('dino-layer');
        if (!canvas || !layer) return;
        ctx = canvas.getContext('2d');
        pal = readColors();
        hi = parseInt(localStorage.getItem(HI_KEY) || '0', 10) || 0;
        resize();
        resetRun();
        lastTs = 0;
        raf = requestAnimationFrame(loop);
    }

    function stopGame() {
        if (raf) cancelAnimationFrame(raf);
        raf = 0;
    }

    function resize() {
        dpr = Math.min(window.devicePixelRatio || 1, 2);
        W = window.innerWidth;
        H = window.innerHeight;
        canvas.width = W * dpr;
        canvas.height = H * dpr;
        canvas.style.width = W + 'px';
        canvas.style.height = H + 'px';
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        groundY = Math.round(H * 0.82);
    }

    function resetRun() {
        var dinoH = Math.max(46, Math.min(78, Math.round(H * 0.11)));
        dino = {
            x: Math.max(30, Math.round(W * 0.08)),
            y: groundY,
            vy: 0,
            h: dinoH,
            scale: dinoH / 18,
            duck: false,
            jumping: false,
            legFrame: 0
        };
        obstacles = [];
        clouds = [];
        dashes = [];
        speed = 6;
        distance = 0;
        score = 0;
        gameOver = false;
        running = false;
        spawnTimer = 60;
        pteroTimer = 900;
        frameCount = 0;
        for (var i = 0; i < 3; i++) {
            clouds.push({ x: W + Math.random() * W * 0.5, y: H * (0.12 + Math.random() * 0.25), s: 0.8 + Math.random() * 0.6 });
        }
        for (var j = 0; j < 30; j++) {
            dashes.push({ x: Math.random() * W, y: groundY + 8 + Math.random() * (H - groundY - 20), w: 6 + Math.random() * 16 });
        }
    }

    function pressAction() {
        if (!dino) return; // 展开动画期间 dino 尚未初始化
        if (gameOver) {
            resetRun();
            return;
        }
        running = true; // 第一次按键/点击即开跑并起跳
        if (!dino.jumping && !dino.duck) {
            dino.vy = JUMP_V * (dino.scale * 20 / 60); // 随体型微调
            dino.jumping = true;
        }
    }

    function setDuck(on) {
        if (dino && !dino.jumping) dino.duck = on;
    }

    function spawnObstacle() {
        // 150 分起出现翼龙：中飞的要蹲下躲，下蹲才有用武之地
        var isPtero = score > 150 && Math.random() < 0.3;
        if (isPtero) {
            // 低：必须跳过；中：必须蹲下；高：直接跑过
            // 低：必须跳过；中：必须蹲下（按蹲姿实际高度）；高：直接跑过
            var duckH = CAT_DUCK_A.length * dino.scale;
            var heights = [groundY - 24, groundY - duckH - 30, groundY - dino.h * 2.2];
            obstacles.push({
                type: 'ptero',
                x: W + 60,
                y: heights[Math.floor(Math.random() * heights.length)],
                w: 48, h: 28,
                frame: 0
            });
            return;
        }
        var count = 1 + Math.floor(Math.random() * 3);
        var cw = 16 + Math.random() * 8;
        var ch = 34 + Math.random() * 30;
        obstacles.push({
            type: 'cactus',
            x: W + 40,
            y: groundY - ch, // 碰撞盒顶边（盒体向下延伸到地面）
            w: cw * count + (count - 1) * 4,
            h: ch,
            count: count,
            cw: cw
        });
    }

    function update(f) {
        frameCount++;
        if (gameOver || !running) return;
        speed = Math.min(13, 6 + distance * 0.0012);
        distance += speed * f;
        score = Math.floor(distance * 0.05);
        if (score > hi) {
            hi = score;
            localStorage.setItem(HI_KEY, String(hi));
        }

        // 恐龙物理
        if (dino.jumping) {
            dino.vy += GRAVITY * f;
            dino.y += dino.vy * f;
            if (dino.y >= groundY) {
                dino.y = groundY;
                dino.vy = 0;
                dino.jumping = false;
            }
        }
        if (frameCount % 6 === 0) dino.legFrame = 1 - dino.legFrame;

        // 障碍生成与移动
        spawnTimer -= f;
        if (spawnTimer <= 0) {
            spawnObstacle();
            // 间距随速度拉长，保证可反应距离
            spawnTimer = (90 + Math.random() * 90) - Math.min(30, (speed - 6) * 4);
        }
        for (var i = obstacles.length - 1; i >= 0; i--) {
            var o = obstacles[i];
            o.x -= speed * f;
            if (o.type === 'ptero') {
                o.y += Math.sin(frameCount * 0.08) * 0.3;
                if (frameCount % 14 === 0) o.frame = 1 - o.frame;
            }
            if (o.x + o.w < -20) obstacles.splice(i, 1);
        }

        // 云与地面碎纹
        clouds.forEach(function (c) {
            c.x -= speed * 0.25 * f;
            if (c.x < -60) { c.x = W + 40 + Math.random() * W * 0.4; c.y = H * (0.12 + Math.random() * 0.25); }
        });
        dashes.forEach(function (d) {
            d.x -= speed * f;
            if (d.x < -20) { d.x = W + Math.random() * 60; d.y = groundY + 8 + Math.random() * (H - groundY - 20); d.w = 6 + Math.random() * 16; }
        });

        // 碰撞（AABB，收边宽容一点）
        var d = dinoBox();
        for (var k = 0; k < obstacles.length; k++) {
            var ob = obstacles[k];
            var pad = 4;
            if (d.x + pad < ob.x + ob.w && d.x + d.w - pad > ob.x &&
                d.y + pad < ob.y + ob.h && d.y + d.h - pad > ob.y) {
                gameOver = true;
                break;
            }
        }
    }

    function dinoBox() {
        if (dino.duck) {
            var duckH = CAT_DUCK_A.length * dino.scale;
            return { x: dino.x + 4, y: groundY - duckH + 2, w: dino.h * 1.35, h: duckH - 2 };
        }
        // 体型较宽，判定盒比视觉略窄，留宽容度
        return { x: dino.x + 8, y: dino.y - dino.h + 2, w: dino.h * 1.1, h: dino.h - 4 };
    }

    // ---------- 绘制 ----------
    var CAT_BODY = '#fffdf6';  // 吉祥物暖白
    var CAT_FACE = '#453a29';  // 眼睛与 ω 嘴（白身上的深色）

    function cellsOf(c, grid, chars, x, y, scale, color) {
        c.fillStyle = color;
        for (var r = 0; r < grid.length; r++) {
            var row = grid[r];
            for (var cc = 0; cc < row.length; cc++) {
                if (chars.indexOf(row.charAt(cc)) !== -1) {
                    c.fillRect(x + cc * scale, y + r * scale, scale + 0.5, scale + 0.5);
                }
            }
        }
    }

    function drawMascot(c, grid, x, y, scale, p) {
        var off = Math.max(1, Math.round(scale * 0.3));
        // 主题色描边：四向偏移勾边（浅色背景上白色身体也清晰可见）
        cellsOf(c, grid, 'Ww', x + off, y, scale, p.accent);
        cellsOf(c, grid, 'Ww', x - off, y, scale, p.accent);
        cellsOf(c, grid, 'Ww', x, y + off, scale, p.accent);
        cellsOf(c, grid, 'Ww', x, y - off, scale, p.accent);
        cellsOf(c, grid, 'Ww', x, y, scale, p.accent);
        cellsOf(c, grid, 'W', x, y, scale, CAT_BODY);
        cellsOf(c, grid, 'b', x, y, scale, 'rgba(' + p.rgb + ', 0.45)');
        cellsOf(c, grid, 'em', x, y, scale, CAT_FACE);
    }

    function drawDino() {
        var s = dino.scale;
        var x = dino.x;
        if (dino.duck && !dino.jumping) {
            var dg = dino.legFrame ? CAT_DUCK_A : CAT_DUCK_B;
            drawMascot(ctx, dg, x, groundY - dg.length * s, s, pal);
            return;
        }
        var grid = dino.legFrame ? CAT_A : CAT_B;
        drawMascot(ctx, grid, x, dino.y - grid.length * s, s, pal);
    }

    function drawCactus(o) {
        ctx.fillStyle = pal.deep;
        var trunkW = o.cw * 0.38;
        for (var i = 0; i < o.count; i++) {
            var bx = o.x + i * (o.cw + 4);
            var cx = bx + (o.cw - trunkW) / 2;
            var ch = o.h * (0.8 + 0.2 * ((i * 7) % 3) / 2);
            ctx.fillRect(cx, groundY - ch, trunkW, ch);
            var armW = trunkW * 0.7;
            // 左臂
            ctx.fillRect(bx, groundY - ch * 0.72, o.cw * 0.32, armW);
            ctx.fillRect(bx, groundY - ch * 0.72 - ch * 0.22, armW, ch * 0.22 + armW);
            // 右臂
            ctx.fillRect(bx + o.cw * 0.68, groundY - ch * 0.5, o.cw * 0.32, armW);
            ctx.fillRect(bx + o.cw - armW, groundY - ch * 0.5 - ch * 0.18, armW, ch * 0.18 + armW);
        }
    }

    function drawPtero(o) {
        var x = o.x, y = o.y;
        ctx.fillStyle = pal.deep;
        // 身体
        ctx.beginPath();
        ctx.ellipse(x + 20, y + 12, 15, 6, 0, 0, Math.PI * 2);
        ctx.fill();
        // 喙
        ctx.beginPath();
        ctx.moveTo(x + 33, y + 9);
        ctx.lineTo(x + 46, y + 13);
        ctx.lineTo(x + 33, y + 15);
        ctx.closePath();
        ctx.fill();
        // 翅膀（两帧）
        ctx.beginPath();
        if (o.frame === 0) {
            ctx.moveTo(x + 8, y + 11);
            ctx.lineTo(x + 22, y - 8);
            ctx.lineTo(x + 34, y + 11);
        } else {
            ctx.moveTo(x + 8, y + 12);
            ctx.lineTo(x + 22, y + 28);
            ctx.lineTo(x + 34, y + 12);
        }
        ctx.closePath();
        ctx.fill();
        // 眼睛
        ctx.fillStyle = pal.bg;
        ctx.fillRect(x + 27, y + 9, 3, 3);
    }

    function drawCloud(c) {
        var s = c.s;
        ctx.strokeStyle = 'rgba(' + pal.rgb + ', 0.4)';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(c.x, c.y, 10 * s, Math.PI * 1.1, Math.PI * 1.9);
        ctx.arc(c.x + 16 * s, c.y - 4 * s, 9 * s, Math.PI, Math.PI * 1.95);
        ctx.arc(c.x + 32 * s, c.y, 8 * s, Math.PI * 1.05, Math.PI * 1.9);
        ctx.stroke();
    }

    function drawText(text, x, y, size, align, color) {
        ctx.fillStyle = color;
        ctx.font = 'bold ' + size + 'px "Segoe UI", "Microsoft YaHei", sans-serif';
        ctx.textAlign = align;
        ctx.fillText(text, x, y);
    }

    function draw() {
        // 主题/色板若在游戏期间被切换（含游戏外 Alt+T），立即同步颜色
        var darkNow = document.documentElement.dataset.theme === 'dark';
        if (darkNow !== pal.dark) {
            pal = readColors();
            var bgLayer = document.getElementById('dino-layer');
            if (bgLayer) bgLayer.style.background = pal.bg;
        }
        ctx.clearRect(0, 0, W, H);
        // 云
        clouds.forEach(drawCloud);
        // 地面
        ctx.strokeStyle = 'rgba(' + pal.rgb + ', 0.75)';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(0, groundY);
        ctx.lineTo(W, groundY);
        ctx.stroke();
        ctx.fillStyle = 'rgba(' + pal.rgb + ', 0.3)';
        dashes.forEach(function (d) { ctx.fillRect(d.x, d.y, d.w, 2); });

        obstacles.forEach(function (o) {
            if (o.type === 'cactus') drawCactus(o);
            else drawPtero(o);
        });
        drawDino();

        // 分数（避开右上角退出/主题按钮）
        var pad = Math.max(14, Math.round(W * 0.02));
        var scoreStr = String(score).padStart(5, '0');
        var hiStr = String(hi).padStart(5, '0');
        drawText('HI ' + hiStr + '  ' + scoreStr, W - pad - 110, pad + 20, Math.max(14, Math.min(18, W * 0.014)), 'right', 'rgba(' + pal.rgb + ', 0.85)');

        if (!running && !gameOver) {
            drawText('按空格 / 点击 开始', W / 2, H / 2 + 24, Math.max(15, Math.min(20, W * 0.016)), 'center', 'rgba(' + pal.rgb + ', 0.9)');
        }

        if (gameOver) {
            var cx = W / 2, cy = H / 2;
            drawText('G A M E   O V E R', cx, cy - 20, Math.max(22, Math.min(40, W * 0.035)), 'center', pal.accent);
            drawText('按空格 / 点击 重新开始 · Esc 退出', cx, cy + 24, Math.max(13, Math.min(17, W * 0.013)), 'center', 'rgba(' + pal.rgb + ', 0.8)');
            // 重启小图标（三角+圆环）
            ctx.strokeStyle = pal.accent;
            ctx.lineWidth = 3;
            ctx.beginPath();
            ctx.arc(cx, cy + 70, 16, Math.PI * 0.4, Math.PI * 2.2);
            ctx.stroke();
            ctx.fillStyle = pal.accent;
            ctx.beginPath();
            ctx.moveTo(cx + 16, cy + 56);
            ctx.lineTo(cx + 26, cy + 63);
            ctx.lineTo(cx + 14, cy + 69);
            ctx.closePath();
            ctx.fill();
        }
    }

    function loop(ts) {
        if (state !== 'open') return;
        if (!lastTs) lastTs = ts;
        var dt = Math.min(34, ts - lastTs);
        lastTs = ts;
        update(dt / 16.7);
        draw();
        raf = requestAnimationFrame(loop);
    }

    window.addEventListener('resize', function () {
        if (state === 'open') resize();
        flyCtx = null; // 触发飞行画布重设尺寸
        flyUpdate();
    });

    // ---------- 下滑航程：飞行猫（滚动驱动滑翔，落地后提示起飞） ----------
    var flyCv = null, flyCtx = null, flyPal = null, flyOn = false, flyFrame = 0, flyY = -80, flyTrail = [], flyLandShown = false;

    function flySize() {
        if (!flyCtx) return;
        var dpr = Math.min(window.devicePixelRatio || 1, 2);
        flyCv.width = 150 * dpr;
        flyCv.height = window.innerHeight * dpr;
        flyCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function flyLoop() {
        if (!flyOn || !flyCv || !flyCv.isConnected || state !== 'closed') {
            flyOn = false;
            if (flyCv) flyCv.classList.remove('on');
            return;
        }
        flyFrame++;
        // 主题/色板跟随
        var darkNow = document.documentElement.dataset.theme === 'dark';
        if (!flyPal || darkNow !== flyPal.dark) flyPal = readColors();
        // 滚动进度 0→1：从画面上方一路滑到跑道
        var max = document.documentElement.scrollHeight - window.innerHeight;
        var p = max > 0 ? Math.min(1, window.scrollY / max) : 0;
        var target = -70 + p * (window.innerHeight - 20);
        var bob = p >= 1 ? 0 : Math.sin(flyFrame * 0.09) * 7;
        flyY += (target + bob - flyY) * 0.16;
        var catX = window.innerWidth > 900 ? 96 : 66;
        // 金色轨迹
        if (flyFrame % 2 === 0) {
            flyTrail.push(flyY + 20);
            if (flyTrail.length > 24) flyTrail.shift();
        }
        flyCtx.clearRect(0, 0, 150, window.innerHeight);
        flyTrail.forEach(function (ty, i) {
            flyCtx.fillStyle = 'rgba(' + flyPal.rgb + ', ' + (0.04 + 0.3 * i / flyTrail.length).toFixed(3) + ')';
            flyCtx.fillRect(catX + 18, ty, 5, 3);
        });
        var grid = (flyFrame % 20 < 10) ? CAT_A : CAT_B;
        drawMascot(flyCtx, grid, catX, flyY, 2.4, flyPal);
        // 降落到底：提示起飞
        if (p >= 1 && !flyLandShown && state === 'closed') {
            flyLandShown = true;
            hintShown = true;
            showHint();
        }
        requestAnimationFrame(flyLoop);
    }

    function flyUpdate() {
        flyCv = document.getElementById('dino-fly');
        if (!flyCv || !flyCv.isConnected) {
            flyOn = false;
            flyCtx = null;
            return;
        }
        var active = isHome() && state === 'closed' && window.scrollY > 40 && window.innerWidth > 560;
        flyCv.classList.toggle('on', active);
        if (active && !flyOn) {
            if (!flyCtx) {
                flyCtx = flyCv.getContext('2d');
                flySize();
                flyY = -80;
                flyTrail = [];
            }
            flyOn = true;
            requestAnimationFrame(flyLoop);
        }
        if (!active) flyOn = false;
    }

    if (window.MCRYII_ScrollHub) {
        window.MCRYII_ScrollHub.subscribe(function () { flyUpdate(); });
    } else {
        window.addEventListener('scroll', function () { flyUpdate(); }, { passive: true });
    }
})();
