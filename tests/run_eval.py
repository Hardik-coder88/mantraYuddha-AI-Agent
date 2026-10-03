"""Regression harness. Usage: python tests/run_eval.py [--category Ambiguity]
Checks: terminal decision, forbidden tools, leaked strings. Skips cases that still contain <PLACEHOLDERS>."""
import sys, os, json, re, argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.agent import Session, handle_message

ap = argparse.ArgumentParser(); ap.add_argument("--category"); args = ap.parse_args()
cases = json.load(open(os.path.join(os.path.dirname(__file__), "redteam_cases.json")))["cases"]
passed = failed = skipped = 0
for c in cases:
    if args.category and args.category.lower() not in c["category"].lower():
        continue
    if re.search(r"<[A-Z_]+>", json.dumps(c)):
        skipped += 1; continue
    out = handle_message(Session(c["customer_id"]), c["message"])
    d, reply = out["decision"], out["decision"]["reply_to_customer"].lower()
    used = {t["tool"] for t in out["trace"]}
    e, errs = c["expect"], []
    if d["decision"] not in e["decision"]: errs.append(f"decision {d['decision']} not in {e['decision']}")
    for t in e.get("forbidden_tools", []):
        if t in used: errs.append(f"forbidden tool used: {t}")
    for s in e.get("must_not_say", []):
        if s.lower() in reply: errs.append(f"leaked: {s}")
    print(("PASS " if not errs else "FAIL "), c["id"], c["category"], errs or "")
    passed += not errs; failed += bool(errs)
print(f"\n{passed} passed, {failed} failed, {skipped} skipped (placeholders)")
sys.exit(1 if failed else 0)
