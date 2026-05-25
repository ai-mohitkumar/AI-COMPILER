from __future__ import annotations

import re

from app.pipeline.domain_knowledge import DOMAIN_TEMPLATES
from app.schemas.compiler_schema import AppArchitecture, EntityBlueprint, FieldBlueprint, PageBlueprint, UserFlow
from app.schemas.intent_schema import UserIntent


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "generated-app"


class Architect:
    """Builds an AST-like application architecture from extracted intent."""

    def design(self, intent: UserIntent) -> AppArchitecture:
        domain_key = self._resolve_domain_key(intent.app_type)
        template = DOMAIN_TEMPLATES[domain_key]
        entities = [self._build_entity(entity) for entity in template["entities"]]
        permissions = self._build_permissions(entities, intent.features)
        pages = self._build_pages(entities, permissions, intent.features, intent.constraints)
        flows = self._build_flows(entities, intent.roles, intent.features)
        assumptions = template.get("assumptions", []) + intent.assumptions

        return AppArchitecture(
            app_name=intent.app_name,
            slug=_slugify(intent.app_name),
            summary=intent.summary,
            entities=entities,
            pages=pages,
            permissions=permissions,
            roles=intent.roles,
            flows=flows,
            assumptions=assumptions,
        )

    def _resolve_domain_key(self, app_type: str) -> str:
        normalized = app_type.lower()
        for key, template in DOMAIN_TEMPLATES.items():
            if template["app_type"].lower() == normalized:
                return key
        return "generic_workspace"

    def _build_entity(self, entity_template: dict) -> EntityBlueprint:
        fields = [
            FieldBlueprint(
                name=field["name"],
                type=field["type"],
                required=field.get("required", True),
                searchable=field.get("searchable", False),
                filterable=field.get("filterable", False),
                reference_entity=field.get("reference_entity"),
            )
            for field in entity_template["fields"]
        ]
        return EntityBlueprint(
            name=entity_template["name"],
            description=entity_template["description"],
            fields=fields,
            primary_display_field=entity_template.get("primary_display_field", fields[0].name if fields else "name"),
        )

    def _build_permissions(self, entities: list[EntityBlueprint], features: list[str]) -> list[str]:
        permissions: list[str] = []
        for entity in entities:
            permissions.extend(
                [
                    f"{entity.name}:read",
                    f"{entity.name}:create",
                    f"{entity.name}:update",
                    f"{entity.name}:delete",
                ]
            )
        if "analytics" in features:
            permissions.append("analytics:view")
        if "approvals" in features:
            permissions.append("approvals:manage")
        if "comments" in features:
            permissions.append("comments:moderate")
        return permissions

    def _build_pages(
        self,
        entities: list[EntityBlueprint],
        permissions: list[str],
        features: list[str],
        constraints: list[str],
    ) -> list[PageBlueprint]:
        pages: list[PageBlueprint] = [
            PageBlueprint(
                name="dashboard",
                title="Dashboard",
                page_type="dashboard",
                components=["nav", "stats"],
                required_permissions=["analytics:view"] if "analytics:view" in permissions else [],
            )
        ]

        for entity in entities:
            page_components = ["table"]
            if "read_only" not in constraints:
                page_components.append("form")

            pages.append(
                PageBlueprint(
                    name=entity.name,
                    title=entity.name.replace("_", " ").title(),
                    page_type="resource",
                    entity=entity.name,
                    components=page_components,
                    required_permissions=[f"{entity.name}:read"],
                )
            )

        if "analytics" in features:
            pages.append(
                PageBlueprint(
                    name="analytics",
                    title="Analytics",
                    page_type="analytics",
                    components=["chart"],
                    required_permissions=["analytics:view"],
                )
            )

        if "single_page" in constraints:
            return pages[:1]
        return pages

    def _build_flows(self, entities: list[EntityBlueprint], roles: list[str], features: list[str]) -> list[UserFlow]:
        actor = roles[0] if roles else "admin"
        flows: list[UserFlow] = []
        for entity in entities:
            flows.append(
                UserFlow(
                    name=f"manage_{entity.name}",
                    actor=actor,
                    steps=[
                        f"Open the {entity.name.replace('_', ' ')} page",
                        f"Review existing {entity.name.replace('_', ' ')} records",
                        f"Create or update a {entity.name[:-1] if entity.name.endswith('s') else entity.name} record",
                    ],
                    outcome=f"{entity.name.replace('_', ' ').title()} stay synchronized across UI, API, and DB layers.",
                )
            )
        if "analytics" in features:
            flows.append(
                UserFlow(
                    name="review_analytics",
                    actor=actor,
                    steps=["Open the analytics page", "Inspect entity counts and activity signals"],
                    outcome="The operator gets a fast operational summary.",
                )
            )
        return flows
