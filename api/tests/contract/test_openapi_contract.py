"""API Contract Testing Suite.

Verifies bidirectional contract consistency between:
1. Backend FastAPI OpenAPI specification (via app.openapi()) and Pydantic models.
2. Frontend TypeScript endpoint calls in web/src/api/endpoints.ts.
3. Frontend TypeScript Zod schemas in web/src/api/schemas.ts.
4. Domain enums and standard error envelopes.

Also contains negative contract tests to prove that the shared comparison engine
catches contract drift (missing fields, type mismatches, enum differences, nullability).
"""

import json
from pathlib import Path
from typing import Any

import pytest

from app.core.errors import AppError, format_error_response
from app.main import app
from app.schemas.user import ALLOWED_DIETS, ALLOWED_SPICE_LEVELS
from app.services.freshness import FreshnessStatus
from tests.contract.endpoint_extractor import (
    ExtractedEndpoint,
    extract_endpoints_from_ts,
)
from tests.contract.schema_comparator import (
    FieldDef,
    SchemaDef,
    compare_schemas,
    parse_all_zod_schemas,
    resolve_openapi_schema,
)

# Project paths
ROOT_DIR = Path(__file__).resolve().parents[3]
WEB_DIR = ROOT_DIR / "web"
ENDPOINTS_TS_PATH = WEB_DIR / "src" / "api" / "endpoints.ts"
SCHEMAS_TS_PATH = WEB_DIR / "src" / "api" / "schemas.ts"

# Verified bidirectional response schema mappings
RESPONSE_SCHEMA_MAP = {
    "AuthResponseSchema": "TokenResponse",
    "UserProfileResponseSchema": "UserProfileResponse",
    "UserPreferencesSchema": "UserPreferenceResponse",
    "IngredientCatalogueItemSchema": "IngredientOut",
    "RecipeDetailSchema": "RecipeOut",
    "InventoryItemSchema": "InventoryItemResponse",
    "InventoryListResponseSchema": "InventoryListResponse",
    "InventoryUseResponseSchema": "InventoryUseResponse",
    "InventoryWasteResponseSchema": "InventoryWasteResponse",
    "ScanResponseSchema": "ScanSessionResponse",
    "ScanCandidateSchema": "ScanCandidate",
    "RecommendationResponseSchema": "RecommendationResponse",
    "MealPlanSchema": "MealPlanResponse",
    "ShoppingListSchema": "ShoppingListResponse",
    "ShoppingListItemSchema": "ShoppingListItem",
    "DashboardResponseSchema": "DashboardResponse",
}

