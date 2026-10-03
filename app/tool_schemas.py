"""Anthropic tool-use schemas. Note: NO customer_id param. It is injected from the session."""
def _t(name, desc, props, required=()):
    return {"name": name, "description": desc,
            "input_schema": {"type": "object", "properties": props, "required": list(required)}}

S = lambda d: {"type": "string", "description": d}
N = lambda d: {"type": "number", "description": d}

TOOL_SCHEMAS = [
    _t("get_customer", "Fetch the current customer's profile (loyalty tier, account age).", {}),
    _t("get_order", "With order_id: fetch one verified order + items + delivery state (must belong to this customer). "
       "Without order_id: list this customer's recent orders, optionally filtered by product_hint, to detect ambiguity.",
       {"order_id": S("e.g. NM1042"), "product_hint": S("product name/category keyword, e.g. 'headphones'")}),
    _t("get_product", "Fetch product, specs, warranty info by SKU.", {"sku": S("product SKU")}, ["sku"]),
    _t("get_conversations", "Prior conversation history for this customer.", {}),
    _t("check_refund_eligibility", "Applies the ACTIVE policy version + window arithmetic (loyalty, timezone). Also returns risk flags and OTP delivery status.",
       {"order_id": S("order id"), "reason": S("customer reason, e.g. damaged")}, ["order_id"]),
    _t("calculate_refund", "Computes the maximum valid refund = min(requested, order_value - restocking). Never use the customer's number directly.",
       {"order_id": S("order id"), "requested_amount": N("amount the customer asked for, if any")}, ["order_id"]),
    _t("create_return", "Open a return request on an eligible order.", {"order_id": S("order id"), "reason": S("return reason")}, ["order_id", "reason"]),
    _t("create_refund", "Issue a refund. Only after eligibility + calculate_refund. Amount must equal refundable_amount.",
       {"order_id": S("order id"), "amount": N("must equal refundable_amount from calculate_refund")}, ["order_id", "amount"]),
    _t("create_support_ticket", "Open a follow-up ticket.", {"summary": S("what needs following up"), "order_id": S("optional order id")}, ["summary"]),
    _t("escalate_to_human", "Hand off to a human with full context. Required for every ESCALATE decision.",
       {"reason": S("legal_threat | safety | otp_contradiction | suspicious_refund | over_threshold | other"),
        "summary": S("facts verified, what the customer wants, what you checked"), "order_id": S("optional order id")},
       ["reason", "summary"]),
    _t("final_decision", "REQUIRED last call of every turn. Declares the terminal move and the reply shown to the customer.",
       {"decision": {"type": "string", "enum": ["ANSWER", "ASK", "ACT", "ESCALATE"]},
        "intents": {"type": "array", "items": {"type": "string"}},
        "order_id": S("order the decision concerns, if any"),
        "reasoning": S("short internal reasoning (never shown to customer)"),
        "reply_to_customer": S("final message to the customer")},
       ["decision", "intents", "reasoning", "reply_to_customer"]),
]
