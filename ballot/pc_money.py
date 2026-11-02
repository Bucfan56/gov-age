"""Big givers to Florida candidate-controlled political committees (unlimited-contribution
accounts). Usage: py pc_money.py OUT.json "Committee Name" [...]"""
import json, re, sys, time, urllib.parse, urllib.request
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
EP = "https://dos.elections.myflorida.com/cgi-bin/contrib.exe"
UA = {"User-Agent": "gov-age-state-finance/1.0 (public data research)"}
BASE = {"party": "All", "committee": "All", "CanNameSrch": "2", "ComNameSrch": "2", "namesearch": "2",
        "csort1": "AMT", "csort2": "CAN", "queryformat": "2", "election": "All"}
BASE["ComNameSrch"] = "1"


def q(**kw):
    f = dict(BASE); f.update(kw)
    t = urllib.request.urlopen(urllib.request.Request(EP, data=urllib.parse.urlencode(f).encode(), headers=UA),
                               timeout=600).read().decode("latin-1")
    time.sleep(1.5)
    if "Error in /cgi-bin" in t:
        raise RuntimeError(t[:200])
    rows = [r for r in t.replace("\r", "").split("\n") if r.strip()]
    h = rows[0].split("\t") if rows else []
    return [dict(zip(h, r.split("\t"))) for r in rows[1:]]


out = json.load(open(sys.argv[1], encoding="utf-8")) if len(sys.argv) > 1 and __import__("os").path.exists(sys.argv[1]) else {}
for name in sys.argv[2:]:
    tot = q(search_on="5", ComName=name, rowlimit="20")
    big = q(search_on="4", ComName=name, cdollar_minimum="5000", rowlimit="30000")
    agg = defaultdict(lambda: [0.0, 0, ""])
    first, last = "99999999", ""
    for r in big:
        if (r.get("Candidate/Committee") or "").strip().upper() != name.upper() and not (r.get("Candidate/Committee") or "").upper().startswith(name.upper()):
            continue
        try:
            a = float((r.get("Amount") or "0").replace("$", "").replace(",", ""))
        except ValueError:
            continue
        if (r.get("Typ") or "") in ("LOA", "INT"):
            continue
        dt = r.get("Date") or ""
        if len(dt) == 10:
            k = dt[6:] + dt[:2] + dt[3:5]; first = min(first, k); last = max(last, k)
        nm = (r.get("Contributor Name") or "").strip().upper()
        agg[nm][0] += a; agg[nm][1] += 1; agg[nm][2] = (r.get("City State Zip") or "").strip()
    top = sorted(agg.items(), key=lambda kv: -kv[1][0])
    out[name] = {"totals": [(t.get("Committee Name"), t.get("Type"), t.get("Total Amount")) for t in tot],
                 "gifts_5k_plus_sum": round(sum(v[0] for v in agg.values())), "givers_5k_plus": len(agg),
                 "span": [first, last],
                 "top": [(k, round(v[0]), v[1], v[2]) for k, v in top[:40]]}
    print("==", name, out[name]["totals"], out[name]["gifts_5k_plus_sum"], out[name]["givers_5k_plus"], out[name]["span"])
    for k, a, n, w in out[name]["top"][:15]:
        print(f"   {a:>12,}  x{n:<3} {k}  [{w}]")
json.dump(out, open(sys.argv[1], "w", encoding="utf-8"), indent=1)
