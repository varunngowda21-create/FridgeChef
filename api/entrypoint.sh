#!/usr/bin/env sh
set -e

echo "[FridgeChef API] Starting container entrypoint..."

# Wait for PostgreSQL database readiness if DATABASE_URL is defined
if [ -n "$DATABASE_URL" ]; then
    echo "[FridgeChef API] Verifying database connectivity..."
    python - <<'EOF'
import os
import sys
import time
from sqlalchemy import create_engine, text

db_url = os.environ.get("DATABASE_URL", "")
if not db_url:
    sys.exit(0)

display_target = db_url.split("@")[-1] if "@" in db_url else "configured database"
print(f"[FridgeChef API] Waiting for PostgreSQL at {display_target}...")

max_attempts = 30
for attempt in range(1, max_attempts + 1):
    try:
        engine = create_engine(db_url, connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[FridgeChef API] PostgreSQL is ready and accepting connections!")
        sys.exit(0)
    except Exception as exc:
        if attempt % 5 == 0:
            print(f"[FridgeChef API] Still waiting for database (attempt {attempt}/{max_attempts})...")
        time.sleep(1)

print("[FridgeChef API] FATAL: Database check timed out after 30 seconds; aborting startup!", file=sys.stderr)
sys.exit(1)
EOF
fi

# Run Alembic migrations to head
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "[FridgeChef API] Running database migrations (alembic upgrade head)..."
    alembic upgrade head || { echo "[FridgeChef API] FATAL: Alembic database migration failed!" >&2; exit 1; }
    echo "[FridgeChef API] Migrations completed successfully."
fi

# Seed catalogue data idempotently with schema validation (PRD Section 13.4)
if [ "${RUN_SEED:-true}" = "true" ]; then
    echo "[FridgeChef API] Validating seed catalogue schemas (scripts/validate_data.py)..."
    python scripts/validate_data.py || { echo "[FridgeChef API] FATAL: Seed data validation failed!" >&2; exit 1; }
    echo "[FridgeChef API] Seeding catalogue data (scripts/seed.py)..."
    python scripts/seed.py || { echo "[FridgeChef API] FATAL: Database seeding failed!" >&2; exit 1; }
fi

echo "[FridgeChef API] Starting application server: $@"
exec "$@"