# Frontend request contract specifications derived from web/src/api/endpoints.ts
FRONTEND_REQUEST_SCHEMAS: dict[str, SchemaDef] = {
    "UserRegisterRequest": SchemaDef(
        name="UserRegisterRequest",
        fields={
            "email": FieldDef(name="email", type_name="string", required=True),
            "password": FieldDef(name="password", type_name="string", required=True),
            "display_name": FieldDef(name="display_name", type_name="string", required=True),
        },
    ),
    "UserLoginRequest": SchemaDef(
        name="UserLoginRequest",
        fields={
            "email": FieldDef(name="email", type_name="string", required=True),
            "password": FieldDef(name="password", type_name="string", required=True),
        },
    ),
    "RefreshTokenRequestBody": SchemaDef(
        name="RefreshTokenRequestBody",
        fields={
            "refresh_token": FieldDef(name="refresh_token", type_name="string", required=False, nullable=True),
        },
    ),
    "AccountDeleteRequest": SchemaDef(
        name="AccountDeleteRequest",
        fields={
            "password": FieldDef(name="password", type_name="string", required=True),
        },
    ),
    "UserPreferenceUpdate": SchemaDef(
        name="UserPreferenceUpdate",
        fields={
            "household_size": FieldDef(name="household_size", type_name="integer", required=False, nullable=True),
            "diet": FieldDef(name="diet", type_name="string", required=False, nullable=True),
            "spice_level": FieldDef(name="spice_level", type_name="string", required=False, nullable=True),
            "cuisines": FieldDef(name="cuisines", type_name="array", required=False, nullable=True, array_item_type="string"),
            "max_cooking_time": FieldDef(name="max_cooking_time", type_name="integer", required=False, nullable=True),
            "allergies": FieldDef(name="allergies", type_name="array", required=False, nullable=True, array_item_type="string"),
            "avoided_ingredients": FieldDef(name="avoided_ingredients", type_name="array", required=False, nullable=True, array_item_type="string"),
        },
    ),
    "InventoryItemCreate": SchemaDef(
        name="InventoryItemCreate",
        fields={
            "canonical_id": FieldDef(name="canonical_id", type_name="string", required=True),
            "quantity": FieldDef(name="quantity", type_name="number", required=True),
            "unit": FieldDef(name="unit", type_name="string", required=True),
            "storage": FieldDef(name="storage", type_name="string", required=True),
            "opened_on": FieldDef(name="opened_on", type_name="string", required=False, nullable=True),
            "added_on": FieldDef(name="added_on", type_name="string", required=False, nullable=True),
            "display_name": FieldDef(name="display_name", type_name="string", required=False, nullable=True),
        },
    ),
    "InventoryItemUpdate": SchemaDef(
        name="InventoryItemUpdate",
        fields={
            "quantity": FieldDef(name="quantity", type_name="number", required=False, nullable=True),
            "storage": FieldDef(name="storage", type_name="string", required=False, nullable=True),
            "opened_on": FieldDef(name="opened_on", type_name="string", required=False, nullable=True),
            "added_on": FieldDef(name="added_on", type_name="string", required=False, nullable=True),
            "display_name": FieldDef(name="display_name", type_name="string", required=False, nullable=True),
        },
    ),
    "InventoryUseRequest": SchemaDef(
        name="InventoryUseRequest",
        fields={
            "quantity": FieldDef(name="quantity", type_name="number", required=True),
        },
    ),
    "InventoryWasteRequest": SchemaDef(
        name="InventoryWasteRequest",
        fields={
            "quantity": FieldDef(name="quantity", type_name="number", required=False, nullable=True),
        },
    ),
    "ScanConfirmItem": SchemaDef(
        name="ScanConfirmItem",
        fields={
            "candidate_id": FieldDef(name="candidate_id", type_name="string", required=False, nullable=True),
            "canonical_id": FieldDef(name="canonical_id", type_name="string", required=False, nullable=True),
            "name": FieldDef(name="name", type_name="string", required=True),
            "quantity": FieldDef(name="quantity", type_name="number", required=True),
            "unit": FieldDef(name="unit", type_name="string", required=True),
            "storage": FieldDef(name="storage", type_name="string", required=True),
            "opened_on": FieldDef(name="opened_on", type_name="string", required=False, nullable=True),
        },
    ),
    "RecipeCookedRequest": SchemaDef(
        name="RecipeCookedRequest",
        fields={
            "servings": FieldDef(name="servings", type_name="integer", required=False, nullable=True),
            "rating": FieldDef(name="rating", type_name="integer", required=False, nullable=True),
        },
    ),
    "MealPlanCreateRequest": SchemaDef(
        name="MealPlanCreateRequest",
        fields={
            "start_date": FieldDef(name="start_date", type_name="string", required=False, nullable=True),
            "locked_slots": FieldDef(name="locked_slots", type_name="array", required=False, nullable=True, array_item_type="object"),
        },
    ),
    "ShoppingListCreateRequest": SchemaDef(
        name="ShoppingListCreateRequest",
        fields={
            "source": FieldDef(name="source", type_name="string", required=True),
            "plan_id": FieldDef(name="plan_id", type_name="string", required=False, nullable=True),
            "recipes": FieldDef(name="recipes", type_name="array", required=False, nullable=True, array_item_type="object"),
            "manual_items": FieldDef(name="manual_items", type_name="array", required=False, nullable=True, array_item_type="object"),
        },
    ),
    "ShoppingItemPatchRequest": SchemaDef(
        name="ShoppingItemPatchRequest",
        fields={
            "bought": FieldDef(name="bought", type_name="boolean", required=True),
            "add_to_inventory": FieldDef(name="add_to_inventory", type_name="boolean", required=False),
        },
    ),
}


@pytest.fixture(scope="session")
def openapi_spec() -> dict[str, Any]:
    """Retrieve the generated FastAPI OpenAPI 3.1 specification."""
    return app.openapi()


@pytest.fixture(scope="session")
def frontend_zod_schemas() -> dict[str, SchemaDef]:
    """Parse all exported Zod schemas from web/src/api/schemas.ts."""
    assert SCHEMAS_TS_PATH.exists(), f"Frontend schemas.ts not found at {SCHEMAS_TS_PATH}"
    ts_content = SCHEMAS_TS_PATH.read_text(encoding="utf-8")
    return parse_all_zod_schemas(ts_content)


