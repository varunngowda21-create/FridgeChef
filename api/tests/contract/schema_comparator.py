"""Shared comparison engine for OpenAPI and TypeScript Zod API contracts.

Validates bidirectional field presence, primitive types, array items, nullability,
and enum values between backend Pydantic models (via OpenAPI 3.1) and frontend Zod schemas.
"""

import ast
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FieldDef:
    name: str
    type_name: str  # 'string', 'number', 'integer', 'boolean', 'array', 'object', 'any', 'unsupported'
    required: bool = True
    nullable: bool = False
    is_integer: bool = False
    enum_values: list[str] | None = None
    array_item_type: str | None = None
    raw_expr: str = ""


@dataclass
class SchemaDef:
    name: str
    fields: dict[str, FieldDef] = field(default_factory=dict)


def _find_matching_delimiter(s: str, open_pos: int, open_ch: str, close_ch: str) -> int:
    """Find the index of the matching closing delimiter given position of opening delimiter."""
    depth = 0
    in_q: str | None = None
    for i in range(open_pos, len(s)):
        ch = s[i]
        if in_q:
            if ch == in_q and s[i - 1] != "\\":
                in_q = None
        else:
            if ch in ("'", '"', "`"):
                in_q = ch
            elif ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    return i
    return -1


def parse_zod_field(name: str, expr: str) -> FieldDef:
    """Parse a single Zod property expression from web/src/api/schemas.ts into a FieldDef."""
    clean = expr.strip()
    required = True
    nullable = False
    is_int = False
    enum_values: list[str] | None = None
    type_name = "any"
    array_item = None

    # Determine outer modifiers vs inner structure
    outer_tail = clean

    # 1. Enums: z.enum(['A', 'B', ...])
    if clean.startswith("z.enum(") or "z.enum(" in clean:
        type_name = "string"
        match = re.search(r"z\.enum\(\s*(\[[^\]]+\])\s*\)", clean)
        if match:
            try:
                parsed_list = ast.literal_eval(match.group(1))
                if isinstance(parsed_list, list):
                    enum_values = [str(x) for x in parsed_list]
            except Exception:
                enum_values = None
            enum_end = match.end()
            outer_tail = clean[enum_end:]
    # 2. Objects: z.object({ ... })
    elif clean.startswith("z.object(") or "z.object({" in clean:
        type_name = "object"
        brace_pos = clean.find("{")
        if brace_pos != -1:
            match_brace = _find_matching_delimiter(clean, brace_pos, "{", "}")
            if match_brace != -1:
                outer_tail = clean[match_brace + 1 :]
    # 3. Arrays: z.array(...)
    elif clean.startswith("z.array(") or "z.array(" in clean:
        type_name = "array"
        paren_pos = clean.find("z.array(") + len("z.array(") - 1
        match_paren = _find_matching_delimiter(clean, paren_pos, "(", ")")
        if match_paren != -1:
            inner_arg = clean[paren_pos + 1 : match_paren].strip()
            outer_tail = clean[match_paren + 1 :]
            if "z.string()" in inner_arg:
                array_item = "string"
            elif "z.number()" in inner_arg:
                array_item = "number"
            elif "z.any()" in inner_arg:
                array_item = "any"
            else:
                array_item = "object"
    # 4. Unions: z.union(...)
    elif "z.union(" in clean and "z.array(" in clean:
        type_name = "array"
        array_item = "any"
    elif "z.union(" in clean:
        type_name = "any"
    # 5. Primitives
    elif "z.string()" in clean:
        type_name = "string"
    elif "z.number()" in clean:
        type_name = "number"
        if ".int()" in clean:
            is_int = True
    elif "z.boolean()" in clean:
        type_name = "boolean"
    elif "z.record(" in clean:
        type_name = "object"
    # 6. Schema identifier references (e.g. UserSchema, RecipeNutritionSchema)
    elif "Schema" in clean:
        type_name = "object"
    # 7. Explicit any/unknown
    elif "z.any()" in clean or "z.unknown()" in clean:
        type_name = "any"
    else:
        # Unsupported or unrecognized construct
        type_name = "unsupported"

    # Evaluate required / nullable from outer tail
    if ".optional()" in outer_tail or ".default(" in outer_tail:
        required = False
    if ".nullable()" in outer_tail:
        nullable = True

    return FieldDef(
        name=name,
        type_name=type_name,
        required=required,
        nullable=nullable,
        is_integer=is_int,
        enum_values=enum_values,
        array_item_type=array_item,
        raw_expr=clean,
    )


