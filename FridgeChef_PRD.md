# FridgeChef AI — Product Requirements Document

Version: 1.0
Status: Ready for implementation
Target implementer: AI coding agent
LLM provider: Groq (OpenAI-compatible API, key in `GROQ_API_KEY`)

---

## 1. Purpose

FridgeChef AI helps households in India reduce food waste. A user photographs their fridge or pantry. The system identifies the ingredients, asks the user to confirm them, tracks how long each item stays usable, and recommends recipes and a weekly meal plan that use the items closest to expiry first. It then produces a shopping list containing only what is missing.

The product is a mobile-first web application (installable as a PWA) backed by a REST API.

## 2. Problem Statement

Households waste a large share of purchased produce because they lose track of what they have and when it will spoil. Existing recipe apps suggest what to cook without considering what is about to expire, and they assume perfect ingredient knowledge. FridgeChef closes that gap with three principles:

1. AI proposes, the user confirms. Vision output is never written to inventory without user confirmation.
2. Expiry is computed by deterministic rules, not by the language model.
3. Recipe ranking is deterministic and explainable. The language model supplies recipe candidates, not the final ranking.

## 3. Goals and Non-Goals

### 3.1 Goals (MVP)

- G1. Detect ingredients from a single fridge or pantry photo with at least 80% precision on the 30 most common Indian household ingredients (measured on the evaluation set in Section 14).
- G2. Let the user confirm, correct, add, or remove detected items in under 60 seconds for a typical fridge (15 items).
- G3. Track an estimated remaining-life value per inventory item and classify each as USE_FIRST, USE_SOON, or SAFE.
- G4. Recommend at least 5 recipes ranked by the waste-prevention score, with each recommendation listing the expiring items it uses.
- G5. Generate a 7-day meal plan that uses expiring items first and reuses ingredients across meals.
- G6. Produce a shopping list containing only missing ingredients, grouped by aisle category.
- G7. Work on Android Chrome and iOS Safari at 360px width and up.
- G8. Keep the Groq API key on the server only.

### 3.2 Non-Goals (MVP)

- Grocery store integrations, price comparison, or ordering.
- Gram-accurate weighing from a photo. Quantities are estimates confirmed by the user.
- Barcode scanning.
- Nutrition calculated per gram from a food database. Nutrition values are estimates per serving and are labelled as such.
- Native iOS or Android apps. The PWA covers mobile use.
- Multi-household sharing.
- Payments.

## 4. Users and Personas

- Primary: Urban Indian household cook (25–50), cooks most meals at home, uses a smartphone, wants less waste and less planning effort.
- Secondary: Working professional living alone, buys produce in small quantities and throws out what spoils.
- Tertiary: Family cook managing for 3–6 people with budget constraints.

## 5. Core User Flows

### 5.1 First-time onboarding
1. User opens the app and registers with email, password, and display name.
2. Onboarding asks: household size (1–10), diet (Vegetarian, Eggless, Non-vegetarian, Vegan), spice level (Mild, Medium, Hot), preferred cuisines (multi-select: North Indian, South Indian, Gujarati, Bengali, Maharashtrian, Punjabi, Continental, Quick meals), maximum cooking time (15, 30, 45, 60 minutes), allergies (free text, mapped to canonical ingredients where possible).
3. The user lands on the dashboard.

### 5.2 Scan and confirm
1. User taps "Scan fridge" and takes a photo or chooses one from the gallery.
2. Client compresses the image to at most 1600 px on the long edge and sends it to the API.
3. The API validates the file, strips EXIF metadata, calls the vision model, and returns candidate items.
4. The verification screen lists each candidate with: name, detected quantity, unit, confidence label (High, Medium, Low), and a thumbnail crop if available.
5. Items with Low confidence are pre-unchecked. The user can check, uncheck, edit name (with autocomplete from the canonical ingredient list), edit quantity, edit storage location (Fridge, Freezer, Pantry, Counter), and add items manually.
6. User taps "Save to inventory". Confirmed items are written to inventory with an added date, storage location, and freshness estimate.

### 5.3 Inventory and freshness
1. Inventory screen groups items by status: USE_FIRST (red), USE_SOON (amber), SAFE (green).
2. Each item shows name, quantity, unit, storage, and "about N days left".
3. User can mark an item as used (quantity decremented), wasted (logged to waste log), or delete it.
4. User can edit the added date or opened date, which recalculates freshness.

### 5.4 Recipe recommendations
1. Dashboard shows the top 5 recipes ranked by waste-prevention score.
2. Each card shows: title, cuisine, cooking time, servings, match percentage, expiring items used (with status badges), missing ingredients (count and names), and estimated cost of missing items.
3. Tapping a card opens the full recipe: ingredients with quantities scaled to household size, numbered steps, nutrition per serving (labelled estimate), and a "Cooked this" button.
4. "Cooked this" decrements the used inventory quantities and records a cooking event. The user can rate the recipe 1–5.

### 5.5 Weekly meal plan
1. User taps "Plan my week". The system generates 7 days × 2 meals (lunch and dinner) respecting diet, cooking time, and cuisine preferences.
2. Plan view shows each day, each meal, prioritised ingredients per meal, and an overall "expected waste prevented" count.
3. User can regenerate a single meal slot, which keeps the rest of the plan fixed.
4. Plan shows the consolidated shopping list for all planned meals.

### 5.6 Shopping list
1. List contains only ingredients required by selected recipes or the meal plan that are not in inventory (or not in sufficient quantity).
2. Items are grouped by category: Vegetables, Fruits, Dairy and Eggs, Proteins, Grains and Pulses, Spices, Oils and Condiments, Other.
3. User can tick items as bought. Ticking an item offers to add it to inventory.

### 5.7 Waste and impact summary
1. Dashboard shows: items saved from expiry this month, items wasted this month, estimated waste prevented in kg (from the per-item weight table), and estimated money saved (from the per-item price table).
2. Figures are labelled as estimates.

## 6. Functional Requirements

Priority: P0 = MVP required, P1 = next release.

### 6.1 Authentication and accounts
- FR-001 (P0): Register with email, password (minimum 8 characters, at least one letter and one digit), and display name. Email must be unique, case-insensitive.
- FR-002 (P0): Login returns a JWT access token (expires in 60 minutes) and a refresh token (expires in 30 days, rotated on each use).
- FR-003 (P0): Passwords are hashed with bcrypt (cost factor 12) or argon2. Plain text is never stored or logged.
- FR-004 (P0): Logout revokes the refresh token.
- FR-005 (P0): Users can only read and modify their own data. Every query is scoped by the authenticated user ID.
- FR-006 (P1): Password reset by email link.

