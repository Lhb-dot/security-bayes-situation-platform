"""生成开发用「快捷登录」账号清单：frontend/src/components/dev/devAccounts.generated.ts

数据来源是**数据库本身**（app_user / scenario 两张表），不是种子脚本：

- 账号、角色、绑定场景：直接读表；
- 场景名：读 scenario.name；
- 口令：库里只有 PBKDF2 哈希（app_user.password_hash），明文取不回来，所以用候选口令
  逐个比对哈希，命中哪个就写哪个 —— 写进文件的口令由**库里的哈希**决定，不是照抄种子脚本。

候选口令的来源（按优先级）：``--password`` 参数 > 环境变量 ``QUICK_LOGIN_PASSWORD_CANDIDATES``
（逗号分隔）> 内置默认。命不中任何候选口令的账号（口令被改过）不会写进文件，只在终端列出。

用法::

    python scripts/gen_quick_login_accounts.py              # 生成
    python scripts/gen_quick_login_accounts.py --check      # 只看结果，不写文件
    python scripts/gen_quick_login_accounts.py --password 123456
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models.app_user import AppUser  # noqa: E402
from app.models.scenario import Scenario  # noqa: E402
from app.utils.common import verify_password  # noqa: E402

OUTPUT_PATH = (
    PROJECT_ROOT / "frontend" / "src" / "components" / "dev" / "devAccounts.generated.ts"
)

#: 探测口令用的默认候选：开发库里账号口令基本都出自这两个种子脚本。
DEFAULT_CANDIDATES = [
    "123456",
    "admin123",
    "net123456",
    "alice123",
    "bob123456",
    "carol123456",
]


def candidate_passwords(cli_password: str | None) -> list[str]:
    if cli_password:
        return [cli_password]
    raw = os.environ.get("QUICK_LOGIN_PASSWORD_CANDIDATES", "")
    if raw.strip():
        return [item.strip() for item in raw.split(",") if item.strip()]
    return list(DEFAULT_CANDIDATES)


def resolve_password(password_hash: str, candidates: list[str]) -> str | None:
    """库里的哈希能通过哪个候选口令，就返回哪个；都不过返回 None。"""
    return next((pwd for pwd in candidates if verify_password(pwd, password_hash)), None)


def ts_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def render(
    super_admins: list[dict],
    scenarios: list[dict],
    generated_at: str,
) -> str:
    out = [
        "/**",
        " * 本文件由 scripts/gen_quick_login_accounts.py 从数据库（app_user / scenario）生成，请勿手改。",
        f" * 生成时间：{generated_at}",
        " * 重新生成：python scripts/gen_quick_login_accounts.py",
        " */",
        "import type { UserRole } from '@/types/security';",
        "",
        "export interface DevQuickAccount {",
        "  username: string;",
        "  role: UserRole;",
        "  /** 库里该账号 password_hash 能通过校验的口令 */",
        "  password: string;",
        "}",
        "",
        "export interface DevQuickScenario {",
        "  code: string;",
        "  name: string;",
        "  accounts: DevQuickAccount[];",
        "}",
        "",
        "export const DEV_QUICK_SUPER_ADMINS: DevQuickAccount[] = [",
    ]
    for account in super_admins:
        out.append(
            "  { username: %s, role: 'SUPER_ADMIN', password: %s },"
            % (ts_string(account["username"]), ts_string(account["password"]))
        )
    out += ["];", "", "export const DEV_QUICK_SCENARIOS: DevQuickScenario[] = ["]
    for scenario in scenarios:
        out += [
            "  {",
            f"    code: {ts_string(scenario['code'])},",
            f"    name: {ts_string(scenario['name'])},",
            "    accounts: [",
        ]
        for account in scenario["accounts"]:
            out.append(
                "      { username: %s, role: %s, password: %s },"
                % (
                    ts_string(account["username"]),
                    ts_string(account["role"]),
                    ts_string(account["password"]),
                )
            )
        out += ["    ],", "  },"]
    out += ["];", ""]
    return "\n".join(out)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="从数据库生成开发用快捷登录账号清单")
    parser.add_argument("--password", help="指定口令（对每个账号只试这一个）")
    parser.add_argument("--check", action="store_true", help="只打印结果，不写文件")
    args = parser.parse_args()

    candidates = candidate_passwords(args.password)
    session = SessionLocal()
    try:
        scenarios = session.scalars(select(Scenario).order_by(Scenario.id)).all()
        users = session.scalars(select(AppUser).order_by(AppUser.username)).all()
    finally:
        session.close()

    super_admins: list[dict] = []
    per_scenario: dict[int, list[dict]] = {scenario.id: [] for scenario in scenarios}
    unresolved: list[str] = []
    disabled: list[str] = []
    unbound: list[str] = []

    for user in users:
        if user.status != "ENABLED":
            disabled.append(user.username)
            continue
        password = resolve_password(user.password_hash, candidates)
        if password is None:
            unresolved.append(user.username)
            continue
        record = {"username": user.username, "role": user.role, "password": password}
        if user.scenario_id is None:
            if user.role == "SUPER_ADMIN":
                super_admins.append(record)
            else:
                unbound.append(user.username)
        elif user.scenario_id in per_scenario:
            per_scenario[user.scenario_id].append(record)
        else:
            unbound.append(user.username)

    def order(accounts: list[dict]) -> list[dict]:
        # 场景管理员排在场景用户前面，同类按用户名
        return sorted(accounts, key=lambda a: (a["role"] != "SCENARIO_ADMIN", a["username"]))

    scenario_payload = [
        {
            "code": scenario.code,
            "name": scenario.name,
            "accounts": order(per_scenario[scenario.id]),
        }
        for scenario in scenarios
    ]
    super_admins = order(super_admins)

    print(f"数据库：{len(users)} 个账号 / {len(scenarios)} 个场景")
    print(f"超管：{[a['username'] for a in super_admins]}")
    for item in scenario_payload:
        print(f"  {item['code']:22s} {item['name']:8s} {[a['username'] for a in item['accounts']]}")
    if disabled:
        print(f"跳过（已禁用）：{disabled}")
    if unbound:
        print(f"跳过（未绑定场景）：{unbound}")
    if unresolved:
        print(f"跳过（候选口令对不上，口令可能被改过）：{unresolved}")

    content = render(super_admins, scenario_payload, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    if args.check:
        print("\n--check：不写文件。内容如下：\n")
        print(content)
        return 0

    OUTPUT_PATH.write_text(content, encoding="utf-8")
    print(f"\n已写入 {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
