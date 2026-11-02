"""Florida candidate-account contributions for the 2026 general-election races on a
Palmetto (34221) ballot, pulled live from the Division of Elections today.
Usage: py fl_money.py OUTDIR"""
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
for office, dist in RACES:
    totals = q(election=EL, search_on="3", office=office, cdistrict=dist, rowlimit="500")
    rows = []
    for t in totals:
        nm = t.get("Candidate Name", "").strip()
        last = nm.split()[-1] if nm else ""
        bands = [("0", "")]
        got = q(election=EL, search_on="2", office=office, cdistrict=dist, CanLName=last, cdollar_minimum="0", rowlimit="32000")
        if len(got) >= 32000:
            got = []
            for lo, hi in [("0", "49.99"), ("50", "249.99"), ("250", "999.99"), ("1000", "")]:
                part = q(election=EL, search_on="2", office=office, cdistrict=dist, CanLName=last, cdollar_minimum=lo, cdollar_maximum=hi, rowlimit="32000")
                print("  band", nm, lo, hi, len(part), file=sys.stderr)
                got += part
        print(" ", nm, len(got), file=sys.stderr)
        rows += got
    print(office, dist, "candidates", len(totals), "rows", len(rows), file=sys.stderr)
    key = f"{office}{dist}"
    res[key] = {"totals": [{"name": t.get("Candidate Name", "").strip(), "party": t.get("Party", "").strip(),
                            "district": t.get("District", "").strip(), "total": money(t.get("Total Amount"))}
                           for t in totals], "rows": rows}
    with open(os.path.join(OUT, f"fl_{key}.json"), "w", encoding="utf-8") as fh:
        json.dump(res[key], fh)
print("done", file=sys.stderr)
