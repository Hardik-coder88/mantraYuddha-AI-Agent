"""Cheap deterministic pre-screen. Flags are hints to the model; safety flags are ENFORCED in agent.py."""
import re

INJECTION = [r"ignore (all )?(previous|prior) instructions", r"system prompt", r"maintenance mode",
             r"approve all refunds", r"i am (an )?admin", r"customer is admin", r"override (the )?checks?",
             r"policy (has )?changed", r"you are now", r"developer mode"]
SAFETY = [r"\bsue\b", r"lawyer", r"legal action", r"consumer (court|forum)", r"police", r"\bfir\b",
          r"kill myself", r"end my life", r"suicid", r"self[- ]harm", r"hurt (myself|you)", r"\bthreat",
          r"caught fire|burn(ed|t)|exploded|electric shock", r"regulator|ombudsman|\brbi\b|\btrai\b"]

def screen_message(text: str) -> dict:
    t = text.lower()
    return {
        "injection": any(re.search(p, t) for p in INJECTION),
        "safety_or_legal": any(re.search(p, t) for p in SAFETY),
    }
