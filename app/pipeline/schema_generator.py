from __future__ import annotations

from app.schemas.api_schema import APISchema, RouteDefinition
from app.schemas.auth_schema import AuthSchema, PermissionDefinition, RoleDefinition
from app.schemas.compiler_schema import AppArchitecture, SchemaBundle
from app.schemas.db_schema import DatabaseSchema, EntitySchema, FieldDefinition, RelationshipDefinition
from app.schemas.intent_schema import UserIntent
from app.schemas.ui_schema import ComponentDefinition, PageDefinition, UISchema


SYSTEM_FIELDS = [
    FieldDefinition(name="id", type="uuid", required=True, unique=True, indexed=True),
    FieldDefinition(name="created_at", type="datetime", required=True, indexed=True),
    FieldDefinition(name="updated_at", type="datetime", required=True, indexed=True),
]


class SchemaGenerator:
    """Generates isolated schemas from the intermediate architecture."""

    def generate(self, intent: UserIntent, architecture: AppArchitecture) -> SchemaBundle:
        db_schema = self._build_db_schema(architecture)
        auth_schema = self._build_auth_schema(intent, architecture)
        api_schema = self._build_api_schema(intent, architecture)
        ui_schema = self._build_ui_schema(intent, architecture)
        return SchemaBundle(
            intent=intent,
            architecture=architecture,
            db_schema=db_schema,
            api_schema=api_schema,
            ui_schema=ui_schema,
            auth_schema=auth_schema,
        )

    def _build_db_schema(self, architecture: AppArchitecture) -> DatabaseSchema:
        entities: list[EntitySchema] = []
        for blueprint in architecture.entities:
            fields = SYSTEM_FIELDS[:] + [
                FieldDefinition(
                    name=field.name,
                    type=field.type,  # type: ignore[arg-type]
                    required=field.required,
                    indexed=field.searchable or field.filterable,
                    ui_exposed=True,
                    reference_entity=field.reference_entity,
                )
                for field in blueprint.fields
            ]
            relationships = [
                RelationshipDefinition(
                    name=f"{field.name}_to_{field.reference_entity}",
                    kind="many_to_one",
                    target_entity=field.reference_entity,
                    source_field=field.name,
                )
                for field in blueprint.fields
                if field.reference_entity
            ]
            entities.append(
                EntitySchema(
                    name=blueprint.name,
                    plural_name=blueprint.name if blueprint.name.endswith("s") else f"{blueprint.name}s",
                    description=blueprint.description,
                    fields=fields,
                    relationships=relationships,
                )
            )
        return DatabaseSchema(entities=entities)

    def _build_api_schema(self, intent: UserIntent, architecture: AppArchitecture) -> APISchema:
        routes: list[RouteDefinition] = []
        read_only = "read_only" in intent.constraints

        for entity in architecture.entities:
            base_path = f"/api/{entity.name}"
            response_fields = ["id", "created_at", "updated_at"] + [field.name for field in entity.fields]
            writable_fields = [field.name for field in entity.fields]

            routes.append(
                RouteDefinition(
                    method="GET",
                    path=base_path,
                    entity=entity.name,
                    action="list",
                    response_fields=response_fields,
                    permission=f"{entity.name}:read",
                    description=f"List {entity.name.replace('_', ' ')} records.",
                )
            )
            routes.append(
                RouteDefinition(
                    method="GET",
                    path=f"{base_path}/{{record_id}}",
                    entity=entity.name,
                    action="detail",
                    response_fields=response_fields,
                    permission=f"{entity.name}:read",
                    description=f"Fetch a single {entity.name[:-1] if entity.name.endswith('s') else entity.name}.",
                )
            )
            if not read_only:
                routes.append(
                    RouteDefinition(
                        method="POST",
                        path=base_path,
                        entity=entity.name,
                        action="create",
                        request_fields=writable_fields,
                        response_fields=response_fields,
                        permission=f"{entity.name}:create",
                        description=f"Create a new {entity.name[:-1] if entity.name.endswith('s') else entity.name}.",
                    )
                )
                routes.append(
                    RouteDefinition(
                        method="PUT",
                        path=f"{base_path}/{{record_id}}",
                        entity=entity.name,
                        action="update",
                        request_fields=writable_fields,
                        response_fields=response_fields,
                        permission=f"{entity.name}:update",
                        description=f"Update an existing {entity.name[:-1] if entity.name.endswith('s') else entity.name}.",
                    )
                )
                routes.append(
                    RouteDefinition(
                        method="DELETE",
                        path=f"{base_path}/{{record_id}}",
                        entity=entity.name,
                        action="delete",
                        permission=f"{entity.name}:delete",
                        description=f"Delete an existing {entity.name[:-1] if entity.name.endswith('s') else entity.name}.",
                    )
                )

        if "analytics" in intent.features:
            routes.append(
                RouteDefinition(
                    method="GET",
                    path="/api/analytics/summary",
                    action="analytics",
                    response_fields=["entity", "count"],
                    permission="analytics:view",
                    description="Return lightweight app analytics.",
                )
            )

        routes.append(
            RouteDefinition(
                method="GET",
                path="/api/session",
                action="detail",
                response_fields=["role", "auth_enabled"],
                public=True,
                description="Return the effective runtime role and auth mode.",
            )
        )
        return APISchema(routes=routes)

    def _build_auth_schema(self, intent: UserIntent, architecture: AppArchitecture) -> AuthSchema:
        permissions = [PermissionDefinition(code=permission, description=permission.replace(":", " ").replace("_", " ")) for permission in architecture.permissions]
        roles: list[RoleDefinition] = []
        all_permissions = [permission.code for permission in permissions]

        for role in architecture.roles:
            if role == "admin":
                role_permissions = all_permissions
            elif role in {"manager", "warehouse_manager", "instructor", "sales_rep"}:
                role_permissions = [permission for permission in all_permissions if not permission.endswith(":delete")]
            else:
                role_permissions = [permission for permission in all_permissions if permission.endswith(":read")]
                if "analytics:view" in all_permissions and role in {"member", "employee", "student", "customer", "user"}:
                    role_permissions.append("analytics:view")
            roles.append(RoleDefinition(name=role, permissions=sorted(set(role_permissions))))

        default_role = "admin" if any(role.name == "admin" for role in roles) else (roles[0].name if roles else "admin")
        return AuthSchema(
            enabled=intent.needs_auth,
            permissions=permissions,
            roles=roles,
            default_role=default_role,
        )

    def _build_ui_schema(self, intent: UserIntent, architecture: AppArchitecture) -> UISchema:
        pages: list[PageDefinition] = []
        roles = architecture.roles or ["admin"]

        for page in architecture.pages:
            components: list[ComponentDefinition] = []

            if page.page_type == "dashboard":
                components.extend(
                    [
                        ComponentDefinition(
                            id="main-nav",
                            type="nav",
                            title="Navigation",
                            visible_to_roles=roles,
                        ),
                        ComponentDefinition(
                            id="headline-stats",
                            type="stats",
                            title="Snapshot",
                            data_source="/api/analytics/summary" if "analytics:view" in architecture.permissions else None,
                            visible_to_roles=roles,
                        ),
                    ]
                )

            if page.entity:
                entity = next(entity for entity in architecture.entities if entity.name == page.entity)
                list_fields = [field.name for field in entity.fields]
                components.append(
                    ComponentDefinition(
                        id=f"{entity.name}-table",
                        type="table",
                        title=f"{page.title} Table",
                        entity=entity.name,
                        data_source=f"/api/{entity.name}",
                        fields=list_fields,
                        visible_to_roles=roles,
                    )
                )
                if "read_only" not in intent.constraints:
                    components.append(
                        ComponentDefinition(
                            id=f"{entity.name}-form",
                            type="form",
                            title=f"Create {page.title[:-1] if page.title.endswith('s') else page.title}",
                            entity=entity.name,
                            action_route=f"/api/{entity.name}",
                            fields=list_fields,
                            visible_to_roles=[role for role in roles if role != "customer"] or roles,
                        )
                    )

            if page.page_type == "analytics":
                components.append(
                    ComponentDefinition(
                        id="analytics-chart",
                        type="chart",
                        title="Entity Volume",
                        data_source="/api/analytics/summary",
                        visible_to_roles=roles,
                    )
                )

            pages.append(
                PageDefinition(
                    name=page.name,
                    path="/" if page.name == "dashboard" else f"/{page.name}",
                    title=page.title,
                    page_type=page.page_type,
                    components=components,
                    required_permissions=page.required_permissions,
                )
            )

        return UISchema(pages=pages)
