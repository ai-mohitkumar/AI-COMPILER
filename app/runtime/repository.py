from __future__ import annotations

import json
from pathlib import Path

from app.schemas.compiler_schema import SchemaBundle


class RuntimeRepository:
    """Loads persisted runtime manifests and schema bundles."""

    def __init__(self, base_dir: str | Path = "generated/apps") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_index: dict[str, Path] = {}

    def register(self, app_id: str, manifest_path: str) -> None:
        self._manifest_index[app_id] = Path(manifest_path)

    def get_manifest(self, app_id: str) -> dict:
        manifest_path = self._manifest_index.get(app_id) or self._discover_manifest(app_id)
        if manifest_path is None:
            raise KeyError(app_id)
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    def load_bundle(self, app_id: str) -> SchemaBundle:
        manifest = self.get_manifest(app_id)
        return SchemaBundle.model_validate(manifest["bundle"])

    def runtime_meta(self, app_id: str) -> dict:
        return self.get_manifest(app_id)["runtime"]

    def _discover_manifest(self, app_id: str) -> Path | None:
        for path in self.base_dir.rglob("manifest.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("app_id") == app_id:
                self._manifest_index[app_id] = path
                return path
        return None