### 6.2 Preferences
- FR-010 (P0): Store and update household size, diet, spice level, cuisines, max cooking time, and allergies.
- FR-011 (P0): Allergies and avoided ingredients are excluded from all recipes and meal plans. Excluded ingredients are matched using canonical IDs and their aliases.

### 6.3 Fridge scanning
- FR-020 (P0): Accept JPEG, PNG, WEBP, and HEIC images up to 8 MB. Reject other types with HTTP 415. Reject files over the limit with HTTP 413.
- FR-021 (P0): Verify the file is a real image by decoding it with Pillow. Reject files that fail decoding with HTTP 422.
- FR-022 (P0): Strip EXIF metadata (including GPS) before storing or sending the image anywhere.
- FR-023 (P0): Resize to at most 1600 px on the long edge and re-encode as JPEG quality 85. The resized copy is what is sent to Groq. Keep it under 4 MB.
- FR-024 (P0): Send the image to the Groq vision model (Section 9.2) and require a JSON response matching the schema in Section 9.3.
- FR-025 (P0): Map each returned ingredient name to a canonical ingredient ID using the alias table (Section 8.4). Unmapped names are returned with `canonical_id: null` and the user must choose a canonical item before saving.
- FR-026 (P0): Return candidate items with a scan ID. Candidates expire after 30 minutes and are stored temporarily in the database table `scan_sessions`.
- FR-027 (P0): Do not write detected items into inventory until the user confirms them through the verify endpoint.
- FR-028 (P0): Delete the stored original image within 24 hours. Store only the resized copy used for detection, and delete it when the scan session expires.
- FR-029 (P0): If the vision call fails or returns invalid JSON after one retry, return HTTP 502 with error code `VISION_UNAVAILABLE` and a message that the user can add items manually.

### 6.4 Inventory
- FR-030 (P0): CRUD operations on inventory items. Each item stores canonical ingredient ID, display name, quantity, unit, storage location, added date, opened date (optional), and status fields computed on read.
- FR-031 (P0): Freshness estimate is computed by the freshness engine (Section 8.1) and stored as `shelf_life_days_estimate` and `expires_on` when the item is created or edited. It is recalculated on read so that the "days left" value is always current.
- FR-032 (P0): Mark as used (reduces quantity; if zero, item is archived), mark as wasted (archives item and writes a waste log entry), or delete.
- FR-033 (P0): Quantity units are normalised to base units: `g`, `ml`, or `piece`. Unit conversions are defined in Section 8.5.
- FR-034 (P0): Inventory list endpoint supports filtering by status and storage location, and sorting by expiry.

### 6.5 Recipes
- FR-040 (P0): The recipe catalogue contains at least 150 curated Indian recipes stored in `data/recipes.json` and loaded into the database at startup (idempotent upsert). Schema is defined in Section 8.3.
- FR-041 (P0): Recipe recommendation combines curated recipes with AI-generated recipes (Section 9.4) when fewer than 5 curated recipes score at or above 40% match.
- FR-042 (P0): AI-generated recipes must pass schema validation and canonical ingredient mapping. Generated recipes that use only unmapped ingredients are discarded.
- FR-043 (P0): Ranking uses the scoring function in Section 8.2. Ranking is deterministic for the same inputs.
- FR-044 (P0): Each recommendation response includes: recipe ID, title, cuisine, cooking time, scaled servings, match percentage, used expiring items with status, missing ingredients with estimated cost, and a plain-language reason string built from templates (no LLM).
- FR-045 (P0): Recipe responses exclude any recipe containing an allergen or avoided ingredient, and any recipe that violates the diet setting (for example, non-vegetarian recipes for a vegetarian user).
- FR-046 (P0): Recommendations are cached per user for 30 minutes, keyed by a hash of (canonical inventory IDs with quantities, preference version). Cache is invalidated on any inventory or preference change.
- FR-047 (P1): Users can save favourite recipes and add custom recipes.

### 6.6 Meal planning
- FR-050 (P0): Generate a plan for 7 days, 2 meals per day, with a configurable start date (default: today).
- FR-051 (P0): Planner algorithm is in Section 8.6. It must not schedule the same recipe more than twice in 7 days.
- FR-052 (P0): Planner uses the inventory snapshot at generation time and tracks quantity consumption across days. Items not in inventory are added to the shopping list.
- FR-053 (P0): Regenerating a single slot keeps all other slots unchanged.
- FR-054 (P0): Plan is stored and retrievable by ID. A user can have one active plan at a time; generating a new plan archives the previous one.

### 6.7 Shopping list
- FR-060 (P0): Shopping list can be generated from (a) a meal plan, (b) a set of selected recipes, or (c) manual items.
- FR-061 (P0): Items are aggregated by canonical ID, quantities summed in base units, and grouped by category.
- FR-062 (P0): Marking an item as bought updates its state. Optionally adds it to inventory with the purchased quantity.

### 6.8 Dashboard and impact
- FR-070 (P0): Dashboard endpoint returns counts by freshness status, top 5 recommendations, current plan summary, and month-to-date impact figures.
- FR-071 (P0): Impact figures are computed from the waste log and cooking events, using the price and weight tables. Labelled as estimates in the response (`"is_estimate": true`).

### 6.9 Feedback
- FR-080 (P1): Thumbs up/down on recommendations and meal plan slots. Stored and used to adjust preference match weight for that recipe for the user (bounded, see Section 8.2).

## 7. Non-Functional Requirements

### 7.1 Performance
- NFR-001: P95 latency for non-AI endpoints under 300 ms at 100 concurrent users.
- NFR-002: Scan endpoint returns within 15 seconds P95 including the Groq call. Client shows a progress state with the message "Looking at your fridge…".
- NFR-003: Recipe recommendation returns within 2 seconds P95 when cached and 8 seconds P95 when AI generation is needed.
- NFR-004: Meal plan generation returns within 10 seconds P95.

### 7.2 Reliability
- NFR-010: Groq calls use a 20-second timeout and up to 2 retries with exponential backoff (1 s, 3 s) on HTTP 429, 500, 502, 503, and 504 and on network errors.
- NFR-011: If Groq is unavailable, recipe recommendations fall back to curated recipes only and set `"degraded": true` in the response. Scanning falls back to manual entry.
- NFR-012: All writes that touch multiple rows run in a single database transaction.

