"""NovaMart tools adapted to the supplied public dataset schema.
The authenticated customer_id is always injected by the session and never accepted from the model.
"""
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from .config import TZ_NAME
from .db import q, get_db
from .policy import get_policy_for_order, window_cutoff, refund_cap, restocking_percent, PolicyError

def _now():
    return datetime.now(ZoneInfo(TZ_NAME))

def _own_order(order_id: str, customer_id: str):
    rows = q("SELECT * FROM orders WHERE order_id=?", (order_id,))
    if not rows: return None, {"error":"ORDER_NOT_FOUND"}
    if len(rows) > 1: return None, {"error":"DUPLICATE_ORDER_ID"}
    if str(rows[0]["customer_id"]) != str(customer_id): return None, {"error":"ORDER_NOT_FOUND"}
    return rows[0], None

def _normalized_order(o):
    o = dict(o)
    o["status"] = o.get("order_status")
    o["delivered_at"] = o.get("actual_delivery_date")
    o["estimated_delivery_date"] = o.get("estimated_delivery_date")
    o["otp_verified"] = bool(o.get("delivery_otp_verified", False))
    return o

def get_customer(customer_id: str, **_):
    r = q("SELECT * FROM customers WHERE customer_id=?", (customer_id,))
    return r[0] if r else {"error":"CUSTOMER_NOT_FOUND"}

def get_order(customer_id: str, order_id: str | None = None, product_hint: str | None = None, **_):
    if order_id:
        o, err = _own_order(order_id, customer_id)
        if err: return err
        o = _normalized_order(o)
        o["items"] = q("""SELECT oi.*, p.product_name, p.sku, p.category, p.warranty_months,
                          p.returnable, p.replacement_available
                          FROM order_items oi LEFT JOIN products p ON p.product_id=oi.product_id
                          WHERE oi.order_id=?""", (order_id,))
        return o
    sql = """SELECT o.order_id, o.order_status AS status, o.total_amount,
             o.actual_delivery_date AS delivered_at, o.estimated_delivery_date,
             GROUP_CONCAT(DISTINCT p.product_name) AS product_names,
             GROUP_CONCAT(DISTINCT p.category) AS categories
             FROM orders o JOIN order_items oi ON oi.order_id=o.order_id
             LEFT JOIN products p ON p.product_id=oi.product_id WHERE o.customer_id=?"""
    args = [customer_id]
    if product_hint:
        sql += " AND (LOWER(p.product_name) LIKE ? OR LOWER(p.category) LIKE ?)"
        args += [f"%{product_hint.lower()}%"] * 2
    sql += " GROUP BY o.order_id, o.order_status, o.total_amount, o.actual_delivery_date, o.estimated_delivery_date"
    return {"orders": q(sql + " ORDER BY COALESCE(o.actual_delivery_date,o.estimated_delivery_date) DESC LIMIT 20", tuple(args))}

def get_product(sku: str, **_):
    rows = q("SELECT * FROM products WHERE sku=? OR product_id=?", (sku, sku))
    if not rows: return {"error":"PRODUCT_NOT_FOUND"}
    p = rows[0]
    category = str(p.get("category", "")).lower().replace(" ", "_")
    docs = q("SELECT content FROM product_specs WHERE LOWER(category)=?", (category,))
    p["spec_document"] = docs[0]["content"] if docs else None
    return p

def get_conversations(customer_id: str, **_):
    return {"conversations": q("SELECT conversation_id, order_id, ticket_id, channel, language, started_at, status, transcript FROM conversations WHERE customer_id=? ORDER BY started_at DESC LIMIT 20", (customer_id,))}

def _recent_claims(customer_id: str):
    since = (_now() - timedelta(days=90)).isoformat()
    rows = q("""SELECT COUNT(*) AS c FROM support_tickets
               WHERE customer_id=? AND created_at>=?
               AND LOWER(category) IN ('refund','return','delivery','non_delivery')
               AND (LOWER(issue_summary) LIKE '%not received%' OR LOWER(issue_summary) LIKE '%refund%' OR LOWER(issue_summary) LIKE '%return%' OR LOWER(category) LIKE '%delivery%')""", (customer_id, since))
    return int(rows[0]["c"]) if rows else 0

