#!/usr/bin/env python3
"""
Smoke test. Run after any rebuild; CI runs it before committing.

    python3 verify.py

Exits non-zero on anything that would ship broken data or a broken page.
"""
import json, os, re, sys

# Windows consoles default to a legacy codepage; keep the report readable there.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

FAIL = []
WARN = []


def check(cond, msg):
    if not cond:
        FAIL.append(msg)


def warn(cond, msg):
    if not cond:
        WARN.append(msg)


# ---------- files present ----------
for f in ["index.html", "finance.json", "roster_map.json",
          "build_finance.py", "inline_data.py"]:
    check(os.path.exists(f), f"missing file: {f}")
if FAIL:
    print("\n".join("FAIL  " + m for m in FAIL))
    sys.exit(1)

fin = json.load(open("finance.json", encoding="utf-8"))
roster = json.load(open("roster_map.json", encoding="utf-8"))
html = open("index.html", encoding="utf-8").read()

# ---------- dataset shape ----------
people = fin.get("people", {})
check(len(people) >= 40, f"only {len(people)} people in finance.json, expected 40+")
check(bool(fin.get("built")), "finance.json has no build timestamp")
check(set(people) == set(roster),
      "finance.json and roster_map.json disagree on who is tracked: "
      f"{sorted(set(roster) ^ set(people))[:5]}")

funded = [p for p in people.values() if p["career"]["receipts"] > 0]
check(len(funded) >= 40, f"only {len(funded)} people have receipts, expected 40+")

grand = sum(p["career"]["receipts"] for p in people.values())
check(grand > 1e9, f"total receipts ${grand:,.0f} looks too low")

# every funded person should have coherent internals
for name, p in people.items():
    c = p["career"]
    if c["receipts"] <= 0:
        continue
    check(c["pac"] <= c["receipts"] * 1.05,
          f"{name}: PAC ${c['pac']:,.0f} exceeds receipts ${c['receipts']:,.0f}")
    check(c["indiv"] <= c["receipts"] * 1.05,
          f"{name}: individual money exceeds receipts")
    check(p["first"] and p["last"] and p["first"] <= p["last"],
          f"{name}: bad cycle range {p.get('first')}-{p.get('last')}")
    warn(p["cycles"], f"{name}: no per-cycle history")

# ---------- known-good anchors ----------
# These are stable published facts. If they move a lot, something broke upstream.
ANCHORS = {
    "Chuck Grassley":           (40e6, 70e6),
    "Mitch McConnell":          (120e6, 220e6),
    "Alexandria Ocasio-Cortez": (60e6, 140e6),
    "Nancy Pelosi":             (70e6, 140e6),
}
for name, (lo, hi) in ANCHORS.items():
    if name not in people:
        FAIL.append(f"anchor person missing: {name}")
        continue
    r = people[name]["career"]["receipts"]
    warn(lo <= r <= hi,
         f"{name} career receipts ${r/1e6:.1f}M outside expected ${lo/1e6:.0f}-{hi/1e6:.0f}M")

# AOC should be near-zero PAC, long-serving House leaders should be high.
def pac_pct(n):
    c = people[n]["career"]
    return 100 * c["pac"] / c["receipts"] if c["receipts"] else 0

warn(pac_pct("Alexandria Ocasio-Cortez") < 5, "AOC PAC share should be near zero")
warn(pac_pct("Steny Hoyer") > 40, "Hoyer PAC share should be high")

# ---------- page wiring ----------
check("var FINANCE_DATA = " in html, "index.html has no inlined FINANCE_DATA block")
m = re.search(r"<script>var FINANCE_DATA = (.*?);</script>", html, re.S)
check(bool(m), "FINANCE_DATA block is malformed")
if m:
    try:
        inlined = json.loads(m.group(1))
        check(inlined.get("built") == fin.get("built"),
              "inlined data is stale — run inline_data.py")
        check(len(inlined.get("people", {})) == len(people),
              "inlined data has a different number of people than finance.json")
    except json.JSONDecodeError as e:
        FAIL.append(f"inlined FINANCE_DATA is not valid JSON: {e}")

for needle, why in [
    ("id=\"genBars\"",   "generation PAC chart container"),
    ("id=\"genMix\"",    "money-type chart container"),
    ("id=\"drawer\"",    "money drawer"),
    ("id=\"invOut\"",    "investigator output"),
    ("Read this before you use the generation numbers", "generation caveat box"),
    ("PAC_DATA_FROM",    "pre-1990 data guard"),
    ("noFecReason",      "explanation for people with no FEC record"),
]:
    check(needle in html, f"index.html is missing the {why}")

check(html.count("<script>") == html.count("</script>"), "unbalanced script tags")

# ---------- report ----------
for w in WARN:
    print("WARN  " + w)
for f in FAIL:
    print("FAIL  " + f)

if FAIL:
    print(f"\n{len(FAIL)} failure(s).")
    sys.exit(1)

print(f"\nOK  {len(people)} people · {len(funded)} with filings · "
      f"${grand/1e9:.2f}B tracked · built {fin['built']}"
      + (f" · {len(WARN)} warning(s)" if WARN else ""))
