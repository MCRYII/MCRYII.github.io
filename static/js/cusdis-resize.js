window.addEventListener('load', function() {
    // 等待 Cusdis iframe 出现
    var observer = new MutationObserver(function(mutations) {
        var iframe = document.querySelector('#cusdis_thread iframe');
        if (iframe) {
            // 设置 iframe 高度为内容高度
            function resizeIframe() {
                try {
                    var body = iframe.contentWindow.document.body;
                    iframe.style.height = body.scrollHeight + 'px';
                } catch(e) {
                    // 跨域问题，无法访问内部
                    console.log('无法调整iframe高度:', e);
                }
            }
            iframe.addEventListener('load', resizeIframe);
            resizeIframe();
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });
});