### 7.3 Security
- NFR-020: Groq API key is read from the environment only. It must never be sent to the client, logged, or committed. The application fails to start if it is missing.
- NFR-021: All endpoints except register, login, refresh, and health require a valid access token.
- NFR-022: Rate limits per user: 20 scans per day, 60 recommendation requests per hour, 200 other requests per minute. Implemented with a sliding window; exceeding returns HTTP 429 with `Retry-After`.
- NFR-023: Login rate limit: 10 attempts per 15 minutes per email and per IP.
- NFR-024: All traffic is HTTPS in production. HSTS enabled.
- NFR-025: CORS allows only origins in `CORS_ORIGINS`.
- NFR-026: Input validation on all request bodies with Pydantic v2. Unknown fields are rejected.
- NFR-027: SQL is generated through SQLAlchemy ORM parameters only. No string-built queries.
- NFR-028: Uploaded images are stored outside the web root and are never served publicly. Access is by scan ID through an authenticated endpoint, and only until the scan session expires.

### 7.4 Privacy
- NFR-030: Users can export their data as JSON (`GET /api/me/export`) and delete their account (`DELETE /api/me`). Deletion removes all personal data within 30 days and all images immediately.
- NFR-031: Images sent to Groq are not retained by the application after the scan session ends. The privacy policy must state that images are processed by Groq as a third-party processor.
- NFR-032: Logs must not contain passwords, tokens, image bytes, or full email addresses (mask as `a***@domain`).

### 7.5 Observability
- NFR-040: Structured JSON logs with request ID, user ID (hashed), endpoint, status, latency, and error code.
- NFR-041: Record Groq token usage (prompt and completion tokens), model name, and latency per call in a `llm_calls` table for cost monitoring.
- NFR-042: `/api/health` returns liveness. `/api/health/ready` checks database connectivity and that the configured Groq model IDs are present in the Groq model list (checked once at startup and cached for 1 hour).

### 7.6 Accessibility and UX
- NFR-050: WCAG 2.1 AA colour contrast. Status is never conveyed by colour alone; each status also has a text label and icon.
- NFR-051: Touch targets at least 44×44 px.
- NFR-052: All flows work with the phone keyboard and screen reader labels on interactive controls.
- NFR-053: UI supports English at launch. Strings are externalised for later Hindi support.

### 7.7 Portability
- NFR-060: Backend runs on Python 3.11 and 3.12 on Linux, macOS, and Windows (via Docker or native).
- NFR-061: Frontend builds to static files served by any static host or nginx.

## 8. Domain Logic and Algorithms

### 8.1 Freshness engine (deterministic)

Data source: `data/shelf_life.json`, one entry per canonical ingredient with shelf life in days for each storage location, plus a `opened_shelf_life_days` value where applicable (null if not applicable).

Remaining life for an item:

```
base_life      = shelf_life[canonical_id][storage]   # days
reference_date = opened_date if opened_date is set else added_date
age_days       = floor((today - reference_date).days)
life_used      = age_days
days_left      = max(0, base_life - life_used)
```

If `opened_date` is set and `opened_shelf_life_days` is not null, use it as `base_life` with `reference_date = opened_date`.

Status:
- USE_FIRST: days_left ≤ 1
- USE_SOON: 2 ≤ days_left ≤ 3
- SAFE: days_left ≥ 4

Items with base_life of 0 or null (not applicable for that storage) are rejected at creation with a validation error asking the user to pick a different storage location.

Items with very long shelf life (for example rice, lentils) have days_left above 365; these are displayed as "over a year".

### 8.2 Recipe scoring (deterministic)

For a user with inventory `I` and recipe `R` (with ingredient list `R.ingredients`, each with canonical ID, base quantity, and `is_optional` flag):

Let `required` be the set of non-optional ingredients in R and `matched` the subset present in inventory with positive quantity.

Components, each in [0, 1]:

- `coverage` = |matched| / |required|  (1.0 if required is empty)
- `urgency` = mean over matched ingredients of `u(i)`, where `u(i) = max(0, 1 - days_left(i) / 7)`. A USE_FIRST item has `u` close to 1; a SAFE item with 7+ days has `u = 0`. If no matched ingredients, `urgency = 0`.
- `quantity_fit` = mean over matched ingredients of `min(1, inventory_qty / recipe_qty)`, scaled by household size. This rewards recipes that use the stock without exceeding it.
- `preference` = 1.0 if cuisine is in the user's preferred cuisines, else 0.5; multiplied by spice match (1.0 exact, 0.7 adjacent, 0.4 otherwise). Result in [0, 1].
- `time_fit` = 1.0 if cooking_time ≤ max_cooking_time, linearly decreasing to 0.0 at 2× max_cooking_time.

Final score:

```
score = 0.35 * coverage
      + 0.35 * urgency
      + 0.10 * quantity_fit
      + 0.10 * preference
      + 0.10 * time_fit
```

Match percentage shown to the user = `round(100 * coverage)`.

Hard filters (recipe excluded, not scored):
- Contains an allergen or avoided ingredient.
- Violates diet.
- Cooking time exceeds 2× max_cooking_time.
- coverage < 0.4 (too many missing ingredients to be useful).

Tie-breaking: higher coverage, then shorter cooking time, then recipe ID alphabetically.

Feedback adjustment (P1): preference component is adjusted by `+0.1` for a thumbs-up on the same recipe in the last 90 days and `-0.2` for a thumbs-down, clamped to [0, 1].

### 8.3 Recipe schema (`data/recipes.json`)

```json
{
  "id": "aloo-palak",
  "title": "Aloo Palak",
  "cuisine": "North Indian",
  "diet": "VEGETARIAN",
  "spice_level": "MEDIUM",
  "cooking_time_minutes": 25,
  "base_servings": 2,
  "ingredients": [
    {"canonical_id": "potato", "qty": 300, "unit": "g", "is_optional": false},
    {"canonical_id": "spinach", "qty": 200, "unit": "g", "is_optional": false},
    {"canonical_id": "onion", "qty": 1, "unit": "piece", "is_optional": false},
    {"canonical_id": "tomato", "qty": 1, "unit": "piece", "is_optional": true},
    {"canonical_id": "garlic", "qty": 3, "unit": "piece", "is_optional": false}
  ],
  "steps": ["Boil and cube the potatoes.", "..."],
  "nutrition_per_serving_estimate": {"kcal": 210, "protein_g": 7, "carbs_g": 32, "fat_g": 6, "fiber_g": 6},
  "tags": ["quick", "high-fibre"]
}
```

