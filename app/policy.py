"""Deterministic policy engine backed by the supplied versioned policy documents."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from .config import TZ_NAME
from .db import q

class PolicyError(Exception):
    pass

def _dt(value):
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    tz = ZoneInfo(TZ_NAME)
    return dt.replace(tzinfo=tz) if dt.tzinfo is None else dt.astimezone(tz)

def get_policy_for_order(order_date: str) -> dict:
    rows = q("SELECT * FROM policies WHERE policy_name='refund'")
    if not rows:
        raise PolicyError("refund policies not loaded")
    placed = _dt(order_date)
    eligible = [r for r in rows if _dt(r["effective_from"]) <= placed]
    if not eligible:
        raise PolicyError("no refund policy applies to this order date")
    eligible.sort(key=lambda r: _dt(r["effective_from"]))
    return eligible[-1]

def get_active_policy() -> dict:
    # Backward-compatible helper: active means latest policy in the supplied dataset.
    rows = q("SELECT * FROM policies WHERE policy_name='refund'")
    if not rows:
        raise PolicyError("refund policies not loaded")
    rows.sort(key=lambda r: _dt(r["effective_from"]))
    return rows[-1]

def refund_window_days(policy: dict, reason: str | None) -> int:
    r = (reason or "change_of_mind").lower()
    if any(x in r for x in ("defect", "dead", "damaged", "damage", "wrong item", "missing")):
        return int(policy["defect_window_days"])
    return int(policy["change_window_days"])

def window_cutoff(delivered_at: str, policy: dict, loyalty_tier: str | None, reason: str | None = None) -> datetime:
    start = _dt(delivered_at)
    days = refund_window_days(policy, reason)
    if (reason or "change_of_mind").lower() in ("change_of_mind", "change of mind", "changed my mind"):
        tier = str(loyalty_tier or "").lower()
        if tier == "gold": days += 2
        elif tier == "platinum": days += 3
    # Day 0 is delivery day; N <= window is in time. End at 23:59:59 on day N.
    return (start + timedelta(days=days)).replace(hour=23, minute=59, second=59, microsecond=0)

def restocking_percent(policy: dict, category: str | None, reason: str | None) -> float:
    if policy.get("version") != "v2":
        return 0.0
    r = (reason or "change_of_mind").lower()
    if r not in ("change_of_mind", "change of mind", "changed my mind"):
        return 0.0
    cats = {x.strip().lower() for x in str(policy.get("restocking_categories") or "").split(",") if x.strip()}
    return float(policy.get("restocking_pct") or 0) if str(category or "").lower() in cats else 0.0

def refund_cap(requested: float | None, order_value: float, restocking_pct: float = 0.0) -> float:
    ceiling = max(0.0, order_value - order_value * (restocking_pct / 100.0))
    return round(min(requested, ceiling) if requested is not None else ceiling, 2)
