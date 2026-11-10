# FridgeChef AI — PRD Analysis & Architecture Specification

**Document Version**: 1.0  
**Based on Source**: [`FridgeChef_PRD.md`](file:///c:/Users/chara/Desktop/Fridge%20project/FridgeChef_PRD.md) (v1.0, Ready for implementation)  
**Status**: Approved Foundation for Phase 0  

---

## 1. Executive Summary & Product Goals

### 1.1 Purpose and Core Problem
FridgeChef AI is designed for households in India to reduce food waste. Existing recipe platforms suggest meals without accounting for perishable inventory, resulting in unnecessary household waste. FridgeChef addresses this by:
1. Allowing users to photograph their fridge or pantry to detect existing ingredients.
2. Giving the user full editorial control to confirm, correct, and annotate detected items.
3. Tracking food freshness deterministically to prioritize items closest to expiry (`USE_FIRST`, `USE_SOON`, `SAFE`).
4. Recommending recipes ranked by an explainable, deterministic waste-prevention score.
5. Generating a weekly 7-day meal plan that utilizes expiring produce first.
6. Producing an optimized, aisle-grouped shopping list covering only missing quantities.

### 1.2 Core Product Principles
The PRD establishes three inviolable product principles (Section 2):
1. **AI Proposes, User Confirms**: Vision output is never directly saved to inventory. It is staged in a temporary session until user verification.
2. **Deterministic Freshness**: Expiry dates and remaining shelf life are computed via deterministic rules and reference tables (`shelf_life.json`), never by LLM speculation.
3. **Deterministic & Explainable Recipe Ranking**: Ranking is performed via a deterministic mathematical scoring formula. The LLM provides candidate recipes only when curated options fall short, never the final ranking.

### 1.3 MVP Goals vs. Non-Goals
| Goal ID | Target / Requirement (Section 3.1) |
|---|---|
| **G1** | ≥80% precision on the 30 most common Indian ingredients from single fridge/pantry photo. |
| **G2** | Complete verification/editing of typical fridge (15 items) in under 60 seconds. |
| **G3** | Track remaining-life days and classify items as `USE_FIRST` (≤1d), `USE_SOON` (2-3d), or `SAFE` (≥4d). |
| **G4** | Recommend ≥5 recipes ranked by waste prevention score, highlighting expiring items used. |
| **G5** | Generate a 7-day meal plan (lunch & dinner) prioritizing expiring items and ingredient reuse across meals. |
| **G6** | Generate shopping lists for missing ingredients only, grouped by aisle category. |
| **G7** | Mobile-first responsive web app (PWA) operational at ≥360px viewport width (Android Chrome & iOS Safari). |
| **G8** | Server-side isolation of Groq API keys; no exposure to clients or source control. |

**Explicit Non-Goals for MVP (Section 3.2)**:
- Direct grocery store delivery integrations, live price scraping, or automated purchasing.
- Gram-accurate image weighing (quantities are user-confirmed estimates).
- Barcode scanning.
- Per-gram clinical nutrition calculations (nutrition figures are serving-level estimates).
- Native iOS/Android app wrappers (PWA covers mobile).
- Multi-household sharing or multi-user fridges.
- Payments and billing systems.

---

## 2. Architecture & Technology Stack

### 2.1 Technology Stack Matrix
| Layer | PRD Specified Technology | PRD Section | Notes / Version Constraints |
|---|---|---|---|
| **Frontend Runtime** | React 18, TypeScript, Vite | 12.1 | Strict typing, mobile-first responsive |
| **Frontend Styling** | Tailwind CSS v3 | 12.1 | Mobile-first utility design; WCAG 2.1 AA |
| **Frontend Routing** | React Router v6 | 12.1 | Client-side routing and navigation guards |
| **Frontend State** | TanStack Query (React Query) | 12.1 | Server state caching, optimistic updates |
| **Frontend Validation** | Zod | 12.1 | Schema validation at API response boundary |
| **Frontend PWA** | `vite-plugin-pwa` | 12.1 | Service worker & manifest (app shell caching only) |
| **Backend Runtime** | Python 3.11+ / FastAPI | 13.1 | ASGI web framework with async support |
| **Backend Validation** | Pydantic v2, `pydantic-settings` | 13.1 | Request/response models; unknown fields rejected |
| **Database & ORM** | PostgreSQL 16, SQLAlchemy 2.x, Alembic | 10, 13.1 | Relational DB; strict migrations; parameterized queries |
| **AI / LLM Integration** | Groq Python SDK | 9.1, 13.1 | Vision & recipe candidate generation |
| **Media Pipeline** | Pillow, `pillow-heif` | 13.1 | Image validation, EXIF stripping, JPEG compression |
| **Auth & Security** | PyJWT, `passlib[bcrypt]` or `argon2-cffi` | 13.1 | Bcrypt (cost 12), JWT (60m access / 30d refresh) |
| **Rate Limiting** | `slowapi` or Redis-backed limiter | 13.1 | Sliding window rate limits |
| **Testing** | pytest, pytest-asyncio, httpx, respx | 13.1, 14 | 85% coverage on services & LLM; Vitest/Playwright |
| **Containers & Infra** | Docker, Docker Compose, Nginx / Caddy | 15.1, 15.2 | Multi-stage builds, non-root users |

### 2.2 System Architecture Diagram
```
                     +---------------------------------------+
                     | Mobile Browser / PWA (React 18 + TS)  |
                     | 360px+ Viewport, Tailwind CSS v3      |
                     +-------------------+-------------------+
                                         | HTTPS / REST (JSON & Multipart)
                                         v
                     +---------------------------------------+
                     | Nginx / Caddy (Reverse Proxy & TLS)   |
                     +-------------------+-------------------+
                                         | Proxies /api/v1
                                         v
                     +---------------------------------------+
                     | FastAPI Application (Python 3.11+)     |
                     | - Auth & Rate Limiting (slowapi)      |
                     | - Pydantic v2 Request Validation      |
                     +-----+-------------+-------------+-----+
                           |             |             |
            SQLAlchemy 2.x |             | Image Ops   | Groq SDK (HTTPS)
                           v             v             v
       +-----------------------+   +-----------+   +-------------------+
       | PostgreSQL 16         |   | Disk      |   | Groq Cloud API    |
       | - Users & Preferences |   | Storage   |   | - Vision Model    |
       | - Inventory & Scans   |   | (Outside  |   |   (Llama-4 Scout) |
       | - Recipes & Catalogue |   | Web Root) |   | - Text Model      |
       | - Plans & Shopping    |   | Resized   |   |   (Llama-3.3-70B) |
       | - Audit & LLM Logs    |   | Copies    |   +-------------------+
       +-----------------------+   +-----------+
```

---

## 3. Detailed Component Responsibilities

### 3.1 Backend Responsibilities (`api/`)
1. **Authentication & Session Lifecycle**: User registration, credential hashing (bcrypt cost 12), JWT generation, token rotation, and refresh token revocation.
2. **User Preferences & Scoping**: Manage dietary restrictions, allergies, max cooking time, household size; ensure 100% of queries filter by authenticated `user_id`.
3. **Media Pipeline & Vision Ingestion**: Validate MIME type (JPEG/PNG/WEBP/HEIC ≤8MB), decode with Pillow, strip EXIF metadata, resize to ≤1600px long edge, encode to JPEG q85 (≤4MB).
4. **AI Orchestration**: Interface with Groq API; enforce JSON schema responses, retry with backoff, fall back to degraded mode gracefully, record token usage in `llm_calls`.
5. **Deterministic Freshness Engine**: Calculate remaining shelf life based on canonical ingredient storage rules (`shelf_life.json`) and opened status; categorize into `USE_FIRST`, `USE_SOON`, `SAFE`.
6. **Deterministic Recipe Recommendation**: Rank curated recipes using mathematical score weights (coverage 0.35, urgency 0.35, quantity fit 0.10, preference 0.10, time fit 0.10); cache recommendations for 30 minutes.
7. **Meal Planning Engine**: Greedy lookahead algorithm across 7 days (14 meal slots), track inventory depletion, avoid consecutive duplicate meals, enforce max 2 repeats per week.
8. **Shopping List Engine**: Aggregate ingredient deficits across selected recipes or meal plans, subtract available inventory, group by grocery category, attach cost estimates.
9. **Impact Tracking**: Calculate waste prevented and money saved using canonical weight and price tables; tag all outputs with `"is_estimate": true`.
10. **Background Jobs / Housekeeping**: Hourly cleanup of expired scan images and daily purge of accounts marked for deletion.

### 3.2 Frontend Responsibilities (`web/`)
1. **Responsive App Shell & PWA**: Mobile-first design (360px+), bottom navigation bar (Home, Inventory, Scan, Recipes, Plan), PWA manifest and service worker shell caching.
2. **Camera Ingestion UX**: Native file input with `accept="image/*" capture="environment"`; visual progress indicator ("Looking at your fridge…"); error messaging.
3. **Verification Screen**: Presentation of vision candidates with confidence badges (High, Medium, Low); low-confidence items pre-unchecked; inline editing for name (with canonical autocomplete), quantity, unit, and storage location.
4. **Inventory Management UI**: Filterable tabs (`All`, `USE_FIRST`, `USE_SOON`, `SAFE`), quick search, decrement on use, waste logging, edit freshness dates.
5. **Recipe & Recommendation View**: Display match percentage, expiring items used badges, missing items count and cost; detailed modal with servings scaler stepper, step checklist, nutrition estimate disclaimer, and "Cooked this" action.
6. **Weekly Meal Plan View**: 7-day grid showing lunch and dinner; single-slot regeneration with lock toggle; consolidated shopping list export.
7. **Accessibility & Form Usability**: WCAG 2.1 AA color contrast; non-color status icons; minimum 44x44px touch targets; virtual keyboard layout preservation via `visualViewport` API.

---

## 4. Functional Requirements Traceability Matrix

| Requirement ID | PRD Section | Summary of Requirement | Priority | Verification Method |
|---|---|---|---|---|
| **FR-001** | 6.1 | User registration with email, password (min 8 chars, 1 letter, 1 digit), display name. Case-insensitive unique email. | P0 | Unit / Integration Test |
| **FR-002** | 6.1 | Login returns JWT access token (60m) and refresh token (30d, rotated on each use). | P0 | Integration Test |
| **FR-003** | 6.1 | Passwords hashed with bcrypt (cost factor 12) or Argon2. Plain text never stored or logged. | P0 | Security Unit Test |
| **FR-004** | 6.1 | Logout revokes refresh token in database. | P0 | Integration Test |
| **FR-005** | 6.1 | Strict multi-tenancy: every data query and mutation is scoped by authenticated user ID. | P0 | Security Integration Test |
| **FR-006** | 6.1 | Password reset via email link. | P1 | Post-MVP |
| **FR-010** | 6.2 | Store and update user preferences (household size 1-10, diet, spice, cuisines, max cooking time, allergies, avoided ingredients). | P0 | Schema & API Test |
| **FR-011** | 6.2 | Allergies and avoided ingredients excluded from all recipes and meal plans via canonical ID and alias resolution. | P0 | Algorithmic Unit Test |
| **FR-020** | 6.3 | Accept JPEG, PNG, WEBP, HEIC up to 8MB. Reject invalid types with 415, oversized with 413. | P0 | Media Pipeline Test |
| **FR-021** | 6.3 | Decode image with Pillow to verify valid image data; reject corrupt files with 422. | P0 | Media Pipeline Test |
| **FR-022** | 6.3 | Strip all EXIF metadata (specifically GPS) before persisting or sending to Groq. | P0 | Media Pipeline Test |
| **FR-023** | 6.3 | Resize to max 1600px long edge, encode as JPEG q85 (must remain <4MB). | P0 | Media Pipeline Test |
| **FR-024** | 6.3 | Send image to Groq vision model; enforce JSON response schema (Section 9.3). | P0 | Mock Integration Test |
| **FR-025** | 6.3 | Map returned ingredient names to canonical ingredient IDs via alias table and fuzzy matching (Levenshtein ≤2 on 5+ chars). Unmapped get `null`. | P0 | Normalization Test |
| **FR-026** | 6.3 | Return scan candidates with scan ID; candidates expire after 30 minutes in `scan_sessions`. | P0 | Integration Test |
| **FR-027** | 6.3 | Detected items are never written to inventory without explicit user confirmation via verify endpoint. | P0 | Flow Integration Test |
| **FR-028** | 6.3 | Original uploaded image deleted within 24h; resized copy deleted when scan session expires. | P0 | Cleanup Job Test |
| **FR-029** | 6.3 | Groq vision failure or invalid JSON after 1 retry returns HTTP 502 `VISION_UNAVAILABLE`. | P0 | Error Handling Test |
| **FR-030** | 6.4 | Full CRUD on inventory items (canonical ID, display name, quantity, unit, storage, added_on, opened_on). | P0 | API Integration Test |
| **FR-031** | 6.4 | Freshness estimate computed via freshness engine (8.1) stored on item and recalculated on read. | P0 | Unit / API Test |
| **FR-032** | 6.4 | Mark item as used (decrements quantity, archives if 0), wasted (logs to `waste_log`), or delete. | P0 | API Integration Test |
| **FR-033** | 6.4 | Normalise units to base units (`g`, `ml`, `piece`) per catalogue conversion factors (8.5). | P0 | Unit Test |
| **FR-034** | 6.4 | Inventory listing supports filtering by status (`USE_FIRST`, `USE_SOON`, `SAFE`) and storage, and sorting by expiry. | P0 | API Test |
| **FR-040** | 6.5 | Seed database at startup with ≥150 curated Indian recipes from `data/recipes.json` (idempotent upsert). | P0 | Seed / Data Test |
| **FR-041** | 6.5 | Trigger AI recipe generation if fewer than 5 curated recipes match at ≥40% coverage score. | P0 | Recommendation Test |
| **FR-042** | 6.5 | Validate AI recipes against recipe schema and canonical IDs; discard if unmapped. | P0 | Schema Validation Test |
| **FR-043** | 6.5 | Rank recipes deterministically using formula in Section 8.2. | P0 | Algorithmic Unit Test |
| **FR-044** | 6.5 | Recommendation response includes match %, expiring items used, missing items with cost, and templated reason. | P0 | API Contract Test |
| **FR-045** | 6.5 | Hard filters: exclude recipes with allergens, diet violations, cooking time > 2x max, or coverage < 0.4. | P0 | Algorithmic Unit Test |
| **FR-046** | 6.5 | Cache recommendations per user for 30m keyed by inventory and preference hash; invalidate on changes. | P0 | Cache Test |
| **FR-047** | 6.5 | Favourites and custom user recipes. | P1 | Post-MVP |
| **FR-050** | 6.6 | Generate 7-day meal plan (2 meals/day, lunch & dinner) from given start date. | P0 | Planner Test |
| **FR-051** | 6.6 | Planner enforces: no recipe scheduled >2 times in 7 days, no same recipe on consecutive meals. | P0 | Algorithmic Unit Test |
| **FR-052** | 6.6 | Track simulated inventory consumption across 7 days; add deficits to shopping list. | P0 | Planner Test |
| **FR-053** | 6.6 | Regenerating a single slot keeps all other slots unchanged. | P0 | Planner Test |
| **FR-054** | 6.6 | One active plan per user; generating a new plan archives previous. | P0 | Database Test |
| **FR-060** | 6.7 | Generate shopping list from meal plan, selected recipes, or manual entry. | P0 | Shopping Test |
| **FR-061** | 6.7 | Aggregate quantities by canonical ID, subtract inventory, group by aisle category. | P0 | Unit / API Test |
| **FR-062** | 6.7 | Mark item as bought; option to auto-add to inventory with purchased quantity. | P0 | Integration Test |
| **FR-070** | 6.8 | Dashboard endpoint returning freshness counts, recommendation summary (unresolved decision: 5 per Sec 5.4 & FR-070 vs 3 per Sec 11.10 & 12.3), active plan summary, month-to-date impact. | P0 | Dashboard API Test |
| **FR-071** | 6.8 | Compute impact figures from waste log & cooking events using price/weight tables; set `"is_estimate": true`. | P0 | Unit / API Test |
| **FR-080** | 6.9 | Recipe thumbs up/down feedback adjusting preference weights. | P1 | Post-MVP |

---

## 5. Non-Functional Requirements & Guardrails

| NFR ID | Category | Requirement Detail | Verification Metric |
|---|---|---|---|
| **NFR-001** | Performance | Non-AI endpoint latency P95 < 300ms at 100 concurrent users. | k6 / Locust load test |
| **NFR-002** | Performance | Scan endpoint P95 < 15s including Groq vision call; UI progress state. | Integration latency test |
| **NFR-003** | Performance | Recommendation latency P95 < 2s when cached, < 8s when AI generation is needed. | Integration latency test |
| **NFR-004** | Performance | Meal plan generation P95 < 10s. | Performance unit test |
| **NFR-010** | Reliability | Groq client: 20s timeout, up to 2 retries with exponential backoff (1s, 3s) on 429, 500, 502, 503, 504. | Mock retry tests |
| **NFR-011** | Reliability | Graceful degradation: curated recipes only with `"degraded": true` if Groq fails; manual scan fallback. | Fault injection tests |
| **NFR-012** | Reliability | Multi-row database writes execute within a single atomic database transaction. | Database rollback tests |
| **NFR-020** | Security | `GROQ_API_KEY` read strictly from environment; app fails to start if missing; never logged or committed. | Startup validation test |
| **NFR-021** | Security | All endpoints except register, login, refresh, health require valid JWT access token. | Auth matrix test |
| **NFR-022** | Security | Rate limits: 20 scans/day, 60 recommendations/hour, 200 other requests/minute per user (sliding window). | Slowapi rate limit tests |
| **NFR-023** | Security | Login rate limits: 10 attempts per 15 minutes per email and per IP address. | Auth security tests |
| **NFR-024** | Security | HTTPS enforced in production with HSTS enabled. | Deployment config audit |
| **NFR-025** | Security | CORS restricted strictly to origins specified in `CORS_ORIGINS`. | CORS middleware test |
| **NFR-026** | Security | Pydantic v2 validation on all request bodies; unknown fields rejected (`extra="forbid"`). | Schema fuzz tests |
| **NFR-027** | Security | Parameterized ORM queries only; zero raw string SQL concatenation. | Code inspection / lint |
| **NFR-028** | Security | Uploaded images stored outside web root; accessible only via authenticated session owner. | Storage security test |
| **NFR-030** | Privacy | Data export (`GET /api/me/export`) and account deletion (`DELETE /api/me`, purge within 30 days, images immediate). | Privacy lifecycle test |
| **NFR-031** | Privacy | Images not retained after scan session expires; privacy disclosure of Groq third-party processing. | Audit verification |
| **NFR-032** | Privacy | Log sanitization: no passwords, tokens, image bytes; emails masked as `a***@domain`. | Log sanitization test |
| **NFR-040** | Observability | Structured JSON logs with request ID, hashed user ID, endpoint, status, latency, error code. | Logging format tests |
| **NFR-041** | Observability | Record Groq token consumption, model name, and latency in `llm_calls` table. | Audit table tests |
| **NFR-042** | Observability | Health endpoints: `/api/health` (liveness), `/api/health/ready` (checks DB and Groq models availability). | Health check tests |
| **NFR-050** | UX / A11y | WCAG 2.1 AA color contrast; status never communicated by color alone (text badge + icon). | Accessibility audit |
| **NFR-051** | UX / A11y | Touch targets ≥44x44px across all interactive controls. | CSS / UI inspection |
| **NFR-052** | UX / A11y | Full support for on-screen keyboard without button occlusion; screen reader accessibility labels. | Mobile UI test |
| **NFR-053** | Localization | English at launch; externalized strings in frontend dictionary for Hindi support. | Code inspection |
| **NFR-060** | Portability | Backend runs on Python 3.11/3.12 across Linux, macOS, and Windows. | Cross-platform CI |
| **NFR-061** | Portability | Frontend compiles to static distribution served by Nginx or static file hosts. | Build check |

---

## 6. Database Schema & Data Relationships

### 6.1 Database Entity Relationship Architecture
The data model comprises 15 relational entities in PostgreSQL 16 (Section 10):

```
+------------------+         1:1         +--------------------+
|      users       | +-----------------> |  user_preferences  |
+--------+---------+                     +--------------------+
         |
         | 1:N
         +-------------------------------------------------------------+
         |                     |                     |                 |
         v                     v                     v                 v
+------------------+  +------------------+  +------------------+  +------------------+
|  refresh_tokens  |  | inventory_items  |  |  scan_sessions   |  |    waste_log     |
+------------------+  +--------+---------+  +------------------+  +------------------+
                               |
                               | N:1
                               v
                      +------------------+         1:N            +--------------------+
                      |   ingredients    | <--------------------+ | recipe_ingredients |
                      +--------+---------+                        +---------+----------+
                               |                                            |
                               | 1:N                                        | N:1
                               v                                            v
                      +------------------+                        +--------------------+
                      |    shelf_life    |                        |      recipes       |
                      +------------------+                        +---------+----------+
                                                                            |
                               +--------------------------------------------+
                               |
                               v 1:N
                      +------------------+  +------------------+  +--------------------+
                      |  cooking_events  |  |    meal_plans    |  |   shopping_lists   |
                      +------------------+  +------------------+  +--------------------+

                      +------------------+  +----------------------+
                      |    llm_calls     |  | recommendation_cache |
                      +------------------+  +----------------------+
```

### 6.2 Table Specifications and Constraints
1. **`users`**:
   - `id` (UUID PK), `email` (VARCHAR, Unique, Lowercase), `password_hash` (VARCHAR), `display_name` (VARCHAR), `created_at` (TIMESTAMPTZ), `deleted_at` (TIMESTAMPTZ, Nullable).
2. **`user_preferences`**:
   - `user_id` (UUID PK, FK `users.id` CASCADE), `household_size` (INT, 1–10), `diet` (ENUM: VEGETARIAN, EGGLESS, NON_VEGETARIAN, VEGAN), `spice_level` (ENUM: MILD, MEDIUM, HOT), `cuisines` (TEXT[]), `max_cooking_time` (INT), `allergies` (TEXT[] of canonical IDs), `avoided_ingredients` (TEXT[]), `version` (INT default 1).
3. **`refresh_tokens`**:
   - `id` (UUID PK), `user_id` (UUID FK `users.id` CASCADE), `token_hash` (VARCHAR), `expires_at` (TIMESTAMPTZ), `revoked_at` (TIMESTAMPTZ, Nullable).
4. **`ingredients`**:
   - `id` (VARCHAR PK - canonical slug, e.g. `potato`), `display_name` (VARCHAR), `category` (VARCHAR), `aliases` (TEXT[]), `default_unit` (ENUM: piece, g, ml), `grams_per_piece` (DECIMAL, Nullable), `ml_per_piece` (DECIMAL, Nullable), `price_inr_per_kg` (DECIMAL), `allergen_group` (VARCHAR, Nullable).
5. **`shelf_life`**:
   - `id` (UUID PK), `ingredient_id` (VARCHAR FK `ingredients.id` CASCADE), `storage` (ENUM: FRIDGE, FREEZER, PANTRY, COUNTER), `days` (INT, Nullable), `opened_days` (INT, Nullable). Unique constraint on `(ingredient_id, storage)`.
6. **`recipes`**:
   - `id` (VARCHAR PK - slug), `title` (VARCHAR), `cuisine` (VARCHAR), `diet` (ENUM), `spice_level` (ENUM), `cooking_time_minutes` (INT), `base_servings` (INT), `steps` (JSONB), `nutrition` (JSONB), `tags` (TEXT[]), `source` (ENUM: CURATED, AI), `status` (ENUM: APPROVED, PENDING_REVIEW), `created_by_user_id` (UUID FK `users.id`, Nullable).
7. **`recipe_ingredients`**:
   - `id` (UUID PK), `recipe_id` (VARCHAR FK `recipes.id` CASCADE), `ingredient_id` (VARCHAR FK `ingredients.id`), `qty` (DECIMAL), `unit` (ENUM: g, ml, piece), `is_optional` (BOOLEAN). Unique on `(recipe_id, ingredient_id)`. Index on `ingredient_id`.
8. **`inventory_items`**:
   - `id` (UUID PK), `user_id` (UUID FK `users.id` CASCADE), `ingredient_id` (VARCHAR FK `ingredients.id`), `display_name` (VARCHAR), `quantity` (DECIMAL ≥ 0), `unit` (ENUM), `storage` (ENUM), `added_on` (DATE), `opened_on` (DATE, Nullable), `archived_at` (TIMESTAMPTZ, Nullable). Index on `(user_id, archived_at)`.
9. **`scan_sessions`**:
   - `id` (UUID PK), `user_id` (UUID FK `users.id` CASCADE), `status` (ENUM: PENDING_VERIFY, CONFIRMED, EXPIRED), `image_path` (VARCHAR, Nullable), `candidates` (JSONB), `image_quality` (VARCHAR), `created_at` (TIMESTAMPTZ), `expires_at` (TIMESTAMPTZ). Index on `(user_id, status)`.
10. **`waste_log`**:
    - `id` (UUID PK), `user_id` (UUID FK `users.id` CASCADE), `inventory_item_id` (UUID FK, Nullable), `ingredient_id` (VARCHAR FK), `quantity` (DECIMAL), `unit` (ENUM), `action` (ENUM: USED_BEFORE_EXPIRY, WASTED), `estimated_value_inr` (DECIMAL), `created_at` (TIMESTAMPTZ). Index on `(user_id, created_at)`.
11. **`cooking_events`**:
    - `id` (UUID PK), `user_id` (UUID FK `users.id` CASCADE), `recipe_id` (VARCHAR FK `recipes.id`), `servings` (INT), `rating` (INT 1-5, Nullable), `created_at` (TIMESTAMPTZ).
12. **`meal_plans`**:
    - `id` (UUID PK), `user_id` (UUID FK `users.id` CASCADE), `start_date` (DATE), `status` (ENUM: ACTIVE, ARCHIVED), `low_variety` (BOOLEAN), `created_at` (TIMESTAMPTZ), `plan` (JSONB: slots, shopping list, impact). Index on `(user_id, status)`.
13. **`shopping_lists`**:
    - `id` (UUID PK), `user_id` (UUID FK `users.id` CASCADE), `source` (ENUM: PLAN, RECIPES, MANUAL), `items` (JSONB), `created_at` (TIMESTAMPTZ).
14. **`llm_calls`**:
    - `id` (UUID PK), `user_id` (UUID FK, Nullable), `purpose` (ENUM: VISION, RECIPE_GEN), `model` (VARCHAR), `prompt_version` (VARCHAR), `prompt_tokens` (INT), `completion_tokens` (INT), `latency_ms` (INT), `status` (ENUM: OK, ERROR, RETRIED), `error_code` (VARCHAR, Nullable), `created_at` (TIMESTAMPTZ).
15. **`recommendation_cache`**:
    - `user_id` (UUID FK `users.id` CASCADE), `cache_key` (VARCHAR), `payload` (JSONB), `expires_at` (TIMESTAMPTZ). PK `(user_id, cache_key)`.

---

## 7. Mathematical & Deterministic Algorithmic Formulations

### 7.1 Freshness Calculation Formula (Section 8.1)
```python
# Compute remaining shelf-life days
base_life = shelf_life[canonical_id][storage] # In days
reference_date = opened_date if opened_date is not None else added_date
age_days = floor((today - reference_date).days)
days_left = max(0, base_life - age_days)

# Status Classification:
if days_left <= 1:
    status = "USE_FIRST"  # Red badge
elif 2 <= days_left <= 3:
    status = "USE_SOON"   # Amber badge
else:
    status = "SAFE"       # Green badge
```

### 7.2 Recipe Scoring Formula (Section 8.2)
For inventory $I$ and recipe $R$ with required (non-optional) ingredients:
- **Coverage**:
  $$\text{coverage} = \frac{|\text{matched non-optional ingredients}|}{|\text{required non-optional ingredients}|}$$
- **Urgency**:
  $$\text{urgency} = \frac{1}{|\text{matched}|} \sum_{i \in \text{matched}} \max\left(0, 1 - \frac{\text{days\_left}(i)}{7}\right)$$
- **Quantity Fit**:
  $$\text{quantity\_fit} = \frac{1}{|\text{matched}|} \sum_{i \in \text{matched}} \min\left(1.0, \frac{\text{inventory\_qty}(i)}{\text{recipe\_qty}(i) \times \frac{\text{household\_size}}{\text{base\_servings}}}\right)$$
- **Preference**:
  Base cuisine match ($1.0$ if preferred, $0.5$ otherwise) $\times$ spice match ($1.0$ exact, $0.7$ adjacent, $0.4$ otherwise).
- **Time Fit**:
  $1.0$ if $\text{cooking\_time} \le \text{max\_time}$; linearly scales down to $0.0$ at $2 \times \text{max\_time}$.

**Composite Deterministic Score**:
$$\text{Score} = 0.35 \times \text{coverage} + 0.35 \times \text{urgency} + 0.10 \times \text{quantity\_fit} + 0.10 \times \text{preference} + 0.10 \times \text{time\_fit}$$

**Hard Exclusion Filters**:
- Any ingredient in user's allergy or avoided list.
- Violation of dietary constraints (e.g., non-veg recipe for vegetarian).
- $\text{cooking\_time} > 2 \times \text{max\_cooking\_time}$.
- $\text{coverage} < 0.40$.

---

## 8. External Integrations & API Contracts

### 8.1 Groq Cloud API
- **Client**: `groq` Python SDK.
- **Vision Model**: Default `meta-llama/llama-4-scout-17b-16e-instruct` (or current active vision model). Max completion tokens: 1200. Temperature: 0.1.
- **Recipe Text Model**: Default `llama-3.3-70b-versatile`. Max completion tokens: 3000. Temperature: 0.4.
- **JSON Enforcement**: Mandatory `response_format={"type": "json_object"}`. System prompt must include the schema definition and the literal word "JSON".
- **Resilience**: 20-second timeout, up to 2 retries on 429/5xx with exponential backoff (1s, 3s). Fallback to curated catalog (`degraded: true`) when unavailable.

### 8.2 Standard Error Envelope
All error responses adhere to the standard envelope (Section 11):
```json
{
  "error": {
    "code": "CANONICAL_ID_REQUIRED",
    "message": "Item requires a valid canonical ingredient ID.",
    "details": null,
    "request_id": "c9bf9e57-1685-4c89-bafb-ff5af830be8a"
  }
}
```

### 8.3 Authentication, Token Storage & Transport Specifications
1. **Access Tokens**: Short-lived (60 minutes), stored strictly in client memory, transmitted via `Authorization: Bearer <token>` header (PRD Section 6.1, 12.5).
2. **Refresh Tokens**: Long-lived (30 days), rotated on every use, persisted as SHA-256 hash in `refresh_tokens` table. Revoked upon logout (PRD FR-002, FR-004).
3. **Transport Selection & Configuration**:
   - **Default Transport**: An `httpOnly` cookie set by the API on authentication endpoints with `Path=/api/v1/auth`, `SameSite=Lax` (or `Strict`), and `Secure` in production, accompanied by CSRF protection (PRD Section 12.5).
   - **Alternative Transport**: Passing `{refresh_token}` in request bodies and storing in `sessionStorage` is permitted **strictly and only when the deployment topology genuinely makes cookie setup infeasible** (e.g., cross-origin domain decoupling without proxying), with the XSS trade-off explicitly documented (PRD Section 12.5).
   - **No Silent Dual Acceptance**: Deployments must not silently authorize unconditional dual acceptance from multiple transports simultaneously. The active transport is governed by explicit server configuration (`AUTH_REFRESH_TRANSPORT=cookie` [default] vs `AUTH_REFRESH_TRANSPORT=body`) and validated at startup.
   - **Prohibition on Testing Workarounds**: `sessionStorage` must never be used as a workaround for plain-HTTP LAN testing. Per PRD Section 12.6, plain-HTTP LAN testing supports browsing and manual entry only; full mobile camera and PWA features require HTTPS (local tunnel or staging).
4. **Unresolved Specification Conflict (Section 11.1 vs. Section 12.5)**:
   - PRD Section 11.1 explicitly defines request body schemas `{refresh_token}` for `POST /auth/refresh` and `POST /auth/logout`, while Section 12.5 mandates `httpOnly` cookie storage where browser JavaScript cannot access the token to construct a request body.
   - This tension represents an open specification conflict: if `httpOnly` cookies are used, the request body field is inaccessible to the client; if request bodies are required, cookies cannot be `httpOnly`.
   - This conflict is documented as an unresolved specification issue to be confirmed with the user prior to Phase 2 implementation.

---

## 9. Dependencies, Risks, Discrepancies & Ambiguities

### 9.1 Technical Dependencies
1. **Groq Model Availability**: Model IDs in fast-moving providers can deprecate or change active status.
   - *Mitigation*: Startup validation checks `/models` list (PRD Section 9.1); fallbacks are wired into the client; defaults are environment-configurable.
2. **HEIC Decoding (`pillow-heif`)**: Native C-library bindings can vary across operating systems (Windows vs Linux container).
   - *Mitigation*: Containerized testing in Docker for production parity; isolated unit test fixtures.
3. **Data Seed Volume**: The PRD requires $\ge 150$ curated Indian recipes and $\ge 200$ canonical ingredients at launch.
   - *Mitigation*: Dedicated seed validation scripts (`validate_data.py`) in CI ensuring recipe-ingredient relational consistency.

### 9.2 Verified PRD Inconsistencies & Unresolved Decisions

#### 1. Dashboard Recommendation Count (Unresolved Product Decision)
- **Conflicting PRD Requirements**:
  - *Section 5.4 (User Flow 5.4, step 1)*: *"Dashboard shows the top 5 recipes ranked by waste-prevention score."*
  - *Section 6.8 (FR-070)*: *"Dashboard endpoint returns counts by freshness status, top 5 recommendations, current plan summary, and month-to-date impact figures."*
  - *Section 11.10 (API Specification)*: *"GET /dashboard → counts by status, top 3 recommendations (from cache if warm), active plan summary, month-to-date impact with is_estimate: true."*
  - *Section 12.3 (Screen 3)*: *"Dashboard (status counts, top 3 recipes, active plan card, impact card, primary 'Scan fridge' button)"*
- **Status & Decision Rule**:
  - Neither 3 nor 5 can be declared definitively correct from the PRD alone.
  - This is an **unresolved product decision**.
  - **Required Clarification Point**: Must be explicitly clarified with the user prior to implementing Phase 7 (Dashboard endpoint) and Phase 8 (Dashboard UI).
  - **Implementation Strategy**: Implementation must avoid hardcoding either count; the dashboard recommendation limit will be parameterized via a configuration constant (`DASHBOARD_RECOMMENDATIONS_LIMIT`), holding an unresolved default pending product confirmation.

#### 2. Health-Check Route Mapping (Source Requirements & Proposals)
- **PRD References**:
  - *PRD Section 7.5 (NFR-042)*: Explicitly specifies `/api/health` for liveness and `/api/health/ready` for readiness (checking DB and cached Groq model availability).
  - *PRD Section 15.1 (Containers)*: Explicitly specifies Docker container health check targeting `/api/health`.
  - *PRD Section 11 & Section 11.11*: Section 11 defines `Base path: /api/v1.` and Section 11.11 lists `GET /health` and `GET /health/ready`, resulting in canonical paths `/api/v1/health` and `/api/v1/health/ready`.
- **Route Specifications**:
  - `/api/health` (**Mandatory**, PRD NFR-042 & 15.1): Dedicated liveness probe for Docker container healthchecks and orchestrators. Returns 200 OK when process is running.
  - `/api/health/ready` (**Mandatory**, PRD NFR-042): Dedicated readiness probe for orchestrators. Verifies database connectivity and that configured Groq model IDs are present in the cached model list. Returns 200 or 503.
  - `/api/v1/health` and `/api/v1/health/ready` (**Proposal Requiring Confirmation**): Proposed versioned aliases to satisfy Section 11's base path convention. They are retained as thin aliases to `/api/health` and `/api/health/ready` for API client consistency, but are marked as a design proposal rather than an independent mandatory PRD requirement.

#### 3. Catalogue & Recipe Detail Endpoints in Plan
- *Section 11.3*: `GET /ingredients?query=&category=&limit=` and `GET /recipes/{id}`.
- *Status*: Read-only endpoints scheduled in Phase 1 (foundation) to verify seeded catalogue items and support Phase 4 verification autocomplete.

#### 4. Meal Plan Endpoints in Plan
- *Section 11.8*: Requires `GET /meal-plans/{id}` (owner only) and `DELETE /meal-plans/{id}` (archives).
- *Status*: Scheduled in Phase 7 along with plan generation and slot regeneration.

#### 5. Local Phone LAN Testing Limitations (Section 12.6)
- *Explicit Rule*: Plain HTTP LAN testing supports only browsing and manual inventory entry. Camera access and PWA installation require HTTPS (via local tunnel or deployment). No security mechanisms should be bypassed for local testing.