Rules:
- `canonical_id` must exist in the ingredient catalogue (Section 8.4), enforced by a validation script run in CI.
- The seed file must contain at least 150 recipes, with at least 25 for each of: vegetarian North Indian, vegetarian South Indian, and eggless or non-vegetarian options for each cuisine family.
- Each recipe has at least 3 steps and at most 12.
- `nutrition_per_serving_estimate` values are estimates and must be labelled as such in the UI.

### 8.4 Ingredient catalogue and alias mapping

`data/ingredients.json` stores canonical ingredients:

```json
{
  "id": "capsicum",
  "display_name": "Capsicum (Bell Pepper)",
  "category": "Vegetables",
  "aliases": ["capsicum", "bell pepper", "shimla mirch", "green pepper", "sweet pepper"],
  "default_unit": "piece",
  "grams_per_piece": 150,
  "price_inr_per_kg": 120,
  "allergen_group": null
}
```

Requirements:
- At least 200 canonical ingredients covering vegetables, fruits, dairy and eggs, proteins, grains and pulses, spices, and oils and condiments common in Indian households.
- Aliases include Hindi and common regional names (for example: `lady finger`, `bhindi`, `okra`; `coriander leaves`, `dhania`, `cilantro`; `curd`, `dahi`, `yogurt`).
- Alias matching is case-insensitive and ignores punctuation and plural `s`.
- Vision output names are matched against aliases first, then fuzzy-matched (Levenshtein distance ≤ 2 on names of 5+ characters). Otherwise `canonical_id` is null.

### 8.5 Unit conversion

Base units: `g`, `ml`, `piece`. Conversions use `grams_per_piece` and `ml_per_piece` from the catalogue. Examples: 1 cup = 240 ml; 1 bunch of spinach = 200 g; 1 tbsp = 15 ml. Conversions that cannot be done (for example, grams to pieces for an ingredient with no `grams_per_piece`) return a validation error rather than guessing.

### 8.6 Meal planner

Input: inventory snapshot, preferences, start date, optional locked slots.

Algorithm (greedy with lookahead, deterministic):

1. Build candidate set: all recipes passing hard filters from 8.2 against the snapshot.
2. For each slot in order (day 1 lunch, day 1 dinner, day 2 lunch, …):
   a. Score each candidate against the current simulated inventory using 8.2.
   b. Exclude any recipe already scheduled twice in the plan.
   c. Exclude a recipe scheduled on the previous slot.
   d. Pick the highest-scoring candidate. Subtract its required quantities from the simulated inventory (floored at 0).
3. After all slots are filled, compute the shopping gap: for each ingredient required by the plan, `max(0, total_required - original_inventory)`.
4. Output per slot: recipe, prioritised ingredients (those with USE_FIRST or USE_SOON status), and estimated waste prevented (sum of quantities of USE_FIRST items consumed).

If fewer than 14 candidates pass the filters, the planner allows any recipe to repeat once and marks the plan with `"low_variety": true`.

### 8.7 Shopping list generation

Inputs: list of recipe IDs with scale factors, or a meal plan, or manual items. Steps:
1. Sum required quantities per canonical ID in base units.
2. Subtract inventory quantities (floored at 0).
3. Drop items where the remainder is 0.
4. Group by category and sort alphabetically within group.
5. Attach estimated cost using `price_inr_per_kg` for `g`, and `grams_per_piece` × price for `piece`.

### 8.8 Impact estimates

- Waste prevented (kg) = sum over "used before expiry" events of quantity converted to grams.
- Wasted (kg) = sum over "wasted" log entries converted to grams.
- Money saved (INR) = sum over "used before expiry" events of estimated cost. Wasted items are not subtracted from savings; they are reported separately.
- All values carry `"is_estimate": true`.

## 9. AI Integration (Groq)

### 9.1 Provider configuration

- SDK: `groq` Python package (official). Equivalent OpenAI-compatible base URL `https://api.groq.com/openai/v1` is acceptable.
- Environment variables:
  - `GROQ_API_KEY` (required)
  - `GROQ_VISION_MODEL` (default: `meta-llama/llama-4-scout-17b-16e-instruct`)
  - `GROQ_TEXT_MODEL` (default: `llama-3.3-70b-versatile`)
  - `GROQ_TIMEOUT_SECONDS` (default: 20)
  - `GROQ_MAX_RETRIES` (default: 2)
- At startup, the application calls the Groq models list endpoint, confirms both configured model IDs exist and are active, and logs a clear error if not. The agent must verify current model IDs against Groq's model list before the first deployment, since model availability changes.
- All calls set `temperature` to 0.1 for vision and 0.4 for recipe generation, and `max_completion_tokens` explicitly (vision: 1200, recipe generation: 3000).
- JSON responses use `response_format={"type": "json_object"}`. The prompt must contain the word "JSON" and the exact schema.

### 9.2 Vision call

Message structure: a system message defining the task and rules; a user message containing the image as a base64 data URL in an `image_url` content part and a text part with the instruction.

Rules included in the system prompt:
- List only food items and beverages visible inside the fridge, freezer, pantry, or counter.
- Do not guess items that are hidden or not visible. Set confidence accordingly.
- Use common Indian English names when applicable (for example, "bhindi" or "lady finger" as shown on the item; use "okra" if unsure).
- Report counts for countable items. For bulk items (rice, flour, sugar, oil) report `"piece": null` and use `"unit": "container"` with `"quantity": null`.
- Never include people, pets, brands, or text unrelated to food.
- Return only JSON matching the schema.

### 9.3 Vision response schema

```json
{
  "items": [
    {
      "name": "string",
      "quantity": "number or null",
      "unit": "piece | bunch | packet | container | bottle | g | ml | unknown",
      "storage_guess": "FRIDGE | FREEZER | PANTRY | COUNTER | UNKNOWN",
      "confidence": "HIGH | MEDIUM | LOW",
      "visible_note": "string, max 80 characters"
    }
  ],
  "image_quality": "GOOD | POOR",
  "image_quality_note": "string or null"
}
```

