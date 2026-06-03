---
title: "站内搜索"
draft: false
---

输入关键词，搜索本站文章：

<form onsubmit="searchSite(event)">
  <input type="text" id="searchInput" placeholder="输入关键词..." style="width: 100%; padding: 10px; font-size: 16px; border: 1px solid #ccc; border-radius: 5px;">
  <button type="submit" style="margin-top: 10px; padding: 10px 20px; font-size: 16px; background: #5c4ee5; color: white; border: none; border-radius: 5px; cursor: pointer;">搜索</button>
</form>

<script>
function searchSite(e) {
  e.preventDefault();
  var keyword = document.getElementById('searchInput').value;
  var url = 'https://www.baidu.com/s?wd=site%3Amcryii.fun+' + encodeURIComponent(keyword);
  window.open(url, '_blank');
}
</script>
