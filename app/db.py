"""Load the supplied NovaMart public dataset into an in-memory SQLite database.
The loader adapts the real CSV/JSON/Markdown files to stable internal tables.
"""
import json
import os
import re
import sqlite3
from pathlib import Path
import pandas as pd
from .config import DATA_DIR, FILES, POLICY_DIR, PRODUCT_DOC_DIR

_conn = None

def _read_conversations(path: str) -> pd.DataFrame:
    raw = json.load(open(path, encoding="utf-8"))
    rows = []
    for conv in raw:
        messages = conv.get("messages") or []
        rows.append({
            "conversation_id": conv.get("conversation_id"),
            "customer_id": conv.get("customer_id"),
            "order_id": conv.get("order_id"),
            "ticket_id": conv.get("ticket_id"),
            "channel": conv.get("channel"),
            "language": conv.get("language"),
            "started_at": conv.get("started_at"),
            "status": conv.get("status"),
            "handled_by": conv.get("handled_by"),
            "messages_json": json.dumps(messages, ensure_ascii=False),
            "transcript": "\n".join(f"{m.get('role','')}: {m.get('message','')}" for m in messages),
        })
    return pd.DataFrame(rows)

def _policy_value(text: str, label: str):
    pat = rf"\|\s*\*{{0,2}}{re.escape(label)}\*{{0,2}}\s*\|\s*\*{{0,2}}([^|\n]+?)\*{{0,2}}\s*\|"
    m = re.search(pat, text, re.I)
    return m.group(1).strip() if m else None


def _load_policies(conn):
    rows = []
    policy_files = sorted(Path(POLICY_DIR).glob("*.md"))
    for path in policy_files:
        text = path.read_text(encoding="utf-8")
        version = _policy_value(text, "Version") or ("v2" if "_v2" in path.name else "v1" if "_v1" in path.name else "1.0")
        version = version.split(" ")[0]
        effective = _policy_value(text, "Effective date") or "2026-01-01"
        if "refund_policy_v1" in path.name:
            rows.append({"policy_name":"refund", "version":"v1", "effective_from":effective, "status":"active", "change_window_days":10, "defect_window_days":15, "approval_threshold":100000, "restocking_pct":0, "restocking_categories":""})
        elif "refund_policy_v2" in path.name:
            rows.append({"policy_name":"refund", "version":"v2", "effective_from":effective, "status":"active", "change_window_days":7, "defect_window_days":10, "approval_threshold":75000, "restocking_pct":5, "restocking_categories":"Laptops,Tablets,Cameras,Monitors"})
        else:
            rows.append({"policy_name":path.stem, "version":version, "effective_from":effective, "status":"active", "document":text})
    pd.DataFrame(rows).to_sql("policies", conn, index=False, if_exists="replace")


def _load_product_specs(conn):
    rows = []
    for path in Path(PRODUCT_DOC_DIR).glob("*.md"):
        rows.append({"category": path.stem, "content": path.read_text(encoding="utf-8")})
    pd.DataFrame(rows).to_sql("product_specs", conn, index=False, if_exists="replace")


def get_db() -> sqlite3.Connection:
    global _conn
    if _conn is not None:
        return _conn
    _conn = sqlite3.connect(":memory:", check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    for table, fname in FILES.items():
        path = os.path.join(DATA_DIR, fname)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Dataset file missing: {path}")
        if fname.endswith(".json"):
            df = _read_conversations(path)
        else:
            df = pd.read_csv(path)
        df.to_sql(table, _conn, index=False, if_exists="replace")
    _load_policies(_conn)
    _load_product_specs(_conn)
    _conn.execute("CREATE TABLE IF NOT EXISTS refunds(refund_id TEXT, order_id TEXT, customer_id TEXT, amount REAL, created_at TEXT)")
    _conn.execute("CREATE TABLE IF NOT EXISTS returns(return_id TEXT, order_id TEXT, customer_id TEXT, reason TEXT, created_at TEXT)")
    _conn.execute("CREATE TABLE IF NOT EXISTS new_tickets(ticket_id TEXT, customer_id TEXT, order_id TEXT, kind TEXT, summary TEXT, created_at TEXT)")
    return _conn

def q(sql: str, args=()):
    return [dict(r) for r in get_db().execute(sql, args).fetchall()]
