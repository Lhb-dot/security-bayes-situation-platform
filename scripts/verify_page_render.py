# -*- coding: utf-8 -*-
"""verify_page_render.py — 用无头 Chrome 对「渲染后的真实页面」做断言（本项目专用）。

背景
----
本项目前端是 **hash 路由**（`createWebHashHistory`），且由后端 StaticFiles 托管
（12312 本身就是完整站点）。因此：
- `curl http://127.0.0.1:12312/risk` 会得到 FastAPI 的 `{"detail":"Not Found"}`，
  因为真实地址是 `http://127.0.0.1:12312/#/risk`；靠抓 HTML/JS 只能证明产物里
  有/没有字符串，**证明不了页面上看得见什么**。
- 直接硬加载 `/#/xxx`（已登录状态）会被路由守卫弹回角色落地页：`main.ts` 里
  `app.use(router)` 在 `userStore.bootstrap()` 之前，守卫先跑、`currentUser` 还是
  null → 跳 /login → bootstrap 完成后守卫再跑一次 → roleLanding。所以本脚本
  **先登录 + reload，再用 `location.hash` 做客户端跳转**。

用法
----
    <python> scripts/verify_page_render.py --route "#/risk" \
        --absent "仅展示当前场景下的数据集版本" "训练参数右侧说明" \
        --present "训练配置" "开始训练" \
        --shot tmp/training_page.png

依赖：`websockets`（隔离 venv 内已装）
    C:\\Users\\11543\\.workbuddy-ai\\binaries\\python\\envs\\default\\Scripts\\python.exe

退出码：0 = 全部断言通过；1 = 有断言失败或环境/登录失败。
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

# 沙箱里 localhost 会被代理拦（502），必须显式绕过代理
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _find_chrome() -> str:
    for p in CHROME_CANDIDATES:
        if os.path.exists(p):
            return p
    raise SystemExit("未找到 Chrome/Edge 可执行文件，请补进 CHROME_CANDIDATES")


async def run(args) -> int:
    import websockets

    chrome = _find_chrome()
    port = args.port
    base = args.base.rstrip("/")
    profile = tempfile.mkdtemp(prefix="cdp-profile-")
    proc = subprocess.Popen(
        [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--no-proxy-server",
            "--remote-debugging-port=%d" % port,
            "--user-data-dir=%s" % profile,
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    ws_url = None
    for _ in range(60):
        try:
            with _OPENER.open("http://127.0.0.1:%d/json/list" % port, timeout=5) as r:
                for t in json.loads(r.read().decode("utf-8")):
                    if t.get("type") == "page":
                        ws_url = t["webSocketDebuggerUrl"]
                        break
            if ws_url:
                break
        except Exception:
            pass
        time.sleep(0.5)

    if not ws_url:
        proc.kill()
        shutil.rmtree(profile, ignore_errors=True)
        print("FATAL: 连不上 Chrome devtools 端点")
        return 1

    try:
        async with websockets.connect(ws_url, max_size=64 * 1024 * 1024) as ws:
            msg_id = 0

            async def send(method, params=None):
                nonlocal msg_id
                msg_id += 1
                mid = msg_id
                await ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
                while True:
                    raw = json.loads(await ws.recv())
                    if raw.get("id") == mid:
                        if "error" in raw:
                            raise RuntimeError("%s -> %s" % (method, raw["error"]))
                        return raw.get("result", {})

            async def js(expr, await_promise=False):
                res = await send(
                    "Runtime.evaluate",
                    {"expression": expr, "awaitPromise": await_promise, "returnByValue": True},
                )
                return res.get("result", {}).get("value")

            await send("Page.enable")
            await send("Runtime.enable")
            await send(
                "Emulation.setDeviceMetricsOverride",
                {
                    "width": args.width,
                    "height": args.height,
                    "deviceScaleFactor": 1,
                    "mobile": False,
                },
            )

            # 1) 载入真实 SPA（登录页），拿到正确 origin
            await send("Page.navigate", {"url": base + "/#/login"})
            await asyncio.sleep(4)

            # 2) 在页面内登录，cookie 落到正确 origin
            ok_login = False
            for pwd in args.passwords:
                expr = """(async () => {
                  const r = await fetch('/api/v1/auth/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    credentials: 'include',
                    body: JSON.stringify({username: %s, password: %s})
                  });
                  return r.status;
                })()""" % (json.dumps(args.username), json.dumps(pwd))
                status = await js(expr, await_promise=True)
                print("login %s/%s -> HTTP %s" % (args.username, pwd, status))
                if status == 200:
                    ok_login = True
                    break
            if not ok_login:
                print("FATAL: 登录失败（候选密码都不对）")
                return 1

            # 3) reload 让 bootstrap() 认到会话，再用 hash 做客户端跳转
            await js("location.reload()")
            await asyncio.sleep(5)
            await js("location.hash = %s" % json.dumps(args.route))
            text = ""
            for _ in range(20):
                await asyncio.sleep(1)
                text = await js("document.body ? document.body.innerText : ''") or ""
                if args.ready and args.ready in text:
                    break

            print("\n===== PAGE TEXT (%s) =====" % args.route)
            print(text[:3000])
            print("===== END PAGE TEXT =====\n")

            ok = True
            for s in args.absent:
                hit = s in text
                ok = ok and not hit
                print("ABSENT?  %-40s %s" % (s, "OK" if not hit else "!! STILL VISIBLE"))
            for s in args.present:
                hit = s in text
                ok = ok and hit
                print("PRESENT? %-40s %s" % (s, "OK" if hit else "!! MISSING"))

            if args.shot:
                shot = await send(
                    "Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True}
                )
                os.makedirs(os.path.dirname(os.path.abspath(args.shot)), exist_ok=True)
                with open(args.shot, "wb") as f:
                    f.write(base64.b64decode(shot["data"]))
                print("screenshot -> %s" % args.shot)

            print("VERDICT:", "PASS" if ok else "FAIL")
            return 0 if ok else 1
    finally:
        proc.kill()
        shutil.rmtree(profile, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="无头 Chrome 渲染断言（本项目专用）")
    ap.add_argument("--base", default="http://127.0.0.1:12312", help="站点根地址")
    ap.add_argument("--route", default="#/risk", help="hash 路由，如 '#/risk'")
    ap.add_argument("--username", default="admin")
    ap.add_argument(
        "--passwords",
        nargs="*",
        default=["123456", "admin123"],
        help="候选密码，逐个尝试（实测种子密码是 123456）",
    )
    ap.add_argument("--absent", nargs="*", default=[], help="断言页面上【不应出现】的文本")
    ap.add_argument("--present", nargs="*", default=[], help="断言页面上【应出现】的文本")
    ap.add_argument("--ready", default="", help="等到该文本出现即认为页面就绪")
    ap.add_argument("--shot", default="", help="截图输出路径")
    ap.add_argument("--port", type=int, default=9333)
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=1250)
    args = ap.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
