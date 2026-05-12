"""Audit trail — logs every interaction and tracks ROI metrics."""

import sqlite3, os
DB_PATH = os.environ.get("DATABASE_PATH", "sales_agent.db")

def _conn():
    c = sqlite3.connect(DB_PATH); c.row_factory = sqlite3.Row; return c

def init_db():
    with _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, skill_id TEXT,
            input_summary TEXT, output TEXT, created_at TEXT DEFAULT (datetime('now')))""")
        c.execute("""CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT, metric_key TEXT UNIQUE,
            metric_value INTEGER DEFAULT 0, updated_at TEXT DEFAULT (datetime('now')))""")
        c.execute("""CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, name TEXT, company TEXT,
            score INTEGER DEFAULT 0, tier TEXT, status TEXT DEFAULT 'new',
            hubspot_id TEXT, notes TEXT, created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')))""")

def log_interaction(session_id: str, skill_id: str, user_input: str, output: str):
    with _conn() as c:
        c.execute("INSERT INTO audit_log (session_id,skill_id,input_summary,output) VALUES (?,?,?,?)",
                  (session_id, skill_id, user_input[:300], output))
        for key in (f"count_{skill_id}", "total"):
            c.execute("INSERT INTO metrics (metric_key,metric_value) VALUES (?,1) ON CONFLICT(metric_key) DO UPDATE SET metric_value=metric_value+1", (key,))

def is_already_qualified(hubspot_id: str) -> bool:
    """Returns True if this HubSpot contact has already been qualified."""
    if not hubspot_id:
        return False
    with _conn() as c:
        row = c.execute("SELECT 1 FROM leads WHERE hubspot_id=? LIMIT 1", (hubspot_id,)).fetchone()
        return row is not None


def save_lead(email: str, name: str, company: str, score: int, tier: str, hubspot_id: str = "", notes: str = ""):
    with _conn() as c:
        c.execute("""INSERT INTO leads (email,name,company,score,tier,hubspot_id,notes)
            VALUES (?,?,?,?,?,?,?) ON CONFLICT DO NOTHING""", (email, name, company, score, tier, hubspot_id, notes))

def get_leads(limit: int = 50, tier: str = None) -> list[dict]:
    with _conn() as c:
        if tier:
            rows = c.execute("SELECT * FROM leads WHERE tier=? ORDER BY score DESC, created_at DESC LIMIT ?", (tier, limit)).fetchall()
        else:
            rows = c.execute("SELECT * FROM leads ORDER BY score DESC, created_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]

def get_audit_log(limit: int = 50) -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]

def get_metrics() -> dict:
    with _conn() as c:
        rows = c.execute("SELECT metric_key,metric_value FROM metrics").fetchall()
    return {r["metric_key"]: r["metric_value"] for r in rows}
