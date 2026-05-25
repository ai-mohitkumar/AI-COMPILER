from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


RouteMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
RouteAction = Literal["list", "detail", "create", "update", "delete", "analytics"]


class RouteDefinition(BaseModel):
    method: RouteMethod
    path: str
    entity: str | None = None
    action: RouteAction
    request_fields: list[str] = Field(default_factory=list)
    response_fields: list[str] = Field(default_factory=list)
    permission: str | None = None
    public: bool = False
    description: str


class APISchema(BaseModel):
    base_path: str = "/api"
    routes: list[RouteDefinition] = Field(default_factory=list)
