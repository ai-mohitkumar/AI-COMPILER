from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from app.pipeline.architect import Architect
from app.pipeline.intent_extractor import IntentExtractor
from app.pipeline.repair_engine import RepairEngine
from app.pipeline.schema_generator import SchemaGenerator
from app.pipeline.validator import Validator
from app.runtime.runtime_builder import RuntimeBuilder
from app.schemas.compiler_schema import CompileResponse, StageTiming


class AppCompiler:
    """Orchestrates the compiler pipeline end to end."""

    def __init__(self, runtime_base_dir: str | Path = "generated/apps") -> None:
        self.intent_extractor = IntentExtractor()
        self.architect = Architect()
        self.schema_generator = SchemaGenerator()
        self.validator = Validator()
        self.repair_engine = RepairEngine()
        self.runtime_builder = RuntimeBuilder(runtime_base_dir)

    def compile(self, prompt: str, max_repair_rounds: int = 3) -> CompileResponse:
        timings: list[StageTiming] = []

        intent, timing = self._time_stage("intent_extraction", lambda: self.intent_extractor.extract(prompt))
        timings.append(timing)
        architecture, timing = self._time_stage("architecture", lambda: self.architect.design(intent))
        timings.append(timing)
        bundle, timing = self._time_stage("schema_generation", lambda: self.schema_generator.generate(intent, architecture))
        timings.append(timing)

        validation, timing = self._time_stage("validation", lambda: self.validator.validate(bundle))
        timings.append(timing)

        repair_log: list[str] = []
        repair_attempts = 0
        repaired = False

        while not validation.passed and repair_attempts < max_repair_rounds:
            repair_attempts += 1
            repaired = True
            repair_result, timing = self._time_stage(
                f"repair_round_{repair_attempts}",
                lambda: self._repair(bundle, validation),
            )
            timings.append(timing)
            bundle, round_log = repair_result
            repair_log.extend(round_log)
            validation, timing = self._time_stage(
                f"revalidation_round_{repair_attempts}",
                lambda: self.validator.validate(bundle, repair_attempts=repair_attempts, repaired=True),
            )
            timings.append(timing)

        runtime, timing = self._time_stage("runtime_build", lambda: self.runtime_builder.build(bundle))
        timings.append(timing)

        final_validation = self.validator.validate(bundle, repair_attempts=repair_attempts, repaired=repaired)
        return CompileResponse(
            app_id=runtime.app_id,
            created_at=datetime.now(timezone.utc),
            bundle=bundle,
            validation=final_validation,
            runtime=runtime,
            repair_log=repair_log,
            timings=timings,
        )

    def _repair(self, bundle, validation):
        return self.repair_engine.repair(bundle, [issue for issue in validation.issues if issue.severity == "error"])

    def _time_stage(self, stage_name: str, fn):
        started_at = perf_counter()
        result = fn()
        duration_ms = round((perf_counter() - started_at) * 1000, 2)
        return result, StageTiming(stage=stage_name, duration_ms=duration_ms)
