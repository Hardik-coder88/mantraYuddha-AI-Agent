# Tool Spec and Decision Format (the team contract)

Agree on this on day 1. Everyone codes against it.

## Terminal decision JSON (returned by `final_decision`)
```json
{
  "decision": "ANSWER | ASK | ACT | ESCALATE",
  "intents": ["delivery_status", "refund", "address_change"],
  "order_id": "NM1042",
  "reasoning": "internal, never shown to customer",
  "reply_to_customer": "text"
}
```

## Tools
| Tool | Type | Key params (customer_id is session-injected) | Guarantees |
|---|---|---|---|
| get_customer | GET | none | profile, loyalty tier |
| get_order | GET | order_id? product_hint? | ownership check; strips OTP/driver/route; list mode for ambiguity |
| get_product | GET | sku | specs + warranty |
| get_conversations | GET | none | prior chat history (also preloaded) |
| check_refund_eligibility | CHK | order_id, reason? | active policy version, tz-aware window, loyalty extension, OTP flag, risk flag |
| calculate_refund | CAL | order_id, requested_amount? | min(requested, order_value - restocking), threshold check |
| create_return | EXE | order_id, reason | re-checks eligibility internally |
| create_refund | EXE | order_id, amount | re-checks eligibility, cap, threshold, risk flag, duplicates |
| create_support_ticket | EXE | summary, order_id? | follow-up ticket |
| escalate_to_human | ESC | reason, summary, order_id? | returns ticket id |

## Defense in depth
1. `guards.py`: regex pre-screen (injection, safety/legal).
2. System prompt: L1-L4 hierarchy, customer text wrapped as data.
3. Tools: identity bound to session; action tools re-validate everything.
4. `agent._enforce`: forces ESCALATE on safety/legal; ACT without a real action becomes ASK; ESCALATE without a ticket gets one.