@pytest.fixture(scope="session")
def extracted_endpoints() -> list[ExtractedEndpoint]:
    """Extract all client API calls from web/src/api/endpoints.ts."""
    assert ENDPOINTS_TS_PATH.exists(), f"Frontend endpoints.ts not found at {ENDPOINTS_TS_PATH}"
    return extract_endpoints_from_ts(ENDPOINTS_TS_PATH)


class TestFrontendEndpointsContract:
    """Verifies that all frontend endpoint definitions match registered backend OpenAPI routes."""

    def test_all_frontend_endpoints_exist_in_openapi(
        self,
        openapi_spec: dict[str, Any],
        extracted_endpoints: list[ExtractedEndpoint],
    ) -> None:
        """Every frontend endpoint declaration must correspond to an active OpenAPI path and method."""
        openapi_paths = openapi_spec.get("paths", {})
        assert len(extracted_endpoints) >= 28, f"Expected at least 28 frontend endpoints, got {len(extracted_endpoints)}"

        missing_endpoints: list[str] = []
        for ep in extracted_endpoints:
            path_item = openapi_paths.get(ep.normalized_path)
            if not path_item:
                missing_endpoints.append(f"Route path not found in OpenAPI: {ep.http_method} {ep.normalized_path} ({ep.name})")
                continue

            method_lower = ep.http_method.lower()
            if method_lower not in path_item:
                missing_endpoints.append(
                    f"HTTP method '{ep.http_method}' not found for path '{ep.normalized_path}' (Available: {list(path_item.keys())})"
                )

        assert not missing_endpoints, "Frontend endpoints mismatch with backend OpenAPI routes:\n" + "\n".join(
            missing_endpoints
        )

    def test_path_parameters_consistency(
        self,
        openapi_spec: dict[str, Any],
        extracted_endpoints: list[ExtractedEndpoint],
    ) -> None:
        """Verify that every dynamic path parameter in frontend endpoints is declared as path parameter in OpenAPI."""
        openapi_paths = openapi_spec.get("paths", {})
        import re

        for ep in extracted_endpoints:
            path_params = re.findall(r"\{([a-zA-Z0-9_]+)\}", ep.normalized_path)
            if not path_params:
                continue

            path_item = openapi_paths.get(ep.normalized_path, {})
            op = path_item.get(ep.http_method.lower(), {})
            registered_params = {
                p["name"] for p in op.get("parameters", []) if p.get("in") == "path"
            }

            for param in path_params:
                assert param in registered_params, (
                    f"Path parameter '{param}' in endpoint '{ep.name}' ({ep.normalized_path}) "
                    f"is not declared in OpenAPI parameters ({registered_params})"
                )


class TestResponseSchemasContract:
    """Verifies that frontend Zod response schemas match backend Pydantic models via OpenAPI."""

    @pytest.mark.parametrize("zod_name, backend_name", RESPONSE_SCHEMA_MAP.items())
    def test_response_schema_parity(
        self,
        zod_name: str,
        backend_name: str,
        openapi_spec: dict[str, Any],
        frontend_zod_schemas: dict[str, SchemaDef],
    ) -> None:
        assert zod_name in frontend_zod_schemas, f"Frontend Zod schema '{zod_name}' was not found in schemas.ts"
        f_schema = frontend_zod_schemas[zod_name]

        components = openapi_spec.get("components", {}).get("schemas", {})
        assert backend_name in components, f"Backend schema '{backend_name}' not found in OpenAPI components"

        o_schema = resolve_openapi_schema(openapi_spec, components[backend_name], name=backend_name)
        mismatches = compare_schemas(f_schema, o_schema)

        assert not mismatches, f"Contract drift detected between {zod_name} and {backend_name}:\n" + "\n".join(mismatches)


