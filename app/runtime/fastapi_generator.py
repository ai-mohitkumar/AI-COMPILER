from __future__ import annotations

from app.schemas.api_schema import APISchema


class FastAPIGenerator:
    def generate(self, api_schema: APISchema, api_base_path: str) -> str:
        lines = [
            "from fastapi import APIRouter",
            "",
            "router = APIRouter()",
            "",
            f'# Generated runtime base path: "{api_base_path}"',
            "",
        ]

        for route in api_schema.routes:
            lines.extend(
                [
                    f'@router.{route.method.lower()}("{route.path}")',
                    f"def {route.action}_{(route.entity or 'analytics').replace('-', '_')}_handler():",
                    f'    return {{"route": "{route.method} {route.path}", "description": "{route.description}"}}',
                    "",
                ]
            )

        return "\n".join(lines).strip() + "\n"
