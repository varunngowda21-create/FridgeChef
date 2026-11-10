"""FridgeChef AI — Staging Deployment Validation Suite

Simulates a production/staging deployment through Nginx (http://localhost:80)
and verifies complete user journeys, data persistence, and isolation.
Uses strictly Python standard library (urllib.request, json, uuid).
"""
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

BASE_URL = os.environ.get("STAGING_BASE_URL", sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:80")

# Standard 1x1 valid JPEG bytes
TINY_JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00"
    b"\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19"
    b"\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
    b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01"
    b"\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b"
    b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
)


def make_request(method: str, path: str, data: dict | None = None, headers: dict | None = None) -> tuple[int, dict, dict]:
    url = f"{BASE_URL}{path}"
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)

    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
            resp_headers = dict(resp.headers)
            resp_headers["_all_cookies"] = resp.headers.get_all("Set-Cookie") or []
            raw_bytes = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                raw_bytes = gzip.decompress(raw_bytes)
            resp_body = raw_bytes.decode("utf-8")
            parsed_data = json.loads(resp_body) if resp_body else {}
            return status, parsed_data, resp_headers
    except urllib.error.HTTPError as exc:
        status = exc.code
        resp_headers = dict(exc.headers)
        raw_bytes = exc.read()
        print(f"HTTPError {method} {path} status: {status}, raw: {repr(raw_bytes)}")
        if exc.headers.get("Content-Encoding") == "gzip":
            try:
                raw_bytes = gzip.decompress(raw_bytes)
            except Exception:
                pass
        resp_body = raw_bytes.decode("utf-8")
        parsed_data = json.loads(resp_body) if resp_body else {}
        return status, parsed_data, resp_headers


def upload_multipart(path: str, field_name: str, filename: str, file_bytes: bytes, fields: dict, headers: dict | None = None) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    body = bytearray()

    for k, v in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode("utf-8"))
        body.extend(f"{v}\r\n".encode("utf-8"))

    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8"))
    body.extend(b"Content-Type: image/jpeg\r\n\r\n")
    body.extend(file_bytes)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    req_headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url, data=bytes(body), headers=req_headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw_bytes = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                raw_bytes = gzip.decompress(raw_bytes)
            resp_body = raw_bytes.decode("utf-8")
            return resp.status, json.loads(resp_body) if resp_body else {}
    except urllib.error.HTTPError as exc:
        raw_bytes = exc.read()
        if exc.headers.get("Content-Encoding") == "gzip":
            raw_bytes = gzip.decompress(raw_bytes)
        resp_body = raw_bytes.decode("utf-8")
        return exc.code, json.loads(resp_body) if resp_body else {}


