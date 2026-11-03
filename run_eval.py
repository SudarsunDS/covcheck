"""Run all synthetic scenarios and write results/results.md + results/decisions.json."""
import json
from pathlib import Path
from covcheck import load_documents, decide
from scenarios import SCENARIOS, DATA

def main():
    docs = load_documents(DATA)
    rows, dump = [], {}
    for s in SCENARIOS:
        d = decide(docs, s["ext"], s["fin"], s["cert"])
        ok = d.status == s["expected"]
        ratio = d.computed.get("total_net_leverage_ratio")
        rows.append((s["id"], s["name"], s["expected"], d.status, "yes" if ok else "NO",
                     f"{ratio:.4f}" if ratio is not None else "-",
                     s.get("correct", s["expected"]), d.reasons[0] if d.reasons else ""))
        dump[s["id"]] = json.loads(d.to_json())
        if "ablation" in s:
            a = s["ablation"]; da = decide(docs, a["ext"], s["fin"], s["cert"])
            rows.append((s["id"] + "-ablation", a["note"], a["expected"], da.status,
                         "yes" if da.status == a["expected"] else "NO", "-", "(ablation)", da.reasons[0]))
    out = Path(__file__).parent / "results"; out.mkdir(exist_ok=True)
    lines = ["| ID | Scenario | Expected (code) | Actual | Match | Recomputed ratio | Correct answer | First reason |",
             "|---|---|---|---|---|---|---|---|"]
    lines += ["| " + " | ".join(str(c).replace("|", "/") for c in r) + " |" for r in rows]
    (out / "results.md").write_text("\n".join(lines) + "\n")
    (out / "decisions.json").write_text(json.dumps(dump, indent=2))
    for r in rows:
        print(f"{r[0]:<14} {r[3]:<12} expected={r[2]:<12} match={r[4]:<4} correct={r[6]}")
    print(f"\n{sum(r[4]=='yes' for r in rows)}/{len(rows)} rows match expected code behaviour")

if __name__ == "__main__":
    main()
