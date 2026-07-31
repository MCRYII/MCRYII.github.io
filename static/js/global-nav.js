/* =========================================================
 * 全局局部刷新（PJAX）
 * 点击站内链接时只替换 <main> 内容，避免整页刷新，
 * 让音乐播放器等页面级状态跨页面持续存在。
 * ========================================================= */
(function () {
    'use strict';

    var loading = false;

    var LOOPBACK = ['localhost', '127.0.0.1', '::1'];

    // 本地预览时 localhost 与 127.0.0.1 互通，统一到当前地址
    function normalizeUrl(url) {
        var u = new URL(url);
        if (LOOPBACK.indexOf(u.hostname) !== -1 &&
            LOOPBACK.indexOf(window.location.hostname) !== -1 &&
            u.port === window.location.port) {
            u.hostname = window.location.hostname;
        }
        return u;
    }

    function shouldHandle(anchor) {
        if (!anchor || anchor.hasAttribute('download') || anchor.target === '_blank') return false;
        var href = anchor.getAttribute('href');
        if (!href) return false;
        href = href.trim();
        if (href === '' || href.charAt(0) === '#' || /^javascript:/i.test(href)) return false;
        var url;
        try {
            url = new URL(href, window.location.href);
        } catch (e) {
            return false;
        }
        url = normalizeUrl(url);
        if (url.origin !== window.location.origin) return false;
        if (url.protocol !== 'http:' && url.protocol !== 'https:') return false;
        return true;
    }

    // 执行新内容里的脚本（Cusdis 单独处理，避免重复执行累积监听器）
    function executeScripts(container) {
        var scripts = container.querySelectorAll('script');
        Array.prototype.forEach.call(scripts, function (old) {
            var src = old.getAttribute('src') || '';
            if (src.indexOf('cusdis') !== -1) return;
            var s = document.createElement('script');
            if (src) {
                s.src = src;
                s.async = true;
            } else {
                s.textContent = old.textContent;
            }
            old.parentNode.replaceChild(s, old);
        });
    }

    function initCusdis() {
        var thread = document.getElementById('cusdis_thread');
        if (!thread) return;
        if (window.CUSDIS && window.CUSDIS.renderTo) {
            if (!thread.querySelector('iframe')) {
                window.CUSDIS.renderTo(thread);
            }
            return;
        }
        var s = document.createElement('script');
        s.src = 'https://cusdis.com/js/cusdis.es.js';
        s.async = true;
        document.body.appendChild(s);
    }

    function applyPage(doc, url, push) {
        var newMain = doc.querySelector('main.main');
        var curMain = document.querySelector('main.main');
        if (!newMain || !curMain) throw new Error('main container not found');

        if (doc.title) document.title = doc.title;
        document.body.className = doc.body.className;

        // 页面背景样式（按 id 同步）
        document.querySelectorAll('style[id^="page-bg-"]').forEach(function (s) {
            s.remove();
        });
        doc.querySelectorAll('style[id^="page-bg-"]').forEach(function (s) {
            document.head.appendChild(s.cloneNode(true));
        });

        // canonical
        var canon = document.querySelector('link[rel="canonical"]');
        var newCanon = doc.querySelector('link[rel="canonical"]');
        if (canon && newCanon) canon.href = newCanon.href;

        // 阅读进度条：按新页面有无进行同步（以整个容器为单位）
        var hasProgress = doc.querySelector('.progress-container');
        var curProgress = document.querySelector('.progress-container');
        if (hasProgress && !curProgress) {
            document.body.appendChild(hasProgress.cloneNode(true));
        } else if (!hasProgress && curProgress) {
            curProgress.remove();
        }

        // 替换主内容
        curMain.innerHTML = newMain.innerHTML;
        executeScripts(curMain);
        initCusdis();

        // 图片懒加载 + medium-zoom
        curMain.querySelectorAll('img').forEach(function (img) {
            if (!img.hasAttribute('loading')) img.setAttribute('loading', 'lazy');
        });
        if (window.mediumZoom) {
            window.mediumZoom(curMain.querySelectorAll('.post-content img, .post-single img, .home-info img'));
        }

        // 先更新 URL，再执行依赖路径判断的初始化（如首页打字效果）
        if (push) history.pushState({ pjax: true }, '', url);

        // 重新初始化页面级效果
        if (window.MCRYII_TypeHome) window.MCRYII_TypeHome();
        if (window.MCRYII_InitHomeScroll) window.MCRYII_InitHomeScroll();
        if (window.MCRYII_InitProgress) window.MCRYII_InitProgress();
        if (window.MCRYII_InitSearch) window.MCRYII_InitSearch();
        if (window.__syncNavActive) window.__syncNavActive();

        // 滚动重置 + 进度条立即刷新
        window.scrollTo(0, 0);
        window.dispatchEvent(new Event('scroll'));
    }

    function loadPage(url, push) {
        if (loading) return;
        loading = true;
        fetch(url, { headers: { 'X-PJAX': '1' }, credentials: 'same-origin' })
            .then(function (res) {
                if (!res.ok) throw new Error('HTTP ' + res.status);
                return res.text();
            })
            .then(function (html) {
                var doc = new DOMParser().parseFromString(html, 'text/html');
                applyPage(doc, url, push);
                loading = false;
            })
            .catch(function (err) {
                loading = false;
                console.warn('局部刷新失败，整页跳转:', err);
                window.location.href = url;
            });
    }

    document.addEventListener('click', function (e) {
        if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
        var anchor = e.target && e.target.closest ? e.target.closest('a') : null;
        if (!anchor || !shouldHandle(anchor)) return;
        e.preventDefault();
        var url = normalizeUrl(new URL(anchor.getAttribute('href'), window.location.href));
        if (url.pathname === window.location.pathname) {
            if (url.hash) {
                history.pushState(null, '', url.href);
                var target = document.querySelector(url.hash);
                if (target) target.scrollIntoView();
            } else {
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
            return;
        }
        loadPage(url.href, true);
    });

    window.addEventListener('popstate', function (e) {
        if (e.state && e.state.pjax) {
            loadPage(window.location.href, false);
        }
    });
})();
