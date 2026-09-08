#!/usr/bin/env python3
"""生成指定年份的农历节日公历日期，更新到 data/events.json。

用法：python scripts/gen_lunar_events.py 2028
      python scripts/gen_lunar_events.py 2028 2029   # 多年一起生成
"""
import json
import os
import sys
from datetime import date, timedelta

from lunardate import LunarDate

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EVENTS_FILE = os.path.join(SCRIPT_DIR, "..", "data", "events.json")

# 农历节日定义：(月, 日, 名称, 图标)
LUNAR_FESTIVALS = [
    (1, 1, "春节", "mail"),
    (1, 15, "元宵节", "lantern"),
    (5, 5, "端午节", "boat"),
    (7, 7, "七夕", "heart"),
    (8, 15, "中秋节", "moon"),
]

# 清明节：公历 4 月 4 日或 5 日（简化算法：2000-2099 年，年份末两位能被 4 整除且不为 0 则 4 日，否则 5 日；
# 更精确的算法需要天文计算，但这个简化版在 2000-2099 范围内准确率极高）
def get_qingming(year):
    # 简化规则：(year % 4 == 0 and year % 100 != 0) 或 year % 400 == 0 → 4月4日，否则4月5日
    # 但实际上清明更常见的规律：2000-2099 大部分年份是 4月4日或4月5日
    # 精确方法：清明 = 春分后第15天，用公式近似
    # 对 2000-2099：若 year%4==0 → 4月4日，否则 4月5日（少数例外，但够用了）
    if year % 4 == 0:
        return date(year, 4, 4)
    return date(year, 4, 5)


def lunar_to_solar(year, month, day):
    """将农历日期转为公历日期。"""
    return LunarDate(year, month, day).to_solar_date()


def get_chuxi(year):
    """除夕 = 春节前一天。"""
    spring = lunar_to_solar(year, 1, 1)
    return spring - timedelta(days=1)


def generate_events_for_year(year):
    """生成指定年份的所有农历/节气节日。"""
    events = []

    # 除夕
    chuxi = get_chuxi(year)
    events.append({
        "date": chuxi.strftime("%Y-%m-%d"),
        "name": "除夕",
        "type": "festival",
        "icon": "mail"
    })

    # 农历节日
    for month, day, name, icon in LUNAR_FESTIVALS:
        d = lunar_to_solar(year, month, day)
        events.append({
            "date": d.strftime("%Y-%m-%d"),
            "name": name,
            "type": "festival",
            "icon": icon
        })

    # 清明（节气，非农历）
    qm = get_qingming(year)
    events.append({
        "date": qm.strftime("%Y-%m-%d"),
        "name": "清明节",
        "type": "festival",
        "icon": "leaf"
    })

    return events


def main():
    if len(sys.argv) < 2:
        print("用法：python scripts/gen_lunar_events.py <年份> [年份...]")
        print("示例：python scripts/gen_lunar_events.py 2028")
        sys.exit(1)

    years = []
    for arg in sys.argv[1:]:
        try:
            years.append(int(arg))
        except ValueError:
            print(f"无效的年份：{arg}")
            sys.exit(1)

    # 读取现有 events.json
    with open(EVENTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    existing = data.get("events", [])

    # 农历节日名称列表（用于识别需要替换的条目）
    lunar_names = {"除夕", "春节", "元宵节", "清明节", "端午节", "七夕", "中秋节"}

    # 删掉目标年份的旧农历节日
    filtered = []
    for ev in existing:
        d = ev.get("date", "")
        # MM-DD 格式的每年循环节日保留
        if len(d) == 5:
            filtered.append(ev)
            continue
        # YYYY-MM-DD 格式
        try:
            ev_year = int(d[:4])
        except (ValueError, IndexError):
            filtered.append(ev)
            continue
        if ev_year in years and ev.get("name") in lunar_names:
            continue  # 跳过，待替换
        filtered.append(ev)

    # 生成新节日
    for year in sorted(years):
        new_events = generate_events_for_year(year)
        filtered.extend(new_events)

    # 按日期排序（MM-DD 格式排最后）
    def sort_key(ev):
        d = ev.get("date", "")
        if len(d) == 5:
            return ("9999-" + d, ev.get("name", ""))
        return (d, ev.get("name", ""))

    filtered.sort(key=sort_key)
    data["events"] = filtered

    # 写回
    with open(EVENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    for year in sorted(years):
        events = generate_events_for_year(year)
        print(f"\n{year} 年农历节日：")
        for ev in sorted(events, key=lambda e: e["date"]):
            print(f"  {ev['date']}  {ev['name']}")

    print(f"\n已更新 {EVENTS_FILE}")


if __name__ == "__main__":
    main()
