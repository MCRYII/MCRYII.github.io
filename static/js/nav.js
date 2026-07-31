/* =========================================================
 * 顶栏导航交互：下拉菜单、搜索弹窗、快捷键、移动端抽屉
 * ========================================================= */
(function () {
    'use strict';

    function closeAllDropdowns(except) {
        document.querySelectorAll('.nav-item.is-open').forEach(function (item) {
            if (item !== except) {
                item.classList.remove('is-open');
                delete item.dataset.clickOpen;
                var t = item.querySelector('[data-dropdown-trigger]');
                if (t) t.setAttribute('aria-expanded', 'false');
            }
        });
    }

    // 桌面下拉：hover 展开 + 延迟关闭（允许鼠标穿过按钮与弹窗之间的间隙）
    var dropdownTimer = null;
    function scheduleClose() {
        if (dropdownTimer) clearTimeout(dropdownTimer);
        dropdownTimer = setTimeout(function () {
            closeAllDropdowns();
            dropdownTimer = null;
        }, 200);
    }
    function cancelClose() {
        if (dropdownTimer) {
            clearTimeout(dropdownTimer);
            dropdownTimer = null;
        }
    }

    document.querySelectorAll('.nav-pill [data-dropdown]').forEach(function (item) {
        item.addEventListener('mouseenter', function () {
            cancelClose();
            closeAllDropdowns(item);
            item.classList.add('is-open');
            var trigger = item.querySelector('[data-dropdown-trigger]');
            if (trigger) trigger.setAttribute('aria-expanded', 'true');
        });
        item.addEventListener('mouseleave', function () {
            // 点击固定展开的状态不因鼠标移开而关闭
            if (!item.dataset.clickOpen) scheduleClose();
        });
    });

    document.addEventListener('click', function (e) {
        var item = e.target.closest ? e.target.closest('[data-dropdown]') : null;
        if (item) {
            e.stopPropagation();
            var wasOpen = item.classList.contains('is-open');
            closeAllDropdowns();
            if (!wasOpen) {
                item.classList.add('is-open');
                item.dataset.clickOpen = '1';
                var trigger = item.querySelector('[data-dropdown-trigger]');
                if (trigger) trigger.setAttribute('aria-expanded', 'true');
            }
            return;
        }
        if (!e.target.closest('.nav-dropdown')) {
            closeAllDropdowns();
        }
    });

    // 搜索弹窗
    var searchBtn = document.getElementById('nav-search-btn');
    var searchContainer = document.getElementById('search-container');
    function openSearch() {
        if (!searchContainer) return;
        searchContainer.classList.add('open');
        var input = document.getElementById('search-input');
        if (input) {
            input.focus();
            input.select();
        }
    }
    function closeSearch() {
        if (searchContainer) searchContainer.classList.remove('open');
    }
    if (searchBtn) {
        searchBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            if (searchContainer && searchContainer.classList.contains('open')) {
                closeSearch();
            } else {
                openSearch();
            }
        });
    }
    document.addEventListener('keydown', function (e) {
        if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
            e.preventDefault();
            openSearch();
        }
        if (e.key === 'Escape') {
            closeSearch();
            closeAllDropdowns();
            closeDrawer();
        }
    });
    document.addEventListener('click', function (e) {
        if (searchContainer && searchContainer.classList.contains('open') &&
            !searchContainer.contains(e.target) && e.target !== searchBtn) {
            closeSearch();
        }
    });

    // 移动端抽屉
    var menuSwitch = document.getElementById('nav-menu-switch');
    var drawer = document.getElementById('nav-drawer');
    var overlay = document.getElementById('nav-drawer-overlay');
    var drawerClose = document.getElementById('nav-drawer-close');
    function openDrawer() {
        if (drawer) drawer.classList.add('open');
        if (overlay) overlay.classList.add('open');
        document.body.style.overflow = 'hidden';
    }
    function closeDrawer() {
        if (drawer) drawer.classList.remove('open');
        if (overlay) overlay.classList.remove('open');
        document.body.style.overflow = '';
    }
    if (menuSwitch) menuSwitch.addEventListener('click', function (e) {
        e.stopPropagation();
        if (drawer && drawer.classList.contains('open')) {
            closeDrawer();
        } else {
            openDrawer();
        }
    });
    if (overlay) overlay.addEventListener('click', closeDrawer);
    if (drawerClose) drawerClose.addEventListener('click', closeDrawer);

    // 抽屉子菜单折叠
    document.addEventListener('click', function (e) {
        var toggle = e.target.closest ? e.target.closest('[data-drawer-toggle]') : null;
        if (toggle) {
            e.stopPropagation();
            toggle.parentElement.classList.toggle('is-open');
            toggle.setAttribute('aria-expanded', toggle.parentElement.classList.contains('is-open'));
            return;
        }
        // 点击抽屉里的链接后关闭抽屉
        if (e.target.closest && e.target.closest('[data-nav-link]')) {
            closeDrawer();
        }
    });

    // 导航高亮同步（PJAX 切页后由 global-nav.js 调用）
    window.__syncNavActive = function () {
        var path = window.location.pathname;
        document.querySelectorAll('[data-nav-link]').forEach(function (a) {
            var href = (a.getAttribute('href') || '').split('#')[0];
            var isActive = href === path || (href !== '/' && path.indexOf(href) === 0);
            a.classList.toggle('active', isActive);
        });
        document.querySelectorAll('[data-dropdown]').forEach(function (dd) {
            var hasActive = !!dd.querySelector('[data-nav-link].active');
            var trigger = dd.querySelector('[data-dropdown-trigger]');
            if (trigger) trigger.classList.toggle('active', hasActive);
        });
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', window.__syncNavActive);
    } else {
        window.__syncNavActive();
    }
})();
