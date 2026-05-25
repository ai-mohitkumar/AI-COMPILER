from __future__ import annotations

from app.schemas.db_schema import DatabaseSchema


PRISMA_TYPE_MAP = {
    "uuid": "String",
    "string": "String",
    "text": "String",
    "integer": "Int",
    "float": "Float",
    "boolean": "Boolean",
    "datetime": "DateTime",
    "date": "DateTime",
}


class PrismaGenerator:
    def generate(self, db_schema: DatabaseSchema) -> str:
        blocks = [
            'generator client {\n  provider = "prisma-client-js"\n}',
            'datasource db {\n  provider = "sqlite"\n  url      = env("DATABASE_URL")\n}',
        ]

        for entity in db_schema.entities:
            field_lines = []
            for field in entity.fields:
                prisma_type = PRISMA_TYPE_MAP[field.type]
                modifiers = []
                if field.name == entity.primary_key:
                    modifiers.append("@id")
                if field.unique and field.name != entity.primary_key:
                    modifiers.append("@unique")
                optional_marker = "?" if not field.required else ""
                field_lines.append(f"  {field.name} {prisma_type}{optional_marker} {' '.join(modifiers)}".rstrip())

            blocks.append(f"model {entity.name.title().replace('_', '')} {{\n" + "\n".join(field_lines) + "\n}")

        return "\n\n".join(blocks) + "\n"