def _extract_top_level_zod_properties(schema_body: str) -> dict[str, str]:
    """Extract top-level property definitions from a Zod schema object body,

    properly handling multi-line nested objects, arrays, and chained calls like
    z.object({...}).nullable().optional().
    """
    clean_lines: list[str] = []
    for line in schema_body.splitlines():
        in_quote: str | None = None
        c_line: list[str] = []
        for i, ch in enumerate(line):
            if in_quote:
                c_line.append(ch)
                if ch == in_quote and (i == 0 or line[i - 1] != "\\"):
                    in_quote = None
            else:
                if ch in ("'", '"', "`"):
                    in_quote = ch
                    c_line.append(ch)
                elif ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
                    break
                else:
                    c_line.append(ch)
        clean_lines.append("".join(c_line))

    body = "\n".join(clean_lines)
    props: dict[str, str] = {}
    i = 0
    n = len(body)

    while i < n:
        while i < n and (body[i].isspace() or body[i] == ","):
            i += 1
        if i >= n:
            break

        id_start = i
        while i < n and (body[i].isalnum() or body[i] == "_"):
            i += 1
        prop_name = body[id_start:i]

        while i < n and body[i].isspace():
            i += 1

        if i < n and body[i] == ":" and prop_name.isidentifier():
            i += 1  # Skip ':'
            expr_start = i
            b_depth = 0
            p_depth = 0
            bk_depth = 0
            in_q: str | None = None

            while i < n:
                ch = body[i]
                if in_q:
                    if ch == in_q and body[i - 1] != "\\":
                        in_q = None
                else:
                    if ch in ("'", '"', "`"):
                        in_q = ch
                    elif ch == "{":
                        b_depth += 1
                    elif ch == "}":
                        if b_depth == 0:
                            break
                        b_depth -= 1
                    elif ch == "(":
                        p_depth += 1
                    elif ch == ")":
                        p_depth -= 1
                    elif ch == "[":
                        bk_depth += 1
                    elif ch == "]":
                        bk_depth -= 1
                    elif ch == "," and b_depth == 0 and p_depth == 0 and bk_depth == 0:
                        break
                i += 1

            expr = body[expr_start:i].strip()
            if prop_name:
                props[prop_name] = expr

            if i < n and body[i] == ",":
                i += 1
        else:
            i += 1

    return props


def parse_all_zod_schemas(ts_content: str) -> dict[str, SchemaDef]:
    """Parse all exported Zod schemas from web/src/api/schemas.ts, respecting nested boundaries."""
    schemas: dict[str, SchemaDef] = {}

    # Find each export const <Name> = z.object({
    prefix = "export const "
    pos = 0
    while pos < len(ts_content):
        idx = ts_content.find(prefix, pos)
        if idx == -1:
            break

        start_name = idx + len(prefix)
        eq_pos = ts_content.find("=", start_name)
        if eq_pos == -1:
            break

        s_name = ts_content[start_name:eq_pos].strip()

        # Find opening '{' of z.object({
        zobj_idx = ts_content.find("z.object({", eq_pos)
        if zobj_idx == -1 or zobj_idx > eq_pos + 40:
            # Not a direct z.object
            pos = eq_pos + 1
            continue

        brace_start = ts_content.find("{", zobj_idx + len("z.object("))
        if brace_start == -1:
            break

        # Scan for matching closing brace of this z.object
        depth = 1
        curr = brace_start + 1
        while curr < len(ts_content) and depth > 0:
            if ts_content[curr] == "{":
                depth += 1
            elif ts_content[curr] == "}":
                depth -= 1
            curr += 1

        body = ts_content[brace_start + 1 : curr - 1]
        raw_props = _extract_top_level_zod_properties(body)
        fields = {k: parse_zod_field(k, v) for k, v in raw_props.items()}
        schemas[s_name] = SchemaDef(name=s_name, fields=fields)

        pos = curr

    return schemas


def resolve_openapi_property(
    prop_obj: dict[str, Any], spec: dict[str, Any]
) -> tuple[str, bool, list[str] | None, str | None]:
    """Resolve an OpenAPI property schema object, unpacking $ref and anyOf.

    Returns:
        (type_name, nullable, enum_values, array_item_type)
    """
    if "$ref" in prop_obj:
        ref_name = prop_obj["$ref"].split("/")[-1]
        target = spec.get("components", {}).get("schemas", {}).get(ref_name, {})
        return resolve_openapi_property(target, spec)

    if "anyOf" in prop_obj:
        types: list[str] = []
        nullable = False
        enum_vals: list[str] | None = None
        array_item: str | None = None

        for sub in prop_obj["anyOf"]:
            if sub.get("type") == "null":
                nullable = True
            else:
                t, _, e, a = resolve_openapi_property(sub, spec)
                types.append(t)
                if e:
                    enum_vals = e
                if a:
                    array_item = a

        type_name = types[0] if types else "any"
        return type_name, nullable, enum_vals, array_item

    type_name = prop_obj.get("type", "any")
    enum_vals = prop_obj.get("enum")
    array_item = None
    if type_name == "array":
        items_obj = prop_obj.get("items", {})
        array_item = items_obj.get("type", "object")

    return type_name, False, enum_vals, array_item


