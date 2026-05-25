from pathlib import Path

from app.pipeline.compiler import AppCompiler
from app.runtime.runtime_builder import RuntimeBuilder


def test_compile_crm_prompt(tmp_path: Path) -> None:
    compiler = AppCompiler()
    compiler.runtime_builder = RuntimeBuilder(tmp_path / "apps")

    result = compiler.compile("Build a CRM with login, contacts, tasks, and analytics.")

    assert result.validation.passed is True
    assert result.bundle.intent.app_type == "CRM"
    assert any(entity.name == "contacts" for entity in result.bundle.db_schema.entities)
    assert Path(result.runtime.manifest_path).exists()
    assert Path(result.runtime.database_path).exists()


def test_conflicting_auth_prompt_triggers_repair(tmp_path: Path) -> None:
    compiler = AppCompiler()
    compiler.runtime_builder = RuntimeBuilder(tmp_path / "apps")

    result = compiler.compile("Build a CRM with no login but role-based permissions.")

    assert result.validation.passed is True
    assert result.validation.repaired is True
    assert result.bundle.auth_schema.enabled is True
    assert result.repair_log
