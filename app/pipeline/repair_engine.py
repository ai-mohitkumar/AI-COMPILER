from __future__ import annotations

from collections import defaultdict

from app.schemas.api_schema import RouteDefinition
from app.schemas.auth_schema import PermissionDefinition, RoleDefinition
from app.schemas.compiler_schema import SchemaBundle, ValidationIssue
from app.schemas.db_schema import FieldDefinition


class RepairEngine:
    """Applies local patches based on validation failures."""

    def repair(self, bundle: SchemaBundle, issues: list[ValidationIssue]) -> tuple[SchemaBundle, list[str]]:
        repaired = bundle.model_copy(deep=True)
        log: list[str] = []

        grouped: dict[str, list[ValidationIssue]] = defaultdict(list)
        for issue in issues:
            grouped[issue.code].append(issue)

        for issue in grouped.get("AUTH_DISABLED_WITH_PROTECTED_ROUTE", []):
            repaired.auth_schema.enabled = True
            repaired.intent.needs_auth = True
            repaired.intent.assumptions.append("Enabled auth to satisfy protected route permissions.")
            log.append("Enabled auth because protected routes were present.")

        for issue in grouped.get("AUTH_DEFAULT_ROLE_UNKNOWN", []):
            if repaired.auth_schema.roles:
                repaired.auth_schema.default_role = repaired.auth_schema.roles[0].name
                log.append(f"Reset default role to '{repaired.auth_schema.default_role}'.")

        for issue in grouped.get("API_PERMISSION_UNKNOWN", []) + grouped.get("UI_PERMISSION_UNKNOWN", []):
            permission = issue.details.get("permission")
            if permission and not any(existing.code == permission for existing in repaired.auth_schema.permissions):
                repaired.auth_schema.permissions.append(
                    PermissionDefinition(code=permission, description=permission.replace(":", " ").replace("_", " "))
                )
                self._grant_permission_to_admin(repaired, permission)
                log.append(f"Added missing permission '{permission}'.")

        for issue in grouped.get("UI_ROLE_UNKNOWN", []):
            role_name = issue.details.get("role")
            if role_name and not any(role.name == role_name for role in repaired.auth_schema.roles):
                repaired.auth_schema.roles.append(RoleDefinition(name=role_name, permissions=self._read_permissions(repaired)))
                log.append(f"Added missing role '{role_name}' with read-only permissions.")

        for issue in grouped.get("UI_SOURCE_MISSING_ROUTE", []) + grouped.get("UI_SOURCE_NOT_GETTABLE", []):
            self._ensure_get_route(repaired, issue, log)

        for issue in grouped.get("UI_ACTION_MISSING_ROUTE", []) + grouped.get("UI_ACTION_NOT_POSTABLE", []):
            self._ensure_post_route(repaired, issue, log)

        for issue in grouped.get("API_FIELD_UNKNOWN", []) + grouped.get("UI_FIELD_MISSING_IN_ENTITY", []) + grouped.get("DB_RELATION_FIELD_UNKNOWN", []):
            self._ensure_field(repaired, issue, log)

        for issue in grouped.get("DB_RELATION_TARGET_UNKNOWN", []):
            entity_name = issue.details.get("entity")
            relationship_name = issue.details.get("relationship")
            if not entity_name or not relationship_name:
                continue
            entity = next((item for item in repaired.db_schema.entities if item.name == entity_name), None)
            if entity:
                entity.relationships = [rel for rel in entity.relationships if rel.name != relationship_name]
                log.append(f"Removed invalid relationship '{relationship_name}' from '{entity_name}'.")

        for issue in grouped.get("API_DUPLICATE_ROUTE", []):
            method = issue.details.get("method")
            path = issue.details.get("path")
            seen = False
            deduped = []
            for route in repaired.api_schema.routes:
                signature = route.method == method and route.path == path
                if signature and seen:
                    continue
                if signature:
                    seen = True
                deduped.append(route)
            repaired.api_schema.routes = deduped
            log.append(f"Deduplicated route '{method} {path}'.")

        return repaired, log

    def _grant_permission_to_admin(self, bundle: SchemaBundle, permission: str) -> None:
        admin_role = next((role for role in bundle.auth_schema.roles if role.name == "admin"), None)
        if admin_role is None:
            admin_role = RoleDefinition(name="admin", permissions=[])
            bundle.auth_schema.roles.insert(0, admin_role)
        if permission not in admin_role.permissions:
            admin_role.permissions.append(permission)

    def _read_permissions(self, bundle: SchemaBundle) -> list[str]:
        return [permission.code for permission in bundle.auth_schema.permissions if permission.code.endswith(":read")]

    def _ensure_get_route(self, bundle: SchemaBundle, issue: ValidationIssue, log: list[str]) -> None:
        path = issue.details.get("path")
        entity_name = issue.details.get("entity")
        if not path or not entity_name:
            return
        if any(route.method == "GET" and route.path == path for route in bundle.api_schema.routes):
            return

        entity = next((item for item in bundle.db_schema.entities if item.name == entity_name), None)
        if not entity:
            return

        bundle.api_schema.routes.append(
            RouteDefinition(
                method="GET",
                path=path,
                entity=entity_name,
                action="list",
                response_fields=[field.name for field in entity.fields],
                permission=f"{entity_name}:read",
                description=f"Repaired GET route for {entity_name}.",
            )
        )
        log.append(f"Added GET route '{path}' for entity '{entity_name}'.")

    def _ensure_post_route(self, bundle: SchemaBundle, issue: ValidationIssue, log: list[str]) -> None:
        path = issue.details.get("path")
        entity_name = issue.details.get("entity")
        if not path or not entity_name:
            return
        if any(route.method == "POST" and route.path == path for route in bundle.api_schema.routes):
            return

        entity = next((item for item in bundle.db_schema.entities if item.name == entity_name), None)
        if not entity:
            return

        fields = [field.name for field in entity.fields if field.name not in {"id", "created_at", "updated_at"}]
        bundle.api_schema.routes.append(
            RouteDefinition(
                method="POST",
                path=path,
                entity=entity_name,
                action="create",
                request_fields=fields,
                response_fields=[field.name for field in entity.fields],
                permission=f"{entity_name}:create",
                description=f"Repaired POST route for {entity_name}.",
            )
        )
        log.append(f"Added POST route '{path}' for entity '{entity_name}'.")

    def _ensure_field(self, bundle: SchemaBundle, issue: ValidationIssue, log: list[str]) -> None:
        entity_name = issue.details.get("entity")
        field_name = issue.details.get("field")
        if not entity_name or not field_name:
            return

        entity = next((item for item in bundle.db_schema.entities if item.name == entity_name), None)
        if entity is None or any(field.name == field_name for field in entity.fields):
            return

        target_entity = issue.details.get("target_entity")
        field_type = "uuid" if field_name.endswith("_id") or target_entity else "string"
        entity.fields.append(
            FieldDefinition(
                name=field_name,
                type=field_type,  # type: ignore[arg-type]
                required=False,
                indexed=field_name.endswith("_id"),
                reference_entity=target_entity if isinstance(target_entity, str) else None,
            )
        )
        log.append(f"Added missing field '{field_name}' to entity '{entity_name}'.")
