from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.api_schema import APISchema
from app.schemas.auth_schema import AuthSchema
from app.schemas.db_schema import DatabaseSchema
from app.schemas.intent_schema import UserIntent
from app.schemas.ui_schema import UISchema


class FieldBlueprint(BaseModel):
    name: str
    type: str
    required: bool = True
    searchable: bool = False
    filterable: bool = False
    reference_entity: str | None = None


class EntityBlueprint(BaseModel):
    name: str
    description: str
    fields: list[FieldBlueprint] = Field(default_factory=list)
    primary_display_field: str = "name"


class PageBlueprint(BaseModel):
    name: str
    title: str
    page_type: str
    entity: str | None = None
    components: list[str] = Field(default_factory=list)
    required_permissions: list[str] = Field(default_factory=list)


class UserFlow(BaseModel):
    name: str
    actor: str
    steps: list[str] = Field(default_factory=list)
    outcome: str


class AppArchitecture(BaseModel):
    app_name: str
    slug: str
    summary: str
    entities: list[EntityBlueprint] = Field(default_factory=list)
    pages: list[PageBlueprint] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    flows: list[UserFlow] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class SchemaBundle(BaseModel):
    intent: UserIntent
    architecture: AppArchitecture
    db_schema: DatabaseSchema
    api_schema: APISchema
    ui_schema: UISchema
    auth_schema: AuthSchema


class ValidationIssue(BaseModel):
    severity: Literal["error", "warning"]
    component: Literal["intent", "architecture", "db", "api", "ui", "auth", "runtime"]
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    repairable: bool = True


class ValidationReport(BaseModel):
    passed: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    repair_attempts: int = 0
    repaired: bool = False


class RuntimeManifest(BaseModel):
    app_id: str
    slug: str
    preview_path: str
    api_base_path: str
    artifact_dir: str
    manifest_path: str
    database_path: str
    seed_summary: dict[str, int] = Field(default_factory=dict)
    backend_code: str
    frontend_code: str
    prisma_schema: str


class StageTiming(BaseModel):
    stage: str
    duration_ms: float


class CompileResponse(BaseModel):
    app_id: str
    created_at: datetime
    bundle: SchemaBundle
    validation: ValidationReport
    runtime: RuntimeManifest
    repair_log: list[str] = Field(default_factory=list)
    timings: list[StageTiming] = Field(default_factory=list)
