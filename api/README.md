# FridgeChef AI — Backend API (`api/`)

Backend REST API for FridgeChef AI, built with FastAPI, SQLAlchemy 2.x, PostgreSQL 16, and Pydantic v2.

---

## 1. Prerequisites

- Python 3.10+ (Python 3.11+ recommended)
- PostgreSQL 16 running locally on port 5432 (or via Docker Compose)

---

## 2. Environment Setup

1. **Create virtual environment**:
   ```bash
   cd api
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # Linux/macOS
   source .venv/bin/activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -e ".[dev]"
   ```

3. **Configure environment**:
   Copy `.env.example` to `.env`:
   ```bash
   copy .env.example .env
   ```
   Ensure `DATABASE_URL` points to your PostgreSQL instance (e.g., `postgresql+psycopg://postgres:postgres@localhost:5432/fridgechef`).

---

## 3. Database & Migrations

1. **Create database** (if not already created):
   ```sql
   CREATE DATABASE fridgechef;
   ```

2. **Run Alembic migrations**:
   ```bash
   alembic upgrade head
   ```

3. **Seed canonical ingredients and recipes**:
   ```bash
   python scripts/seed.py
   ```

---

## 4. Seed Data Validation

Verify data integrity, schema rules, and PRD quotas:
```bash
python scripts/validate_data.py
```

---

## 5. Running the API

Start development server with live reload:
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Interactive API documentation:
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

Health Probes:
- Liveness: `GET http://localhost:8000/health`
- Readiness: `GET http://localhost:8000/health/ready`

---

## 6. Running Tests & Quality Checks

- **Run test suite**:
  ```bash
  pytest
  ```

- **Run linter**:
  ```bash
  ruff check .
  ```

- **Run type checker**:
  ```bash
  mypy app
  ```