def check_refund_eligibility(customer_id: str, order_id: str, reason: str | None = None, **_):
    o, err = _own_order(order_id, customer_id)
    if err: return {"eligible":False, **err}
    o = _normalized_order(o)
    try:
        policy = get_policy_for_order(o["order_date"])
        if str(o.get("payment_status", "")).lower() == "pending":
            return {"eligible":False,"code":"PAYMENT_PENDING","policy_version":policy["version"]}
        if o.get("order_status") != "delivered" or not o.get("actual_delivery_date"):
            return {"eligible":False,"code":"NOT_DELIVERED_YET","policy_version":policy["version"]}
        cust = get_customer(customer_id)
        tier = cust.get("loyalty_tier")
        cutoff = window_cutoff(o["actual_delivery_date"], policy, tier, reason)
        in_window = _now() <= cutoff
        repeated = _recent_claims(customer_id)
        suspended = str(cust.get("account_status","")).lower() == "suspended"
        return {
            "eligible": in_window and not suspended and repeated < 3,
            "code": "OK" if in_window else "OUTSIDE_WINDOW",
            "policy_version": policy["version"], "window_ends": cutoff.isoformat(),
            "otp_verified_delivery": bool(o.get("delivery_otp_verified")),
            "recent_claims_90d": repeated, "risk_flag": repeated >= 3 or suspended,
            "approval_threshold": float(policy["approval_threshold"]),
            "order_total": float(o["total_amount"]),
            "reason": reason or "change_of_mind"
        }
    except PolicyError as e:
        return {"eligible":False,"code":"POLICY_ERROR","detail":str(e)}

def calculate_refund(customer_id: str, order_id: str, requested_amount: float | None = None, reason: str | None = None, **_):
    o, err = _own_order(order_id, customer_id)
    if err: return err
    try:
        policy = get_policy_for_order(o["order_date"])
        items = q("""SELECT oi.*, p.category, p.product_name
                     FROM order_items oi JOIN products p ON p.product_id=oi.product_id
                     WHERE oi.order_id=?""", (order_id,))
        category = items[0].get("category") if len(items) == 1 else None
        pct = restocking_percent(policy, category, reason)
        cap = refund_cap(requested_amount, float(o["total_amount"]), pct)
        return {"order_value":float(o["total_amount"]),"requested":requested_amount,
                "refundable_amount":cap,"restocking_pct":pct,
                "policy_version":policy["version"],"within_approval_threshold":float(o["total_amount"]) <= float(policy["approval_threshold"]),
                "approval_threshold":float(policy["approval_threshold"]),
                "capped": requested_amount is not None and cap < requested_amount}
    except PolicyError as e:
        return {"error":"POLICY_ERROR","detail":str(e)}

def create_return(customer_id: str, order_id: str, reason: str, **_):
    el = check_refund_eligibility(customer_id, order_id, reason)
    if not el.get("eligible"): return {"error":"NOT_ELIGIBLE","detail":el}
    rid=f"RET-{uuid.uuid4().hex[:8].upper()}"
    get_db().execute("INSERT INTO returns VALUES (?,?,?,?,?)", (rid,order_id,customer_id,reason,_now().isoformat()))
    get_db().commit()
    return {"return_id":rid,"status":"created"}

def create_refund(customer_id: str, order_id: str, amount: float, **_):
    el = check_refund_eligibility(customer_id, order_id)
    if not el.get("eligible") or el.get("risk_flag") or float(el.get("order_total",0)) > float(el.get("approval_threshold",0)):
        return {"error":"BLOCKED","detail":el}
    calc = calculate_refund(customer_id, order_id, amount)
    if "error" in calc or calc["capped"] or not calc["within_approval_threshold"]:
        return {"error":"AMOUNT_REJECTED","detail":calc}
    if q("SELECT 1 FROM refunds WHERE order_id=?", (order_id,)): return {"error":"ALREADY_REFUNDED"}
    fid=f"RF-{uuid.uuid4().hex[:8].upper()}"
    get_db().execute("INSERT INTO refunds VALUES (?,?,?,?,?)", (fid,order_id,customer_id,calc["refundable_amount"],_now().isoformat()))
    get_db().commit()
    return {"refund_id":fid,"amount":calc["refundable_amount"],"destination":"original_payment_method","status":"created"}

def create_support_ticket(customer_id: str, summary: str, order_id: str | None = None, **_):
    tid=f"ST-{uuid.uuid4().hex[:4].upper()}"
    get_db().execute("INSERT INTO new_tickets VALUES (?,?,?,?,?,?)", (tid,customer_id,order_id,"follow_up",summary,_now().isoformat()))
    get_db().commit()
    return {"ticket_id":tid}

def escalate_to_human(customer_id: str, reason: str, summary: str, order_id: str | None = None, **_):
    tid=f"ST-{uuid.uuid4().hex[:4].upper()}"
    get_db().execute("INSERT INTO new_tickets VALUES (?,?,?,?,?,?)", (tid,customer_id,order_id,f"escalation:{reason}",summary,_now().isoformat()))
    get_db().commit()
    return {"ticket_id":tid,"status":"escalated"}

REGISTRY={f.__name__:f for f in (get_customer,get_order,get_product,get_conversations,check_refund_eligibility,calculate_refund,create_return,create_refund,create_support_ticket,escalate_to_human)}
ACTION_TOOLS={"create_return","create_refund"}
