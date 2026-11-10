"""Robust parser to extract client API endpoint calls from frontend TypeScript source."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExtractedEndpoint:
    name: str
    http_method: str
    raw_path_expr: str
    normalized_path: str


def normalize_ts_template_path(raw_expr: str) -> str:
    """Normalize a TypeScript template or literal path to a standard OpenAPI route path.

    Examples:
        '/auth/register' -> '/api/v1/auth/register'
        '`/recipes/${recipeId}${qs}`' -> '/api/v1/recipes/{id}'
        '`/inventory/${id}`' -> '/api/v1/inventory/{item_id}'
        '`/meal-plans/${planId}/slots/${day}/${meal}/regenerate`' -> '/api/v1/meal-plans/{id}/slots/{day}/{meal}/regenerate'
    """
    clean = raw_expr.strip().strip("'\"`")

    # Remove query string expressions like ${qs ? ...}
    if "${qs" in clean:
        clean = clean.split("${qs")[0]
    if "?" in clean and "${" not in clean.split("?")[1]:
        clean = clean.split("?")[0]

    # Map dynamic route parameters to match backend FastAPI path param names
    clean = clean.replace("/inventory/${id}", "/inventory/{item_id}")
    clean = clean.replace("${scanId}", "{scan_id}")
    clean = clean.replace("${recipeId}", "{id}")
    clean = clean.replace("${planId}", "{id}")
    clean = clean.replace("${listId}", "{id}")
    clean = clean.replace("${canonicalId}", "{canonical_id}")
    clean = clean.replace("${day}", "{day}")
    clean = clean.replace("${meal}", "{meal}")

    # Generic fallback for any remaining ${var} -> {var}
    while "${" in clean:
        start = clean.find("${")
        end = clean.find("}", start)
        if end != -1:
            var_name = clean[start + 2 : end].strip()
            clean = clean[:start] + f"{{{var_name}}}" + clean[end + 1 :]
        else:
            break

    if not clean.startswith("/api/v1"):
        clean = f"/api/v1{clean}"

    return clean


def _extract_property_name_before(content: str, api_pos: int) -> str:
    """Scan backward from api.<method> to find the enclosing method name in `endpoints = { name: ... }`."""
    before = content[:api_pos]
    # Find the nearest '=>' before api.<method>
    arrow_pos = before.rfind("=>")
    if arrow_pos == -1:
        return "unknown"
    pre_arrow = before[:arrow_pos].rstrip()
    if pre_arrow.endswith(")"):
        # Match back to opening paren
        depth = 1
        i = len(pre_arrow) - 2
        while i >= 0 and depth > 0:
            if pre_arrow[i] == ")":
                depth += 1
            elif pre_arrow[i] == "(":
                depth -= 1
            i -= 1
        pre_paren = pre_arrow[: i + 1].rstrip()
    else:
        pre_paren = pre_arrow

    colon_pos = pre_paren.rfind(":")
    if colon_pos != -1:
        ident_part = pre_paren[:colon_pos].rstrip()
        name_chars: list[str] = []
        for ch in reversed(ident_part):
            if ch.isalnum() or ch == "_":
                name_chars.append(ch)
            else:
                break
        if name_chars:
            return "".join(reversed(name_chars))

    return "unknown"


def extract_endpoints_from_ts(ts_file_path: Path) -> list[ExtractedEndpoint]:
    """Parse web/src/api/endpoints.ts by token scanning, robust against multiline declarations and generics."""
    content = ts_file_path.read_text(encoding="utf-8")
    methods = ["get", "post", "put", "patch", "delete", "upload"]
    endpoints: list[ExtractedEndpoint] = []

    pos = 0
    while pos < len(content):
        # Find next api.<method>
        next_pos = -1
        next_target = None
        next_method = None
        for m in methods:
            target = f"api.{m}"
            p = content.find(target, pos)
            if p != -1 and (next_pos == -1 or p < next_pos):
                next_pos = p
                next_target = target
                next_method = m

        if next_pos == -1 or next_method is None or next_target is None:
            break

        name = _extract_property_name_before(content, next_pos)

        # Scan forwards past generic arguments <...>
        curr = next_pos + len(next_target)
        while curr < len(content) and content[curr].isspace():
            curr += 1

        if curr < len(content) and content[curr] == "<":
            depth = 1
            curr += 1
            while curr < len(content) and depth > 0:
                if content[curr] == "<":
                    depth += 1
                elif content[curr] == ">":
                    depth -= 1
                curr += 1

        while curr < len(content) and content[curr].isspace():
            curr += 1

        # Find opening paren '('
        if curr < len(content) and content[curr] == "(":
            curr += 1
            while curr < len(content) and content[curr].isspace():
                curr += 1

            # Extract path string literal or template
            if curr < len(content) and content[curr] in ("'", '"', "`"):
                q_char = content[curr]
                start_str = curr
                curr += 1
                while curr < len(content):
                    if content[curr] == q_char and content[curr - 1] != "\\":
                        break
                    curr += 1
                if curr < len(content):
                    raw_str = content[start_str : curr + 1]
                    http_method = "POST" if next_method in ("post", "upload") else next_method.upper()
                    norm_path = normalize_ts_template_path(raw_str)
                    endpoints.append(
                        ExtractedEndpoint(
                            name=name,
                            http_method=http_method,
                            raw_path_expr=raw_str,
                            normalized_path=norm_path,
                        )
                    )

        pos = curr + 1

    return endpoints
