from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


FieldType = Literal["uuid", "string", "text", "integer", "float", "boolean", "datetime", "date"]
RelationshipType = Literal["one_to_many", "many_to_one", "many_to_many", "one_to_one"]
DatabaseEngine = Literal["sqlite", "postgresql"]


class FieldDefinition(BaseModel):
    name: str
    type: FieldType
    required: bool = True
    unique: bool = False
    indexed: bool = False
    ui_exposed: bool = True
    reference_entity: str | None = None
    default: str | int | float | bool | None = None


class RelationshipDefinition(BaseModel):
    name: str
    kind: RelationshipType
    target_entity: str
    source_field: str
    target_field: str = "id"
    nullable: bool = False


class EntitySchema(BaseModel):
    name: str
    plural_name: str
    description: str
    fields: list[FieldDefinition] = Field(default_factory=list)
    primary_key: str = "id"
    relationships: list[RelationshipDefinition] = Field(default_factory=list)
    seed_count: int = Field(default=3, ge=1, le=20)


class DatabaseSchema(BaseModel):
    engine: DatabaseEngine = "sqlite"
    entities: list[EntitySchema] = Field(default_factory=list)
