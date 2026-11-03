"""Florida candidate-account contributions for EVERY 2026 State Senate and State House
general-election race (any-address ballot), pulled live from the Division of Elections.
Usage: py fl_money_all.py OUTDIR   (skips districts already saved, so it can be re-run)"""
import json, os, re, sys, time, urllib.parse, urllib.request
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = sys.argv[1]
EP = "https://dos.elections.myflorida.com/cgi-bin/contrib.exe"
UA = {"User-Agent": "gov-age-state-finance/1.0 (public data research)"}
BASE = {"party": "All", "committee": "All", "CanNameSrch": "2", "ComNameSrch": "2",
        "namesearch": "2", "csort1": "AMT", "csort2": "CAN", "queryformat": "2"}
EL = "20261103-GEN"
RACES = [("GOV", ""), ("ATG", ""), ("CFO", ""), ("AGR", ""), ("STS", "20"), ("STR", "70"), ("STR", "71")]
SUFFIX = re.compile(r"\s*\([A-Z]{2,4}\)\s*\([A-Z]{2,4}\)\s*$")


def q(**kw):
    f = dict(BASE); f.update({k: v for k, v in kw.items() if v})
    body = urllib.parse.urlencode(f).encode()
    for attempt in range(3):
        try:
            t = urllib.request.urlopen(urllib.request.Request(EP, data=body, headers=UA), timeout=600).read().decode("latin-1")
            break
        except Exception as e:
            print("retry", e, file=sys.stderr); time.sleep(5)
    else:
        raise RuntimeError("Florida endpoint failed")
    time.sleep(1.5)
    if "Error in /cgi-bin" in t or "ODBC" in t:
        raise RuntimeError(t[:300])
    rows = [r for r in t.replace("\r", "").split("\n") if r.strip()]
    if not rows:
        return []
    h = rows[0].split("\t")
    return [dict(zip(h, r.split("\t"))) for r in rows[1:]]


def money(v):
    try:
        return float((v or "0").replace("$", "").replace(",", ""))
    except ValueError:
        return 0.0


res = {}
for office in ("STS", "STR"):
    allt = q(election=EL, search_on="3", office=office, rowlimit="2000")
    dists = sorted({t.get("District", "").strip() for t in allt if t.get("District", "").strip()}, key=lambda d: int(re.sub(r"\D", "", d) or 0))
    print(office, "districts", len(dists), "candidates", len(allt), file=sys.stderr)
    for dist in dists:
        dnum = str(int(re.sub(r"\D", "", dist)))
        key = f"{office}{dnum}"
        path = os.path.join(OUT, f"fl_{key}.json")
        if os.path.exists(path):
            continue
        totals = [t for t in allt if t.get("District", "").strip() == dist]
        rows = q(election=EL, search_on="2", office=office, cdistrict=dnum, cdollar_minimum="0", rowlimit="32000")
        if len(rows) >= 32000:
            rows = []
            for lo, hi in [("0", "49.99"), ("50", "249.99"), ("250", "999.99"), ("1000", "")]:
                rows += q(election=EL, search_on="2", office=office, cdistrict=dnum, cdollar_minimum=lo, cdollar_maximum=hi, rowlimit="32000")
        print(" ", key, len(totals), "cands", len(rows), "rows", file=sys.stderr)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"totals": [{"name": t.get("Candidate Name", "").strip(), "party": t.get("Party", "").strip(),
                                   "district": dnum, "total": money(t.get("Total Amount"))} for t in totals], "rows": rows}, fh)
print("done", file=sys.stderr)
