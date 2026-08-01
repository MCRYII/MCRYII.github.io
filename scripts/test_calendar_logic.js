/* 日历纯逻辑自检：从 calendar.html 提取 CAL-LOGIC 块，断言关键行为 */
'use strict';
const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(
    path.join(__dirname, '..', 'layouts', '_default', 'calendar.html'),
    'utf8'
);
const m = html.match(/\/\* CAL-LOGIC-BEGIN \*\/([\s\S]*?)\/\* CAL-LOGIC-END \*\//);
if (!m) throw new Error('未找到 CAL-LOGIC 块');

const fn = new Function(m[1] + '\nreturn { schedMs: schedMs, remindMs: remindMs, festMapForYear: festMapForYear };');
const { schedMs, remindMs, festMapForYear } = fn();

// 全天日程（无时间）：按当天 09:00 计算
let s = { date: '2026-08-03', time: '', remind: 'same-day' };
if (schedMs(s) !== new Date('2026-08-03T09:00:00').getTime()) throw new Error('全天日程时间错误');
if (remindMs(s) !== schedMs(s)) throw new Error('当天提醒应等于日程时间');

// 提前 10 分钟
s = { date: '2026-08-03', time: '19:00', remind: '10m' };
if (remindMs(s) !== new Date('2026-08-03T18:50:00').getTime()) throw new Error('提前10分钟错误');

// 提前 1 小时
s = { date: '2026-08-03', time: '19:00', remind: '1h' };
if (remindMs(s) !== new Date('2026-08-03T18:00:00').getTime()) throw new Error('提前1小时错误');

// 循环纪念日：MM-DD 展开到指定年份，不泄漏到其他年份
const ev = [{ date: '06-01', name: '建站纪念日' }];
const map = festMapForYear(ev, 2026);
if (!map['2026-06-01'] || map['2026-06-01'][0].name !== '建站纪念日') throw new Error('循环日期展开错误');
if (map['2027-06-01']) throw new Error('循环日期不应泄漏到其他年份');

// 固定日期节日按原样使用
const ev2 = [{ date: '2026-10-01', name: '国庆节' }];
if (!festMapForYear(ev2, 2026)['2026-10-01']) throw new Error('固定日期节日错误');

console.log('calendar logic OK');