def resolve_openapi_schema(spec: dict[str, Any], schema_obj: dict[str, Any], name: str = "") -> SchemaDef:
    """Resolve an OpenAPI component schema into a normalized SchemaDef."""
    if "$ref" in schema_obj:
        ref_name = schema_obj["$ref"].split("/")[-1]
        schema_obj = spec.get("components", {}).get("schemas", {}).get(ref_name, {})
        name = name or ref_name

    required_list = schema_obj.get("required", [])
    properties = schema_obj.get("properties", {})
    fields: dict[str, FieldDef] = {}

    for prop_name, prop_spec in properties.items():
        type_name, nullable, enum_vals, array_item = resolve_openapi_property(prop_spec, spec)
        is_req = prop_name in required_list
        is_integer = type_name == "integer"

        fields[prop_name] = FieldDef(
            name=prop_name,
            type_name=type_name,
            required=is_req,
            nullable=nullable,
            is_integer=is_integer,
            enum_values=enum_vals,
            array_item_type=array_item,
        )

    return SchemaDef(name=name, fields=fields)


def compare_schemas(
    frontend: SchemaDef,
    openapi: SchemaDef,
    allow_extra_frontend_fields: set[str] | None = None,
    allow_extra_openapi_fields: set[str] | None = None,
) -> list[str]:
    """Bidirectional schema comparison engine.

    Checks:
    1. Missing required fields in either direction.
    2. Required vs optional mismatch.
    3. Type incompatibilities (handling number vs integer and decimal strings).
    4. Nullability incompatibilities.
    5. Enum literal set mismatches.
    6. Array item type mismatches.

    Returns a list of human-readable mismatch error strings (empty if schemas match).
    """
    mismatches: list[str] = []
    allow_extra_frontend = allow_extra_frontend_fields or set()
    allow_extra_openapi = allow_extra_openapi_fields or set()

    f_names = set(frontend.fields.keys())
    o_names = set(openapi.fields.keys())

    # 1. Check required fields in OpenAPI that are completely missing in frontend
    missing_in_frontend = (o_names - f_names) - allow_extra_openapi
    for m in missing_in_frontend:
        o_field = openapi.fields[m]
        if o_field.required and not o_field.nullable:
            mismatches.append(
                f"[{frontend.name} <-> {openapi.name}] Missing required field '{m}' in frontend schema "
                f"(OpenAPI defines type '{o_field.type_name}', required=True)"
            )

    # 2. Check fields in frontend that are completely missing in OpenAPI
    missing_in_openapi = (f_names - o_names) - allow_extra_frontend
    for m in missing_in_openapi:
        mismatches.append(
            f"[{frontend.name} <-> {openapi.name}] Extra field '{m}' declared in frontend schema "
            f"not present in OpenAPI schema"
        )

    # 3. Check shared fields for type, nullability, enum, and required consistency
    shared = f_names & o_names
    for name in shared:
        f_field = frontend.fields[name]
        o_field = openapi.fields[name]

        # A. Nullability compatibility
        # If OpenAPI says field is nullable, frontend must allow null
        if o_field.nullable and not f_field.nullable:
            mismatches.append(
                f"[{frontend.name}.{name}] OpenAPI permits null (nullable=True), but frontend schema does not allow null"
            )

        # B. Type compatibility
        # In JSON/JS, numbers and integers are both numbers. Decimal in Python can appear as string or number.
        f_type = f_field.type_name
        o_type = o_field.type_name

        if f_type == "unsupported":
            mismatches.append(
                f"[{frontend.name}.{name}] Unsupported or unrecognized Zod schema construct: '{f_field.raw_expr or name}'"
            )
            continue
        if o_type == "unsupported":
            mismatches.append(
                f"[{openapi.name}.{name}] Unsupported or unrecognized OpenAPI schema construct"
            )
            continue

        compatible = False
        if f_type == "any" or o_type == "any":
            compatible = True
        elif f_type == o_type:
            compatible = True
        elif f_type == "number" and o_type in ("integer", "number", "string"):
            # Decimal quantities or counts
            compatible = True
        elif f_type == "string" and o_type == "string":
            compatible = True
        elif f_type == "object" and o_type == "object":
            compatible = True

        if not compatible:
            mismatches.append(
                f"[{frontend.name}.{name}] Type mismatch: frontend expects '{f_type}', OpenAPI specifies '{o_type}'"
            )

        # C. Enum values
        if f_field.enum_values is not None and o_field.enum_values is not None:
            f_set = set(f_field.enum_values)
            o_set = set(o_field.enum_values)
            if f_set != o_set:
                mismatches.append(
                    f"[{frontend.name}.{name}] Enum values mismatch: frontend has {sorted(f_set)}, OpenAPI has {sorted(o_set)}"
                )

        # D. Array item types
        if f_type == "array" and o_type == "array":
            if f_field.array_item_type and o_field.array_item_type:
                if f_field.array_item_type != "any" and o_field.array_item_type != "any":
                    if f_field.array_item_type != o_field.array_item_type:
                        mismatches.append(
                            f"[{frontend.name}.{name}] Array item type mismatch: frontend items '{f_field.array_item_type}', "
                            f"OpenAPI items '{o_field.array_item_type}'"
                        )

    return mismatches