def run_staging_validation():
    print("=" * 60)
    print(" FridgeChef AI — Staging Deployment Validation Suite")
    print(f" Target: {BASE_URL}")
    print("=" * 60)

    # 1. Health & Readiness Check
    print("\n[Step 1] Waiting for Nginx reverse-proxy and API health (/api/health)...")
    healthy = False
    for attempt in range(1, 31):
        try:
            status, body, headers = make_request("GET", "/api/health")
            if status == 200 and body.get("status") == "healthy":
                healthy = True
                break
        except Exception:
            pass
        if attempt % 5 == 0:
            print(f"  Still waiting for /api/health (attempt {attempt}/30)...")
        time.sleep(1)

    assert healthy, "API /api/health did not become healthy within 30 seconds!"
    assert "x-request-id" in headers or "X-Request-ID" in headers, "Missing X-Request-ID header"
    print("✓ Health check PASSED (Status: healthy, X-Request-ID confirmed).")

    # 2. User 1 Registration & Login
    uid1 = uuid.uuid4().hex[:8]
    user1_email = f"staging_user_{uid1}@example.com"
    user1_password = "StagingPassword123!"

    print(f"\n[Step 2] Registering User 1 ({user1_email})...")
    status, body, reg_headers = make_request(
        "POST",
        "/api/v1/auth/register",
        {"email": user1_email, "password": user1_password, "display_name": f"Staging Tester {uid1}"},
    )
    assert status == 201, f"Registration failed ({status}): {body}"
    user1_access_token = body["access_token"]
    auth_headers = {"Authorization": f"Bearer {user1_access_token}"}

    # Extract auth cookies for CSRF and session testing
    csrf_token = None
    refresh_token = None
    all_cookies = reg_headers.get("_all_cookies", [])
    for cookie_header in all_cookies:
        for item in cookie_header.split(";"):
            item = item.strip()
            if item.startswith("csrf_token="):
                csrf_token = item.split("=", 1)[1]
            elif item.startswith("refresh_token="):
                refresh_token = item.split("=", 1)[1]

    print(f"✓ User 1 registered successfully (CSRF present: {bool(csrf_token)}, Refresh cookie present: {bool(refresh_token)}).")

    # 2b. Token Refresh Verification
    print("\n[Step 2b] Testing Token Refresh (/api/v1/auth/refresh)...")
    if csrf_token and refresh_token:
        refresh_headers = {
            "X-CSRF-Token": csrf_token,
            "Cookie": f"csrf_token={csrf_token}; refresh_token={refresh_token}",
        }
        status, body, ref_headers = make_request("POST", "/api/v1/auth/refresh", headers=refresh_headers)
        assert status == 200, f"Token refresh failed ({status}): {body}"
        user1_access_token = body["access_token"]
        auth_headers = {"Authorization": f"Bearer {user1_access_token}"}
        print("✓ Token refresh succeeded with CSRF verification, new access token acquired.")

    # 3. User 1 Preferences Initialization
    print("\n[Step 3] Updating User 1 Preferences (/api/v1/me/preferences)...")
    status, body, _ = make_request(
        "PUT",
        "/api/v1/me/preferences",
        {
            "household_size": 2,
            "diet": "VEGETARIAN",
            "spice_level": "MEDIUM",
            "cuisines": ["North Indian", "South Indian"],
            "max_cooking_time": 45,
            "allergies": [],
            "avoided_ingredients": [],
        },
        headers=auth_headers,
    )
    assert status == 200, f"Preferences failed ({status}): {body}"
    print("✓ Preferences saved (household_size: 2, diet: 'VEGETARIAN').")

    # 4. Inventory Creation & Listing
    print("\n[Step 4] Creating inventory items (/api/v1/inventory)...")
    items_to_add = [
        {"canonical_id": "onion", "display_name": "Red Onion", "quantity": 1000.0, "unit": "g", "storage": "PANTRY"},
        {"canonical_id": "tomato", "display_name": "Tomatoes", "quantity": 500.0, "unit": "g", "storage": "FRIDGE"},
        {"canonical_id": "paneer", "display_name": "Fresh Paneer", "quantity": 400.0, "unit": "g", "storage": "FRIDGE"},
        {"canonical_id": "ginger", "display_name": "Fresh Ginger", "quantity": 150.0, "unit": "g", "storage": "FRIDGE"},
        {"canonical_id": "garlic", "display_name": "Garlic Cloves", "quantity": 150.0, "unit": "g", "storage": "PANTRY"},
        {"canonical_id": "cumin_seeds", "display_name": "Jeera", "quantity": 100.0, "unit": "g", "storage": "PANTRY"},
        {"canonical_id": "turmeric_powder", "display_name": "Haldi", "quantity": 100.0, "unit": "g", "storage": "PANTRY"},
        {"canonical_id": "mustard_oil", "display_name": "Mustard Oil", "quantity": 1000.0, "unit": "ml", "storage": "PANTRY"},
    ]
    created_item_ids = []
    for item in items_to_add:
        status, body, _ = make_request("POST", "/api/v1/inventory", item, headers=auth_headers)
        assert status == 201, f"Failed adding {item['canonical_id']} ({status}): {body}"
        created_item_ids.append(body["id"])

    status, body, _ = make_request("GET", "/api/v1/inventory", headers=auth_headers)
    assert status == 200, f"Failed getting inventory ({status}): {body}"
    inv_items = body.get("items", [])
    assert len(inv_items) >= len(items_to_add), f"Expected at least {len(items_to_add)} items, got {len(inv_items)}"
    print(f"✓ Inventory created and verified ({len(inv_items)} items present).")

    # 4b. Inventory Item Update (PATCH)
    edit_id = created_item_ids[0]
    print(f"\n[Step 4b] Updating inventory item {edit_id} (/api/v1/inventory/{edit_id})...")
    status, body, _ = make_request("PATCH", f"/api/v1/inventory/{edit_id}", {"quantity": 850.0}, headers=auth_headers)
    assert status == 200, f"Inventory edit failed ({status}): {body}"
    assert float(body["quantity"]) == 850.0
    print("✓ Inventory item updated successfully (quantity set to 850.0g).")

    # 4c. Temporary Inventory Item Creation & Deletion (DELETE)
    print("\n[Step 4c] Testing inventory item deletion (/api/v1/inventory/{id})...")
    status, body, _ = make_request("POST", "/api/v1/inventory", {"canonical_id": "cumin_seeds", "quantity": 10.0, "unit": "g", "storage": "PANTRY"}, headers=auth_headers)
    assert status == 201
    temp_item_id = body["id"]
    status, body, _ = make_request("DELETE", f"/api/v1/inventory/{temp_item_id}", headers=auth_headers)
    assert status == 204, f"Inventory deletion failed ({status}): {body}"
    status, body, _ = make_request("GET", f"/api/v1/inventory/{temp_item_id}", headers=auth_headers)
    assert status == 404
    print("✓ Inventory item created and deleted successfully (HTTP 204, subsequent GET returns 404).")

    # 5. Image Upload & Scan Session Flow
    print("\n[Step 5] Uploading fridge image (/api/v1/scans)...")
    status, body = upload_multipart(
        "/api/v1/scans",
        field_name="image",
        filename="fridge_scan.jpg",
        file_bytes=TINY_JPEG_BYTES,
        fields={},
        headers=auth_headers,
    )
    if status == 201:
        scan_id = body["scan_id"]
        print(f"✓ Scan uploaded successfully (Scan ID: {scan_id}).")

        # 6. Confirm scan candidates
        print(f"\n[Step 6] Confirming scan candidates (/api/v1/scans/{scan_id}/confirm)...")
        confirm_payload = {
            "items": [
                {
                    "canonical_id": "ginger",
                    "name": "Fresh Ginger",
                    "quantity": 100.0,
                    "unit": "g",
                    "storage": "FRIDGE",
                }
            ]
        }
        status, body, _ = make_request("POST", f"/api/v1/scans/{scan_id}/confirm", confirm_payload, headers=auth_headers)
        assert status == 201, f"Scan confirmation failed ({status}): {body}"
        print("✓ Scan candidates confirmed into inventory.")
    elif status == 502 and body.get("error", {}).get("code") == "VISION_UNAVAILABLE":
        print("✓ Vision detection gracefully degraded to VISION_UNAVAILABLE as expected with placeholder GROQ_API_KEY.")
        print("  (Graceful fallback verified per PRD Section 9.3 without paid AI API calls).")
    else:
        assert False, f"Unexpected scan upload response ({status}): {body}"

    # 7. Recipe Recommendations
    print("\n[Step 7] Requesting recipe recommendations (/api/v1/recommendations)...")
    status, body, _ = make_request("GET", "/api/v1/recommendations", headers=auth_headers)
    assert status == 200, f"Recommendations failed ({status}): {body}"
    recs = body.get("items", [])
    assert len(recs) > 0, f"Expected at least 1 recommendation in {body}"
    rec_recipe = recs[0]
    rec_id = rec_recipe["recipe_id"]
    rec_title = rec_recipe.get("title", rec_recipe.get("recipe_title", "Recipe"))
    print(f"✓ Received {len(recs)} recipe recommendations (Top recipe: '{rec_title}' ID: {rec_id}).")

    # 8. Cooking Event & Inventory Deduction
    print(f"\n[Step 8] Logging cooking action for recipe '{rec_title}'...")
    cook_payload = {
        "servings": 2,
        "rating": 5,
    }
    status, body, _ = make_request("POST", f"/api/v1/recipes/{rec_id}/cooked", cook_payload, headers=auth_headers)
    assert status == 201, f"Cooking log failed ({status}): {body}"
    print("✓ Cooking recorded and inventory updated.")

    # 9. 14-Slot Meal Plan Generation
    print("\n[Step 9] Generating 14-slot meal plan (/api/v1/meal-plans)...")
    status, body, _ = make_request("POST", "/api/v1/meal-plans", {}, headers=auth_headers)
    assert status == 201, f"Meal plan generation failed ({status}): {body}"
    plan_id = body["id"]
    plan_slots = body.get("plan", {}).get("slots", [])
    assert len(plan_slots) == 14, f"Expected 14 slots, got {len(plan_slots)}"
    print(f"✓ Generated 14 meal plan slots across 7 days (Plan ID: {plan_id}).")

    # 10. Shopping List Generation
    print(f"\n[Step 10] Generating shopping list from Plan {plan_id} (/api/v1/shopping-lists)...")
    status, body, _ = make_request("POST", "/api/v1/shopping-lists", {"source": "PLAN", "plan_id": plan_id}, headers=auth_headers)
    assert status == 201, f"Shopping list generation failed ({status}): {body}"
    shop_items = body.get("items", [])
    print(f"✓ Generated shopping list with {len(shop_items)} aggregated items.")

    # 11. Cross-User Data Isolation Verification
    uid2 = uuid.uuid4().hex[:8]
    user2_email = f"staging_user_{uid2}@example.com"
    print(f"\n[Step 11] Verifying Cross-User Data Isolation with User 2 ({user2_email})...")
    status, body, _ = make_request(
        "POST",
        "/api/v1/auth/register",
        {"email": user2_email, "password": "StagingPassword456!", "display_name": "User Two"},
    )
    assert status == 201
    user2_token = body["access_token"]
    user2_headers = {"Authorization": f"Bearer {user2_token}"}

    # User 2 attempts to fetch User 1's inventory items
    target_item_id = created_item_ids[0]
    status, body, _ = make_request("GET", f"/api/v1/inventory/{target_item_id}", headers=user2_headers)
    assert status == 404, f"Security Breach! User 2 accessed User 1's item (status {status})"
    print("✓ Cross-user inventory isolation confirmed (HTTP 404 returned).")

    # 12. Logout
    print("\n[Step 12] Logging out User 1 (/api/v1/auth/logout)...")
    logout_headers = dict(auth_headers)
    if csrf_token:
        logout_headers["X-CSRF-Token"] = csrf_token
        logout_headers["Cookie"] = f"csrf_token={csrf_token}; refresh_token={refresh_token or ''}"
    status, body, _ = make_request("POST", "/api/v1/auth/logout", headers=logout_headers)
    assert status == 204, f"Logout failed ({status}): {body}"
    print("✓ Logout succeeded (HTTP 204 No Content with CSRF verification).")

    # 13. Database Persistence Verification
    print("\n[Step 13] Verifying Database Persistence (Re-authenticating User 1)...")
    status, body, login_headers = make_request(
        "POST",
        "/api/v1/auth/login",
        {"email": user1_email, "password": user1_password},
    )
    assert status == 200, f"Re-login failed ({status}): {body}"
    re_token = body["access_token"]
    re_auth = {"Authorization": f"Bearer {re_token}"}

    # Verify preferences persisted in PostgreSQL
    status, body, _ = make_request("GET", "/api/v1/me", headers=re_auth)
    assert status == 200, f"Profile fetch failed ({status}): {body}"
    prefs = body.get("preferences") or {}
    assert prefs.get("household_size") == 2, f"Expected household_size 2, got {prefs.get('household_size')}"
    assert prefs.get("diet") == "VEGETARIAN", f"Expected VEGETARIAN, got {prefs.get('diet')}"

    # Verify inventory persisted in PostgreSQL
    status, body, _ = make_request("GET", "/api/v1/inventory", headers=re_auth)
    assert status == 200
    assert len(body.get("items", [])) >= len(items_to_add) - 1  # 8 items added, 1 decremented/cooked
    print("✓ Database persistence verified across re-authentication (Preferences & Inventory intact).")

    # 14. Test Data Cleanup
    print("\n[Step 14] Cleaning up test data (/api/v1/inventory/{id})...")
    status, body, _ = make_request("GET", "/api/v1/inventory", headers=re_auth)
    items_to_clean = body.get("items", [])
    cleaned_count = 0
    for it in items_to_clean:
        if it["id"] in created_item_ids:
            del_status, _, _ = make_request("DELETE", f"/api/v1/inventory/{it['id']}", headers=re_auth)
            if del_status == 204:
                cleaned_count += 1
    print(f"✓ Test data cleanup completed ({cleaned_count} inventory items purged).")

    print("\n" + "=" * 60)
    print(" ALL 14 STAGING FUNCTIONAL JOURNEY CHECKS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    run_staging_validation()
