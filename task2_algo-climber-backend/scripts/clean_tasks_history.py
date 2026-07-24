import json
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "output"
TASKS_FILE = OUTPUT_DIR / "tasks.json"
BACKUP_FILE = OUTPUT_DIR / f"tasks.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"


def looks_like_mojibake(text: str) -> bool:
    if not text:
        return False

    suspicious_tokens = [
        "Ã", "Â", "Ð", "Ñ", "å", "ä", "ç", "è", "é", "ï", "ö", "ü", "æ", "œ", "¤", "¦", "±", "¼", "½", "¿",
        "\x83", "\x84", "\x85", "\x86", "\x87", "\x88", "\x89", "\x8a", "\x8b", "\x8c", "\x8d", "\x8e", "\x8f",
        "\x90", "\x91", "\x92", "\x93", "\x94", "\x95", "\x96", "\x97", "\x98", "\x99", "\x9a", "\x9b", "\x9c", "\x9d", "\x9e", "\x9f",
    ]
    if any(token in text for token in suspicious_tokens):
        return True

    gbk_mojibake_chars = set("鐨鍦鍥鍙鍚鍒鍔鍩鍥鏃鏄鏉鏋楠彂灞曡涓氶噺鏈鏂版崯鎶樼瓑閫氶亾杞ㄨ澶囧競璇璁鍏鍏憡")
    hit = sum(1 for ch in text if ch in gbk_mojibake_chars)
    ratio = hit / max(len(text), 1)
    return ratio >= 0.18 and hit >= 6


def text_quality_score(text: str) -> int:
    if not text:
        return -10000
    length = max(len(text), 1)
    cjk_count = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    suspicious_count = sum(1 for ch in text if ch in {"Ã", "Â", "Ð", "Ñ", "å", "ä", "ç", "è", "é", "ï", "ö", "ü", "æ", "œ", "¤", "¦", "±", "¼", "½", "¿"})
    control_count = sum(1 for ch in text if (0 <= ord(ch) < 32 and ch not in "\t\n\r") or (127 <= ord(ch) <= 159))
    replacement_count = text.count("�")
    printable_count = sum(1 for ch in text if ch.isprintable() or ch in "\t\n\r")
    printable_ratio = int((printable_count / length) * 100)
    return cjk_count * 8 + printable_ratio - suspicious_count * 6 - control_count * 12 - replacement_count * 10


def fix_mojibake(text: str) -> str:
    if not text:
        return text
    if not looks_like_mojibake(text):
        return text

    candidates = [text]

    def add_candidate(src: str, dst: str, mode: str) -> None:
        try:
            transformed = text.encode(src, errors=mode).decode(dst, errors=mode)
            if transformed:
                candidates.append(transformed)
        except Exception:
            return

    for src in ("latin1", "cp1252"):
        for dst in ("utf-8", "gb18030"):
            add_candidate(src, dst, "ignore")

    for src in ("gbk", "gb18030"):
        add_candidate(src, "utf-8", "ignore")

    return max(candidates, key=text_quality_score)


def to_text(value: Any) -> str:
    if value is None:
        return ""
    return fix_mojibake(str(value).strip())


def is_readable(text: str) -> bool:
    cleaned = to_text(text)
    if not cleaned:
        return False
    if looks_like_mojibake(cleaned):
        return False
    return text_quality_score(cleaned) >= 40


def clean_event_item(item: Dict[str, Any], title_key: str) -> Dict[str, Any]:
    cleaned = dict(item)
    for key in list(cleaned.keys()):
        if isinstance(cleaned[key], str):
            cleaned[key] = to_text(cleaned[key])
    title = to_text(cleaned.get(title_key, ""))
    cleaned[title_key] = title
    return cleaned


def clean_tasks(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []

    for task in tasks:
        if not isinstance(task, dict):
            continue
        cleaned_task = dict(task)

        for key in ("id", "name", "status", "time"):
            if key in cleaned_task and isinstance(cleaned_task[key], str):
                cleaned_task[key] = to_text(cleaned_task[key])

        articles = cleaned_task.get("articles", [])
        intel = cleaned_task.get("intel", [])

        new_articles = []
        if isinstance(articles, list):
            for article in articles:
                if not isinstance(article, dict):
                    continue
                cleaned_article = clean_event_item(article, "title")
                if is_readable(cleaned_article.get("title", "")):
                    new_articles.append(cleaned_article)

        new_intel = []
        if isinstance(intel, list):
            for intel_item in intel:
                if not isinstance(intel_item, dict):
                    continue
                cleaned_intel = clean_event_item(intel_item, "title")
                if is_readable(cleaned_intel.get("title", "")):
                    new_intel.append(cleaned_intel)

        cleaned_task["articles"] = new_articles
        cleaned_task["intel"] = new_intel
        result.append(cleaned_task)

    return result


def main() -> None:
    if not TASKS_FILE.exists():
        print(f"tasks.json not found: {TASKS_FILE}")
        return

    with TASKS_FILE.open("r", encoding="utf-8") as f:
        tasks = json.load(f)

    if isinstance(tasks, dict):
        tasks = [tasks]
    if not isinstance(tasks, list):
        print("Invalid tasks.json format")
        return

    with BACKUP_FILE.open("w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)

    cleaned = clean_tasks(tasks)

    with TASKS_FILE.open("w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

    before_articles = sum(len(t.get("articles", [])) for t in tasks if isinstance(t, dict))
    after_articles = sum(len(t.get("articles", [])) for t in cleaned if isinstance(t, dict))
    before_intel = sum(len(t.get("intel", [])) for t in tasks if isinstance(t, dict))
    after_intel = sum(len(t.get("intel", [])) for t in cleaned if isinstance(t, dict))

    print("Clean completed")
    print(f"Backup: {BACKUP_FILE}")
    print(f"Articles: {before_articles} -> {after_articles}")
    print(f"Intel: {before_intel} -> {after_intel}")


if __name__ == "__main__":
    main()
