# FridgeChef AI — Agent Implementation Guidelines & Repository Guardrails

This document establishes the binding operational rules, architectural constraints, and engineering standards for all AI coding agents working on the FridgeChef repository.

All agents must strictly adhere to these guidelines across all implementation phases.

---

## 1. Core Operating Principles

1. **The PRD is the Single Source of Truth**
   - The primary reference for all product logic, schemas, algorithms, and contracts is [`FridgeChef_PRD.md`](file:///c:/Users/chara/Desktop/Fridge%20project/FridgeChef_PRD.md).
   - If requirements are ambiguous, contradictory, or underspecified, **stop and report the issue to the user** before making consequential assumptions. Never invent requirements, silently resolve conflicts by picking a favorite interpretation, or expand scope without explicit approval. Unresolved conflicts (such as dashboard count 3 vs 5, and token transport body vs cookie) must be documented and flagged for user clarification before their respective implementation phases.

2. **Phase Boundary Discipline**
   - Work strictly within the current approved implementation phase as defined in [`docs/IMPLEMENTATION_PLAN.md`](file:///c:/Users/chara/Desktop/Fridge%20project/docs/IMPLEMENTATION_PLAN.md).
   - Do not jump ahead, build unrequested features, or introduce premature abstractions.
   - Do not create mock or placeholder implementations simply to create the appearance of progress.

3. **Preservation of Existing Work**
   - Never overwrite user files or delete existing implementation assets without explicit justification and prior user approval.
   - Preserve existing documentation and code comments unless explicitly refactoring.

4. **Lean Dependencies and Clean Architecture**
   - Install only the dependencies explicitly specified in the PRD or directly necessary to satisfy approved requirements.
   - Reject bloat, redundant utility libraries, and unvetted packages.

---

## 2. Security and Privacy Guardrails

1. **Absolute Prohibition on Secret Exposure**
   - Never commit API keys (`GROQ_API_KEY`), database passwords, `JWT_SECRET`, or production credentials to git.
   - All secrets must be loaded via environment variables (`pydantic-settings`).
   - The server must refuse to start if required security variables (`GROQ_API_KEY`, `JWT_SECRET`, `DATABASE_URL`) are missing or insecure.
   - The repository must maintain an accurate `.env.example` with safe placeholder values; `.env` must be in `.gitignore`.

2. **User Data Isolation and Authorization**
   - All database queries and modifications touching user data must be scoped by the authenticated user's ID (`WHERE user_id = :user_id`).
   - Cross-user data leaks are critical security defects. Every protected endpoint must verify authorization before returning or modifying entities.

3. **Media and Storage Privacy**
   - Uploaded fridge/pantry images must be stored outside the web root (`UPLOAD_DIR`).
   - Images must never be served publicly. Access is gated by scan ID through an authenticated endpoint and valid session only.
   - Original upload images must be purged within 24 hours; resized detection images must be deleted immediately upon scan session expiry.
   - EXIF metadata (specifically GPS coordinates and camera fingerprints) must be stripped during ingestion before storage or transmission to third-party APIs.

4. **Structured Logging and Data Masking**
   - Never log passwords, tokens, full image bytes, or complete email addresses.
   - Emails must be masked in logs (e.g., `a***@example.com`).
   - All log output must be structured JSON containing `request_id`, hashed `user_id`, endpoint, status code, latency, and error code.

5. **Token Storage & Transport Configuration**
   - Access tokens must reside strictly in client memory; never persist access tokens in localStorage, sessionStorage, or cookies.
   - The default and standard refresh-token transport is an `httpOnly` cookie set by the API with `Path=/api/v1/auth`, `SameSite=Lax` (or `Strict`), and `Secure` in production, accompanied by CSRF protection.
   - Do not silently authorize unconditional dual acceptance of multiple transports in every deployment. The active refresh transport must be explicitly configured and validated via server settings (`AUTH_REFRESH_TRANSPORT=cookie` by default).
   - An alternative transport (request-body token via `sessionStorage`) is permitted strictly and only when the deployment topology genuinely precludes cookie setup (e.g., decoupled cross-origin topologies unable to share cookies), with the XSS trade-off explicitly documented per PRD Section 12.5.
   - Never use `sessionStorage` as a workaround for plain-HTTP local LAN testing. Testing on mobile phones over LAN plain HTTP is explicitly limited to browsing and manual entry (PRD Section 12.6); camera scanning and PWA features require an HTTPS tunnel or staging deployment.
   - The specification conflict between Section 11.1 (request-body `{refresh_token}`) and Section 12.5 (`httpOnly` cookie) is an unresolved contract decision that requires explicit confirmation prior to Phase 2 implementation.

---

## 3. Technology Stack & Architectural Standards

### 3.1 Backend (`api/`)
- **Runtime & Framework**: Python 3.11+, FastAPI, Uvicorn (Gunicorn with Uvicorn worker in production).
- **Validation**: Pydantic v2 exclusively. Request bodies must forbid unknown fields (`extra="forbid"`).
- **ORM & Migrations**: SQLAlchemy 2.x (async or sync ORM per architecture) with parameterized statements only. String-concatenated SQL queries are strictly prohibited. Database schema changes must use Alembic migrations (no `Base.metadata.create_all` in production).
- **Data Integrity**: Seed files (`data/ingredients.json`, `data/shelf_life.json`, `data/recipes.json`) must pass strict referential integrity validation via `scripts/validate_data.py` (checking canonical references, step bounds 3–12, and enum values) before running seed migrations.
- **Database**: PostgreSQL 16 (production and integration tests). SQLite is permissible strictly for isolated local unit tests.
- **AI Integration**: Official `groq` Python SDK. LLM provider calls must enforce strict timeouts (default 20s), exponential backoff retries, JSON schema enforcement, and cost tracking recorded in `llm_calls`.
- **Media Processing**: Pillow and `pillow-heif` for image validation, EXIF stripping, and standard JPEG re-encoding.
- **Security**: Passwords hashed using bcrypt (cost factor 12) or Argon2id. Tokens managed with PyJWT (access token 60m, refresh token 30d with rotation and DB tracking).

### 3.2 Frontend (`web/`)
- **Runtime & Build**: React 18, TypeScript, Vite.
- **Styling**: Tailwind CSS v3 (designed mobile-first for 360px+ viewport).
- **State Management**: TanStack Query (React Query) for server state; minimal localized client state.
- **Validation**: Zod for runtime validation at the API response boundary.
- **Routing**: React Router v6.
- **PWA Capabilities**: `vite-plugin-pwa` for app shell caching and manifest (no offline API caching).
- **Mobile UX**: Visual-viewport aware footers for virtual keyboards; native file capture `accept="image/*" capture="environment"`; WCAG 2.1 AA compliant color contrast and non-color-only state indicators.

---

## 4. Coding Standards & Error Handling

1. **Type Safety & Static Analysis**
   - Backend: Complete type hints required on all modules in `app/`. Code must pass `mypy --strict` (or configured strictness) and `ruff check`.
   - Frontend: Strict TypeScript (`strict: true` in `tsconfig.json`). No `any` types unless thoroughly justified.

2. **Standard API Envelope**
   - Success responses should follow standardized payloads (or direct schema models) with pagination:
     ```json
     {"items": [...], "next_cursor": "string or null"}
     ```
   - Error responses must strictly adhere to the PRD error envelope (HTTP 4xx/5xx):
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

3. **Domain Logic Determinism**
   - Freshness tracking and shelf-life calculations must follow the deterministic rule formulas in PRD Section 8.1.
   - Recipe ranking must follow the deterministic formula in PRD Section 8.2 (coverage, urgency, quantity fit, preference, time fit).
   - Meal planning must follow the deterministic greedy-lookahead algorithm in PRD Section 8.6.
   - Never delegate deterministic business rules, mathematical calculations, or ranking algorithms to the LLM.

---

## 5. Testing and Verification Protocols

Before declaring any task or phase complete, agents must execute and report the results of all relevant verification checks:

1. **Test Automation Requirements**:
   - Every service, algorithmic component, and endpoint must have corresponding automated tests.
   - Services (`app/services`) and LLM wrappers (`app/llm`) must maintain at least 85% line coverage.
   - Integration tests must verify database transactions, failure fallbacks (Groq outages, rate limits), and image processing.
   - E2E tests (Playwright) must validate critical user journeys at 360x800 and 1280x800 viewports.

2. **Check Execution & Honesty Rule**:
   - **Never claim a check passed if it was not executed.**
   - If a test, lint check, type check, or build fails, document the exact failure output, explain the root cause, and implement the necessary fix.
   - Record actual command invocations and their stdout/stderr summaries in the phase verification report.

3. **Required Verification Suite**:
   - **Backend**:
     - `ruff check .`
     - `mypy app`
     - `pytest`
   - **Frontend**:
     - `npm run lint`
     - `npm run typecheck` (or `tsc --noEmit`)
     - `npm run test`
     - `npm run build`
