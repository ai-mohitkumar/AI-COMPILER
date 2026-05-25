from __future__ import annotations

from collections import Counter

from app.schemas.compiler_schema import SchemaBundle, ValidationIssue, ValidationReport


class Validator:
    """Runs structural and cross-layer validation across compiler outputs."""

    def validate(self, bundle: SchemaBundle, repair_attempts: int = 0, repaired: bool = False) -> ValidationReport:
        issues: list[ValidationIssue] = []
        issues.extend(self._validate_db(bundle))
        issues.extend(self._validate_api(bundle))
        issues.extend(self._validate_ui(bundle))
        issues.extend(self._validate_auth(bundle))
        issues.extend(self._validate_runtime(bundle))

        passed = not any(issue.severity == "error" for issue in issues)
        return ValidationReport(
            passed=passed,
            issues=issues,
            repair_attempts=repair_attempts,
            repaired=repaired,
        )

    def _validate_db(self, bundle: SchemaBundle) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        entity_names = [entity.name for entity in bundle.db_schema.entities]
        for name, count in Counter(entity_names).items():
            if count > 1:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        component="db",
                        code="DB_DUPLICATE_ENTITY",
                        message=f"Entity '{name}' is defined multiple times.",
                        details={"entity": name},
                    )
                )

        known_entities = set(entity_names)
        for entity in bundle.db_schema.entities:
            field_names = [field.name for field in entity.fields]
            for field_name, count in Counter(field_names).items():
                if count > 1:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            component="db",
                            code="DB_DUPLICATE_FIELD",
                            message=f"Entity '{entity.name}' defines field '{field_name}' multiple times.",
                            details={"entity": entity.name, "field": field_name},
                        )
                    )

            for relationship in entity.relationships:
                if relationship.target_entity not in known_entities:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            component="db",
                            code="DB_RELATION_TARGET_UNKNOWN",
                            message=f"Relationship '{relationship.name}' points to missing entity '{relationship.target_entity}'.",
                            details={"entity": entity.name, "relationship": relationship.name, "target_entity": relationship.target_entity},
                        )
                    )
                if relationship.source_field not in field_names:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            component="db",
                            code="DB_RELATION_FIELD_UNKNOWN",
                            message=f"Relationship '{relationship.name}' references missing field '{relationship.source_field}'.",
                            details={"entity": entity.name, "relationship": relationship.name, "field": relationship.source_field, "target_entity": relationship.target_entity},
                        )
                    )
        return issues

    def _validate_api(self, bundle: SchemaBundle) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        entity_fields = {
            entity.name: {field.name for field in entity.fields}
            for entity in bundle.db_schema.entities
        }
        permission_codes = {permission.code for permission in bundle.auth_schema.permissions}
        signatures = Counter((route.method, route.path) for route in bundle.api_schema.routes)

        for (method, path), count in signatures.items():
            if count > 1:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        component="api",
                        code="API_DUPLICATE_ROUTE",
                        message=f"Route '{method} {path}' is defined multiple times.",
                        details={"method": method, "path": path},
                    )
                )

        for route in bundle.api_schema.routes:
            if route.entity and route.entity not in entity_fields:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        component="api",
                        code="API_ENTITY_UNKNOWN",
                        message=f"Route '{route.method} {route.path}' references missing entity '{route.entity}'.",
                        details={"entity": route.entity, "path": route.path, "method": route.method},
                    )
                )
                continue

            if route.entity:
                known_fields = entity_fields[route.entity]
                for field_name in route.request_fields + route.response_fields:
                    if field_name not in known_fields:
                        issues.append(
                            ValidationIssue(
                                severity="error",
                                component="api",
                                code="API_FIELD_UNKNOWN",
                                message=f"Route '{route.method} {route.path}' references unknown field '{field_name}' for entity '{route.entity}'.",
                                details={"entity": route.entity, "field": field_name, "path": route.path, "method": route.method},
                            )
                        )

            if route.permission and route.permission not in permission_codes:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        component="api",
                        code="API_PERMISSION_UNKNOWN",
                        message=f"Route '{route.method} {route.path}' requires undefined permission '{route.permission}'.",
                        details={"permission": route.permission, "path": route.path, "method": route.method},
                    )
                )
        return issues

    def _validate_ui(self, bundle: SchemaBundle) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        entity_fields = {
            entity.name: {field.name for field in entity.fields}
            for entity in bundle.db_schema.entities
        }
        roles = {role.name for role in bundle.auth_schema.roles}
        permission_codes = {permission.code for permission in bundle.auth_schema.permissions}
        routes = {(route.method, route.path): route for route in bundle.api_schema.routes}
        route_paths = {route.path for route in bundle.api_schema.routes}

        for page in bundle.ui_schema.pages:
            for permission in page.required_permissions:
                if permission not in permission_codes:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            component="ui",
                            code="UI_PERMISSION_UNKNOWN",
                            message=f"Page '{page.name}' requires undefined permission '{permission}'.",
                            details={"page": page.name, "permission": permission},
                        )
                    )

            for component in page.components:
                for role in component.visible_to_roles:
                    if role not in roles:
                        issues.append(
                            ValidationIssue(
                                severity="error",
                                component="ui",
                                code="UI_ROLE_UNKNOWN",
                                message=f"Component '{component.id}' references undefined role '{role}'.",
                                details={"component": component.id, "role": role},
                            )
                        )

                if component.data_source and component.data_source not in route_paths:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            component="ui",
                            code="UI_SOURCE_MISSING_ROUTE",
                            message=f"Component '{component.id}' reads from missing route '{component.data_source}'.",
                            details={"component": component.id, "path": component.data_source, "entity": component.entity},
                        )
                    )
                elif component.data_source and ("GET", component.data_source) not in routes:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            component="ui",
                            code="UI_SOURCE_NOT_GETTABLE",
                            message=f"Component '{component.id}' points to route '{component.data_source}' that is not available as GET.",
                            details={"component": component.id, "path": component.data_source, "entity": component.entity},
                        )
                    )

                if component.action_route and component.action_route not in route_paths:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            component="ui",
                            code="UI_ACTION_MISSING_ROUTE",
                            message=f"Component '{component.id}' posts to missing route '{component.action_route}'.",
                            details={"component": component.id, "path": component.action_route, "entity": component.entity},
                        )
                    )
                elif component.action_route and ("POST", component.action_route) not in routes:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            component="ui",
                            code="UI_ACTION_NOT_POSTABLE",
                            message=f"Component '{component.id}' points to route '{component.action_route}' that is not available as POST.",
                            details={"component": component.id, "path": component.action_route, "entity": component.entity},
                        )
                    )

                if component.entity and component.entity in entity_fields:
                    known_fields = entity_fields[component.entity]
                    for field in component.fields:
                        if field not in known_fields:
                            issues.append(
                                ValidationIssue(
                                    severity="error",
                                    component="ui",
                                    code="UI_FIELD_MISSING_IN_ENTITY",
                                    message=f"Component '{component.id}' references missing field '{field}' on entity '{component.entity}'.",
                                    details={"component": component.id, "field": field, "entity": component.entity},
                                )
                            )
        return issues

    def _validate_auth(self, bundle: SchemaBundle) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        role_names = {role.name for role in bundle.auth_schema.roles}
        if bundle.auth_schema.default_role not in role_names:
            issues.append(
                ValidationIssue(
                    severity="error",
                    component="auth",
                    code="AUTH_DEFAULT_ROLE_UNKNOWN",
                    message=f"Default role '{bundle.auth_schema.default_role}' is not present in the role list.",
                    details={"default_role": bundle.auth_schema.default_role},
                )
            )

        if not bundle.auth_schema.enabled:
            protected_routes = [route for route in bundle.api_schema.routes if route.permission]
            if protected_routes:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        component="auth",
                        code="AUTH_DISABLED_WITH_PROTECTED_ROUTE",
                        message="Auth is disabled but protected routes still require permissions.",
                        details={"protected_routes": [f"{route.method} {route.path}" for route in protected_routes]},
                    )
                )
        return issues

    def _validate_runtime(self, bundle: SchemaBundle) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if not bundle.ui_schema.pages:
            issues.append(
                ValidationIssue(
                    severity="error",
                    component="runtime",
                    code="RUNTIME_NO_PAGES",
                    message="The runtime has no pages to render.",
                )
            )
        if not bundle.db_schema.entities:
            issues.append(
                ValidationIssue(
                    severity="error",
                    component="runtime",
                    code="RUNTIME_NO_ENTITIES",
                    message="The runtime has no entities to persist.",
                )
            )
        return issues
