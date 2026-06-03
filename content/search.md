---
title: "站内搜索"
draft: false
---

<div style="text-align: center; margin-top: 20px;">
  <input type="text" id="searchWord" placeholder="输入关键词..." style="width: 70%; padding: 10px; font-size: 16px; border: 1px solid #ccc; border-radius: 5px;">
  <button onclick="goSearch()" style="padding: 10px 20px; font-size: 16px; background: #5c4ee5; color: white; border: none; border-radius: 5px; cursor: pointer; margin-left: 10px;">搜 索</button>
</div>

<script>
function goSearch() {
  var word = document.getElementById('searchWord').value;
  if (word.trim() === '') return;
  var url = 'https://www.baidu.com/s?wd=site%3Amcryii.fun+' + encodeURIComponent(word);
  window.open(url, '_blank');
}
</script>

