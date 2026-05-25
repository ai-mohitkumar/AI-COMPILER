from __future__ import annotations

from pydantic import BaseModel, Field


class PermissionDefinition(BaseModel):
    code: str
    description: str


class RoleDefinition(BaseModel):
    name: str
    permissions: list[str] = Field(default_factory=list)


class AuthSchema(BaseModel):
    enabled: bool = True
    provider: str = "demo-token"
    permissions: list[PermissionDefinition] = Field(default_factory=list)
    roles: list[RoleDefinition] = Field(default_factory=list)
    default_role: str = "admin"
