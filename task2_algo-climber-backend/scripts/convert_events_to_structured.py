import sys
import json
import os
from pathlib import Path

def risk_level_from_event(level):
    return "高" if str(level).upper() == "STRATEGIC" else "中"

def risk_category_from_event(info_type, event_name):
    info = str(info_type)
    title = str(event_name)
    if info == "军事" or any(k in title for k in ["演训", "军演", "空袭", "导弹", "部署", "无人机", "舰", "战机"]):
        return "军事行动"
    if info == "经济" or any(k in title for k in ["制裁", "关税", "贸易", "投资", "金融", "通胀"]):
        return "经济波动"
    if info == "科技" or any(k in title for k in ["芯片", "网络安全", "AI", "人工智能"]):
        return "科技竞争"
    if info == "社会":
        return "社会舆情"
    if info == "国内":
        return "国内政策"
    if info == "地区":
        return "地区安全"
    if info == "国际":
        return "国际关系"
    return "综合风险"

def impact_type_from_event(level, info_type):
    return "消极" if str(level).upper() == "STRATEGIC" or str(info_type) in {"军事", "经济"} else "中性"

def analysis_sentiment_from_event(level):
    return "支持强硬" if str(level).upper() == "STRATEGIC" else "谨慎观望"

def analysis_driver_from_event(info_type, event_name):
    category = risk_category_from_event(info_type, event_name)
    mapping = {
        "军事行动": "军事安全动作",
        "经济波动": "经济政策变化",
        "科技竞争": "科技竞争升温",
        "社会舆情": "舆论情绪变化",
        "国内政策": "政策调整信号",
        "地区安全": "地区局势变化",
        "国际关系": "国际关系调整",
        "综合风险": "多因素叠加",
    }
    return mapping.get(category, "多因素叠加")

def collect_topics(event, task):
    event_name = str(event.get("event_name", ""))
    source = str(event.get("source", ""))
    country = str(event.get("country", ""))
    source_type = str(event.get("source_type", ""))
    info_type = str(event.get("info_type", ""))
    topics = []
    if task:
        for k in task.get("keywords", []):
            if k and k in event_name and k not in topics:
                topics.append(k)
        for s in task.get("subjects", []):
            if s and s in event_name and s not in topics:
                topics.append(s)
    for t in [info_type, country, source_type]:
        if t and t not in topics:
            topics.append(t)
    for word in ["演训", "军演", "部署", "空袭", "导弹", "制裁", "贸易", "芯片", "AI", "网络安全"]:
        if word in event_name and word not in topics:
            topics.append(word)
    if not topics:
        topics = ["态势感知"]
    return topics[:8]

def format_event(event, task):
    event_name = str(event.get("event_name", ""))
    event_time = str(event.get("time", ""))
    level = str(event.get("level", ""))
    country = str(event.get("country", ""))
    source_type = str(event.get("source_type", ""))
    info_type = str(event.get("info_type", ""))
    risk_level = risk_level_from_event(level)
    risk_category = risk_category_from_event(info_type, event_name)
    impact_type = impact_type_from_event(level, info_type)
    sentiment = analysis_sentiment_from_event(level)
    driver = analysis_driver_from_event(info_type, event_name)
    trend = impact_type
    topics = collect_topics(event, task)
    return {
        "event": {
            "name": event_name,
            "time": event_time,
            "is_key": risk_level == "高",
        },
        "source": {
            "type": source_type or "公共媒体",
            "location": country or "未知",
        },
        "risk": {
            "level": risk_level,
            "category": risk_category,
        },
        "impact": {
            "type": impact_type,
        },
        "analysis": {
            "sentiment": sentiment,
            "driver": driver,
            "trend": trend,
        },
        "topics": topics,
    }

def main():
    if len(sys.argv) < 2:
        print("用法: python convert_events_to_structured.py <task_id>")
        sys.exit(1)
    task_id = sys.argv[1]
    base = Path(__file__).parent.parent / "output"
    events_path = base / "task_events" / f"{task_id}.json"
    tasks_path = base / "tasks.json"
    out_path = base / "task_events" / f"{task_id}_structured.json"
    if not events_path.is_file():
        print(f"事件文件不存在: {events_path}")
        sys.exit(2)
    with open(events_path, "r", encoding="utf-8") as f:
        events = json.load(f)
    with open(tasks_path, "r", encoding="utf-8") as f:
        tasks = json.load(f)
    task = next((t for t in tasks if t.get("id") == task_id), None)
    structured = [format_event(e, task) for e in events]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(structured, f, ensure_ascii=False, indent=2)
    print(f"已生成: {out_path}")

if __name__ == "__main__":
    main()
