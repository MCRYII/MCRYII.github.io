/* Scroll effects: one-frame scheduling + PJAX lifecycle cleanup */
(function () {
    'use strict';

    window.MCRYII_ScrollHub = window.MCRYII_ScrollHub || (function () {
        var callbacks = [];
        var scheduled = false;

        function flush() {
            scheduled = false;
            callbacks.slice().forEach(function (callback) {
                try { callback(); } catch (error) { console.warn('Scroll effect failed:', error); }
            });
        }

        function schedule() {
            if (scheduled) return;
            scheduled = true;
            window.requestAnimationFrame(flush);
        }

        window.addEventListener('scroll', schedule, { passive: true });
        window.addEventListener('resize', schedule, { passive: true });

        return {
            subscribe: function (callback) {
                if (callbacks.indexOf(callback) === -1) callbacks.push(callback);
                return function () {
                    var index = callbacks.indexOf(callback);
                    if (index !== -1) callbacks.splice(index, 1);
                };
            }
        };
    })();

    var pageUnsubscribers = window.MCRYII_PageUnsubscribers || [];
    window.MCRYII_PageUnsubscribers = pageUnsubscribers;
    window.MCRYII_CleanupPageEffects = function () {
        while (pageUnsubscribers.length) {
            var unsubscribe = pageUnsubscribers.pop();
            try { unsubscribe(); } catch (error) { console.warn('Page effect cleanup failed:', error); }
        }
    };

    function trackPageEffect(unsubscribe) {
        pageUnsubscribers.push(unsubscribe);
    }

    window.MCRYII_InitHomeScroll = function () {
        if (window.location.pathname !== '/' && window.location.pathname !== '/index.html') return;
        var homeInfo = document.querySelector('.home-info');
        if (!homeInfo || homeInfo.dataset.scrollInit) return;
        homeInfo.dataset.scrollInit = '1';

        var updateHome = function () {
            if (!homeInfo.isConnected) return;
            var scrollY = window.scrollY;
            homeInfo.style.opacity = Math.max(0, 1 - (scrollY / 300));
            homeInfo.style.transform = 'translateY(' + (scrollY * 0.3) + 'px)';
        };
        var unsubscribe = window.MCRYII_ScrollHub.subscribe(updateHome);
        trackPageEffect(function () {
            delete homeInfo.dataset.scrollInit;
            unsubscribe();
        });
        updateHome();
    };

    window.MCRYII_InitProgress = function () {
        var progressBar = document.getElementById('reading-progress-bar');
        if (!progressBar || progressBar.dataset.init) return;
        progressBar.dataset.init = '1';

        var updateProgress = function () {
            if (!progressBar.isConnected) return;
            var scrollTop = window.scrollY || document.documentElement.scrollTop || document.body.scrollTop;
            var maxScroll = document.documentElement.scrollHeight - window.innerHeight;
            var progress = maxScroll > 0 ? scrollTop / maxScroll : 0;
            progressBar.style.transform = 'scaleX(' + Math.max(0, Math.min(1, progress)) + ')';
        };
        var unsubscribe = window.MCRYII_ScrollHub.subscribe(updateProgress);
        trackPageEffect(function () {
            delete progressBar.dataset.init;
            unsubscribe();
        });
        updateProgress();
    };

    document.addEventListener('DOMContentLoaded', function () {
        var header = document.querySelector('.site-header');
        if (header) {
            var lastScrollY = window.scrollY;
            window.MCRYII_ScrollHub.subscribe(function () {
                if (window.scrollY > 50) header.classList.add('scrolled');
                else header.classList.remove('scrolled');
                if (window.scrollY > 120 && window.scrollY > lastScrollY + 2) {
                    header.classList.add('hidden-nav');
                } else {
                    header.classList.remove('hidden-nav');
                }
                lastScrollY = window.scrollY;
            });
            document.addEventListener('mouseover', function (event) {
                if (event.clientY < 80) header.classList.remove('hidden-nav');
            });
        }

        window.MCRYII_InitHomeScroll();
        window.MCRYII_InitProgress();

        var goTopBtn = document.getElementById('go-top');
        if (!goTopBtn) return;
        function toggleGoTop() {
            if (window.scrollY > 300) {
                goTopBtn.classList.add('show');
                document.body.classList.add('player-up');
            } else {
                goTopBtn.classList.remove('show');
                document.body.classList.remove('player-up');
            }
        }
        window.MCRYII_ScrollHub.subscribe(toggleGoTop);
        toggleGoTop();
        goTopBtn.addEventListener('click', function () {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    });
})();
