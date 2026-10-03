# NovaMart AI Support Agent (Mantra Yudha)

This version includes the supplied **NovaMart public dataset** under `data/public/` and maps its real CSV/JSON/Markdown schema into the agent database automatically.

Layered, tool-calling support agent. **AI reasons, backend verifies, database stores truth.**

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env        # add ANTHROPIC_API_KEY
# The supplied dataset is already included in ./data/public; no manual column mapping is required.
streamlit run ui/app.py
pytest tests/test_policy.py
python tests/run_eval.py
```

## Architecture
Input guard -> memory preload (customer, conversations, open tickets) -> LLM tool loop (understand, verify, policy, decide)
-> `final_decision` -> deterministic enforcement -> reply. See `docs/tool_spec_and_decision_format.md`.

## Team ownership (25% each)
| Member | Owns |
|---|---|
| A: Data & Tools | `app/db.py`, `app/tools.py`, `app/policy.py`, `tests/test_policy.py` |
| B: Agent Brain | `prompts/`, `app/agent.py`, `app/tool_schemas.py`, prompt-strategy doc |
| C: Safety & Red Team | `app/guards.py`, `tests/redteam_cases.json`, known-limitations doc |
| D: UI, Eval & Delivery | `ui/`, `tests/run_eval.py`, README, architecture diagram, demo video |

## TODO before submission
- [x] Map real column names and load CSV/JSON/Markdown dataset
- [x] Implement order-date-based refund policy v1/v2 selection
- [x] Load conversations JSON and product/policy Markdown documents
- [ ] Confirm any remaining organizer-specific evaluation assumptions
- [ ] Fill red-team placeholders from public data; 3+ cases per category
- [ ] Mutation drill: change policy data (e.g. 7 to 10 days), confirm behavior changes with no code edits
- [ ] Architecture diagram, model names + versions, prompt strategy doc, known limitations
- [ ] 3-5 min demo video

## Known limitations (keep this honest)
- Regex guards miss paraphrased or non-English injection and safety language; the LLM is the second layer.
- Restocking fee is currently one global percent; per-category rules depend on the real policy format.