Server-side validation:
- Reject responses that do not parse or do not match the schema. Retry once with a repair instruction that includes the validation error. If the second attempt fails, return `VISION_UNAVAILABLE`.
- Cap items at 60. Discard items with empty names.
- Map `confidence` to a numeric value (HIGH = 0.9, MEDIUM = 0.6, LOW = 0.3) for display ordering only. The model's confidence is treated as a hint; every item is still shown for user confirmation.
- If `image_quality` is POOR, show the user a message to retake the photo with better lighting, and still show candidates.

### 9.4 Recipe generation call

Used only when curated recipes are insufficient (FR-041).

Input to the model: list of available canonical ingredient names with quantities and status (USE_FIRST, USE_SOON, SAFE), user diet, allergies, spice level, cuisines, max cooking time, and the number of recipes requested (default 5).

Requirements in the prompt:
- Use only the provided ingredients plus common pantry staples (salt, water, oil, basic whole spices, and onion, garlic, ginger, tomato, green chilli) listed explicitly.
- Prefer recipes that use the USE_FIRST items.
- Output recipes in the schema of Section 8.3, with `canonical_id` values chosen only from the provided catalogue list (the full catalogue ID list is included in the prompt).
- Output only JSON.

Post-processing:
- Validate against the recipe schema.
- Discard recipes with unknown canonical IDs (do not attempt to repair).
- Discard recipes that break diet or allergy rules (double-check server-side).
- Store accepted recipes in the database with `source = "AI"` and `status = "PENDING_REVIEW"`. They can be recommended to the requesting user immediately, but are excluded from the shared catalogue until reviewed.
- Cache the call result per (inventory hash, preferences hash) for 30 minutes.

### 9.5 Prompt and output versioning

Each prompt template has a version string (for example `vision.v1`, `recipes.v1`) stored with `llm_calls` records so that output changes can be traced.

### 9.6 Cost control

- Vision: 1 call per scan. Maximum 20 scans per user per day (NFR-022).
- Recipe generation: at most 1 call per user per 30 minutes (cache-backed).
- Meal plan generation uses no LLM calls. It runs entirely on curated and accepted recipes.
- Monthly spend alert threshold configurable via `LLM_MONTHLY_BUDGET_USD`; when 80% is reached, disable AI recipe generation and log a warning.

## 10. Data Model

All tables have `id` (UUID), `created_at`, `updated_at`. Foreign keys use `ON DELETE CASCADE` where the child belongs to a user.

- `users`: id, email (unique, lowercase), password_hash, display_name, created_at, deleted_at.
- `user_preferences`: user_id (PK, FK), household_size (1–10), diet (enum), spice_level (enum), cuisines (array of string), max_cooking_time (int), allergies (array of canonical IDs), avoided_ingredients (array of canonical IDs), version (int, incremented on change).
- `refresh_tokens`: id, user_id, token_hash, expires_at, revoked_at.
- `ingredients`: id (canonical ID, PK), display_name, category, aliases (array), default_unit, grams_per_piece, ml_per_piece, price_inr_per_kg, allergen_group.
- `shelf_life`: ingredient_id (FK), storage (enum), days (int or null), opened_days (int or null). Unique on (ingredient_id, storage).
- `recipes`: id (slug PK), title, cuisine, diet, spice_level, cooking_time_minutes, base_servings, steps (JSON), nutrition (JSON), tags (array), source (CURATED | AI), status (APPROVED | PENDING_REVIEW), created_by_user_id (nullable).
- `recipe_ingredients`: recipe_id (FK), ingredient_id (FK), qty (decimal), unit (enum), is_optional (bool). Unique on (recipe_id, ingredient_id).
- `inventory_items`: id, user_id (FK), ingredient_id (FK, nullable only for custom items if P1), display_name, quantity (decimal ≥ 0), unit (enum), storage (enum), added_on (date), opened_on (date, nullable), archived_at (nullable).
- `scan_sessions`: id, user_id (FK), status (PENDING_VERIFY | CONFIRMED | EXPIRED), image_path (nullable, deleted after expiry), candidates (JSON), image_quality, created_at, expires_at.
- `waste_log`: id, user_id (FK), inventory_item_id (nullable), ingredient_id, quantity, unit, action (USED_BEFORE_EXPIRY | WASTED), estimated_value_inr, created_at.
- `cooking_events`: id, user_id (FK), recipe_id (FK), servings, rating (1–5, nullable), created_at.
- `meal_plans`: id, user_id (FK), start_date, status (ACTIVE | ARCHIVED), low_variety (bool), created_at, plan (JSON with slots, shopping list, impact estimate).
- `shopping_lists`: id, user_id (FK), source (PLAN | RECIPES | MANUAL), items (JSON), created_at.
- `llm_calls`: id, user_id (nullable), purpose (VISION | RECIPE_GEN), model, prompt_version, prompt_tokens, completion_tokens, latency_ms, status (OK | ERROR | RETRIED), error_code (nullable), created_at.
- `recommendation_cache`: user_id, cache_key, payload (JSON), expires_at. Primary key (user_id, cache_key).

Indexes: `inventory_items(user_id, archived_at)`, `scan_sessions(user_id, status)`, `waste_log(user_id, created_at)`, `meal_plans(user_id, status)`, `recipe_ingredients(ingredient_id)`.

Migrations via Alembic. No table creation through `create_all` in production.

## 11. API Specification

Base path: `/api/v1`. JSON everywhere except the scan upload (multipart/form-data).

Standard error envelope:

```json
{"error": {"code": "INVENTORY_ITEM_NOT_FOUND", "message": "Item not found.", "details": null, "request_id": "..."}}
```

Standard success pagination: `{"items": [...], "next_cursor": "string or null"}`.

### 11.1 Auth
- `POST /auth/register` body `{email, password, display_name}` → 201 `{user, access_token, refresh_token}`
- `POST /auth/login` body `{email, password}` → 200 same shape
- `POST /auth/refresh` body `{refresh_token}` → 200 new pair (old refresh token revoked)
- `POST /auth/logout` body `{refresh_token}` → 204

### 11.2 Account and preferences
- `GET /me` → user and preferences
- `PUT /me/preferences` body per Section 10 fields → 200
- `GET /me/export` → JSON of all user data
- `DELETE /me` body `{password}` → 202 (deletion job scheduled)

### 11.3 Catalogue (read-only)
- `GET /ingredients?query=&category=&limit=` → list with canonical IDs and aliases
- `GET /recipes/{id}` → full recipe with scaled ingredients when `servings` query param is provided

