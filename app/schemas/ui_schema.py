from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ComponentType = Literal["nav", "stats", "table", "form", "detail", "chart", "banner"]


class ComponentDefinition(BaseModel):
    id: str
    type: ComponentType
    title: str
    entity: str | None = None
    data_source: str | None = None
    action_route: str | None = None
    fields: list[str] = Field(default_factory=list)
    visible_to_roles: list[str] = Field(default_factory=list)


class PageDefinition(BaseModel):
    name: str
    path: str
    title: str
    page_type: str
    components: list[ComponentDefinition] = Field(default_factory=list)
    required_permissions: list[str] = Field(default_factory=list)


class UISchema(BaseModel):
    framework: str = "config-driven-html"
    pages: list[PageDefinition] = Field(default_factory=list)
