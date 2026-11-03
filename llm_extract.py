"""
Optional: LLM extraction step via OpenRouter (OpenAI-compatible chat API).

NOT EXECUTED during development of this prototype: the build environment had no
OpenRouter access, so every result in results/ uses the hand-written fixtures in
data/extraction_*.json. Run this yourself and pipe its output through the same
verifier (covcheck.verify_field) - that is the point of the design: the LLM's
output is never trusted until the clause anchor checks pass.

Usage:
  export OPENROUTER_API_KEY=...        # free account at openrouter.ai
  export OPENROUTER_MODEL=...          # pick a current free-tier model id; record it in the README
  python llm_extract.py data/amendment_1.txt amendment_1 > data/extraction_amendment_1.llm.json
"""
import json, os, sys, urllib.request
from covcheck import SCHEMA

PROMPT = """You extract covenant parameters from ONE credit-agreement document.
Return ONLY a JSON object. For each field below that THIS document sets or changes, output
{{"value": ..., "source_doc": "{doc_id}", "quote": "<exact contiguous text copied from the document>"}}.
Omit fields the document does not set or change. Never infer values from other documents.
The quote MUST be copied character-for-character and MUST contain the value.

Fields and value formats:
- max_ratio_initial: decimal string, e.g. "4.50" (limit before the step-down date)
- step_down_date: ISO date of the step-down
- max_ratio_stepped: decimal string (limit on/after the step-down date)
- synergy_cap_pct: decimal fraction, e.g. "0.15" for 15% (cap on projected cost-savings/synergy add-backs)
- synergy_cap_base: "pre_addback" if the cap is measured before giving effect to the add-backs, else "post_addback"
- cash_netting_cap: integer USD, maximum cash that may be netted from debt

If this is an amendment that replaces text, the value is the NEW value.

DOCUMENT:
<<<
{text}
>>>"""

def extract(path, doc_id):
    body = {"model": os.environ["OPENROUTER_MODEL"], "temperature": 0,
            "messages": [{"role": "user", "content": PROMPT.format(doc_id=doc_id, text=open(path).read())}]}
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
                                          "Content-Type": "application/json"})
    text = json.load(urllib.request.urlopen(req, timeout=120))["choices"][0]["message"]["content"]
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    data = json.loads(text)
    return {k: v for k, v in data.items() if k in SCHEMA}   # drop fields outside the schema

if __name__ == "__main__":
    print(json.dumps(extract(sys.argv[1], sys.argv[2]), indent=2))