class TestRequestContracts:
    """Verifies that frontend request contracts match backend Pydantic request models in OpenAPI."""

    @pytest.mark.parametrize("backend_name, f_schema", FRONTEND_REQUEST_SCHEMAS.items())
    def test_request_body_parity(
        self,
        backend_name: str,
        f_schema: SchemaDef,
        openapi_spec: dict[str, Any],
    ) -> None:
        components = openapi_spec.get("components", {}).get("schemas", {})
        assert backend_name in components, f"Backend request schema '{backend_name}' not found in OpenAPI components"

        o_schema = resolve_openapi_schema(openapi_spec, components[backend_name], name=backend_name)
        mismatches = compare_schemas(f_schema, o_schema)

        assert not mismatches, f"Request contract drift detected for {backend_name}:\n" + "\n".join(mismatches)

    def test_query_parameters_declared_in_openapi(self, openapi_spec: dict[str, Any]) -> None:
        """Verify key query parameters used by frontend exist in OpenAPI operations."""
        paths = openapi_spec.get("paths", {})

        # 1. /api/v1/ingredients
        ing_params = {p["name"]: p for p in paths["/api/v1/ingredients"]["get"]["parameters"]}
        assert "query" in ing_params
        assert "category" in ing_params
        assert "limit" in ing_params

        # 2. /api/v1/recipes/{id}
        recipe_params = {p["name"]: p for p in paths["/api/v1/recipes/{id}"]["get"]["parameters"]}
        assert "servings" in recipe_params

        # 3. /api/v1/inventory
        inv_params = {p["name"]: p for p in paths["/api/v1/inventory"]["get"]["parameters"]}
        assert "status" in inv_params
        assert "storage" in inv_params
        assert "sort" in inv_params

        # 4. /api/v1/recommendations
        rec_params = {p["name"]: p for p in paths["/api/v1/recommendations"]["get"]["parameters"]}
        assert "limit" in rec_params
        assert "servings" in rec_params


class TestDomainEnumsContract:
    """Verifies that frontend enum literals match backend allowed values and enumerations exactly."""

    def test_freshness_status_enum(self, frontend_zod_schemas: dict[str, SchemaDef]) -> None:
        backend_values = {s.value for s in FreshnessStatus}
        item_schema = frontend_zod_schemas["InventoryItemSchema"]
        status_field = item_schema.fields.get("status")
        assert status_field is not None
        assert status_field.enum_values is not None
        frontend_values = set(status_field.enum_values)
        assert frontend_values == backend_values, f"FreshnessStatus drift: {frontend_values} vs {backend_values}"

    def test_diet_type_enum(self, frontend_zod_schemas: dict[str, SchemaDef]) -> None:
        backend_values = set(ALLOWED_DIETS)
        prefs_schema = frontend_zod_schemas["UserPreferencesSchema"]
        diet_field = prefs_schema.fields.get("diet")
        assert diet_field is not None
        assert diet_field.enum_values is not None
        frontend_values = set(diet_field.enum_values)
        assert frontend_values == backend_values, f"DietType drift: {frontend_values} vs {backend_values}"

    def test_spice_level_enum(self, frontend_zod_schemas: dict[str, SchemaDef]) -> None:
        backend_values = set(ALLOWED_SPICE_LEVELS)
        prefs_schema = frontend_zod_schemas["UserPreferencesSchema"]
        spice_field = prefs_schema.fields.get("spice_level")
        assert spice_field is not None
        assert spice_field.enum_values is not None
        frontend_values = set(spice_field.enum_values)
        assert frontend_values == backend_values, f"SpiceLevel drift: {frontend_values} vs {backend_values}"

    def test_storage_location_enum(self, frontend_zod_schemas: dict[str, SchemaDef]) -> None:
        expected_storage = {"FRIDGE", "FREEZER", "PANTRY", "COUNTER"}
        item_schema = frontend_zod_schemas["InventoryItemSchema"]
        storage_field = item_schema.fields.get("storage")
        assert storage_field is not None
        assert storage_field.enum_values is not None
        frontend_values = set(storage_field.enum_values)
        assert frontend_values == expected_storage, f"StorageLocation drift: {frontend_values} vs {expected_storage}"

    def test_scan_confidence_enum(self, frontend_zod_schemas: dict[str, SchemaDef]) -> None:
        expected_confidence = {"HIGH", "MEDIUM", "LOW"}
        candidate_schema = frontend_zod_schemas["ScanCandidateSchema"]
        conf_field = candidate_schema.fields.get("confidence")
        assert conf_field is not None
        assert conf_field.enum_values is not None
        frontend_values = set(conf_field.enum_values)
        assert frontend_values == expected_confidence, f"ScanConfidence drift: {frontend_values} vs {expected_confidence}"


class TestStandardErrorEnvelopeContract:
    """Verifies that API error formatting matches the PRD standard error envelope."""

    def test_format_error_response_structure(self) -> None:
        resp = format_error_response(
            code="TEST_ERROR",
            message="Test error message.",
            status_code=400,
            request_id="req-123",
            details={"field": "test"},
        )
        data = json.loads(bytes(resp.body).decode("utf-8"))

        assert "error" in data, "Response body missing top-level 'error' key"
        err = data["error"]
        assert err["code"] == "TEST_ERROR"
        assert err["message"] == "Test error message."
        assert err["details"] == {"field": "test"}
        assert err["request_id"] == "req-123"

    def test_app_error_attributes(self) -> None:
        err = AppError(code="CUSTOM_CODE", message="Custom message", status_code=403, details="detail")
        assert err.code == "CUSTOM_CODE"
        assert err.message == "Custom message"
        assert err.status_code == 403
        assert err.details == "detail"


