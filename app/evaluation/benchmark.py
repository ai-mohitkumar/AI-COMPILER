from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from time import perf_counter

from app.pipeline.compiler import AppCompiler


def run_benchmark() -> dict:
    dataset_path = Path(__file__).with_name("dataset.json")
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    compiler = AppCompiler()

    cases = []
    for item in dataset:
        started_at = perf_counter()
        result = compiler.compile(item["prompt"])
        latency = round((perf_counter() - started_at) * 1000, 2)

        actual_entities = [entity.name for entity in result.bundle.db_schema.entities]
        actual_features = result.bundle.intent.features
        expectation_passed = (
            result.bundle.intent.app_type == item["expected_app_type"]
            and all(entity in actual_entities for entity in item.get("expected_entities", []))
            and all(feature in actual_features for feature in item.get("expected_features", []))
        )
        repaired = bool(result.repair_log)

        cases.append(
            {
                "id": item["id"],
                "category": item["category"],
                "validation_passed": result.validation.passed,
                "expectation_passed": expectation_passed,
                "repaired": repaired,
                "repair_steps": len(result.repair_log),
                "latency_ms": latency,
                "remaining_errors": [
                    issue.model_dump(mode="json")
                    for issue in result.validation.issues
                    if issue.severity == "error"
                ],
            }
        )

    success_cases = [case for case in cases if case["validation_passed"] and case["expectation_passed"]]
    repaired_cases = [case for case in cases if case["repaired"]]
    retries = [1 if case["repaired"] else 0 for case in cases]

    return {
        "summary": {
            "total_cases": len(cases),
            "success_rate": round((len(success_cases) / len(cases)) * 100, 2),
            "repair_rate": round((len(repaired_cases) / len(cases)) * 100, 2),
            "avg_latency_ms": round(mean(case["latency_ms"] for case in cases), 2),
            "avg_retries": round(mean(retries), 2),
        },
        "cases": cases,
    }


if __name__ == "__main__":
    print(json.dumps(run_benchmark(), indent=2))
