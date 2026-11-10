# FridgeChef AI — Phased Implementation Plan

**Document Version**: 1.0  
**Based on Source**: [`FridgeChef_PRD.md`](file:///c:/Users/chara/Desktop/Fridge%20project/FridgeChef_PRD.md) (v1.0)  
**Status**: Approved Implementation Roadmap  

---

## 1. Overview & Phasing Principles

This implementation plan breaks down the development of FridgeChef AI into sequential, testable, and gated phases. Each phase directly maps to the PRD requirements and milestones (PRD Section 16).

### 1.1 Core Development Rules
1. **Strict Phase Boundaries**: Implementation agents must only execute the currently approved phase. No downstream features or boilerplate may be added out of sequence.
2. **Deterministic Gating**: A phase is complete only when all deliverables exist, pass automated verification (tests, linting, typing, build), and meet all explicit acceptance criteria.
3. **Traceability**: Every delivered file, model, endpoint, and function must trace directly to a requirement in [`FridgeChef_PRD.md`](file:///c:/Users/chara/Desktop/Fridge%20project/FridgeChef_PRD.md) and [`docs/PRD_ANALYSIS.md`](file:///c:/Users/chara/Desktop/Fridge%20project/docs/PRD_ANALYSIS.md).

---

## 2. Phase Breakdown Matrix

| Phase | PRD Milestone | Primary Focus | Key PRD Requirements |
|---|---|---|---|
| **Phase 0** | Pre-requisite | Project Discovery, Setup & Guardrails | PRD Sections 1–19, Guardrails |
| **Phase 1** | Milestone 1 (M1) | Project Scaffolding, Core Infrastructure, DB Schemas & Seed Data | FR-040, NFR-020, NFR-027, NFR-040, NFR-042, Sec 8.3–8.5, 10, 13 |
| **Phase 2** | Milestone 2 (M2) | Authentication, Authorization, Account & Preferences | FR-001–FR-005, FR-010–FR-011, NFR-021, NFR-023, NFR-030, Sec 11.1–11.2 |
| **Phase 3** | Milestone 3 (M3) | Freshness Engine, Inventory CRUD & Waste Logging | FR-030–FR-034, FR-071, Sec 8.1, 8.5, 8.8, 11.5 |
| **Phase 4** | Milestone 4 (M4) | Media Pipeline, Groq Vision Integration & Scan Verification Flow | FR-020–FR-029, NFR-002, NFR-010, NFR-028, NFR-031, Sec 8.4, 9.1–9.3, 11.4 |
| **Phase 5** | Milestone 5 (M5) | Deterministic Recipe Recommendation Engine & Caching | FR-043–FR-046, NFR-003, NFR-011, Sec 8.2, 11.6 |
| **Phase 6** | Milestone 6 (M6) | AI Recipe Generation Fallback & Budget Controls | FR-041–FR-042, NFR-041, Sec 9.4–9.6 |
| **Phase 7** | Milestone 7 (M7) | Deterministic Weekly Meal Planner & Shopping List Aggregation | FR-050–FR-054, FR-060–FR-062, NFR-004, Sec 8.6–8.7, 11.8–11.9 |
| **Phase 8** | Milestone 8 (M8) | Mobile-First Frontend PWA Implementation | FR-070, NFR-050–NFR-053, Sec 12 |
| **Phase 9** | Milestone 9 (M9) | System Hardening, Security, E2E Testing, Vision Eval & Docker Packaging | NFR-001, NFR-022, NFR-024, NFR-032, Sec 14, 15, 19 |

---

## 3. Detailed Phase Specifications

### Phase 0: Project Discovery and Setup (Current Phase)
- **Status**: Completed upon review.
- **Objectives**:
  - Inspect the workspace and read complete PRD (`FridgeChef_PRD.md`).
  - Analyze product goals, functional/non-functional requirements, and data relationships.
  - Establish binding repository guardrails (`AGENTS.md`).
  - Document complete requirements analysis (`docs/PRD_ANALYSIS.md`).
  - Define the structured implementation plan (`docs/IMPLEMENTATION_PLAN.md`).
- **Deliverables**:
  - `AGENTS.md`
  - `docs/PRD_ANALYSIS.md`
  - `docs/IMPLEMENTATION_PLAN.md`
- **Acceptance Criteria**:
  - Workspace contains no premature application code, placeholder modules, or unapproved dependencies.
  - Foundational documentation is completely traceable to `FridgeChef_PRD.md`.

---

### Phase 1: Project Scaffolding, Core Infrastructure, DB Schemas & Seed Data (M1)
- **PRD References**: Sections 8.3, 8.4, 8.5, 10, 11.3, 11.11, 13.1, 13.2, 13.3, 13.4, 15.1; FR-040; NFR-020, NFR-026, NFR-027, NFR-040, NFR-042.
- **Prerequisites**: Phase 0 approved.
- **Implementation Tasks**:
  1. Scaffold `api/` directory structure per Section 13.2 with `pyproject.toml` (FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, `pydantic-settings`, PyJWT, Pillow, `groq`, Ruff, mypy, pytest).
  2. Implement configuration management (`app/core/config.py`) using `pydantic-settings` with strict startup validation for required variables (`GROQ_API_KEY`, `DATABASE_URL`, `JWT_SECRET`).
  3. Create standard JSON structured logging (`app/core/logging.py`) with user masking and request correlation IDs.
  4. Create standard exception handlers and error envelope schemas (`app/core/errors.py`) adhering to Section 11.
  5. Setup SQLAlchemy ORM base and models (`app/db/models/`) for all 15 entities defined in Section 10.
  6. Configure Alembic (`alembic.ini`, `migrations/`) and generate initial migration script for all tables and indexes.
  7. Implement catalogue seed data files:
     - `data/ingredients.json` (≥200 canonical Indian ingredients with aliases, categories, units, prices, weights).
     - `data/shelf_life.json` (shelf life days per storage location and opened shelf life).
     - `data/recipes.json` (≥150 curated Indian recipes adhering to Section 8.3).
  8. Implement data validation script `scripts/validate_data.py` (checks referential integrity, step counts 3-12, enum consistency).
  9. Implement database seed service (`app/services/recipe_catalogue.py` and `scripts/seed.py`) with idempotent upserts.
  10. Implement health endpoints: Mandatory endpoints `GET /api/health` (liveness probe per NFR-042 and 15.1) and `GET /api/health/ready` (readiness checking DB and cached Groq models per NFR-042). Implement proposed versioned aliases `GET /api/v1/health` and `GET /api/v1/health/ready` (per Section 11 base path convention, marked as design proposal requiring confirmation).
  11. Implement read-only catalogue endpoints (`app/api/routes/catalogue.py`) per Section 11.3: `GET /api/v1/ingredients?query=&category=&limit=` and `GET /api/v1/recipes/{id}` to verify seed data and support verification autocomplete.
- **Verification & Acceptance Criteria**:
  - `ruff check api/` and `mypy api/app` pass with zero errors.
  - `python api/scripts/validate_data.py` validates `ingredients.json`, `shelf_life.json`, and `recipes.json` with zero errors.
  - Database migrations apply cleanly (`alembic upgrade head`) against PostgreSQL.
  - Startup sequence verifies DB connectivity and seeds data idempotently.
  - Health endpoints respond with 200 OK (`/api/health` and `/api/health/ready`) with expected component statuses.
  - Catalogue endpoints return seeded ingredients and recipes with accurate schemas.

---

### Phase 2: Authentication, Authorization, Account & Preferences (M2)
- **PRD References**: Sections 6.1, 6.2, 7.3, 7.4, 10, 11.1, 11.2, 12.5; FR-001–FR-005, FR-010–FR-011; NFR-021, NFR-023, NFR-030, NFR-032.
- **Prerequisites**: Phase 1 completed and verified.
- **Implementation Tasks**:
  1. Implement password hashing module (`app/core/security.py`) using bcrypt (cost factor 12) or Argon2id.
  2. Implement JWT token issuing, verification, and rotation logic:
     - Access token (60m) stored strictly in client memory.
     - Refresh token (30d) rotated on each use, persisted as SHA-256 hash in `refresh_tokens`.
     - Standard transport is an `httpOnly`, `SameSite=Lax` (or `Strict`), `Secure` cookie with `Path=/api/v1/auth`, accompanied by CSRF protection.
     - Server settings explicitly configure and validate the active transport (`AUTH_REFRESH_TRANSPORT=cookie` by default). An alternative request-body transport is supported strictly for topologies where cookie setup is genuinely infeasible, with documented trade-offs. The server enforces the configured transport rather than silently accepting both transports simultaneously.
     - Note: The specification conflict between Section 11.1 (request body `{refresh_token}`) and Section 12.5 (`httpOnly` cookie) is an unresolved contract issue flagged for user confirmation prior to implementation.
  3. Implement login attempt rate limiter (10 attempts / 15 minutes per email & IP) using sliding window.
  4. Implement authentication routers (`app/api/routes/auth.py`):
     - `POST /api/v1/auth/register` (unique case-insensitive email, password requirements, auto-creates default `user_preferences`).
     - `POST /api/v1/auth/login` (verifies credentials, issues tokens via configured transport).
     - `POST /api/v1/auth/refresh` (receives token via configured transport; rotates token; invalidates old token; enforces CSRF protection).
     - `POST /api/v1/auth/logout` (receives token via configured transport; revokes refresh token).
  5. Implement user account and preferences routers (`app/api/routes/me.py`):
     - `GET /api/v1/me` (returns profile and current preferences).
     - `PUT /api/v1/me/preferences` (updates preferences and increments preferences version).
     - `GET /api/v1/me/export` (exports all personal data as JSON).
     - `DELETE /api/v1/me` (requires password verification; schedules account purge, deletes images).
  6. Implement authentication dependency (`app/api/deps.py`) enforcing token verification and injecting authenticated `user_id`.
- **Verification & Acceptance Criteria**:
  - Automated tests covering register, login, refresh rotation, logout revocation, and rate limiting.
  - Cross-user access authorization tests proving that User A cannot read or mutate User B's preferences or profile.
  - Password complexity validation enforced (min 8 chars, 1 letter, 1 digit).
  - Configured refresh transport verified with CSRF protections; unauthorized alternative transports rejected.

---

### Phase 3: Freshness Engine, Inventory CRUD & Waste Logging (M3)
- **PRD References**: Sections 6.4, 6.8, 8.1, 8.5, 8.8, 10, 11.5; FR-030–FR-034, FR-071; NFR-012.
- **Prerequisites**: Phase 2 completed and verified.
- **Implementation Tasks**:
  1. Implement deterministic freshness engine (`app/services/freshness.py`):
     - Calculate `days_left` from `shelf_life` table, taking into account `storage`, `added_on`, and `opened_on`.
     - Classify status: `USE_FIRST` (≤1d), `USE_SOON` (2-3d), `SAFE` (≥4d).
     - Reject non-applicable storage locations at creation/update.
  2. Implement unit conversion engine (`app/services/units.py`) supporting base units (`g`, `ml`, `piece`) using catalogue conversion factors.
  3. Implement inventory routers (`app/api/routes/inventory.py`):
     - `GET /api/v1/inventory` (filtering by status/storage, sorting by expiry, computed days left).
     - `POST /api/v1/inventory` (creates item with freshness calculation).
     - `PATCH /api/v1/inventory/{id}` (updates quantity, storage, opened date; recalculates freshness).
     - `POST /api/v1/inventory/{id}/use` (reduces quantity, archives if 0; logs `USED_BEFORE_EXPIRY` if item was expiring).
     - `POST /api/v1/inventory/{id}/waste` (archives or decrements item; writes `WASTED` entry in `waste_log`).
     - `DELETE /api/v1/inventory/{id}` (deletes item).
  4. Implement impact calculation service (`app/services/impact.py`) computing waste prevented (kg), food wasted (kg), and money saved (INR) using price/weight catalogue tables.
- **Verification & Acceptance Criteria**:
  - Unit tests covering all freshness boundary conditions (days 0, 1, 2, 3, 4, 365+).
  - Unit tests covering unit conversion and invalid conversion rejection.
  - Integration tests verifying inventory CRUD, decrementing, and proper atomic transactions for `waste_log` creation.
  - Minimum 85% line coverage on `app/services/freshness.py` and `app/services/units.py`.

---

### Phase 4: Media Pipeline, Groq Vision Integration & Scan Verification Flow (M4)
- **PRD References**: Sections 6.3, 7.3, 7.4, 8.4, 9.1, 9.2, 9.3, 10, 11.4; FR-020–FR-029; NFR-002, NFR-010, NFR-028, NFR-031; NFR-041.
- **Prerequisites**: Phase 3 completed and verified.
- **Implementation Tasks**:
  1. Implement image processing pipeline (`app/media/image_pipeline.py`):
     - Validate MIME types (JPEG, PNG, WEBP, HEIC) and max size (8MB).
     - Decode with Pillow (verify real image).
     - Strip all EXIF metadata.
     - Resize to max 1600px long edge and re-encode to JPEG q85 (≤4MB).
     - Securely store resized copy in `UPLOAD_DIR` (outside web root).
  2. Implement ingredient normalisation service (`app/services/normalise.py`):
     - Match detected names against canonical aliases (case-insensitive, ignore punctuation/plurals).
     - Fuzzy matching fallback (Levenshtein distance ≤2 on names 5+ chars).
     - Return `canonical_id: null` if unmapped.
  3. Implement Groq client wrapper (`app/llm/client.py`) with 20s timeout, exponential backoff retries, and token usage recording in `llm_calls`.
  4. Implement vision service (`app/llm/vision.py` and prompt `app/llm/prompts/vision_v1.py`):
     - System prompt and schema enforcement per Section 9.3.
     - Single retry with error correction on schema violation.
     - Fallback to `VISION_UNAVAILABLE` (HTTP 502) on failure.
  5. Implement scan routers (`app/api/routes/scans.py`):
     - `POST /api/v1/scans` (ingests image, calls Groq vision, creates `scan_sessions` with 30m expiry).
     - `GET /api/v1/scans/{scan_id}` (retrieves session candidates for owner).
     - `POST /api/v1/scans/{scan_id}/confirm` (user confirms items; writes to `inventory_items`; rejects null canonical IDs).
     - `DELETE /api/v1/scans/{scan_id}` (discards session and deletes image immediately).
  6. Implement background cleanup task for expired scan sessions and original images.
- **Verification & Acceptance Criteria**:
  - Unit tests for EXIF stripping (verifying GPS removal) and image resizing.
  - Normalization tests verifying exact alias hits, fuzzy hits, and unmapped rejections.
  - Integration tests with mocked Groq client validating successful candidate creation, retry logic, and 502 fallback.
  - Rate limiting tests: 20 scans per day per user enforced with HTTP 429.

---

### Phase 5: Deterministic Recipe Recommendation Engine & Caching (M5)
- **PRD References**: Sections 6.5, 7.1, 7.2, 8.2, 10, 11.6, 11.7; FR-043–FR-046; NFR-003, NFR-011.
- **Prerequisites**: Phase 4 completed and verified.
- **Implementation Tasks**:
  1. Implement deterministic recipe scoring service (`app/services/scoring.py`):
     - Compute coverage, urgency, quantity fit, preference, and time fit per Section 8.2.
     - Apply hard exclusion filters (allergies, avoided items, diet violations, time > 2x max, coverage < 0.40).
     - Deterministic tie-breaking (coverage, cooking time, recipe ID alphabetically).
  2. Implement recommendation reason generator using deterministic string templates (no LLM).
  3. Implement recommendation caching mechanism (`recommendation_cache` table) with 30m TTL keyed by `(user_id, hash(inventory_snapshot, preferences_version))`.
  4. Invalidate cache on any inventory mutation or preference update.
  5. Implement recommendation routers (`app/api/routes/recommendations.py`):
     - `GET /api/v1/recommendations` (returns top 5 ranked recipes with match %, expiring items, missing items with cost).
  6. Implement recipe cooking action (`app/api/routes/recipes.py`):
     - `POST /api/v1/recipes/{id}/cooked` (decrements inventory quantities scaled to servings; logs cooking event and waste prevention).
- **Verification & Acceptance Criteria**:
  - Algorithmic unit tests verifying exact score calculation, component weights, determinism, and hard filter eliminations.
  - Cache hit/miss integration tests confirming invalidation on inventory changes.
  - Integration test for `POST /recipes/{id}/cooked` confirming atomic inventory decrements and `waste_log` entries.
  - Minimum 85% line coverage on `app/services/scoring.py`.

---

### Phase 6: AI Recipe Generation Fallback & Budget Controls (M6)
- **PRD References**: Sections 6.5, 7.5, 9.4, 9.5, 9.6, 10; FR-041, FR-042; NFR-041.
- **Prerequisites**: Phase 5 completed and verified.
- **Implementation Tasks**:
  1. Implement AI recipe generation pipeline (`app/llm/recipe_gen.py` and `app/llm/prompts/recipes_v1.py`):
     - Triggered only when curated recipes matching ≥40% coverage are fewer than 5.
     - Input includes user diet, allergies, spice level, cuisines, max cooking time, available ingredients.
     - Prompt instructs strict JSON output conforming to recipe schema with canonical IDs selected only from provided catalogue.
  2. Server-side validation of generated recipes (validate schema, discard recipes with unknown canonical IDs, verify diet/allergy constraints).
  3. Persist valid generated recipes with `source = 'AI'` and `status = 'PENDING_REVIEW'`.
  4. Implement monthly LLM budget cap tracking (`LLM_MONTHLY_BUDGET_USD`):
     - Sum token costs in `llm_calls` for current month.
     - If spend exceeds 80% of budget, disable AI recipe generation and serve curated recipes only with warning log.
  5. Cache AI generation results for 30 minutes.
- **Verification & Acceptance Criteria**:
  - Mock integration tests validating the trigger threshold (<5 curated recipes at ≥40%).
  - Validation tests rejecting malformed AI recipes or recipes introducing unmapped ingredients.
  - Budget cap tests confirming automatic fallback when monthly spending threshold is reached.

---

### Phase 7: Deterministic Weekly Meal Planner & Shopping List Aggregation (M7)
- **PRD References**: Sections 6.6, 6.7, 7.1, 8.6, 8.7, 10, 11.8, 11.9; FR-050–FR-054, FR-060–FR-062; NFR-004.
- **Prerequisites**: Phase 6 completed and verified.
- **Implementation Tasks**:
  1. Implement deterministic weekly meal planner service (`app/services/planner.py`):
     - Greedy lookahead algorithm across 7 days × 2 meals (14 slots).
     - Filter candidates using Section 8.2 hard filters.
     - Enforce repetition constraints: no recipe >2 times per week; no recipe on consecutive meals.
     - Simulate inventory consumption across slots.
     - Set `low_variety = true` if candidates < 14 and repetition rules relaxed.
  2. Implement single-slot regeneration preserving locked and unmodified slots.
  3. Implement shopping list aggregation service (`app/services/shopping.py`):
     - Sum required ingredients from plan or recipe selection.
     - Subtract inventory snapshot (floored at 0).
     - Group missing items by category and sort alphabetically.
     - Attach estimated cost using catalogue price table.
  4. Implement meal plan and shopping list routers (`app/api/routes/meal_plans.py` and `shopping.py`):
     - `POST /api/v1/meal-plans`, `GET /api/v1/meal-plans/active`, `GET /api/v1/meal-plans/{id}` (owner only), `POST /api/v1/meal-plans/{id}/slots/{day}/{meal}/regenerate`, `DELETE /api/v1/meal-plans/{id}` (archives plan).
     - `POST /api/v1/shopping-lists`, `GET /api/v1/shopping-lists/{id}`, `PATCH /api/v1/shopping-lists/{id}/items/{canonical_id}` (tick bought, add to inventory).
  5. Implement dashboard router (`app/api/routes/dashboard.py`) synthesizing status counts, recommendations summary (parameterized via `DASHBOARD_RECOMMENDATIONS_LIMIT`, addressing the unresolved PRD conflict between 5 recs per Sec 5.4/FR-070 vs 3 recs per Sec 11.10/12.3, pending product clarification prior to phase), active plan, and impact figures.
- **Verification & Acceptance Criteria**:
  - Unit tests verifying meal planner constraints (max 2 repeats, no consecutive repeats).
  - Slot regeneration tests confirming all other slots remain fixed.
  - Shopping list tests verifying correct inventory subtraction, grouping, and cost estimation.
  - Response time for plan generation <10s P95.

---

### Phase 8: Mobile-First Frontend PWA Implementation (M8)
- **PRD References**: Sections 5, 7.6, 11, 12.1–12.6; NFR-050–NFR-053; FR-070.
- **Prerequisites**: Phase 7 completed and verified (API endpoints stable).
- **Implementation Tasks**:
  1. Scaffold `web/` application using React 18, TypeScript, Vite, Tailwind CSS v3, and React Router v6.
  2. Setup API client with TanStack Query and Zod schema validation matching backend OpenAPI contract.
  3. Implement auth handling:
     - Access token stored in client memory.
     - Refresh token managed via `httpOnly` cookie set by the API by default.
     - Alternative transport (sessionStorage + request body) supported strictly when deployment topology genuinely precludes cookies, with the security trade-off documented (PRD Section 12.5). Prohibit sessionStorage as a plain-HTTP LAN testing shortcut.
     - Automatic 401 refresh interception, then redirect to login.
  4. Implement mobile-first navigation shell: bottom navigation bar (Home, Inventory, Scan, Recipes, Plan) and top bar (Shopping, Settings).
  5. Implement screens (Section 12.3):
     - Auth: Login, Register.
     - Onboarding: 3-step wizard (household & diet, cuisines & spice, allergies & cooking time).
     - Dashboard: freshness summary badges, recommendations summary card (displaying count according to product-clarified `DASHBOARD_RECOMMENDATIONS_LIMIT`), active plan summary, month-to-date impact card.
     - Scan & Camera: input with `accept="image/*" capture="environment"`, progress state ("Looking at your fridge…"), error handling.
     - Verify Candidates: editable checklist, confidence badges, canonical search autocomplete, manual item entry, save to inventory.
     - Inventory: filter tabs (`All`, `USE_FIRST`, `USE_SOON`, `SAFE`), search, item use/waste actions, edit dates.
     - Recommendations & Recipe Detail: filterable recommendations list, recipe modal with servings stepper, step checklist, nutrition estimate badge, "Cooked this" action.
     - Meal Plan: 7-day grid, slot regenerate button, lock toggles, waste prevented metric.
     - Shopping List: grouped categories, bought checkmarks, auto-add to inventory prompt.
     - Settings: preferences editor, data export, account deletion.
  6. Implement PWA manifest and service worker shell caching via `vite-plugin-pwa`.
  7. Implement UX safeguards: `visualViewport` responsive sticky footers for virtual keyboard compatibility; minimum 44x44px touch targets; WCAG 2.1 AA contrast compliance.
- **Verification & Acceptance Criteria**:
  - `npm run lint`, `npm run typecheck`, and `npm run test` pass with zero errors.
  - Mobile viewport responsiveness verified at 360px width.
  - Vitest component tests covering verification screen, inventory filtering, servings scaling, and auth state.
  - Complete user flow runnable against mock or local API.

---

### Phase 9: System Hardening, Security, E2E Testing, Vision Eval & Docker Packaging (M9)
- **PRD References**: Sections 7.1–7.5, 14, 15, 19; NFR-001–NFR-042.
- **Prerequisites**: Phase 8 completed and verified.
- **Implementation Tasks**:
  1. Implement rate limiting middleware with sliding windows:
     - 20 scans per day per user.
     - 60 recommendation requests per hour per user.
     - 200 general requests per minute.
  2. Implement contract testing suite ensuring frontend Zod schemas and backend Pydantic models remain in sync.
  3. Implement Playwright E2E test suite covering full user journey at 360x800 and 1280x800:
     - Register → Onboard → Scan (fixture) → Verify → Inventory → Recipe Detail → Cook → Plan → Shopping List.
  4. Implement vision evaluation harness (`api/tests/eval/`) with 40+ labeled test images:
     - Measure precision and recall on the 30 common Indian ingredients (target: precision ≥0.80, recall ≥0.60).
  5. Conduct load performance test with k6/Locust (100 concurrent users, NFR-001 latency verification).
  6. Build production multi-stage Dockerfiles:
     - `api`: Python 3.11 slim, non-root user, Gunicorn + Uvicorn workers, healthcheck.
     - `web`: Node 20 build stage, Nginx alpine runtime proxying `/api/` to `api`.
  7. Finalize `docker-compose.yml` and production configuration documentation.
- **Verification & Acceptance Criteria**:
  - All unit, integration, contract, and Playwright E2E tests pass.
  - Vision evaluation meets PRD targets (precision ≥0.80, recall ≥0.60).
  - Multi-container stack boots cleanly from `docker compose up --build` with automatic migration and seed loading.
  - All 10 MVP Definition of Done criteria in PRD Section 19 verified.

---

## 4. Phase Verification & Approval Protocol

Before any phase is declared complete:
1. Run linting and static analysis:
   - Backend: `ruff check api/`, `mypy api/app`
   - Frontend: `npm run lint`, `npm run typecheck`
2. Run automated test suites:
   - Backend: `pytest`
   - Frontend: `npm run test`
3. Document executed commands, test outputs, and coverage figures honestly.
4. Stop execution and submit the phase completion report for review before proceeding to the subsequent phase.
