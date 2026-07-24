import json
import time
import urllib.request
from pathlib import Path

BASE_URL = "http://127.0.0.1:12312"


def post_json(path: str, payload: dict) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    return json.loads(urllib.request.urlopen(req).read().decode("utf-8"))


def get_json(path: str) -> dict:
    return json.loads(urllib.request.urlopen(BASE_URL + path).read().decode("utf-8"))


def main() -> None:
    create_resp = post_json(
        "/api/opinion/tasks",
        {
            "task_name": "联调测试-重跑",
            "keywords": ["红海", "航运"],
            "subjects": ["外交部"],
            "depth": 600,
            "intensity": 75,
        },
    )
    print("CREATE:", create_resp)

    task_id = create_resp.get("task_id")
    if not task_id:
        tasks_resp = get_json("/api/opinion/tasks")
        tasks = tasks_resp.get("tasks") or []
        task_id = tasks[-1].get("id") if tasks else ""

    if not task_id:
        raise RuntimeError("task_id 为空，无法继续")

    print("TASK_ID:", task_id)

    task_file = Path("output/task_events") / f"{task_id}.json"
    ready = False

    for _ in range(120):
        time.sleep(2)
        try:
            events_resp = post_json("/api/opinion/events", {"task_id": task_id, "limit": 50})
            total = int(events_resp.get("total") or 0)
        except Exception:
            total = 0
            events_resp = {"events": []}

        if task_file.exists() and total > 0:
            ready = True
            print("READY:", {"task_id": task_id, "events_total": total, "task_events_file": str(task_file)})
            events = events_resp.get("events") or []
            print("SAMPLE_EVENT:", events[0].get("event_name", "") if events else "")
            break

    if not ready:
        print("WAIT_TIMEOUT:", {"task_id": task_id, "file_exists": task_file.exists()})


if __name__ == "__main__":
    main()
