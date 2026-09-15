"""Validate the complete explanation configuration before deployment.

This check expands generated feature families first, then validates the same
configuration shape used by the explanation service. It exits non-zero on any
missing scenario field or feature metadata item.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.data.scenario_feature_catalog import expand_scenario_feature_catalog  # noqa: E402
from app.schemas.scenario_config import validate_scenario_configs  # noqa: E402


def main() -> int:
    config_path = BACKEND_ROOT / "app" / "data" / "scenario_configs.json"
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"解释配置读取失败: {exc}", file=sys.stderr)
        return 1

    configs = expand_scenario_feature_catalog(raw)
    errors = validate_scenario_configs(configs)
    if errors:
        print("解释配置校验失败:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("解释配置校验通过:")
    for code, config in configs.items():
        print(
            f"- {code}: {len(config.get('required_feature_names') or [])} 个输入字段，"
            f"{len(config.get('feature_dictionary') or {})} 个字段说明"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
