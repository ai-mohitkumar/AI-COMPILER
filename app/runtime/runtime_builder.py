from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.runtime.fastapi_generator import FastAPIGenerator
from app.runtime.prisma_generator import PrismaGenerator
from app.runtime.react_generator import ReactGenerator
from app.schemas.compiler_schema import RuntimeManifest, SchemaBundle
from app.schemas.db_schema import DatabaseSchema, EntitySchema, FieldDefinition


SQLITE_TYPE_MAP = {
    "uuid": "TEXT",
    "string": "TEXT",
    "text": "TEXT",
    "integer": "INTEGER",
    "float": "REAL",
    "boolean": "INTEGER",
    "datetime": "TEXT",
    "date": "TEXT",
}


class RuntimeBuilder:
    """Creates executable runtime artifacts from a validated schema bundle."""

    def __init__(self, base_dir: str | Path = "generated/apps") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.fastapi_generator = FastAPIGenerator()
        self.react_generator = ReactGenerator()
        self.prisma_generator = PrismaGenerator()

    def build(self, bundle: SchemaBundle) -> RuntimeManifest:
        app_id = uuid4().hex[:10]
        slug = bundle.architecture.slug
        artifact_dir = self.base_dir / f"{slug}-{app_id}"
        artifact_dir.mkdir(parents=True, exist_ok=True)

        preview_path = f"/runtime/apps/{app_id}"
        api_base_path = f"/runtime/apps/{app_id}/api"
        database_path = artifact_dir / "app.db"
        manifest_path = artifact_dir / "manifest.json"
        backend_path = artifact_dir / "backend.py"
        frontend_path = artifact_dir / "frontend.html"
        prisma_path = artifact_dir / "schema.prisma"

        seed_rows = self._build_seed_rows(bundle.db_schema)
        self._write_sqlite_database(database_path, bundle.db_schema, seed_rows)

        backend_code = self.fastapi_generator.generate(bundle.api_schema, api_base_path)
        frontend_code = self.react_generator.generate(
            app_name=bundle.intent.app_name,
            app_id=app_id,
            api_base_path=api_base_path,
            preview_path=preview_path,
            ui_schema=bundle.ui_schema,
            auth_schema=bundle.auth_schema,
        )
        prisma_schema = self.prisma_generator.generate(bundle.db_schema)

        backend_path.write_text(backend_code, encoding="utf-8")
        frontend_path.write_text(frontend_code, encoding="utf-8")
        prisma_path.write_text(prisma_schema, encoding="utf-8")

        manifest_payload = {
            "app_id": app_id,
            "slug": slug,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "bundle": bundle.model_dump(mode="json"),
            "runtime": {
                "preview_path": preview_path,
                "api_base_path": api_base_path,
                "database_path": str(database_path.resolve()),
                "frontend_path": str(frontend_path.resolve()),
                "backend_path": str(backend_path.resolve()),
                "prisma_path": str(prisma_path.resolve()),
            },
        }
        manifest_path.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")

        return RuntimeManifest(
            app_id=app_id,
            slug=slug,
            preview_path=preview_path,
            api_base_path=api_base_path,
            artifact_dir=str(artifact_dir.resolve()),
            manifest_path=str(manifest_path.resolve()),
            database_path=str(database_path.resolve()),
            seed_summary={entity_name: len(rows) for entity_name, rows in seed_rows.items()},
            backend_code=backend_code,
            frontend_code=frontend_code,
            prisma_schema=prisma_schema,
        )

    def _build_seed_rows(self, db_schema: DatabaseSchema) -> dict[str, list[dict[str, object]]]:
        rows_by_entity: dict[str, list[dict[str, object]]] = {}
        ids_by_entity: dict[str, list[str]] = {}
        timestamp = "2026-01-01T09:00:00Z"

        for entity in db_schema.entities:
            rows: list[dict[str, object]] = []
            singular = entity.name[:-1] if entity.name.endswith("s") else entity.name
            for index in range(1, entity.seed_count + 1):
                row: dict[str, object] = {}
                for field in entity.fields:
                    if field.name == "id":
                        value = f"{singular}-{index:03d}"
                    elif field.name in {"created_at", "updated_at"}:
                        value = timestamp
                    elif field.reference_entity:
                        target_ids = ids_by_entity.get(field.reference_entity, [])
                        value = target_ids[(index - 1) % len(target_ids)] if target_ids else f"{field.reference_entity[:-1] if field.reference_entity.endswith('s') else field.reference_entity}-001"
                    else:
                        value = self._seed_value(entity.name, field, index)
                    row[field.name] = value
                rows.append(row)
            rows_by_entity[entity.name] = rows
            ids_by_entity[entity.name] = [str(item["id"]) for item in rows]
        return rows_by_entity

    def _seed_value(self, entity_name: str, field: FieldDefinition, index: int) -> object:
        label = entity_name[:-1] if entity_name.endswith("s") else entity_name
        if field.default is not None:
            return field.default
        if field.name == "email" or field.name.endswith("_email"):
            return f"{label}{index}@example.com"
        if field.name in {"full_name", "name"}:
            return f"{label.replace('_', ' ').title()} {index}"
        if field.name == "title":
            return f"{label.replace('_', ' ').title()} Item {index}"
        if field.name == "status":
            return ["new", "active", "closed"][(index - 1) % 3]
        if field.name in {"company", "department", "category", "owner", "assignee", "job_title", "priority", "movement_type", "request_type"}:
            return f"{field.name.replace('_', ' ').title()} {index}"
        if field.name in {"due_date", "start_date"}:
            return f"2026-01-{index + 9:02d}"
        if field.type == "integer":
            return index * 10
        if field.type == "float":
            return round(index * 19.5, 2)
        if field.type == "boolean":
            return 1 if index % 2 == 0 else 0
        if field.type in {"date", "datetime"}:
            return "2026-01-01T09:00:00Z"
        return f"{field.name.replace('_', ' ').title()} {index}"

    def _write_sqlite_database(
        self,
        database_path: Path,
        db_schema: DatabaseSchema,
        rows_by_entity: dict[str, list[dict[str, object]]],
    ) -> None:
        connection = sqlite3.connect(database_path)
        try:
            connection.execute("PRAGMA foreign_keys = ON;")
            for entity in db_schema.entities:
                self._create_table(connection, entity)
                self._create_indexes(connection, entity)
            for entity in db_schema.entities:
                self._seed_table(connection, entity, rows_by_entity[entity.name])
            connection.commit()
        finally:
            connection.close()

    def _create_table(self, connection: sqlite3.Connection, entity: EntitySchema) -> None:
        column_definitions: list[str] = []
        foreign_keys: list[str] = []

        for field in entity.fields:
            parts = [f'"{field.name}"', SQLITE_TYPE_MAP[field.type]]
            if field.name == entity.primary_key:
                parts.append("PRIMARY KEY")
            if field.required and field.name != entity.primary_key:
                parts.append("NOT NULL")
            if field.unique and field.name != entity.primary_key:
                parts.append("UNIQUE")
            column_definitions.append(" ".join(parts))
            if field.reference_entity:
                foreign_keys.append(f'FOREIGN KEY("{field.name}") REFERENCES "{field.reference_entity}"("id")')

        sql = f'CREATE TABLE IF NOT EXISTS "{entity.name}" (\n  ' + ",\n  ".join(column_definitions + foreign_keys) + "\n);"
        connection.execute(sql)

    def _create_indexes(self, connection: sqlite3.Connection, entity: EntitySchema) -> None:
        for field in entity.fields:
            if field.indexed and field.name != entity.primary_key:
                connection.execute(
                    f'CREATE INDEX IF NOT EXISTS "idx_{entity.name}_{field.name}" ON "{entity.name}"("{field.name}");'
                )

    def _seed_table(self, connection: sqlite3.Connection, entity: EntitySchema, rows: list[dict[str, object]]) -> None:
        if not rows:
            return
        columns = [field.name for field in entity.fields]
        placeholders = ", ".join(["?"] * len(columns))
        quoted_columns = ", ".join(f'"{column}"' for column in columns)
        sql = f'INSERT INTO "{entity.name}" ({quoted_columns}) VALUES ({placeholders})'
        values = [[row.get(column) for column in columns] for row in rows]
        connection.executemany(sql, values)
