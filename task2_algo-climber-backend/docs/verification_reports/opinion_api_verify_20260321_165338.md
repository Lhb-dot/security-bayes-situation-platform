# Opinion API Verification Report

- GeneratedAt: 2026-03-21 16:53:38
- BaseUrl: http://127.0.0.1:12312
- VerifyTaskId: t-1774083149
- Passed: 4
- Failed: 3

| CaseID | API | Scenario | Expected | Actual | Result |
|---|---|---|---|---|---|
| T1 | GET /api/opinion/tasks | success | 200 + success=true | status=200, total=1 | PASS |
| T2 | POST /api/opinion/tasks | create task | 200 + returns task_id | status=200, task_id=t-1774083149, message=èææç¥ä»»å¡å·²åå»ºå¹¶å¯å¨ | PASS |
| T3 | POST /api/opinion/events | query by task_id | 200 + events array | status=404, total=, task_id=t-1774083149 | FAIL |
| T4 | POST /api/opinion/raw | query by task_id | 200 + raw_items array | status=404, total=, task_id=t-1774083149 | FAIL |
| T5 | POST /api/opinion/raw | filter check(title/keyword/source) | 200 + filter applied | status=404, total= | FAIL |
| T6 | POST /api/opinion/raw | task not found | 404 | status=404, error=The remote server returned an error: (404) Not Found. | PASS |
| T7 | POST /api/opinion/raw | limit out of range(limit=5001) | 422 | status=422, error=The remote server returned an error: (422) Unprocessable Entity. | PASS |
