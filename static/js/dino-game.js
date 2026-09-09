/* =========================================================
 * 主页彩蛋：下滑进入上色版小恐龙游戏
 * 颜色全部取自站点 CSS 变量（--accent 等），自动跟随色板与明暗主题
 * 触发：主页滚轮累计下滚 / 手机下拉 → 先提示一次，再滑一次进入游戏
 * ========================================================= */
(function () {
    'use strict';

    if (window.__dinoGameBound) return;
    window.__dinoGameBound = true;

    var WHEEL_THRESHOLD = 320;   // 首次提示滚轮量（px）
    var TOUCH_THRESHOLD = 90;    // 首次提示手指下拉量（px）
    var WHEEL_SWEEP_MAX = 520;   // 跟手展开满屏所需滚轮量（px）
    var TOUCH_SWEEP_MAX = 240;   // 跟手展开满屏所需触控下拉量（px）
    var HI_KEY = 'mcryii-dino-hi';
    var RUN_WHEEL_MAX = 4800;    // 跑道助跑所需滚轮累计量（提速一倍至4800，黄金手感约10~14下）
    var RUN_TOUCH_MAX = 1200;    // 跑道助跑所需触控下拉量（提速一倍至1200）

    var state = 'closed';        // closed | opening | open | closing
    var hintShown = false;
    var runAccum = 0;
    var lastInputTime = 0;
    var bottomReachedTime = 0;   // 触底时间戳（用于过滤滚轮触底惯性）
    var touchStartY = 0;
    var touchLastY = 0;
    var takeoffDone = false;
    var lastPoint = null;

    // iOS Safari 不理 body overflow:hidden，改用 fixed 定位锁滚动（记录位移，解锁时还原）
    var lockScrollY = 0;
    function lockBodyScroll() {
        if (document.body.style.position === 'fixed') return;
        lockScrollY = window.scrollY || window.pageYOffset;
        document.body.style.position = 'fixed';
        document.body.style.top = -lockScrollY + 'px';
        document.body.style.left = '0';
        document.body.style.right = '0';
    }
    function unlockBodyScroll() {
        if (document.body.style.position !== 'fixed') return;
        document.body.style.position = '';
        document.body.style.top = '';
        document.body.style.left = '';
        document.body.style.right = '';
        window.scrollTo(0, lockScrollY);
    }

    function isHome() {
        return window.location.pathname === '/' || window.location.pathname === '/index.html';
    }

    // 主页内容可滚动，须先滚到底部，继续滑动才算触发手势（放宽至 15px 兼容移动端地址栏浮动）
    function atBottom() {
        var max = document.documentElement.scrollHeight - window.innerHeight;
        return max <= 0 || window.scrollY >= max - 15;
    }

    function readColors() {
        var cs = getComputedStyle(document.documentElement);
        var dark = document.documentElement.dataset.theme === 'dark';
        var palette = document.documentElement.dataset.palette || 'gold';
        return {
            accent: cs.getPropertyValue('--accent').trim() || '#d4af37',
            deep: cs.getPropertyValue('--accent-deep').trim() || '#7a5c00',
            contrast: cs.getPropertyValue('--accent-contrast').trim() || '#241a02',
            rgb: cs.getPropertyValue('--accent-rgb').trim() || '212, 175, 55',
            bg: (dark ? cs.getPropertyValue('--card-bg-dark') : cs.getPropertyValue('--card-bg')).trim() || '#fff',
            dark: dark,
            palette: palette,
            themeKey: (dark ? 'dark' : 'light') + '|' + palette
        };
    }

    // ---------- 打开 / 关闭（极度丝滑的圆形扩散过渡） ----------
    function openGame(x, y) {
        var layer = document.getElementById('dino-layer');
        if (!layer || state !== 'closed') return;
        state = 'opening';
        var cx = (typeof x === 'number' && x >= 0) ? x : window.innerWidth / 2;
        var cy = (typeof y === 'number' && y >= 0) ? y : window.innerHeight / 2;
        lastPoint = { x: cx, y: cy };
        var c = readColors();
        layer.style.background = c.bg;
        lockBodyScroll();
        layer.hidden = false;
        layer.style.clipPath = 'circle(0px at ' + cx + 'px ' + cy + 'px)';
        void layer.offsetWidth;
        // 0.85s 超柔和减速缓动（如丝般顺滑展开铺满全屏）
        layer.style.transition = 'clip-path 0.85s cubic-bezier(0.16, 1, 0.3, 1)';
        layer.style.clipPath = 'circle(142vmax at ' + cx + 'px ' + cy + 'px)';

        layer.onpointerdown = function (e) {
            if (e.target.closest('#dino-close') || e.target.closest('#dino-theme') || e.target.closest('#dino-switch')) return;
            handlePress();
        };
        layer.onpointermove = function (e) {
            handlePointerMove(e);
        };
        layer.onpointerleave = function (e) {
            handlePointerLeave(e);
        };

        var closeBtn = document.getElementById('dino-close');
        if (closeBtn) closeBtn.onclick = function (e) { e.stopPropagation(); closeGame(); };
        var themeBtn = document.getElementById('dino-theme');
        if (themeBtn) themeBtn.onclick = function (e) {
            e.stopPropagation();
            var headerToggle = document.getElementById('theme-toggle');
            if (headerToggle) headerToggle.click();
            pal = readColors();
            if (layer) layer.style.background = pal.bg;
            handleTheme(pal);
        };
        var switchBtn = document.getElementById('dino-switch');
        if (switchBtn) switchBtn.onclick = function (e) {
            e.stopPropagation();
            if (window.__gameManager) window.__gameManager.cycleGame();
        };

        setTimeout(function () {
            if (state !== 'opening') return;
            state = 'open';
            layer.style.clipPath = '';
            layer.style.transition = '';
            startGame();
        }, 880);
    }

    function closeGame() {
        var layer = document.getElementById('dino-layer');
        if (!layer || state !== 'open') return;
        state = 'closing';
        stopGame();
        layer.onpointermove = null;
        layer.onpointerleave = null;
        var p = lastPoint || { x: window.innerWidth / 2, y: window.innerHeight / 2 };
        var maxR = Math.ceil(Math.hypot(
            Math.max(p.x, window.innerWidth - p.x),
            Math.max(p.y, window.innerHeight - p.y)
        ));
        layer.style.transition = 'clip-path 0.45s cubic-bezier(0.4, 0, 1, 1)';
        layer.style.clipPath = 'circle(' + maxR + 'px at ' + p.x + 'px ' + p.y + 'px)';
        void layer.offsetWidth;
        layer.style.clipPath = 'circle(0px at ' + p.x + 'px ' + p.y + 'px)';
        setTimeout(function () {
            if (state !== 'closing') return;
            layer.hidden = true;
            layer.style.clipPath = '';
            layer.style.transition = '';
            unlockBodyScroll();
            state = 'closed';
            runAccum = 0;
            takeoffDone = false;
        }, 480);
    }

    // ---------- 触发提示 ----------
    function showHint() {
        var hint = document.getElementById('dino-hint');
        if (!hint || hint.classList.contains('show')) return;
        hint.classList.add('show');
        setTimeout(function () { hint.classList.remove('show'); }, 2600);
    }

    // ---------- 底部下滑手势检测（驱动跑道冲刺） ----------
    document.addEventListener('wheel', function (e) {
        if (e.ctrlKey || !isHome()) return;
        if (state !== 'closed') return;
        if (!atBottom()) return;

        // 过滤刚滚到底部的残余滚轮惯性（必须停稳超过 250ms 才开始接收助跑手势）
        if (runAccum === 0 && bottomReachedTime && (performance.now() - bottomReachedTime < 250)) {
            return;
        }

        lastInputTime = performance.now();
        if (e.deltaY > 0) {
            var clamped = Math.min(e.deltaY, 90);
            runAccum = Math.min(RUN_WHEEL_MAX, runAccum + clamped);
        } else if (e.deltaY < 0) {
            var clampedUp = Math.max(e.deltaY, -110);
            runAccum = Math.max(0, runAccum + clampedUp * 1.5);
        }
    }, { passive: true });

    document.addEventListener('touchstart', function (e) {
        if (!isHome() || state !== 'closed' || !atBottom()) return;
        touchStartY = e.touches[0].clientY;
        touchLastY = touchStartY;
        lastInputTime = performance.now();
    }, { passive: true });

    document.addEventListener('touchmove', function (e) {
        if (!isHome() || state !== 'closed') return;
        if (!atBottom()) { touchStartY = 0; return; }

        if (runAccum === 0 && bottomReachedTime && (performance.now() - bottomReachedTime < 250)) {
            return;
        }

        var curY = e.touches[0].clientY;
        // 移动端触控：手指向上划（curY < touchLastY，即 touchDelta > 0）代表顺着浏览方向继续向前冲刺
        var touchDelta = touchLastY - curY;
        touchLastY = curY;
        lastInputTime = performance.now();

        if (touchDelta > 0) {
            // 手指持续向上推：推进跑道冲刺并起飞，阻止移动端原生过度滚动与页面反弹
            if (e.cancelable) e.preventDefault();
            var clamped = Math.min(touchDelta, 60);
            runAccum = Math.min(RUN_WHEEL_MAX, runAccum + clamped * (RUN_WHEEL_MAX / RUN_TOUCH_MAX));
        } else if (touchDelta < 0) {
            // 手指往下拉：若已有冲刺蓄力，优先平滑回退冲刺（防误触）
            if (runAccum > 0) {
                if (e.cancelable) e.preventDefault();
                var clampedDown = Math.max(touchDelta, -80);
                runAccum = Math.max(0, runAccum + clampedDown * 2);
            }
            // 若 runAccum 为 0，不 preventDefault，允许移动端原生平滑向页面上方回滚
        }
    }, { passive: false });

    document.addEventListener('touchend', function () {
        touchStartY = 0;
    }, { passive: true });

    function handlePress() {
        if (window.__gameManager) {
            var active = window.__gameManager.getActive();
            if (active && active.pressAction) {
                active.pressAction();
                return;
            }
        }
        pressAction();
    }

    function handlePointerMove(e) {
        if (window.__gameManager) {
            var active = window.__gameManager.getActive();
            if (active && active.onPointerMove) active.onPointerMove(e);
        }
    }

    function handlePointerLeave(e) {
        if (window.__gameManager) {
            var active = window.__gameManager.getActive();
            if (active && active.onPointerLeave) active.onPointerLeave(e);
        }
    }

    function handleTheme(p) {
        if (window.__gameManager) {
            var active = window.__gameManager.getActive();
            if (active && active.setPal) active.setPal(p);
        }
    }

    document.addEventListener('keydown', function (e) {
        if (state !== 'open') return;
        if (e.code === 'Escape') { e.preventDefault(); closeGame(); return; }
        if (window.__gameManager) {
            var active = window.__gameManager.getActive();
            if (active && active.onKeyDown) {
                active.onKeyDown(e);
                return;
            }
        }
        if (e.code === 'Space' || e.code === 'ArrowUp') { e.preventDefault(); pressAction(); return; }
        if (e.code === 'ArrowDown') { e.preventDefault(); setDuck(true); return; }
    });
    document.addEventListener('keyup', function (e) {
        if (state !== 'open') return;
        if (window.__gameManager) {
            var active = window.__gameManager.getActive();
            if (active && active.onKeyUp) {
                active.onKeyUp(e);
                return;
            }
        }
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

    // 专属空中飞行悬浮姿态：两腿不交替迈步，两只小脚整齐收拢悬空，翅膀上下扇动
    var CAT_FLY_A = [
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
    var CAT_FLY_B = [
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

    function startDino() {
        hi = parseInt(localStorage.getItem(HI_KEY) || '0', 10) || 0;
        resetRun();
        lastTs = 0;
        if (raf) cancelAnimationFrame(raf);
        raf = requestAnimationFrame(loop);
    }

    function stopDino() {
        if (raf) cancelAnimationFrame(raf);
        raf = 0;
    }

    function startGame() {
        canvas = document.getElementById('dino-canvas');
        var layer = document.getElementById('dino-layer');
        if (!canvas || !layer) return;
        ctx = canvas.getContext('2d');
        pal = readColors();
        resize();
        if (window.__gameManager) {
            window.__gameManager.updateSwitchBtn();
            var active = window.__gameManager.getActive();
            if (active && active.start) {
                active.start(canvas, ctx, pal);
                return;
            }
        }
        startDino();
    }

    function stopGame() {
        if (window.__gameManager) {
            var active = window.__gameManager.getActive();
            if (active && active.stop) {
                active.stop();
                return;
            }
        }
        stopDino();
    }

    function resize() {
        dpr = Math.min(window.devicePixelRatio || 1, 2);
        W = window.innerWidth;
        H = window.innerHeight;
        if (canvas) {
            canvas.width = W * dpr;
            canvas.height = H * dpr;
            canvas.style.width = W + 'px';
            canvas.style.height = H + 'px';
            if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        }
        groundY = Math.round(H * 0.82);
        if (window.__gameManager) {
            var active = window.__gameManager.getActive();
            if (active && active.resize) active.resize(W, H, groundY);
        }
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

    function drawPtero(o, targetCtx, targetPal) {
        var cx = (targetCtx && targetCtx.canvas) ? targetCtx : ctx;
        var p = (targetPal && targetPal.rgb) ? targetPal : pal;
        var x = o.x, y = o.y;
        cx.fillStyle = p.deep;
        // 身体
        cx.beginPath();
        cx.ellipse(x + 20, y + 12, 15, 6, 0, 0, Math.PI * 2);
        cx.fill();
        // 喙
        cx.beginPath();
        cx.moveTo(x + 33, y + 9);
        cx.lineTo(x + 46, y + 13);
        cx.lineTo(x + 33, y + 15);
        cx.closePath();
        cx.fill();
        // 翅膀（两帧）
        cx.beginPath();
        if (o.frame === 0) {
            cx.moveTo(x + 8, y + 11);
            cx.lineTo(x + 22, y - 8);
            cx.lineTo(x + 34, y + 11);
        } else {
            cx.moveTo(x + 8, y + 12);
            cx.lineTo(x + 22, y + 28);
            cx.lineTo(x + 34, y + 12);
        }
        cx.closePath();
        cx.fill();
        // 眼睛
        cx.fillStyle = p.bg;
        cx.fillRect(x + 27, y + 9, 3, 3);
    }

    function drawCloud(c, targetCtx, targetPal) {
        var cx = (targetCtx && targetCtx.canvas) ? targetCtx : ctx;
        var p = (targetPal && targetPal.rgb) ? targetPal : pal;
        var s = c.s;
        cx.strokeStyle = 'rgba(' + p.rgb + ', 0.4)';
        cx.lineWidth = 2;
        cx.beginPath();
        cx.arc(c.x, c.y, 10 * s, Math.PI * 1.1, Math.PI * 1.9);
        cx.arc(c.x + 16 * s, c.y - 4 * s, 9 * s, Math.PI, Math.PI * 1.95);
        cx.arc(c.x + 32 * s, c.y, 8 * s, Math.PI * 1.05, Math.PI * 1.9);
        cx.stroke();
    }

    function drawText(text, x, y, size, align, color, targetCtx) {
        var cx = (targetCtx && targetCtx.canvas) ? targetCtx : ctx;
        cx.fillStyle = color;
        cx.font = 'bold ' + size + 'px "Segoe UI", "Microsoft YaHei", sans-serif';
        cx.textAlign = align;
        cx.fillText(text, x, y);
    }

    function draw() {
        // 主题/色板若在游戏期间被切换（含游戏外 Alt+T 或色板点击），立即同步颜色
        var curThemeKey = (document.documentElement.dataset.theme || 'light') + '|' + (document.documentElement.dataset.palette || 'gold');
        if (!pal || curThemeKey !== pal.themeKey) {
            pal = readColors();
            var bgLayer = document.getElementById('dino-layer');
            if (bgLayer) bgLayer.style.background = pal.bg;
        }
        ctx.clearRect(0, 0, W, H);
        // 云
        clouds.forEach(function (c) { drawCloud(c); });
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
            // 重启小图标（精准咬合的顺时针循环箭头）
            var arcCx = cx;
            var arcCy = cy + 70;
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
        if (state !== 'open') return;
        if (!lastTs) lastTs = ts;
        var dt = Math.min(34, ts - lastTs);
        lastTs = ts;
        update(dt / 16.7);
        draw();
        raf = requestAnimationFrame(loop);
    }

    // ---------- 导出共享绘制能力与像素数据 ----------
    window.__dinoShared = {
        CAT_A: CAT_A,
        CAT_B: CAT_B,
        CAT_DUCK_A: CAT_DUCK_A,
        CAT_DUCK_B: CAT_DUCK_B,
        CAT_FLY_A: CAT_FLY_A,
        CAT_FLY_B: CAT_FLY_B,
        CAT_BODY: CAT_BODY,
        CAT_FACE: CAT_FACE,
        cellsOf: cellsOf,
        drawMascot: drawMascot,
        drawCloud: drawCloud,
        drawText: drawText,
        drawPtero: drawPtero,
        readColors: readColors
    };

    // ---------- 恐龙跑酷适配器 ----------
    var dinoGame = {
        name: '恐龙跑酷',
        start: function (cv, cx, p) {
            canvas = cv;
            ctx = cx;
            pal = p;
            resize();
            startDino();
        },
        stop: function () {
            stopDino();
        },
        resize: function (newW, newH, gy) {
            groundY = gy;
        },
        setPal: function (p) {
            pal = p;
        },
        pressAction: function () {
            pressAction();
        },
        onKeyDown: function (e) {
            if (e.code === 'Space' || e.code === 'ArrowUp') { e.preventDefault(); pressAction(); return; }
            if (e.code === 'ArrowDown') { e.preventDefault(); setDuck(true); return; }
        },
        onKeyUp: function (e) {
            if (e.code === 'ArrowDown') setDuck(false);
        }
    };

    // ---------- 通用游戏管理器 ----------
    window.__gameManager = window.__gameManager || {
        gameList: ['fly', 'dino'],
        games: {},
        current: 'fly',
        register: function (id, gameObj) {
            this.games[id] = gameObj;
            if (this.gameList.indexOf(id) === -1) this.gameList.push(id);
        }
    };
    window.__gameManager.register('dino', dinoGame);

    window.__gameManager.getActive = function () {
        return this.games[this.current] || this.games['fly'] || this.games['dino'];
    };

    window.__gameManager.updateSwitchBtn = function () {
        var btn = document.getElementById('dino-switch');
        if (!btn) return;
        var active = this.getActive();
        var label = active ? active.name : '小游戏';
        var labelEl = btn.querySelector('.dino-switch-name');
        if (labelEl) labelEl.textContent = label;
        btn.setAttribute('title', '点击切换小游戏（当前：' + label + '）');
    };

    window.__gameManager.switchGame = function (id) {
        if (!this.games[id] || id === this.current) return;
        var old = this.getActive();
        if (old && old.stop) old.stop();
        this.current = id;
        this.updateSwitchBtn();
        var cur = this.getActive();
        if (cur && cur.start) {
            var cv = document.getElementById('dino-canvas');
            var cx = cv ? cv.getContext('2d') : null;
            if (cx && cv) {
                cx.clearRect(0, 0, cv.width, cv.height);
            }
            cur.start(cv, cx, readColors());
        }
    };

    window.__gameManager.cycleGame = function () {
        var idx = this.gameList.indexOf(this.current);
        var nextIdx = (idx + 1) % this.gameList.length;
        this.switchGame(this.gameList[nextIdx]);
    };

    window.addEventListener('resize', function () {
        if (state === 'open') resize();
        flySize();
        flyUpdate();
    });

    // ---------- 下滑航程：飞行猫（右侧滑翔 → 中央特写 → 俯冲起跑线 → 跑道狂奔冲刺 → 尽头起飞进入游戏） ----------
    var flyCv = null, flyCtx = null, flyPal = null, flyOn = false, flyFrame = 0;
    var flyX = -400, flyY = -200, flyScale = 2.4;
    var flyTrail = [];
    var dustParticles = [];

    function flySize() {
        if (!flyCv) return;
        var dpr = Math.min(window.devicePixelRatio || 1, 2);
        flyCv.width = window.innerWidth * dpr;
        flyCv.height = window.innerHeight * dpr;
        if (flyCtx) flyCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function flyLoop() {
        if (!flyOn || !flyCv || !flyCv.isConnected || state !== 'closed') {
            flyOn = false;
            if (flyCv) flyCv.classList.remove('on');
            return;
        }
        flyFrame++;

        // 主题/色板跟随
        var curThemeKey = (document.documentElement.dataset.theme || 'light') + '|' + (document.documentElement.dataset.palette || 'gold');
        if (!flyPal || curThemeKey !== flyPal.themeKey) flyPal = readColors();

        var W = window.innerWidth;
        var H = window.innerHeight;

        // 页面纵向滚动进度 0 -> 1
        var max = document.documentElement.scrollHeight - H;
        var p = max > 0 ? Math.min(1, window.scrollY / max) : 0;
        var isBottom = atBottom();

        if (isBottom) {
            if (!bottomReachedTime) bottomReachedTime = performance.now();
        } else {
            bottomReachedTime = 0;
        }

        // 如果用户停止滑动超过 1200ms，且尚未触发起飞，runAccum 自动向 0 平滑衰减
        if (runAccum > 0 && performance.now() - lastInputTime > 1200 && !takeoffDone) {
            runAccum = Math.max(0, runAccum - 3);
        }

        var runP = Math.max(0, Math.min(1, runAccum / RUN_WHEEL_MAX));

        // 动态测量跑道真实位置（像素级精准贴合跑道上边缘）
        var runwayEl = document.querySelector('.home-runway');
        var runwayTop = H - 64;
        if (runwayEl) {
            var rRect = runwayEl.getBoundingClientRect();
            runwayTop = rRect.top;
        }

        // 跑道左端起跑线参数（正常体型 scale: 2.4）
        var normScale = 2.4;
        // 猫像素高 18 格，脚底紧贴跑道上边缘：
        var startY = runwayTop - 18 * normScale;
        var groundY = runwayTop;

        // 中央大特写参数
        var heroScale = Math.min(5.8, Math.max(3.8, W * 0.005 * 2.4));
        var heroX = (W - 24 * heroScale) / 2;
        var heroY = H * 0.35;

        var startX = Math.max(32, Math.round(W * 0.08));

        // 跑道右端终点参数
        var endX = W - Math.max(68, Math.round(W * 0.1));

        var targetX, targetY, targetScale;
        var isRunning = false;

        if (!isBottom) {
            // 【阶段 1】页面正常滚动中：猫在右侧滑翔下落
            targetScale = normScale;
            targetX = W - (W > 900 ? 110 : 80);
            var bob = Math.sin(flyFrame * 0.09) * 7;
            targetY = -70 + p * (H - 90) + bob;
        } else if (runP <= 0.001) {
            // 【阶段 2】滚到底端且未继续下滑：飞向屏幕正中央放大特写！
            targetScale = heroScale;
            targetX = heroX;
            targetY = heroY + Math.sin(flyFrame * 0.08) * 8;

            if (!hintShown) {
                hintShown = true;
                showHint();
            }
        } else if (runP < 0.20) {
            // 【阶段 3 前半程】：从中央特写俯冲飞往左侧起跑线
            var subU = runP / 0.20;
            var t = subU * subU * (3 - 2 * subU); // smoothstep 平滑过渡
            targetScale = heroScale + (normScale - heroScale) * t;
            targetX = heroX + (startX - heroX) * t;
            targetY = heroY + (startY - heroY) * t;
        } else {
            // 【阶段 3 后半程】：在跑道上向右全力冲刺狂奔！
            var dashU = (runP - 0.20) / 0.80;
            targetScale = normScale;
            targetX = startX + dashU * (endX - startX);
            targetY = startY;
            isRunning = true;

            // 产生脚底金色扬尘粒子（踩在跑道线上）
            if (flyFrame % 2 === 0) {
                dustParticles.push({
                    x: flyX + 10 * normScale,
                    y: groundY - 1,
                    vx: -2 - Math.random() * 2.5,
                    vy: -Math.random() * 1.5,
                    life: 1.0
                });
            }
        }

        // 坐标平滑跟随逼近目标（黄金步频，矫健前行）
        if (flyX < -300) {
            flyX = targetX;
            flyY = targetY;
            flyScale = targetScale;
        } else {
            var lerpSpeed = isRunning ? 0.20 : 0.14;
            flyX += (targetX - flyX) * lerpSpeed;
            flyY += (targetY - flyY) * lerpSpeed;
            flyScale += (targetScale - flyScale) * 0.16;
        }

        // 【阶段 4】到达跑道右侧尽头：纵身跃起滞空缓冲，随后丝滑展开游戏
        if (runP >= 1 && !takeoffDone) {
            takeoffDone = true;
            // 顺势向斜上方弹跳跃起 50px
            targetY = startY - 50;
            targetX = endX + 16;
            setTimeout(function () {
                openGame(flyX + 12 * normScale, flyY + 9 * normScale);
            }, 140);
        }

        // 清空画布
        flyCtx.clearRect(0, 0, W, H);

        // 绘制滑翔金色轨迹（非奔跑且非特写阶段）
        if (!isBottom) {
            if (flyFrame % 2 === 0) {
                flyTrail.push({ x: flyX + 18, y: flyY + 20 });
                if (flyTrail.length > 22) flyTrail.shift();
            }
            flyTrail.forEach(function (tp, i) {
                flyCtx.fillStyle = 'rgba(' + flyPal.rgb + ', ' + (0.04 + 0.3 * i / flyTrail.length).toFixed(3) + ')';
                flyCtx.fillRect(tp.x, tp.y, 5, 3);
            });
        } else {
            flyTrail = [];
        }

        // 绘制奔跑金色扬尘
        for (var d = dustParticles.length - 1; d >= 0; d--) {
            var dp = dustParticles[d];
            dp.x += dp.vx;
            dp.y += dp.vy;
            dp.life -= 0.05;
            if (dp.life <= 0) {
                dustParticles.splice(d, 1);
            } else {
                flyCtx.fillStyle = 'rgba(' + flyPal.rgb + ', ' + (dp.life * 0.6).toFixed(2) + ')';
                flyCtx.fillRect(dp.x, dp.y, 4, 3);
            }
        }

        // 选择姿态帧（狂奔冲刺时矫健踏步，空中/特写/起飞时收爪悬浮展开双翼）
        var grid;
        if (isRunning && !takeoffDone) {
            grid = (Math.floor(runAccum / 28) % 2 === 0) ? CAT_A : CAT_B;
        } else {
            grid = (flyFrame % 20 < 10) ? CAT_FLY_A : CAT_FLY_B;
        }

        drawMascot(flyCtx, grid, flyX, flyY, flyScale, flyPal);

        requestAnimationFrame(flyLoop);
    }

    function flyUpdate() {
        flyCv = document.getElementById('dino-fly');
        if (!flyCv || !flyCv.isConnected) {
            flyOn = false;
            flyCtx = null;
            return;
        }
        var active = isHome() && state === 'closed' && window.scrollY > 30;
        flyCv.classList.toggle('on', active);
        if (active && !flyOn) {
            if (!flyCtx) {
                flyCtx = flyCv.getContext('2d');
                flySize();
                flyX = -400;
                flyY = -200;
                flyTrail = [];
                dustParticles = [];
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

    // 监听深浅主题与色板切换（实时生效，无需刷新页面）
    var themeObserver = new MutationObserver(function () {
        var newPal = readColors();
        flyPal = newPal;
        pal = newPal;
        var bgLayer = document.getElementById('dino-layer');
        if (bgLayer && (state === 'open' || state === 'opening')) {
            bgLayer.style.background = newPal.bg;
        }
        handleTheme(newPal);
    });
    themeObserver.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ['data-theme', 'data-palette']
    });
})();
