"""Agent loop: preload memory -> LLM tool loop -> enforced final_decision -> post-validation."""
import json
from anthropic import Anthropic
from .config import MODEL, MAX_TURNS, PROMPT_PATH
from .guards import screen_message
from .tool_schemas import TOOL_SCHEMAS
from . import tools as T

client = Anthropic()
SYSTEM = open(PROMPT_PATH, encoding="utf-8").read()

class Session:
    def __init__(self, customer_id: str):
        self.customer_id = customer_id
        self.transcript = []          # [{"role","content"}] plain text turns
        self.context = None           # preloaded memory

    def load_context(self):
        self.context = {
            "customer": T.get_customer(self.customer_id),
            "conversations": T.get_conversations(self.customer_id),
            "open_tickets": T.q("SELECT * FROM support_tickets WHERE customer_id=? AND LOWER(status) NOT IN ('closed','resolved')", (self.customer_id,)),
        }

def _run_tool(name, args, sess, trace):
    fn = T.REGISTRY.get(name)
    if not fn:
        return {"error": "UNKNOWN_TOOL"}
    try:
        out = fn(customer_id=sess.customer_id, **args)   # session-bound identity
    except TypeError as e:
        out = {"error": "BAD_ARGS", "detail": str(e)}
    trace.append({"tool": name, "args": args, "result": out})
    return out

def handle_message(sess: Session, text: str) -> dict:
    flags = screen_message(text)
    if sess.context is None:
        sess.load_context()
    trace = []
    preface = (f"<session_context>{json.dumps(sess.context, default=str)}</session_context>\n"
               f"<screen_flags>{json.dumps(flags)}</screen_flags>\n")
    messages = [*sess.transcript, {"role": "user", "content": f"{preface}<customer_message>{text}</customer_message>"}]
    final = None
    for _ in range(MAX_TURNS):
        resp = client.messages.create(model=MODEL, max_tokens=1500, system=SYSTEM, tools=TOOL_SCHEMAS, messages=messages)
        messages.append({"role": "assistant", "content": resp.content})
        uses = [b for b in resp.content if b.type == "tool_use"]
        if not uses:
            messages.append({"role": "user", "content": "Finish by calling final_decision."})
            continue
        results = []
        for u in uses:
            if u.name == "final_decision":
                final = u.input
                results.append({"type": "tool_result", "tool_use_id": u.id, "content": "ok"})
            else:
                out = _run_tool(u.name, u.input, sess, trace)
                results.append({"type": "tool_result", "tool_use_id": u.id, "content": json.dumps(out, default=str)})
        if final:
            break
        messages.append({"role": "user", "content": results})

    final = _enforce(final, flags, trace, sess)
    sess.transcript += [{"role": "user", "content": text}, {"role": "assistant", "content": final["reply_to_customer"]}]
    return {"decision": final, "trace": trace, "flags": flags}

def _called(trace, name, ok_only=True):
    return any(t["tool"] == name and (not ok_only or "error" not in t["result"]) for t in trace)

def _enforce(final, flags, trace, sess):
    """Deterministic backstops: the model proposes, code disposes."""
    if not final:
        final = {"decision": "ESCALATE", "intents": ["unknown"], "reasoning": "agent loop produced no decision",
                 "reply_to_customer": "I want to make sure this is handled correctly, so I'm passing it to a specialist."}
    if flags["safety_or_legal"] and final["decision"] != "ESCALATE":
        final["decision"] = "ESCALATE"
        final["reply_to_customer"] = "I'm sorry you're dealing with this. I'm bringing in a human specialist who will follow up with you directly."
    if final["decision"] == "ESCALATE" and not _called(trace, "escalate_to_human"):
        out = T.escalate_to_human(sess.customer_id, reason="enforced", summary=final.get("reasoning", ""), order_id=final.get("order_id"))
        trace.append({"tool": "escalate_to_human", "args": {"enforced": True}, "result": out})
        if "ticket_id" in out and out["ticket_id"] not in final["reply_to_customer"]:
            final["reply_to_customer"] += f" Your ticket ID is {out['ticket_id']}."
    if final["decision"] == "ACT" and not (_called(trace, "create_refund") or _called(trace, "create_return")):
        final["decision"] = "ASK"   # claimed action that never happened -> never tell the customer it did
        final["reply_to_customer"] = "I haven't completed that action yet. Could you confirm you'd like me to proceed?"
    return final