### 11.4 Scanning
- `POST /scans` multipart field `image` → 201
  ```json
  {
    "scan_id": "uuid",
    "expires_at": "iso8601",
    "image_quality": "GOOD",
    "image_quality_note": null,
    "candidates": [
      {
        "candidate_id": "uuid",
        "name": "Tomato",
        "canonical_id": "tomato",
        "quantity": 4,
        "unit": "piece",
        "storage_guess": "FRIDGE",
        "confidence": "HIGH",
        "needs_review": false,
        "visible_note": "three ripe, one green"
      }
    ]
  }
  ```
  Errors: 413 `IMAGE_TOO_LARGE`, 415 `UNSUPPORTED_MEDIA_TYPE`, 422 `IMAGE_UNREADABLE`, 429 `SCAN_LIMIT_REACHED`, 502 `VISION_UNAVAILABLE`.
- `GET /scans/{scan_id}` → scan session with candidates (only the owner)
- `POST /scans/{scan_id}/confirm` body:
  ```json
  {
    "items": [
      {"candidate_id": "uuid|null", "canonical_id": "tomato", "name": "Tomato",
       "quantity": 4, "unit": "piece", "storage": "FRIDGE", "opened_on": null}
    ]
  }
  ```
  → 201 `{"created": [inventory items], "skipped": [...]}`. Items with `canonical_id` null → 422 `CANONICAL_ID_REQUIRED`. Items whose storage has no shelf life → 422 `STORAGE_NOT_APPLICABLE`.
- `DELETE /scans/{scan_id}` → 204 (discards and deletes image)

### 11.5 Inventory
- `GET /inventory?status=USE_FIRST|USE_SOON|SAFE&storage=&sort=expiry|name|added` → list with computed `days_left` and `status`
- `POST /inventory` body `{canonical_id, quantity, unit, storage, opened_on?}` → 201
- `PATCH /inventory/{id}` body partial of quantity, storage, opened_on → 200 (recalculates freshness)
- `POST /inventory/{id}/use` body `{quantity}` → 200 (quantity reduced; logs USED_BEFORE_EXPIRY if status was USE_FIRST or USE_SOON)
- `POST /inventory/{id}/waste` body `{quantity}` → 200 (logs WASTED, archives or reduces)
- `DELETE /inventory/{id}` → 204

### 11.6 Recommendations
- `GET /recommendations?limit=5&servings=` → 200
  ```json
  {
    "degraded": false,
    "generated_at": "iso8601",
    "cache": "HIT|MISS",
    "items": [
      {
        "recipe_id": "aloo-palak",
        "title": "Aloo Palak",
        "cuisine": "North Indian",
        "cooking_time_minutes": 25,
        "servings": 2,
        "match_percent": 75,
        "source": "CURATED|AI",
        "uses_expiring": [{"canonical_id": "spinach", "status": "USE_FIRST", "days_left": 1}],
        "missing": [{"canonical_id": "garlic", "qty": 3, "unit": "piece", "est_cost_inr": 12}],
        "missing_cost_inr": 12,
        "reason": "Uses spinach expiring tomorrow; you have 3 of 4 required items."
      }
    ]
  }
  ```

### 11.7 Recipe actions
- `POST /recipes/{id}/cooked` body `{servings, rating?}` → 201. Decrements inventory by scaled quantities (floored at 0) and logs USED_BEFORE_EXPIRY for items that were USE_FIRST or USE_SOON.
- `POST /recipes/{id}/feedback` body `{vote: "UP|DOWN"}` → 204 (P1)

### 11.8 Meal plans
- `POST /meal-plans` body `{start_date?, locked_slots?: [{day, meal, recipe_id}]}` → 201 with full plan
- `GET /meal-plans/active` → 200 or 404
- `GET /meal-plans/{id}` → 200 (owner only)
- `POST /meal-plans/{id}/slots/{day}/{meal}/regenerate` → 200 updated plan
- `DELETE /meal-plans/{id}` → 204 (archives)

### 11.9 Shopping lists
- `POST /shopping-lists` body `{source: "PLAN|RECIPES|MANUAL", plan_id?, recipes?: [{recipe_id, servings}], manual_items?: [{canonical_id, qty, unit}]}` → 201
- `GET /shopping-lists/{id}` → 200
- `PATCH /shopping-lists/{id}/items/{canonical_id}` body `{bought: bool, add_to_inventory?: bool}` → 200

### 11.10 Dashboard
- `GET /dashboard` → counts by status, top 3 recommendations (from cache if warm), active plan summary, month-to-date impact with `is_estimate: true`.

### 11.11 Health
- `GET /health` → 200 `{"status": "ok"}`
- `GET /health/ready` → 200 or 503 with component checks

## 12. Frontend Specification

### 12.1 Stack
- React 18, TypeScript, Vite
- React Router v6 for routing
- TanStack Query for server state
- Tailwind CSS v3 for styling
- Zod for response validation at the API boundary
- `vite-plugin-pwa` for manifest and service worker (app shell caching only; no offline API data)
- Vitest and React Testing Library for unit and component tests
- Playwright for end-to-end tests

### 12.2 Project structure
```
web/
  index.html
  vite.config.ts
  tailwind.config.ts
  src/
    main.tsx
    app/              router, providers, layout
    api/              client, typed endpoints, zod schemas
    features/
      auth/
      onboarding/
      scan/           capture, verify list
      inventory/
      recommendations/
      recipes/
      meal-plan/
      shopping/
      dashboard/
    components/       shared UI (Button, Card, StatusBadge, Sheet, Toast)
    lib/              formatting, units, date helpers
    styles/
  public/
    icons/            192, 512, maskable icons
```

### 12.3 Screens
1. Login and Register
2. Onboarding (three steps: household and diet, cuisines and spice, allergies and time)
3. Dashboard (status counts, top 3 recipes, active plan card, impact card, primary "Scan fridge" button)
4. Scan (camera capture input with `accept="image/*" capture="environment"`, progress state, error states)
5. Verify candidates (list, checkboxes, edit sheet, add manual item, save button)
6. Inventory (tabs: All, USE_FIRST, USE_SOON, SAFE; search; per-item actions)
7. Recommendations (list with filters: cuisine, max time, diet)
8. Recipe detail (scaled ingredients with servings stepper, steps, nutrition estimate label, "Cooked this" with rating)
9. Meal plan (7-day grid, slot regenerate, lock toggle, expected waste prevented)
10. Shopping list (grouped, tick to bought, add to inventory prompt)
11. Settings (preferences, export data, delete account)

