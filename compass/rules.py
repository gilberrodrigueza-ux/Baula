"""Carga de las reglas versionadas (rules/*.json)."""
from __future__ import annotations

import json
from pathlib import Path

RULES_DIR = Path(__file__).resolve().parent.parent / "rules"


def load_rules(name: str, rules_dir: Path = RULES_DIR) -> dict:
    with open(rules_dir / f"{name}.json", encoding="utf-8") as f:
        return json.load(f)


def rule(broadcom: dict, key: str):
    return broadcom["rules"][key]["value"]