class TestContractDriftDetectionNegative:
    """Verifies that the comparison engine correctly detects intentional contract mismatches.

    Uses the shared compare_schemas engine to prove that any contract drift
    (missing field, extra field, type mismatch, nullability mismatch, enum mismatch, array item mismatch)
    is reliably caught.
    """

    def test_detects_missing_required_field_in_frontend(self) -> None:
        frontend = SchemaDef(
            name="TestModel",
            fields={"id": FieldDef(name="id", type_name="string", required=True)},
        )
        backend = SchemaDef(
            name="TestModel",
            fields={
                "id": FieldDef(name="id", type_name="string", required=True),
                "name": FieldDef(name="name", type_name="string", required=True, nullable=False),
            },
        )
        mismatches = compare_schemas(frontend, backend)
        assert len(mismatches) == 1
        assert "Missing required field 'name' in frontend schema" in mismatches[0]

    def test_detects_extra_field_in_frontend(self) -> None:
        frontend = SchemaDef(
            name="TestModel",
            fields={
                "id": FieldDef(name="id", type_name="string", required=True),
                "phantom": FieldDef(name="phantom", type_name="string", required=False),
            },
        )
        backend = SchemaDef(
            name="TestModel",
            fields={"id": FieldDef(name="id", type_name="string", required=True)},
        )
        mismatches = compare_schemas(frontend, backend)
        assert len(mismatches) == 1
        assert "Extra field 'phantom' declared in frontend schema" in mismatches[0]

    def test_detects_primitive_type_mismatch(self) -> None:
        frontend = SchemaDef(
            name="TestModel",
            fields={"count": FieldDef(name="count", type_name="boolean", required=True)},
        )
        backend = SchemaDef(
            name="TestModel",
            fields={"count": FieldDef(name="count", type_name="integer", required=True)},
        )
        mismatches = compare_schemas(frontend, backend)
        assert len(mismatches) == 1
        assert "Type mismatch: frontend expects 'boolean', OpenAPI specifies 'integer'" in mismatches[0]

    def test_detects_nullability_mismatch(self) -> None:
        frontend = SchemaDef(
            name="TestModel",
            fields={"description": FieldDef(name="description", type_name="string", required=False, nullable=False)},
        )
        backend = SchemaDef(
            name="TestModel",
            fields={"description": FieldDef(name="description", type_name="string", required=False, nullable=True)},
        )
        mismatches = compare_schemas(frontend, backend)
        assert len(mismatches) == 1
        assert "OpenAPI permits null (nullable=True), but frontend schema does not allow null" in mismatches[0]

    def test_detects_enum_literal_mismatch(self) -> None:
        frontend = SchemaDef(
            name="TestModel",
            fields={"status": FieldDef(name="status", type_name="string", required=True, enum_values=["ACTIVE", "PENDING"])},
        )
        backend = SchemaDef(
            name="TestModel",
            fields={"status": FieldDef(name="status", type_name="string", required=True, enum_values=["ACTIVE", "ARCHIVED"])},
        )
        mismatches = compare_schemas(frontend, backend)
        assert len(mismatches) == 1
        assert "Enum values mismatch" in mismatches[0]

    def test_detects_array_item_type_mismatch(self) -> None:
        frontend = SchemaDef(
            name="TestModel",
            fields={"tags": FieldDef(name="tags", type_name="array", required=True, array_item_type="string")},
        )
        backend = SchemaDef(
            name="TestModel",
            fields={"tags": FieldDef(name="tags", type_name="array", required=True, array_item_type="number")},
        )
        mismatches = compare_schemas(frontend, backend)
        assert len(mismatches) == 1
        assert "Array item type mismatch" in mismatches[0]

    def test_detects_unsupported_schema_construct(self) -> None:
        frontend = SchemaDef(
            name="TestModel",
            fields={"custom": FieldDef(name="custom", type_name="unsupported", required=True, raw_expr="z.customBogus()")},
        )
        backend = SchemaDef(
            name="TestModel",
            fields={"custom": FieldDef(name="custom", type_name="string", required=True)},
        )
        mismatches = compare_schemas(frontend, backend)
        assert len(mismatches) == 1
        assert "Unsupported or unrecognized Zod schema construct: 'z.customBogus()'" in mismatches[0]