### 12.4 Responsive and mobile behaviour
- Design for 360 px width first. Bottom navigation with five items: Home, Inventory, Scan, Recipes, Plan. Shopping and Settings are reached from the top bar.
- Camera capture uses the native file input with `capture="environment"`; no custom camera stream is required for MVP.
- Install prompt shown after the second visit on Android Chrome; iOS users see a short instruction to use "Add to Home Screen".
- All forms work with the on-screen keyboard without covering the submit button (use `visualViewport`-aware sticky footers).

### 12.5 Client state and errors
- API base URL is read from `VITE_API_BASE_URL`. In development it is `http://<computer-LAN-IP>:8000/api/v1` when accessed from a phone, configured via environment, never hardcoded to localhost.
- Access token stored in memory; refresh token stored in an httpOnly cookie set by the API. (If cookie setup is not feasible in the deployment topology, store the refresh token in `sessionStorage` and document the trade-off.)
- Any 401 triggers one refresh attempt, then redirect to login.
- Every error code in Section 11 maps to a user-facing message in `src/api/errors.ts`.

### 12.6 Phone access in development
- The API binds to `0.0.0.0`. The frontend dev server runs with `vite --host`.
- The development README documents: find the computer's LAN IP, set `VITE_API_BASE_URL`, add the frontend origin to `CORS_ORIGINS`, and open `http://<LAN-IP>:5173` on the phone.
- Camera access and PWA install require HTTPS on phones. Development over plain HTTP on LAN supports browsing and manual entry; scanning from the phone camera requires the HTTPS deployment or a local HTTPS tunnel. This limitation is documented, not hidden.

## 13. Backend Specification

### 13.1 Stack
- Python 3.11+
- FastAPI, Uvicorn (or Gunicorn with Uvicorn workers in production)
- Pydantic v2, pydantic-settings
- SQLAlchemy 2.x (ORM), Alembic
- PostgreSQL 16 (production and integration tests); SQLite permitted for local unit tests only
- `groq` Python SDK
- Pillow (image validation, EXIF stripping, resizing), pillow-heif (HEIC support)
- PyJWT for tokens, passlib[bcrypt] or argon2-cffi for hashing
- slowapi or a Redis-backed limiter for rate limiting (Redis optional; in-process limiter acceptable for single instance)
- pytest, pytest-asyncio, httpx (test client), respx or pytest-mock for mocking Groq
- Ruff for linting, mypy for type checks on `app/`

### 13.2 Project structure
```
api/
  pyproject.toml
  alembic.ini
  migrations/
  data/
    ingredients.json
    shelf_life.json
    recipes.json
  app/
    main.py                 app factory, middleware, routers
    core/
      config.py             pydantic-settings
      security.py           hashing, JWT
      logging.py            structured logging, masking
      errors.py             exception classes and handlers
      ratelimit.py
    db/
      session.py
      base.py
      models/               one module per table group
    schemas/                Pydantic request/response models
    api/
      deps.py
      routes/
        auth.py
        me.py
        catalogue.py
        scans.py
        inventory.py
        recommendations.py
        recipes.py
        meal_plans.py
        shopping.py
        dashboard.py
        health.py
    services/
      freshness.py          Section 8.1
      scoring.py            Section 8.2
      planner.py            Section 8.6
      shopping.py           Section 8.7
      impact.py             Section 8.8
      units.py              Section 8.5
      normalise.py          alias and fuzzy mapping, Section 8.4
      recipe_catalogue.py   seed loader
    llm/
      client.py             Groq wrapper: timeouts, retries, usage logging
      prompts/
        vision_v1.py
        recipes_v1.py
      vision.py             scan pipeline
      recipe_gen.py         AI recipe pipeline with validation
    media/
      image_pipeline.py     validation, EXIF strip, resize, encode
  scripts/
    validate_data.py        checks recipe and ingredient references (run in CI)
    seed.py
  tests/
    unit/
    integration/
    contract/
    eval/                   vision evaluation harness (Section 14)
```

### 13.3 Configuration (environment variables)

Required:
- `GROQ_API_KEY`
- `DATABASE_URL` (for example `postgresql+psycopg://user:pass@db:5432/fridgechef`)
- `JWT_SECRET` (at least 32 random bytes; the app refuses to start with the default or a short value)

Optional with defaults:
- `APP_ENV` (development | staging | production; default development)
- `CORS_ORIGINS` (comma-separated; default `http://localhost:5173`)
- `GROQ_VISION_MODEL`, `GROQ_TEXT_MODEL` (defaults in Section 9.1)
- `GROQ_TIMEOUT_SECONDS` (20), `GROQ_MAX_RETRIES` (2)
- `UPLOAD_DIR` (default `/var/lib/fridgechef/uploads`; must be outside the code directory)
- `MAX_UPLOAD_MB` (8)
- `ACCESS_TOKEN_MINUTES` (60), `REFRESH_TOKEN_DAYS` (30)
- `RATE_LIMIT_SCANS_PER_DAY` (20), `RATE_LIMIT_RECS_PER_HOUR` (60)
- `LLM_MONTHLY_BUDGET_USD` (unset = no cap)
- `LOG_LEVEL` (INFO)

A `.env.example` file lists all variables with placeholder values. The real `.env` is git-ignored.

### 13.4 Startup sequence
1. Load and validate settings. Exit with a clear message if a required variable is missing or invalid.
2. Verify database connection and that migrations are at head.
3. Load and validate the catalogue and recipe data files against their schemas. Exit on error.
4. Upsert ingredients, shelf life, and curated recipes (idempotent).
5. Check Groq model availability (failure logs a warning and disables AI features; it does not stop the server).
6. Start serving.

## 14. Quality, Testing, and Evaluation

### 14.1 Unit tests (must cover)
- Freshness: each storage type, opened vs purchased reference, boundary values for USE_FIRST/USE_SOON/SAFE, non-applicable storage rejection.
- Scoring: each component in isolation, hard filters (allergen, diet, time, coverage), tie-breaking, determinism for identical input.
- Planner: no recipe more than twice, no same recipe on consecutive slots, low-variety flag, inventory never goes negative, locked slots preserved on regenerate.
- Units: conversions, rejection of impossible conversions.
- Normalisation: alias hits, case and plural handling, fuzzy matching thresholds, null for unknown.
- Shopping list: aggregation, subtraction, category grouping, cost estimates.
- Impact: classification of used vs wasted, estimate flags.
- Security: password policy, token expiry, refresh rotation and revocation, cross-user access denied on every resource.

