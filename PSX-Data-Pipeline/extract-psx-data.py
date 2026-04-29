import logging
import logging.handlers
import os
import re
import subprocess
import psycopg2
import requests
import schedule
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from psycopg2.extras import execute_values


load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

# ── Logging setup ─────────────────────────────────────────────────────────────
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_LOG_DIR  = os.path.join(_BASE_DIR, "logs")
os.makedirs(_LOG_DIR, exist_ok=True)

_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
_level      = getattr(logging, _level_name, logging.INFO)

_fmt_full = logging.Formatter(
    fmt="%(asctime)s [%(levelname)-5s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_fmt_console = logging.Formatter(
    fmt="%(asctime)s [%(levelname)-5s] %(message)s",
    datefmt="%H:%M:%S",
)

# File handler — rolls at midnight, keeps 30 days, suffix = YYYY-MM-DD
_file_handler = logging.handlers.TimedRotatingFileHandler(
    filename=os.path.join(_LOG_DIR, "psx_pipeline.log"),
    when="midnight",
    interval=1,
    backupCount=30,
    encoding="utf-8",
    utc=False,
)
_file_handler.suffix = "%Y-%m-%d"
_file_handler.setLevel(_level)
_file_handler.setFormatter(_fmt_full)

# Console handler — respects LOG_LEVEL
_console_handler = logging.StreamHandler()
_console_handler.setLevel(_level)
_console_handler.setFormatter(_fmt_console)

logging.root.setLevel(logging.DEBUG)
logging.root.addHandler(_file_handler)
logging.root.addHandler(_console_handler)

log = logging.getLogger("psx")
log.info("[INIT] Log level=%s  log_dir=%s", _level_name, _LOG_DIR)

TABLE_NAME = "PsxAllShr"


# ── DB helpers ────────────────────────────────────────────────────────────────

def parse_connection_string(conn_str):
    params = {}
    for part in conn_str.strip('"').split(";"):
        part = part.strip()
        if "=" in part:
            key, val = part.split("=", 1)
            params[key.strip().lower()] = val.strip()
    return {
        "host":     params.get("host"),
        "dbname":   params.get("database"),
        "user":     params.get("username"),
        "password": params.get("password"),
        "sslmode":  "require" if "require" in params.get("channel binding", "").lower() else "prefer",
    }


def get_connection():
    raw = os.getenv("Postgresql_Connection", "")
    if not raw:
        raise RuntimeError("Postgresql_Connection not found in .env")

    kwargs = parse_connection_string(raw)
    log.info("[DB] Connecting  host=%s  db=%s  user=%s  sslmode=%s",
             kwargs["host"], kwargs["dbname"], kwargs["user"], kwargs["sslmode"])

    conn = psycopg2.connect(**kwargs)
    conn.autocommit = False

    with conn.cursor() as cur:
        cur.execute("SELECT version(), current_database(), current_user, current_schema()")
        ver, db, user, schema = cur.fetchone()
        log.info("[DB] Connected successfully")
        log.debug("[DB]   server=%s", ver.split(",")[0])
        log.debug("[DB]   database=%s  user=%s  default_schema=%s", db, user, schema)

        cur.execute("SHOW search_path")
        log.debug("[DB]   search_path=%s", cur.fetchone()[0])

    return conn


# ── Column helpers ────────────────────────────────────────────────────────────

def sanitize_column(name):
    col = re.sub(r"[^\w]", "_", name.lower().strip())
    col = re.sub(r"_+", "_", col).strip("_")
    return col or "col"


def deduplicate_columns(names):
    seen = {}
    result = []
    for name in names:
        if name in seen:
            seen[name] += 1
            result.append(f"{name}_{seen[name]}")
        else:
            seen[name] = 0
            result.append(name)
    return result


# ── Table management ──────────────────────────────────────────────────────────

