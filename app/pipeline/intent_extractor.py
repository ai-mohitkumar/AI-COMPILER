from __future__ import annotations

import re

from app.pipeline.domain_knowledge import DOMAIN_ALIASES, DOMAIN_TEMPLATES, FEATURE_KEYWORDS, ROLE_KEYWORDS
from app.schemas.intent_schema import IntentSignal, UserIntent


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "generated-app"


class IntentExtractor:
    """Deterministic intent extraction from a natural-language request."""

    def extract(self, prompt: str) -> UserIntent:
        normalized = prompt.strip()
        lowered = normalized.lower()
        domain_key, domain_signals = self._detect_domain(lowered)
        template = DOMAIN_TEMPLATES[domain_key]

        features = self._detect_features(lowered, template["features"])
        features = self._stabilize_domain_features(features, template["features"])
        roles = self._detect_roles(lowered, template["roles"])
        suggested_entities = [entity["name"] for entity in template["entities"]]
        constraints = self._detect_constraints(lowered)
        assumptions = self._build_assumptions(lowered, domain_key, features, constraints)
        needs_auth = not any(constraint == "no_auth" for constraint in constraints)
        ambiguity = self._detect_ambiguity(lowered, domain_key)
        app_name = self._derive_app_name(normalized, template["app_type"])

        signals = [
            IntentSignal(name=f"domain:{domain_key}", confidence=domain_signals[1], reason=domain_signals[0]),
            *self._feature_signals(lowered, features),
        ]

        return UserIntent(
            prompt=normalized,
            app_name=app_name,
            app_type=template["app_type"],
            summary=template["summary"],
            features=features,
            roles=roles,
            suggested_entities=suggested_entities,
            constraints=constraints,
            assumptions=assumptions,
            needs_auth=needs_auth,
            ambiguity=ambiguity,
            signals=signals,
        )

    def _detect_domain(self, lowered: str) -> tuple[str, tuple[str, float]]:
        best_key = "generic_workspace"
        best_score = 0
        best_reason = "Fell back to the generic workspace template."

        for domain_key, aliases in DOMAIN_ALIASES.items():
            score = sum(1 for alias in aliases if alias in lowered)
            if score > best_score:
                best_key = domain_key
                best_score = score
                best_reason = f"Matched {score} domain keywords for {domain_key}."

        if any(phrase in lowered for phrase in ("something for", "something to", "something that")) and best_score <= 1:
            best_key = "generic_workspace"
            best_reason = "Prompt was explicitly ambiguous, so the generic workspace template was preferred."
            best_score = max(best_score, 1)

        confidence = 0.45 if best_score == 0 else min(0.95, 0.45 + best_score * 0.15)
        return best_key, (best_reason, confidence)

    def _detect_features(self, lowered: str, defaults: list[str]) -> list[str]:
        detected = {feature for feature, keywords in FEATURE_KEYWORDS.items() if any(keyword in lowered for keyword in keywords)}
        if any(word in lowered for word in ("analytics", "dashboard", "report")):
            detected.add("analytics")
        if "no login" not in lowered and "without login" not in lowered and "auth" in defaults:
            detected.add("auth")

        ordered = [feature for feature in defaults if feature in detected or feature in {"auth", "search"} and feature in defaults]
        extras = [feature for feature in sorted(detected) if feature not in ordered]
        features = ordered + extras
        return features or defaults[:]

    def _stabilize_domain_features(self, features: list[str], defaults: list[str]) -> list[str]:
        protected = {"auth", "search", "analytics"}
        if any(feature not in protected for feature in features):
            return features

        enriched = features[:]
        for feature in defaults:
            if feature not in enriched and feature not in {"auth", "search"}:
                enriched.append(feature)
                break
        return enriched

    def _detect_roles(self, lowered: str, defaults: list[str]) -> list[str]:
        roles = [role for role, keywords in ROLE_KEYWORDS.items() if any(keyword in lowered for keyword in keywords)]
        if roles:
            normalized_roles = []
            for role in roles:
                if role not in normalized_roles:
                    normalized_roles.append(role)
            return normalized_roles
        return defaults[:]

    def _detect_constraints(self, lowered: str) -> list[str]:
        constraints: list[str] = []
        if "no login" in lowered or "without login" in lowered or "no auth" in lowered:
            constraints.append("no_auth")
        if "read only" in lowered or "readonly" in lowered:
            constraints.append("read_only")
        if "single page" in lowered:
            constraints.append("single_page")
        if "mobile" in lowered:
            constraints.append("mobile_friendly")
        if "role-based" in lowered or "role based" in lowered:
            constraints.append("role_permissions")
        return constraints

    def _build_assumptions(
        self,
        lowered: str,
        domain_key: str,
        features: list[str],
        constraints: list[str],
    ) -> list[str]:
        assumptions: list[str] = []
        if domain_key == "generic_workspace":
            assumptions.append("Used a generic operations workspace template because the prompt was ambiguous.")
        if "analytics" not in features and "dashboard" in lowered:
            assumptions.append("Added lightweight dashboard support because the prompt implied operational visibility.")
        if "role_permissions" in constraints and "no_auth" in constraints:
            assumptions.append("Detected a conflict between no-auth and role-based access requirements.")
        if not features:
            assumptions.append("Defaulted to CRUD-first behavior because no explicit feature set was provided.")
        return assumptions

    def _detect_ambiguity(self, lowered: str, domain_key: str) -> str:
        if any(phrase in lowered for phrase in ("something for", "kind of", "maybe", "not sure")):
            return "high"
        if domain_key == "generic_workspace":
            return "medium"
        if len(lowered.split()) < 5:
            return "medium"
        return "low"

    def _derive_app_name(self, prompt: str, fallback_type: str) -> str:
        tokens = [token for token in re.split(r"[^A-Za-z0-9]+", prompt) if token]
        if len(tokens) >= 2:
            candidate = " ".join(tokens[:3]).title()
            if len(candidate) <= 40:
                return candidate
        return fallback_type

    def _feature_signals(self, lowered: str, features: list[str]) -> list[IntentSignal]:
        signals: list[IntentSignal] = []
        for feature in features:
            reason = "Matched explicit prompt keywords." if any(keyword in lowered for keyword in FEATURE_KEYWORDS.get(feature, [])) else "Inherited from the selected domain template."
            confidence = 0.9 if reason.startswith("Matched explicit") else 0.65
            signals.append(IntentSignal(name=f"feature:{feature}", confidence=confidence, reason=reason))
        return signals
