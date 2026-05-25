from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.config import Settings
from app.pipeline.compiler import AppCompiler
from app.runtime.repository import RuntimeRepository
from app.schemas.api_schema import RouteDefinition
from app.schemas.compiler_schema import CompileResponse, SchemaBundle
from app.schemas.db_schema import EntitySchema, FieldDefinition

settings = Settings.from_env()
app = FastAPI(title="AI Application Compiler", version="1.0.0")
compiler = AppCompiler(settings.generated_apps_dir)
repository = RuntimeRepository(settings.generated_apps_dir)
HOME_TEMPLATE = Path(__file__).resolve().parent / "templates" / "home.html"


class CompileRequest(BaseModel):
    prompt: str


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return HOME_TEMPLATE.read_text(encoding="utf-8")


@app.post("/compile", response_model=CompileResponse)
def compile_app(request: CompileRequest) -> CompileResponse:
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt must not be empty.")
    result = compiler.compile(request.prompt)
    repository.register(result.app_id, result.runtime.manifest_path)
    return result


@app.get("/apps/{app_id}/spec")
def app_spec(app_id: str) -> dict[str, Any]:
    try:
        return repository.get_manifest(app_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown app id '{app_id}'.") from exc


@app.get("/runtime/apps/{app_id}", response_class=HTMLResponse)
def runtime_preview(app_id: str) -> str:
    try:
        runtime = repository.runtime_meta(app_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown app id '{app_id}'.") from exc
    frontend_path = Path(runtime["frontend_path"])
    return frontend_path.read_text(encoding="utf-8")


@app.get("/runtime/apps/{app_id}/health")
def runtime_health(app_id: str) -> dict[str, Any]:
    bundle, runtime = _load_runtime(app_id)
    return {
        "app_id": app_id,
        "entities": [entity.name for entity in bundle.db_schema.entities],
        "pages": [page.name for page in bundle.ui_schema.pages],
        "database_path": runtime["database_path"],
    }


@app.get("/runtime/apps/{app_id}/api/session")
def runtime_session(app_id: str, role: str | None = Query(default=None)) -> dict[str, Any]:
    bundle, _ = _load_runtime(app_id)
    effective_role = _resolve_role(bundle, role)
    return {"role": effective_role, "auth_enabled": bundle.auth_schema.enabled}


@app.get("/runtime/apps/{app_id}/api/analytics/summary")
def analytics_summary(app_id: str, role: str | None = Query(default=None)) -> list[dict[str, Any]]:
    bundle, runtime = _load_runtime(app_id)
    route = _route_for(bundle, "GET", "/api/analytics/summary")
    _authorize(bundle, _resolve_role(bundle, role), route)

    with _connect(runtime) as connection:
        rows = []
        for entity in bundle.db_schema.entities:
            count = connection.execute(f'SELECT COUNT(*) AS count FROM "{entity.name}"').fetchone()["count"]
            rows.append({"entity": entity.name, "count": count})
        return rows


@app.get("/runtime/apps/{app_id}/api/{entity}")
def list_records(app_id: str, entity: str, role: str | None = Query(default=None)) -> list[dict[str, Any]]:
    bundle, runtime = _load_runtime(app_id)
    entity_schema = _entity(bundle, entity)
    route = _route_for(bundle, "GET", f"/api/{entity}")
    _authorize(bundle, _resolve_role(bundle, role), route)

    with _connect(runtime) as connection:
        rows = connection.execute(f'SELECT * FROM "{entity_schema.name}" ORDER BY created_at DESC').fetchall()
        return [dict(row) for row in rows]


@app.get("/runtime/apps/{app_id}/api/{entity}/{record_id}")
def detail_record(app_id: str, entity: str, record_id: str, role: str | None = Query(default=None)) -> dict[str, Any]:
    bundle, runtime = _load_runtime(app_id)
    entity_schema = _entity(bundle, entity)
    route = _route_for(bundle, "GET", f"/api/{entity}/{{record_id}}")
    _authorize(bundle, _resolve_role(bundle, role), route)

    with _connect(runtime) as connection:
        row = connection.execute(
            f'SELECT * FROM "{entity_schema.name}" WHERE id = ?',
            (record_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Unknown record '{record_id}'.")
        return dict(row)


@app.post("/runtime/apps/{app_id}/api/{entity}")
async def create_record(app_id: str, entity: str, request: Request, role: str | None = Query(default=None)) -> dict[str, Any]:
    bundle, runtime = _load_runtime(app_id)
    entity_schema = _entity(bundle, entity)
    route = _route_for(bundle, "POST", f"/api/{entity}")
    _authorize(bundle, _resolve_role(bundle, role), route)

    payload = await request.json()
    prepared = _prepare_payload(bundle, runtime, entity_schema, payload, partial=False)
    with _connect(runtime) as connection:
        columns = list(prepared.keys())
        values = [prepared[column] for column in columns]
        placeholders = ", ".join(["?"] * len(columns))
        quoted_columns = ", ".join(f'"{column}"' for column in columns)
        connection.execute(
            f'INSERT INTO "{entity_schema.name}" ({quoted_columns}) VALUES ({placeholders})',
            values,
        )
        connection.commit()
    return prepared


@app.put("/runtime/apps/{app_id}/api/{entity}/{record_id}")
async def update_record(
    app_id: str,
    entity: str,
    record_id: str,
    request: Request,
    role: str | None = Query(default=None),
) -> dict[str, Any]:
    bundle, runtime = _load_runtime(app_id)
    entity_schema = _entity(bundle, entity)
    route = _route_for(bundle, "PUT", f"/api/{entity}/{{record_id}}")
    _authorize(bundle, _resolve_role(bundle, role), route)

    payload = await request.json()
    prepared = _prepare_payload(bundle, runtime, entity_schema, payload, partial=True)
    if not prepared:
        raise HTTPException(status_code=400, detail="No valid fields provided.")

    assignments = ", ".join(f'"{column}" = ?' for column in prepared.keys())
    values = list(prepared.values()) + [record_id]
    with _connect(runtime) as connection:
        result = connection.execute(
            f'UPDATE "{entity_schema.name}" SET {assignments}, "updated_at" = ? WHERE id = ?',
            list(prepared.values()) + [_timestamp(), record_id],
        )
        connection.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Unknown record '{record_id}'.")
        row = connection.execute(f'SELECT * FROM "{entity_schema.name}" WHERE id = ?', (record_id,)).fetchone()
        return dict(row)


@app.delete("/runtime/apps/{app_id}/api/{entity}/{record_id}")
def delete_record(app_id: str, entity: str, record_id: str, role: str | None = Query(default=None)) -> dict[str, Any]:
    bundle, runtime = _load_runtime(app_id)
    entity_schema = _entity(bundle, entity)
    route = _route_for(bundle, "DELETE", f"/api/{entity}/{{record_id}}")
    _authorize(bundle, _resolve_role(bundle, role), route)

    with _connect(runtime) as connection:
        result = connection.execute(f'DELETE FROM "{entity_schema.name}" WHERE id = ?', (record_id,))
        connection.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Unknown record '{record_id}'.")
    return {"deleted": True, "record_id": record_id}


def _load_runtime(app_id: str) -> tuple[SchemaBundle, dict]:
    try:
        return repository.load_bundle(app_id), repository.runtime_meta(app_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown app id '{app_id}'.") from exc


def _connect(runtime: dict) -> sqlite3.Connection:
    connection = sqlite3.connect(runtime["database_path"])
    connection.row_factory = sqlite3.Row
    return connection


def _entity(bundle: SchemaBundle, entity_name: str) -> EntitySchema:
    entity = next((item for item in bundle.db_schema.entities if item.name == entity_name), None)
    if entity is None:
        raise HTTPException(status_code=404, detail=f"Unknown entity '{entity_name}'.")
    return entity


def _route_for(bundle: SchemaBundle, method: str, path: str) -> RouteDefinition:
    route = next((item for item in bundle.api_schema.routes if item.method == method and item.path == path), None)
    if route is None:
        raise HTTPException(status_code=404, detail=f"Unknown route '{method} {path}'.")
    return route


def _resolve_role(bundle: SchemaBundle, requested_role: str | None) -> str:
    known_roles = {role.name for role in bundle.auth_schema.roles}
    if requested_role and requested_role in known_roles:
        return requested_role
    return bundle.auth_schema.default_role


def _authorize(bundle: SchemaBundle, role_name: str, route: RouteDefinition) -> None:
    if route.public or not route.permission or not bundle.auth_schema.enabled:
        return

    role = next((item for item in bundle.auth_schema.roles if item.name == role_name), None)
    if role is None or route.permission not in role.permissions:
        raise HTTPException(status_code=403, detail=f"Role '{role_name}' lacks permission '{route.permission}'.")


def _prepare_payload(
    bundle: SchemaBundle,
    runtime: dict,
    entity: EntitySchema,
    payload: dict[str, Any],
    *,
    partial: bool,
) -> dict[str, Any]:
    fields = [field for field in entity.fields if field.name not in {"id", "created_at", "updated_at"}]
    prepared: dict[str, Any] = {}
    for field in fields:
        if field.name in payload:
            prepared[field.name] = _coerce_value(field, payload[field.name])
        elif not partial:
            if field.reference_entity:
                prepared[field.name] = _first_related_id(runtime, field.reference_entity)
            elif field.required:
                prepared[field.name] = _fallback_value(field)

    if not partial:
        prepared["id"] = uuid4().hex[:12]
        prepared["created_at"] = _timestamp()
        prepared["updated_at"] = _timestamp()
    return prepared


def _coerce_value(field: FieldDefinition, value: Any) -> Any:
    if value in ("", None):
        return None if not field.required else _fallback_value(field)
    if field.type == "integer":
        return int(value)
    if field.type == "float":
        return float(value)
    if field.type == "boolean":
        if isinstance(value, bool):
            return int(value)
        return 1 if str(value).lower() in {"1", "true", "yes", "on"} else 0
    return str(value)


def _fallback_value(field: FieldDefinition) -> Any:
    if field.type == "integer":
        return 0
    if field.type == "float":
        return 0.0
    if field.type == "boolean":
        return 0
    if field.type in {"date", "datetime"}:
        return _timestamp()
    return field.name.replace("_", " ").title()


def _first_related_id(runtime: dict, target_entity: str) -> str:
    with _connect(runtime) as connection:
        row = connection.execute(f'SELECT id FROM "{target_entity}" ORDER BY created_at LIMIT 1').fetchone()
        return str(row["id"]) if row else f"{target_entity[:-1] if target_entity.endswith('s') else target_entity}-001"


def _timestamp() -> str:
    return "2026-01-01T09:00:00Z"
