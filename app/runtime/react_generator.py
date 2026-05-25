from __future__ import annotations

import json
from pathlib import Path

from app.schemas.auth_schema import AuthSchema
from app.schemas.ui_schema import UISchema


class ReactGenerator:
    """Generates a lightweight browser preview from the UI config."""

    TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "preview.html"

    def generate(
        self,
        *,
        app_name: str,
        app_id: str,
        api_base_path: str,
        preview_path: str,
        ui_schema: UISchema,
        auth_schema: AuthSchema,
    ) -> str:
        ui_payload = json.dumps(ui_schema.model_dump(mode="json"))
        auth_payload = json.dumps(auth_schema.model_dump(mode="json"))
        template = self.TEMPLATE_PATH.read_text(encoding="utf-8")
        replacements = {
            "__APP_NAME__": app_name,
            "__APP_ID__": app_id,
            "__API_BASE_PATH__": api_base_path,
            "__PREVIEW_PATH__": preview_path,
            "__AUTH_MODE__": "enabled" if auth_schema.enabled else "disabled",
            "__ROLE_COUNT__": str(len(auth_schema.roles)),
            "__UI_PAYLOAD__": ui_payload,
            "__AUTH_PAYLOAD__": auth_payload,
        }
        for key, value in replacements.items():
            template = template.replace(key, value)
        return template