Target: 85% line coverage on `app/services` and `app/llm`.

### 14.2 Integration tests
- Full API flows against PostgreSQL in Docker: register → preferences → scan (Groq mocked) → confirm → inventory → recommendations → cooked → meal plan → shopping list.
- Groq failure modes mocked: timeout, 429 with retry, 500 then success, invalid JSON then valid, persistent failure → degraded or VISION_UNAVAILABLE.
- Rate limits: scan limit and login limit return 429 with `Retry-After`.
- Image pipeline: rejects non-image, oversize, corrupt; strips EXIF (verify no GPS tags remain); output ≤ 4 MB and ≤ 1600 px.

### 14.3 Contract tests
- Every response body is validated against its Pydantic model in tests.
- The frontend Zod schemas are generated from or checked against the OpenAPI document; CI fails on drift.

### 14.4 Vision evaluation
- Build a labelled set of at least 40 fridge and pantry photos (mix of lighting, cluttered and sparse, containers, and bulk items) with ground-truth canonical IDs.
- Metrics per run: precision and recall for the 30 most common ingredients; false positive rate per image; percentage of images needing the user to correct at least one item.
- Initial acceptance targets for the MVP: precision ≥ 0.80 and recall ≥ 0.60 on the 30 common ingredients. The eval harness writes a report file; a regression of more than 5 points blocks release.
- Prompt changes require re-running the evaluation before merge.

### 14.5 Recipe data quality
- `validate_data.py` in CI checks: every `canonical_id` exists; every recipe has 3–12 steps; no duplicate IDs; diet and spice values are valid enums; allergen-group consistency with ingredients.

### 14.6 End-to-end tests (Playwright)
- Register, onboard, scan (fixture image with mocked backend response), verify, save, see items in inventory, see recommendations, cook a recipe, generate plan, generate shopping list.
- Run at 360×800 mobile viewport and 1280×800 desktop viewport.

### 14.7 Performance check
- Load test with k6 or Locust: 100 concurrent users on read endpoints and recommendations (cached) for 5 minutes; verify NFR-001 and NFR-003.

## 15. Deployment

### 15.1 Containers
- `api`: Python 3.11 slim image, runs Gunicorn with Uvicorn workers, non-root user, health check on `/api/health`.
- `web`: multi-stage build (Node 20 build, nginx alpine serve). nginx serves static files and proxies `/api/` to `api`.
- `db`: PostgreSQL 16 with a named volume.
- Uploads volume mounted only into `api`, with restrictive permissions (0700 owned by app user).

### 15.2 Docker Compose (development)
Services: `db`, `api`, `web`. Environment loaded from `.env`. The `api` service runs `alembic upgrade head` before starting. Expose `api` on 8000 and `web` on 5173 (or 80) bound to the host LAN interface for phone testing.

### 15.3 Production
- TLS terminated at a reverse proxy (Caddy or nginx with Let's Encrypt) in front of `web` and `api`.
- Secrets injected by the hosting platform; `.env` is not used in production.
- Daily automated PostgreSQL backups with 14-day retention.
- Uploads directory cleanup job runs hourly to delete images of expired scan sessions.
- Deletion job runs daily to purge accounts scheduled for deletion.

### 15.4 Release checklist
- All tests green; vision evaluation meets targets.
- Alembic migrations applied in staging before production.
- Groq model IDs confirmed in the models list for the target environment.
- Rate limits and budget cap configured.
- Privacy policy and terms published; Groq listed as processor.
- Error tracking (Sentry or equivalent) receives events from both API and web.

## 16. Milestones for the Implementing Agent

Each milestone ends with passing tests and a runnable state.

- M1 Foundation: repository layout, configuration, database models, Alembic initial migration, catalogue and recipe data files with validation script, health endpoints, structured logging.
- M2 Auth and preferences: register, login, refresh, logout, me, preferences, ownership checks, rate limit on login.
- M3 Inventory and freshness: CRUD, freshness engine, use and waste actions, filters, waste log.
- M4 Scanning: image pipeline, Groq vision client with retries and validation, scan sessions, confirm flow, image deletion job.
- M5 Recommendations: scoring engine, hard filters, cache, curated recipes, degraded mode, reasons.
- M6 AI recipe generation: prompt, schema validation, pending-review storage, cost limits.
- M7 Meal planner and shopping lists: planner, regeneration, shopping aggregation, grouping, cost.
- M8 Frontend: PWA shell, auth, onboarding, dashboard, scan and verify, inventory, recommendations, recipe detail, plan, shopping, settings.
- M9 Hardening: rate limits, security review checklist, vision evaluation, load test, Playwright suite, Docker production build, deployment docs.

## 17. Out of Scope for v1.0 (tracked for later)

- Store integrations, price feeds, ordering
- Barcode scanning
- Native mobile apps
- Hindi and regional-language UI
- Voice assistant
- Household sharing and multi-user fridges
- Recipe video or step photos
- On-device vision models
- Smart fridge or IoT integrations

## 18. Assumptions

- The Groq account has access to a vision-capable model at launch. If none is available, scanning falls back to manual entry and the release is gated on access.
- Users accept that quantities and freshness are estimates.
- Shelf-life values are typical reference values for India-like storage conditions and are editable by admins through a data file change, not a UI.
- Prices and weights in the catalogue are reference values that change over time; they are reviewed quarterly.

## 19. Definition of Done (MVP)

The MVP is complete when all of the following are true:

1. A new user can register, complete onboarding, scan a fridge photo on an Android phone over HTTPS, confirm items, and see freshness-ranked inventory in under 3 minutes.
2. Recommendations show at least 5 recipes with match percentage, expiring items used, and missing items with cost.
3. A 7-day plan can be generated and one slot regenerated without affecting others.
4. A shopping list shows only missing items, grouped by category.
5. Cooking a recipe decrements inventory and records the event.
6. Groq outage produces a degraded but usable experience, with no crashes and no exposure of the API key.
7. All P0 functional requirements have passing tests.
8. Vision evaluation meets Section 14.4 targets.
9. Deployment via Docker Compose works from a clean checkout following the README, with no undocumented steps.
10. Security checklist items in NFR-020 to NFR-032 are verified.