def ensure_table(conn, columns):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_name = %s
        """, (TABLE_NAME,))
        existing = cur.fetchall()
        if existing:
            log.info("[TABLE] Already exists in schema: %s", existing[0][0])
            log.debug("[TABLE]   full entry: %s", existing)
        else:
            log.info("[TABLE] Does not exist yet, will CREATE")

        col_defs   = ", ".join(f'"{c}" TEXT' for c in columns)
        create_sql = f"""
            CREATE TABLE IF NOT EXISTS "{TABLE_NAME}" (
                id         SERIAL PRIMARY KEY,
                fetched_at DATE DEFAULT CURRENT_DATE,
                {col_defs}
            )
        """
        log.debug("[TABLE] CREATE SQL:\n%s", create_sql.strip())
        cur.execute(create_sql)
        log.info("[TABLE] CREATE TABLE executed (no error)")

        cur.execute("""
            SELECT table_schema, table_name, table_type
            FROM information_schema.tables
            WHERE table_name = %s
        """, (TABLE_NAME,))
        log.debug("[TABLE] Post-CREATE visibility (same txn): %s", cur.fetchall())

        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (TABLE_NAME,))
        cols = cur.fetchall()
        log.debug("[TABLE] Columns (%d): %s", len(cols), [c[0] for c in cols])


# ── Main pipeline ─────────────────────────────────────────────────────────────

def fetch_and_push():
    log.info("=" * 60)
    log.info("[RUN] Fetch cycle started")

    # ── 1. Scrape ──────────────────────────────────────────────────────────
    log.info("[SCRAPE] Requesting PSX KMIALLSHR page...")
    try:
        response = requests.get(
            "https://dps.psx.com.pk/indices/KMIALLSHR",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Referer": "https://dps.psx.com.pk/",
            },
            timeout=15,
        )
        log.info("[SCRAPE] HTTP %s", response.status_code)
        log.debug("[SCRAPE]   content-length=%d bytes", len(response.content))
    except requests.RequestException as exc:
        log.error("[SCRAPE] HTTP request failed: %s", exc)
        return

    if response.status_code != 200:
        log.error("[SCRAPE] Non-200 status, aborting")
        return

    # ── 2. Parse ───────────────────────────────────────────────────────────
    log.info("[PARSE] Parsing HTML...")
    soup  = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table")
    if not table:
        log.error("[PARSE] No <table> element found in page")
        return
    log.debug("[PARSE] Found <table> element")

    headers = []
    thead   = table.find("thead")
    if thead:
        headers = [th.get_text(strip=True) for th in thead.find_all("th")]
    log.debug("[PARSE] Raw headers (%d): %s", len(headers), headers)

    rows  = []
    tbody = table.find("tbody")
    if tbody:
        for tr in tbody.find_all("tr"):
            row = [td.get_text(separator=" ", strip=True) for td in tr.find_all("td")]
            if any(cell for cell in row):
                rows.append(row)
    log.info("[PARSE] Extracted %d rows, %d columns", len(rows), len(headers))

    if not headers or not rows:
        log.error("[PARSE] Aborting — headers=%d rows=%d", len(headers), len(rows))
        return

    columns = deduplicate_columns([sanitize_column(h) for h in headers])
    log.debug("[PARSE] Sanitised columns: %s", columns)

    if log.isEnabledFor(logging.DEBUG):
        for i, row in enumerate(rows):
            log.debug("[PARSE] Row %03d: %s", i + 1, dict(zip(columns, row)))

    # ── 3. Connect ─────────────────────────────────────────────────────────
    log.info("[DB] Opening connection...")
    try:
        conn = get_connection()
    except Exception as exc:
        log.error("[DB] Connection failed: %s", exc)
        return

    # ── 4. Ensure table ────────────────────────────────────────────────────
    log.info("[TABLE] Ensuring table exists...")
    try:
        ensure_table(conn, columns)
    except Exception as exc:
        log.error("[TABLE] ensure_table failed: %s", exc)
        conn.rollback()
        conn.close()
        return

    # ── 5. Insert ──────────────────────────────────────────────────────────
    log.info("[INSERT] Inserting %d rows into \"%s\"...", len(rows), TABLE_NAME)
    values = [
        tuple(row[i] if i < len(row) else None for i in range(len(columns)))
        for row in rows
    ]
    log.debug("[INSERT] First tuple: %s", values[0] if values else "—")
    log.debug("[INSERT] Last  tuple: %s", values[-1] if values else "—")

    col_list   = ", ".join(f'"{c}"' for c in columns)
    insert_sql = f'INSERT INTO "{TABLE_NAME}" ({col_list}) VALUES %s ON CONFLICT DO NOTHING'
    log.debug("[INSERT] SQL template: %s", insert_sql)

    try:
        with conn.cursor() as cur:
            execute_values(cur, insert_sql, values)
            log.debug("[INSERT] execute_values done — cursor.rowcount=%s", cur.rowcount)

            cur.execute(f'SELECT COUNT(*) FROM "{TABLE_NAME}"')
            log.debug("[INSERT] Row count inside txn (pre-commit): %d", cur.fetchone()[0])

    except Exception as exc:
        log.error("[INSERT] execute_values failed: %s", exc)
        conn.rollback()
        log.warning("[INSERT] Transaction rolled back")
        conn.close()
        return

    # ── 6. Commit ──────────────────────────────────────────────────────────
    log.info("[COMMIT] Committing transaction...")
    try:
        conn.commit()
        log.info("[COMMIT] commit() returned successfully")
    except Exception as exc:
        log.error("[COMMIT] commit() raised: %s", exc)
        conn.close()
        return

    # ── 7. Verify after commit ─────────────────────────────────────────────
    try:
        with conn.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{TABLE_NAME}"')
            log.info("[VERIFY] Total rows in table after commit: %d", cur.fetchone()[0])

            cur.execute(f'SELECT * FROM "{TABLE_NAME}" ORDER BY id DESC LIMIT 3')
            log.debug("[VERIFY] Last 3 rows: %s", cur.fetchall())
    except Exception as exc:
        log.error("[VERIFY] Post-commit check failed: %s", exc)

    conn.close()
    log.debug("[DB] Connection closed")
    log.info("[RUN] Cycle complete — inserted %d rows into \"%s\"", len(rows), TABLE_NAME)
    log.info("=" * 60)


def run_dbt():
    log.info("[DBT] Starting dbt run...")
    dbt_project_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "psx_analytics")
    dbt_executable = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".venv", "Scripts", "dbt.exe")
    
    try:
        result = subprocess.run(
            [dbt_executable, "run", "--project-dir", dbt_project_path, "--profiles-dir", os.path.expanduser("~/.dbt")],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            log.info("[DBT] dbt run completed successfully")
            log.debug("[DBT] Output: %s", result.stdout)
        else:
            log.error("[DBT] dbt run failed: %s", result.stderr)
    except Exception as exc:
        log.error("[DBT] Failed to execute dbt: %s", exc)


# ── Entry point ───────────────────────────────────────────────────────────────

fetch_and_push()
run_dbt()