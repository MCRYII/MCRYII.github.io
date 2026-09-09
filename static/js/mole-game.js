/* =========================================================
 * 喵喵打地鼠小游戏（Whack-a-Cat）
 * 玩法：3x3 经典地洞，默认 30 秒挑战（上限 45 秒）
 * 核心机制：
 *   1. 击中加时间：普通命中 +1.2s，Combo ≥ 3 奖励 +1.5s，头盔猫击杀 +2.0s
 *   2. 漏打扣时间：猫咪完全缩回洞底逃跑惩罚 -2s（压哨敲中彻底免疫逃跑，鼠标空挥不扣时）
 *   3. 头盔猫机制：hp=2，第一下敲碎头盔（破盔浮动+破盔碎片粒子），第二下敲晕击杀
 *   4. 无尽极限提速：取消速度上限，随存活时间持续加速，后期停留极限 0.25s，同屏最多 6 只！
 * 操作支持：触屏轻点、鼠标点击（带小锤光标）、键盘九宫格（1~9 或 QWE/ASD/ZXC）
 * 颜色全部跟随站点 CSS 变量与明暗主题
 * ========================================================= */
(function () {
    'use strict';

    var HI_KEY = 'mcryii-mole-hi';
    var INIT_TIME = 30; // 默认初始 30 秒
    var MAX_TIME = 45;  // 时间上限 45 秒

    var canvas, ctx, W, H, dpr, raf = 0, lastTs = 0, pal = null;
    var running = false, gameOver = false;
    var score = 0, hi = 0, combo = 0, maxCombo = 0;
    var timeLeft = INIT_TIME;
    var gameTime = 0; // 累计存活时长（秒）
    var hitCount = 0; // 累计击中猫咪总数
    var spawnTimer = 0;
    var frameCount = 0;
    var timeShakeTimer = 0; // 受到逃跑惩罚时时间槽的红色震颤计时

    // 地洞与实体
    var holes = []; // 9 个洞
    var particles = []; // 爆裂粒子（金星、碎屑、安全帽碎片）
    var floatTexts = []; // 浮动得分/Combo 跳字
    var shockwaves = []; // 地洞击打波纹

    // 鼠标与挥锤状态
    var pointer = { x: -100, y: -100, active: false, hammerAngle: 0, hammerDown: false };

    // 键盘九宫格映射配置
    var KEY_MAP = {
        'Digit1': 0, 'Digit2': 1, 'Digit3': 2,
        'Digit4': 3, 'Digit5': 4, 'Digit6': 5,
        'Digit7': 6, 'Digit8': 7, 'Digit9': 8,
        'Numpad7': 0, 'Numpad8': 1, 'Numpad9': 2,
        'Numpad4': 3, 'Numpad5': 4, 'Numpad6': 5,
        'Numpad1': 6, 'Numpad2': 7, 'Numpad3': 8,
        'KeyQ': 0, 'KeyW': 1, 'KeyE': 2,
        'KeyA': 3, 'KeyS': 4, 'KeyD': 5,
        'KeyZ': 6, 'KeyX': 7, 'KeyC': 8
    };

    var KEY_LABELS = ['1 / Q', '2 / W', '3 / E', '4 / A', '5 / S', '6 / D', '7 / Z', '8 / X', '9 / C'];

    // ---------- 戴安全帽小猫像素画 ----------
    // H = 工程黄色安全帽 (#f59e0b)
    // h = 安全帽反光高光白条 (#ffffff)
    // W = 身体暖白，w = 翅膀，e = 眼，k = 耳窝，b = 腮红，m = ω嘴
    var CAT_HELMET = [
        '.......HHHHHHHHHH.......',
        '......HhhhhhhhhhhH......',
        '.....HHHHHHHHHHHHHH.....',
        '...wHHHHHHHHHHHHHHHHW...',
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

    function getShared() {
        return window.__dinoShared || {};
    }

    // 绘制包含安全帽的吉祥物扩展函数
    function drawMoleCat(c, sprite, x, y, scale, p, hasHelmet) {
        var shared = getShared();
        if (hasHelmet) {
            var off = Math.max(1, Math.round(scale * 0.3));
            var cells = shared.cellsOf;
            if (cells) {
                // 主题色外轮廓（包含头盔部分 H 与身体 Ww）
                cells(c, sprite, 'WwH', x + off, y, scale, p.accent);
                cells(c, sprite, 'WwH', x - off, y, scale, p.accent);
                cells(c, sprite, 'WwH', x, y + off, scale, p.accent);
                cells(c, sprite, 'WwH', x, y - off, scale, p.accent);
                cells(c, sprite, 'WwH', x, y, scale, p.accent);

                // 身体与面部
                cells(c, sprite, 'W', x, y, scale, '#fffdf6');
                cells(c, sprite, 'b', x, y, scale, 'rgba(' + p.rgb + ', 0.45)');
                cells(c, sprite, 'emk', x, y, scale, '#453a29');

                // 安全帽与反光带
                cells(c, sprite, 'H', x, y, scale, '#f59e0b');
                cells(c, sprite, 'h', x, y, scale, '#ffffff');
                return;
            }
        }
        if (shared.drawMascot) {
            shared.drawMascot(c, sprite, x, y, scale, p);
        }
    }

    // 初始化/重置地洞网格
    function initHoles() {
        holes = [];
        var boardW = Math.min(W * 0.88, Math.max(280, Math.min(540, H * 0.65)));
        var boardH = boardW * 0.78;
        var startX = (W - boardW) / 2;
        var startY = H * 0.22 + (H * 0.72 - boardH) / 2;

        var colStep = boardW / 3;
        var rowStep = boardH / 3;

        var holeRx = Math.round(colStep * 0.40);
        var holeRy = Math.round(holeRx * 0.38);

        for (var r = 0; r < 3; r++) {
            for (var c = 0; c < 3; c++) {
                var hx = Math.round(startX + colStep * (c + 0.5));
                var hy = Math.round(startY + rowStep * (r + 0.5));
                holes.push({
                    idx: r * 3 + c,
                    x: hx,
                    y: hy,
                    rx: holeRx,
                    ry: holeRy,
                    state: 'empty', // empty | rising | waiting | hiding | hit
                    type: 'normal',  // 'normal' | 'helmet'
                    hp: 1,           // 普通猫 1，头盔猫 2
                    isHelmetCat: false, // 是否原本是头盔猫（用于最终击杀高额奖励结算）
                    progress: 0,
                    waitTimer: 0,
                    hitTimer: 0,
                    keyLabel: KEY_LABELS[r * 3 + c]
                });
            }
        }
    }

    function resetGame() {
        hi = parseInt(localStorage.getItem(HI_KEY) || '0', 10) || 0;
        score = 0;
        combo = 0;
        maxCombo = 0;
        hitCount = 0;
        timeLeft = INIT_TIME;
        gameTime = 0;
        timeShakeTimer = 0;
        running = false;
        gameOver = false;
        spawnTimer = 25;
        frameCount = 0;
        particles = [];
        floatTexts = [];
        shockwaves = [];
        initHoles();
    }

    // 无尽平滑递增的难度系数（0.0 开局 -> 0.5 (35s) -> 1.0 (70s) -> 1.5+ 狂暴地狱级）
    function getDifficultyLevel() {
        return Math.min(2.2, gameTime / 60);
    }

    // 随机让地洞中的猫咪探头
    function trySpawnCat() {
        var diff = getDifficultyLevel();
        var activeCount = 0;
        var availableHoles = [];
        for (var i = 0; i < holes.length; i++) {
            if (holes[i].state === 'empty') {
                availableHoles.push(holes[i]);
            } else {
                activeCount++;
            }
        }

        // 同屏猫咪数量随时间大幅扩充：开局 2 只 -> 30s 3只 -> 55s 4只 -> 80s+ 最多 5~6 只乱窜！
        var maxActive = 2;
        if (gameTime >= 80) maxActive = 6;
        else if (gameTime >= 55) maxActive = 5;
        else if (gameTime >= 30) maxActive = 4;
        else if (gameTime >= 12) maxActive = 3;

        if (activeCount >= maxActive || availableHoles.length === 0) return;

        var targetHole = availableHoles[Math.floor(Math.random() * availableHoles.length)];
        targetHole.state = 'rising';
        targetHole.progress = 0;

        // 10秒后有 30% 几率刷出戴安全帽的头盔猫
        var isHelmet = (gameTime > 10 && Math.random() < 0.32);
        targetHole.type = isHelmet ? 'helmet' : 'normal';
        targetHole.hp = isHelmet ? 2 : 1;
        targetHole.isHelmetCat = isHelmet;

        // 停留时长随无尽难度持续压缩：
        // 开局：约 68 帧 (1.13s)
        // 40s：约 38 帧 (0.63s)
        // 70s：约 24 帧 (0.40s)
        // 100s+：极限压缩至 15~18 帧 (0.25~0.30s)！
        var baseWait = Math.round(68 - diff * 28);
        targetHole.waitTimer = Math.max(16, baseWait + Math.floor(Math.random() * 6));
    }

    // 敲击指定地洞
    function whackHole(holeIndex) {
        if (holeIndex < 0 || holeIndex >= holes.length) return;
        var h = holes[holeIndex];

        // 挥锤动作反馈
        pointer.hammerDown = true;
        pointer.hammerAngle = -35;
        setTimeout(function () {
            pointer.hammerDown = false;
            pointer.hammerAngle = 0;
        }, 120);

        // 敲击波纹反馈
        shockwaves.push({
            x: h.x,
            y: h.y,
            r: h.rx * 0.5,
            maxR: h.rx * 1.35,
            life: 1.0
        });

        // 命中判定（正在冒头、等待、或正在缩回且未完全缩入洞底）
        if (h.state === 'rising' || h.state === 'waiting' || (h.state === 'hiding' && h.progress > 0.15)) {
            // ---------- 分支 A：头盔猫的第一下（碎盔） ----------
            if (h.type === 'helmet' && h.hp === 2) {
                h.hp = 1;
                h.type = 'normal'; // 头盔碎裂，变为普通猫
                // 停留时间微幅充能 16 帧，留出黄金补刀窗口
                h.waitTimer = Math.max(22, h.waitTimer + 16);

                combo++;
                if (combo > maxCombo) maxCombo = combo;
                score += 50;
                if (score > hi) {
                    hi = score;
                    localStorage.setItem(HI_KEY, String(hi));
                }

                // 浮动跳字：破盔提示
                floatTexts.push({
                    text: 'CRACK! 破盔 (+50)',
                    x: h.x,
                    y: h.y - h.ry * 2.8,
                    vy: -1.5,
                    life: 0.9,
                    color: '#f59e0b'
                });

                // 爆开亮黄色安全帽碎片粒子
                for (var i = 0; i < 12; i++) {
                    var angH = Math.random() * Math.PI * 2;
                    var spdH = 2.5 + Math.random() * 4.5;
                    particles.push({
                        x: h.x,
                        y: h.y - h.ry * 2.0,
                        vx: Math.cos(angH) * spdH,
                        vy: Math.sin(angH) * spdH - 2.2,
                        size: 3 + Math.random() * 4,
                        life: 1.0,
                        color: '#f59e0b',
                        isStar: false
                    });
                }
                return;
            }

            // ---------- 分支 B：彻底击中 / 击杀（第二下或普通猫） ----------
            // 切换为受击击晕状态，徹底阻断/免疫任何逃跑扣时！
            h.state = 'hit';
            h.hitTimer = 18;
            hitCount++;

            combo++;
            if (combo > maxCombo) maxCombo = combo;
            var comboBonus = Math.min(120, (combo - 1) * 25);

            // 如果原本是头盔猫，享受丰厚击杀奖励！
            var gained = h.isHelmetCat ? (250 + comboBonus) : (100 + comboBonus);
            score += gained;
            if (score > hi) {
                hi = score;
                localStorage.setItem(HI_KEY, String(hi));
            }

            // 命中加时间奖励
            var timeBonus = h.isHelmetCat ? 2.0 : (combo >= 3 ? 1.5 : 1.2);
            timeLeft = Math.min(MAX_TIME, timeLeft + timeBonus);

            // 浮动跳字
            var text = '+' + gained + ' (+' + timeBonus.toFixed(1) + 's)';
            if (h.isHelmetCat) text = '★击倒盔猫! ' + text;
            else if (combo >= 2) text = 'COMBO x' + combo + ' ' + text;

            floatTexts.push({
                text: text,
                x: h.x,
                y: h.y - h.ry * 2.8,
                vy: -1.6,
                life: 1.0,
                color: h.isHelmetCat ? '#f59e0b' : (combo >= 3 ? pal.accent : 'rgba(' + pal.rgb + ', 0.95)')
            });

            // 爆裂金色星星粒子
            var pCount = Math.min(24, 12 + combo * 2);
            for (var p = 0; p < pCount; p++) {
                var angle = Math.random() * Math.PI * 2;
                var spd = 2 + Math.random() * 4.5;
                particles.push({
                    x: h.x,
                    y: h.y - h.ry * 1.5,
                    vx: Math.cos(angle) * spd,
                    vy: Math.sin(angle) * spd - 1.5,
                    size: 3 + Math.random() * 4,
                    life: 1.0,
                    color: pal.accent,
                    isStar: Math.random() > 0.4
                });
            }
        } else if (h.state === 'empty') {
            // 鼠标/按键打在空地洞：不扣时间！仅轻微提示 MISS 并重置连击
            if (combo > 1) {
                floatTexts.push({
                    text: 'MISS',
                    x: h.x,
                    y: h.y - h.ry * 1.8,
                    vy: -1.0,
                    life: 0.6,
                    color: 'rgba(180, 180, 180, 0.7)'
                });
            }
            combo = 0;
        }
    }

    // 更新逻辑
    function update(f) {
        if (!running || gameOver) return;
        frameCount++;

        gameTime += (f / 60);

        // 倒计时递减
        timeLeft -= (f / 60);
        if (timeLeft <= 0) {
            timeLeft = 0;
            gameOver = true;
            running = false;
            holes.forEach(function (h) {
                if (h.state !== 'hit') h.state = 'empty';
            });
            return;
        }

        if (timeShakeTimer > 0) timeShakeTimer -= f;

        var diff = getDifficultyLevel();

        // 刷新生成计时器：开局约 55 帧 -> 80s 极限 14 帧！
        spawnTimer -= f;
        if (spawnTimer <= 0) {
            trySpawnCat();
            var nextInterval = Math.round(55 - diff * 22);
            spawnTimer = Math.max(12, nextInterval + Math.floor(Math.random() * 8));
        }

        // 动作位移速率随难度递进加速 40%
        var riseSpeed = (0.13 + diff * 0.055) * f;
        var hideSpeed = (0.11 + diff * 0.045) * f;

        // 更新每个地洞的状态机
        for (var i = 0; i < holes.length; i++) {
            var h = holes[i];
            if (h.state === 'rising') {
                h.progress += riseSpeed;
                if (h.progress >= 1) {
                    h.progress = 1;
                    h.state = 'waiting';
                }
            } else if (h.state === 'waiting') {
                h.waitTimer -= f;
                if (h.waitTimer <= 0) {
                    // 超时自然开始下潜缩回（注意：此处绝不立即扣时间！）
                    h.state = 'hiding';
                }
            } else if (h.state === 'hiding') {
                h.progress -= hideSpeed;
                // 【核心Bug彻底修复】：当且仅当猫咪完全缩回洞底（progress <= 0）且未被击中时，才判定逃跑！
                if (h.progress <= 0) {
                    h.progress = 0;
                    h.state = 'empty';
                    combo = 0;

                    // 逃跑扣除时间 -2.0 秒
                    var penalty = 2.0;
                    timeLeft = Math.max(0, timeLeft - penalty);
                    timeShakeTimer = 12;

                    floatTexts.push({
                        text: '逃跑啦! (-' + penalty.toFixed(0) + 's)',
                        x: h.x,
                        y: h.y - h.ry * 2.2,
                        vy: -1.3,
                        life: 0.85,
                        color: '#ff4d4f'
                    });

                    if (timeLeft <= 0) {
                        timeLeft = 0;
                        gameOver = true;
                        running = false;
                        return;
                    }
                }
            } else if (h.state === 'hit') {
                h.hitTimer -= f;
                if (h.hitTimer <= 0) {
                    h.progress -= 0.14 * f;
                    if (h.progress <= 0) {
                        h.progress = 0;
                        h.state = 'empty';
                    }
                }
            }
        }

        // 更新粒子
        for (var pIdx = particles.length - 1; pIdx >= 0; pIdx--) {
            var pt = particles[pIdx];
            pt.x += pt.vx;
            pt.y += pt.vy;
            pt.vy += 0.18;
            pt.life -= 0.038 * f;
            if (pt.life <= 0) particles.splice(pIdx, 1);
        }

        // 更新浮动文字
        for (var tIdx = floatTexts.length - 1; tIdx >= 0; tIdx--) {
            var ft = floatTexts[tIdx];
            ft.y += ft.vy * f;
            ft.life -= 0.024 * f;
            if (ft.life <= 0) floatTexts.splice(tIdx, 1);
        }

        // 更新击打冲击波
        for (var sIdx = shockwaves.length - 1; sIdx >= 0; sIdx--) {
            var sw = shockwaves[sIdx];
            sw.r += (sw.maxR - sw.r) * 0.22 * f;
            sw.life -= 0.08 * f;
            if (sw.life <= 0) shockwaves.splice(sIdx, 1);
        }
    }

    // 绘制小锤子
    function drawHammer(hx, hy, angle) {
        ctx.save();
        ctx.translate(hx, hy);
        ctx.rotate((angle * Math.PI) / 180);

        ctx.fillStyle = pal.deep;
        ctx.fillRect(-3, 0, 6, 26);

        ctx.fillStyle = pal.accent;
        ctx.fillRect(-14, -14, 28, 14);

        ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
        ctx.fillRect(-12, -12, 24, 3);

        ctx.restore();
    }

    // 绘制单颗小星星
    function drawStar(cx, cy, r, color) {
        ctx.save();
        ctx.fillStyle = color;
        ctx.beginPath();
        for (var i = 0; i < 5; i++) {
            var a = (i * 4 * Math.PI) / 5 - Math.PI / 2;
            var sx = cx + Math.cos(a) * r;
            var sy = cy + Math.sin(a) * r;
            if (i === 0) ctx.moveTo(sx, sy);
            else ctx.lineTo(sx, sy);
        }
        ctx.closePath();
        ctx.fill();
        ctx.restore();
    }

    // 绘制主体画面
    function draw() {
        var shared = getShared();
        if (!ctx || !pal) return;

        var curThemeKey = (document.documentElement.dataset.theme || 'light') + '|' + (document.documentElement.dataset.palette || 'gold');
        if ((!pal || curThemeKey !== pal.themeKey) && shared.readColors) {
            pal = shared.readColors();
            var bgLayer = document.getElementById('dino-layer');
            if (bgLayer) bgLayer.style.background = pal.bg;
        }

        ctx.clearRect(0, 0, W, H);

        var scale = Math.max(1.6, Math.min(3.2, Math.round(H * 0.0036 * 2.2 * 10) / 10));
        var catW = 24 * scale;
        var catH = 18 * scale;

        // 绘制 9 个地洞
        holes.forEach(function (h) {
            // 1. 洞口外部光晕
            ctx.save();
            ctx.fillStyle = 'rgba(' + pal.rgb + ', 0.06)';
            ctx.beginPath();
            ctx.ellipse(h.x, h.y, h.rx * 1.15, h.ry * 1.2, 0, 0, Math.PI * 2);
            ctx.fill();

            // 2. 洞口深坑立体渐变
            var holeGrad = ctx.createRadialGradient(h.x, h.y + h.ry * 0.3, 2, h.x, h.y, h.rx);
            holeGrad.addColorStop(0, '#0c0a07');
            holeGrad.addColorStop(0.7, '#1b1712');
            holeGrad.addColorStop(1, 'rgba(' + pal.rgb + ', 0.25)');
            ctx.fillStyle = holeGrad;
            ctx.beginPath();
            ctx.ellipse(h.x, h.y, h.rx, h.ry, 0, 0, Math.PI * 2);
            ctx.fill();

            ctx.strokeStyle = 'rgba(' + pal.rgb + ', 0.55)';
            ctx.lineWidth = 2;
            ctx.stroke();
            ctx.restore();

            // 3. 猫咪钻出
            if (h.state !== 'empty' && h.progress > 0.02) {
                ctx.save();
                ctx.beginPath();
                ctx.rect(h.x - h.rx * 1.5, h.y - h.ry * 4.5, h.rx * 3, h.ry * 4.5 + h.ry * 0.2);
                ctx.clip();

                var curY = (h.y + h.ry * 0.4) - (catH * 0.95 * h.progress);
                var curX = h.x - catW / 2;

                var sprite;
                var hasHelmet = (h.type === 'helmet' && h.hp === 2);

                if (h.state === 'hit' && shared.CAT_HIT) {
                    sprite = shared.CAT_HIT;
                } else if (hasHelmet) {
                    sprite = CAT_HELMET;
                } else {
                    sprite = shared.CAT_A;
                }

                drawMoleCat(ctx, sprite, curX, curY, scale, pal, hasHelmet);
                ctx.restore();

                if (h.state === 'hit') {
                    var starY = (h.y + h.ry * 0.4) - (catH * 0.95 * h.progress) - 6;
                    var starOffset = Math.sin(frameCount * 0.3) * 10;
                    drawStar(h.x - 12 + starOffset, starY, 4.5, pal.accent);
                    drawStar(h.x + 12 - starOffset, starY - 3, 3.5, '#fff');
                }
            }

            // 4. 地洞前沿半圆高光（前后遮挡层次）
            ctx.save();
            ctx.strokeStyle = 'rgba(' + pal.rgb + ', 0.75)';
            ctx.lineWidth = 2.5;
            ctx.beginPath();
            ctx.ellipse(h.x, h.y, h.rx, h.ry, 0, 0, Math.PI);
            ctx.stroke();
            ctx.restore();

            // 5. 快捷键微标提示
            if (shared.drawText) {
                shared.drawText(h.keyLabel, h.x, h.y + h.ry + 16, Math.max(10, Math.min(12, W * 0.010)), 'center', 'rgba(' + pal.rgb + ', 0.45)', ctx);
            }
        });

        // 绘制打击冲击波
        shockwaves.forEach(function (sw) {
            ctx.save();
            ctx.strokeStyle = 'rgba(' + pal.rgb + ', ' + (sw.life * 0.8).toFixed(2) + ')';
            ctx.lineWidth = 2.5;
            ctx.beginPath();
            ctx.ellipse(sw.x, sw.y, sw.r, sw.r * 0.4, 0, 0, Math.PI * 2);
            ctx.stroke();
            ctx.restore();
        });

        // 绘制爆裂粒子（含安全帽碎片与金星）
        particles.forEach(function (pt) {
            if (pt.isStar) {
                drawStar(pt.x, pt.y, pt.size * pt.life, pt.color || pal.accent);
            } else {
                ctx.fillStyle = pt.color || ('rgba(' + pal.rgb + ', ' + (pt.life * 0.9).toFixed(2) + ')');
                ctx.fillRect(pt.x, pt.y, pt.size, pt.size);
            }
        });

        // 绘制浮动跳字
        floatTexts.forEach(function (ft) {
            if (shared.drawText) {
                var sz = Math.max(13, Math.min(21, W * 0.015));
                shared.drawText(ft.text, ft.x, ft.y, sz, 'center', ft.color, ctx);
            }
        });

        // ---------- 顶部 HUD ----------
        var pad = Math.max(14, Math.round(W * 0.02));

        var scoreStr = String(score).padStart(5, '0');
        var hiStr = String(hi).padStart(5, '0');
        if (shared.drawText) {
            shared.drawText('HI ' + hiStr + '  ' + scoreStr, W - pad - 110, pad + 20, Math.max(14, Math.min(18, W * 0.014)), 'right', 'rgba(' + pal.rgb + ', 0.85)', ctx);
        }

        if (running) {
            var timeWidth = Math.min(320, W * 0.45);
            var timeHeight = 9;
            var timeX = (W - timeWidth) / 2;
            var timeY = pad + 16;

            if (timeShakeTimer > 0) {
                timeX += (Math.random() - 0.5) * 6;
            }

            ctx.fillStyle = timeShakeTimer > 0 ? 'rgba(255, 77, 79, 0.25)' : 'rgba(' + pal.rgb + ', 0.15)';
            ctx.fillRect(timeX, timeY, timeWidth, timeHeight);

            var progress = Math.max(0, Math.min(1, timeLeft / MAX_TIME));
            ctx.fillStyle = timeShakeTimer > 0 ? '#ff4d4f' : pal.accent;
            ctx.fillRect(timeX, timeY, timeWidth * progress, timeHeight);

            if (shared.drawText) {
                var secStr = Math.ceil(timeLeft) + 's';
                var secColor = timeShakeTimer > 0 ? '#ff4d4f' : (timeLeft <= 5 ? '#ff4d4f' : 'rgba(' + pal.rgb + ', 0.92)');
                shared.drawText(secStr, W / 2, timeY + timeHeight + 17, Math.max(13, Math.min(16, W * 0.012)), 'center', secColor, ctx);

                if (combo >= 2) {
                    var comboText = '★ COMBO x' + combo + ' (+1.5s 延时加成中)';
                    shared.drawText(comboText, W / 2, timeY + timeHeight + 35, Math.max(11, Math.min(13, W * 0.010)), 'center', pal.accent, ctx);
                }
            }
        }

        // 待机未开始界面
        if (!running && !gameOver && shared.drawText) {
            shared.drawText('喵 喵 打 地 鼠', W / 2, H * 0.14, Math.max(20, Math.min(30, W * 0.024)), 'center', pal.accent, ctx);
            shared.drawText('普通猫敲 1 下 · 黄色头盔猫需敲 2 下（高额积分与延时）', W / 2, H * 0.14 + 30, Math.max(12, Math.min(15, W * 0.012)), 'center', 'rgba(' + pal.rgb + ', 0.85)', ctx);
            shared.drawText('击中 +1.2s~+2.0s · 逃跑 -2s · 空挥不扣时 · 越往后速度越极限！', W / 2, H * 0.14 + 52, Math.max(11, Math.min(13, W * 0.010)), 'center', 'rgba(' + pal.rgb + ', 0.55)', ctx);
            shared.drawText('点击屏幕 / 按空格 开始游戏', W / 2, H * 0.88, Math.max(15, Math.min(19, W * 0.015)), 'center', pal.accent, ctx);
        }

        // 游戏结束结算界面
        if (gameOver && shared.drawText) {
            var cx = W / 2, cy = H / 2;
            ctx.fillStyle = 'rgba(0, 0, 0, 0.48)';
            ctx.fillRect(0, 0, W, H);

            shared.drawText('T I M E   U P !', cx, cy - 42, Math.max(26, Math.min(44, W * 0.038)), 'center', pal.accent, ctx);
            shared.drawText('坚持时长：' + Math.floor(gameTime) + ' 秒  ·  击倒猫咪：' + hitCount + ' 只', cx, cy - 6, Math.max(14, Math.min(17, W * 0.013)), 'center', 'rgba(' + pal.rgb + ', 0.95)', ctx);
            shared.drawText('最终得分：' + score + '  ·  最高连击：' + maxCombo + 'x', cx, cy + 20, Math.max(15, Math.min(19, W * 0.015)), 'center', pal.accent, ctx);
            shared.drawText('历史最高纪录：' + hi, cx, cy + 44, Math.max(13, Math.min(16, W * 0.013)), 'center', 'rgba(' + pal.rgb + ', 0.75)', ctx);
            shared.drawText('点击屏幕 / 按空格 重新开始 · Esc 退出', cx, cy + 78, Math.max(12, Math.min(15, W * 0.012)), 'center', 'rgba(' + pal.rgb + ', 0.65)', ctx);

            var arcCx = cx, arcCy = cy + 116, arcR = 15;
            ctx.strokeStyle = pal.accent;
            ctx.lineWidth = 3;
            ctx.beginPath();
            ctx.arc(arcCx, arcCy, arcR, Math.PI * 0.25, Math.PI * 1.82, false);
            ctx.stroke();
            var endA = Math.PI * 1.82;
            var endX = arcCx + arcR * Math.cos(endA);
            var endY = arcCy + arcR * Math.sin(endA);
            var tangent = endA + Math.PI / 2;
            ctx.fillStyle = pal.accent;
            ctx.beginPath();
            ctx.moveTo(endX + 8 * Math.cos(tangent), endY + 8 * Math.sin(tangent));
            ctx.lineTo(endX + 5.5 * Math.cos(tangent - Math.PI * 0.72), endY + 5.5 * Math.sin(tangent - Math.PI * 0.72));
            ctx.lineTo(endX + 5.5 * Math.cos(tangent + Math.PI * 0.72), endY + 5.5 * Math.sin(tangent + Math.PI * 0.72));
            ctx.closePath();
            ctx.fill();
        }

        // 绘制小锤光标
        if (pointer.active && !gameOver) {
            drawHammer(pointer.x, pointer.y, pointer.hammerAngle);
        }
    }

    function loop(ts) {
        if (!lastTs) lastTs = ts;
        var dt = Math.min(34, ts - lastTs);
        lastTs = ts;
        update(dt / 16.7);
        draw();
        raf = requestAnimationFrame(loop);
    }

    function startLoop() {
        lastTs = 0;
        if (raf) cancelAnimationFrame(raf);
        raf = requestAnimationFrame(loop);
    }

    function stopLoop() {
        if (raf) cancelAnimationFrame(raf);
        raf = 0;
    }

    function resize(newW, newH) {
        W = newW || window.innerWidth;
        H = newH || window.innerHeight;
        initHoles();
    }

    // ---------- 适配器对象与接口 ----------
    var moleGame = {
        name: '喵喵打地鼠',
        start: function (cv, cx, p) {
            canvas = cv;
            ctx = cx;
            pal = p;
            resize();
            resetGame();
            startLoop();
        },
        stop: function () {
            stopLoop();
            running = false;
        },
        resize: function (newW, newH) {
            resize(newW, newH);
        },
        setPal: function (p) {
            pal = p;
            var bgLayer = document.getElementById('dino-layer');
            if (bgLayer) bgLayer.style.background = pal.bg;
        },
        pressAction: function (clickX, clickY) {
            if (gameOver) {
                resetGame();
                running = true;
                return;
            }
            if (!running) {
                running = true;
                return;
            }

            if (typeof clickX === 'number' && typeof clickY === 'number') {
                for (var i = 0; i < holes.length; i++) {
                    var h = holes[i];
                    var dx = clickX - h.x;
                    var dy = clickY - (h.y - h.ry * 0.8);
                    var rx = h.rx * 1.35;
                    var ry = h.ry * 2.2;
                    if ((dx * dx) / (rx * rx) + (dy * dy) / (ry * ry) <= 1) {
                        whackHole(i);
                        return;
                    }
                }
            }
        },
        onKeyDown: function (e) {
            if (e.code === 'Space') {
                e.preventDefault();
                this.pressAction();
                return;
            }

            if (KEY_MAP.hasOwnProperty(e.code)) {
                e.preventDefault();
                if (!running && !gameOver) {
                    running = true;
                }
                if (running && !gameOver) {
                    whackHole(KEY_MAP[e.code]);
                }
            }
        },
        onKeyUp: function () {},
        onPointerMove: function (e) {
            pointer.active = true;
            pointer.x = e.clientX;
            pointer.y = e.clientY;
        },
        onPointerLeave: function () {
            pointer.active = false;
        }
    };

    window.__moleGame = moleGame;

    window.__gameManager = window.__gameManager || {
        gameList: ['fly', 'dino', 'mole'],
        games: {},
        current: 'fly',
        register: function (id, gameObj) {
            this.games[id] = gameObj;
            if (this.gameList.indexOf(id) === -1) this.gameList.push(id);
        }
    };
    window.__gameManager.register('mole', moleGame);

    document.addEventListener('pointerdown', function (e) {
        var layer = document.getElementById('dino-layer');
        if (!layer || layer.hidden) return;
        if (e.target.closest('#dino-close') || e.target.closest('#dino-theme') || e.target.closest('#dino-switch')) return;

        if (window.__gameManager && window.__gameManager.current === 'mole') {
            moleGame.pressAction(e.clientX, e.clientY);
        }
    });
})();
