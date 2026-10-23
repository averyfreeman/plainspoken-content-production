#!/usr/bin/env python3
"""Replay synthetic editing scenarios; these are regression checks, not human studies."""
from __future__ import annotations
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent


def evaluate(data):
    name = "plainspoken_eval"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    from importlib import import_module
    detector = import_module(name + ".detector")
    scenarios = [json.loads(line) for line in Path(data).read_text(encoding="utf-8").splitlines() if line.strip()]
    if not scenarios or len({row["id"] for row in scenarios}) != len(scenarios):
        raise ValueError("evaluation needs nonempty scenarios with unique ids")
    results = []
    for scenario in scenarios:
        if scenario["label"] not in {"needs_edit", "acceptable"}:
            raise ValueError("labels must describe editing behavior")
        report = detector.check(scenario["text"], scenario["surface"])
        expected = scenario["label"] == "needs_edit"
        results.append({"id": scenario["id"], "surface": report.surface,
                        "expected": scenario["label"], "actual": report.verdict,
                        "score": report.score, "matched": report.needs_rewrite == expected,
                        "findings": [f.rule for f in report.findings if f.counted]})
    return {"kind": "synthetic_regression", "scenarios": len(results),
            "matched": sum(row["matched"] for row in results),
            "by_surface": dict(Counter(row["surface"] for row in results)), "results": results}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "eval" / "data" / "english.jsonl")
    parser.add_argument("--json", type=Path, help="Optional destination for the computed results")
    args = parser.parse_args(argv)
    result = evaluate(args.data)
    if args.json:
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Synthetic scenarios matched: {result['matched']}/{result['scenarios']}")
    for row in result["results"]:
        if not row["matched"]:
            print(f"  Mismatch: {row['id']} expected {row['expected']}, got {row['actual']}")
    return 0 if result["matched"] == result["scenarios"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
