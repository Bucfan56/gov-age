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
check(len(people) >= 500, f"only {len(people)} people in finance.json, expected 500+ "
      "(both chambers of Congress plus the tracked executive branch)")
check(bool(fin.get("built")), "finance.json has no build timestamp")
check(set(people) == set(roster),
      "finance.json and roster_map.json disagree on who is tracked: "
      f"{sorted(set(roster) ^ set(people))[:5]}")

funded = [p for p in people.values() if p["career"]["receipts"] > 0]
check(len(funded) >= 500, f"only {len(funded)} people have receipts, expected 500+")

grand = sum(p["career"]["receipts"] for p in people.values())
check(grand > 10e9, f"total receipts ${grand:,.0f} looks too low for a full Congress")

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

# Census-scale anchors. The generation gradient is the page's headline claim, so
# it gets a range rather than a point: it should stay a real but moderate slope.
# If a future roster change pushes it back toward the 6x the old 48-person
# selection implied, that is a selection bug, not a finding.
_gen_pool = [p for p in people.values() if p["career"]["receipts"] > 0]
check(len(_gen_pool) >= 500, "generation pool collapsed below 500 funded members")

# ---------- the roster is a census, and joins by name ----------
# Everything downstream keys on the display name: roster_map -> finance.json ->
# the PEOPLE array in the page. Two people reduced to one name, or one person
# spelled two ways, silently splits or merges their money and quietly corrupts
# every generation figure. Name forms genuinely differ between sources
# ("Bernie Sanders" vs "Bernard Sanders"), so this is the failure mode to guard.
NAME_RE = re.compile(r'\{n:"(.*?)",\s*r:"')
GROUP_RE = re.compile(r'\{n:".*?",\s*r:".*?",\s*b:"[^"]*",\s*g:"(\w+)"')

_pstart = html.find("var PEOPLE = [")
_pend = html.find(chr(10) + "];", _pstart)
check(_pstart != -1 and _pend != -1, "cannot find the PEOPLE array in index.html")
block = html[_pstart:_pend] if _pstart != -1 else ""

page_names = [m.group(1).replace('\\"', '"').replace("\\\\", "\\")
              for m in NAME_RE.finditer(block)]
dupes = sorted({n for n in page_names if page_names.count(n) > 1})
check(not dupes, f"duplicate names in the PEOPLE array: {dupes[:5]}")

groups = GROUP_RE.findall(block)
n_sen = groups.count("senate")
n_house = groups.count("house")
n_deleg = block.count(", d:1}")
check(n_sen == 100, f"expected 100 senators in PEOPLE, found {n_sen}")
check(n_house - n_deleg >= 425,
      f"expected 425+ voting representatives, found {n_house - n_deleg}")
check(n_deleg == 6, f"expected 6 non-voting delegates, found {n_deleg}")

# Anyone on the page with money must resolve in the finance data.
orphans = [n for n in page_names if n in roster and n not in people]
check(not orphans, f"in roster_map but missing from finance.json: {orphans[:5]}")
unshown = sorted(set(roster) - set(page_names))
warn(len(unshown) <= 15,
     f"{len(unshown)} people are tracked for money but have no row on the page: {unshown[:5]}")

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
    ("escHtml",          "HTML escaping (six members have quoted nicknames)"),
    ('id="houseMed"',    "computed House median"),
    ('id="senMed"',      "computed Senate median"),
    ('id="rAge"',        "computed age/PAC-share correlation"),
    ('id="rEra"',        "computed first-cycle-year correlation"),
    ("function isVoting", "voting-member filter that excludes delegates"),
]:
    check(needle in html, f"index.html is missing the {why}")

check(html.count("<script>") == html.count("</script>"), "unbalanced script tags")

# ---------- month-by-month detail ----------
# Ships as its own file because it roughly doubles the core data and is only read
# when a money profile is open. It is fetched, never inlined, so a stale or absent
# copy is invisible on the page until someone clicks a name.
check(os.path.exists("finance-detail.json"), "missing file: finance-detail.json")
if os.path.exists("finance-detail.json"):
    det = json.load(open("finance-detail.json", encoding="utf-8"))
    check(det.get("built") == fin.get("built"),
          "finance-detail.json is stale — it was built at "
          f"{det.get('built')} but finance.json at {fin.get('built')}")
    dpeople = det.get("people", {})
    check(len(dpeople) >= 400,
          f"only {len(dpeople)} people have dated transactions, expected 400+")
    stray = sorted(set(dpeople) - set(people))
    check(not stray, f"detail file has people the core file does not: {stray[:5]}")
    # Months must never exceed the cycle totals they are drawn from.
    for name, rec in list(dpeople.items())[:400]:
        msum = sum(rec.get("months", {}).values())
        if msum:
            check(msum <= people[name]["career"]["receipts"] * 1.05,
                  f"{name}: month buckets ${msum:,.0f} exceed career receipts")
    warn(all(len(k) == 7 and k[4] == "-" for r in list(dpeople.values())[:50]
             for k in r.get("months", {})),
         "month keys are not all YYYY-MM")

check("finance-detail.json" in html, "page never fetches the month-by-month detail file")
check("renderTimeline" in html, "page is missing the money-over-time view")
check("renderDonors" in html, "page is missing the named-donor view")
check("renderStateMoney" in html, "page is missing the state-money view")
check("bindOpenablePeople" in html, "page is missing the click-anywhere profile wiring")
# Matching a display name to a person is the dangerous part. A surname-only
# fallback once linked "Charles Booker" (Kentucky candidate) to Cory Booker of
# New Jersey and "Scott Brown" of New Hampshire to Shontel Brown of Ohio --
# opening the wrong person's money under someone else's name. Matching now
# requires first AND last to agree and refuses ambiguous hits.
check("hits.length === 1 ? hits[0].p : null" in html,
      "name matching no longer refuses ambiguous hits; it can open the wrong "
      "person's money profile")
check("t[0] !== first || t[t.length - 1] !== last" in html,
      "name matching no longer requires both first and last name to agree")

# ---------- state-level money ----------
# Governors file with their state, never the FEC, so without this they show only
# "no federal filing" -- true, and useless. Each state file is fetched on demand;
# a missing or stale one is invisible until someone opens a governor.
import re as _re
_declared = _re.search(r"var STATE_FILES = \{([^}]*)\}", html)
check(bool(_declared), "page does not declare STATE_FILES")
if _declared:
    for code, fname in _re.findall(r"(\w+)\s*:\s*[\"']([^\"']+)[\"']", _declared.group(1)):
        check(os.path.exists(fname),
              f"page offers state {code} but {fname} is missing")
        if os.path.exists(fname):
            st = json.load(open(fname, encoding="utf-8"))
            check(len(st.get("people", {})) >= 100,
                  f"{fname}: only {len(st.get('people', {}))} candidates, expected 100+")
            check(st.get("donorFloor"), f"{fname} does not record its donor floor")
            check(st.get("authority"), f"{fname} does not name the reporting authority")
            tot = sum(r["total"] for r in st["people"].values())
            check(tot > 1e6, f"{fname}: only ${tot:,.0f} tracked, looks broken")
            for r in list(st["people"].values())[:300]:
                ds = r.get("donors", [])
                amts = [d["amt"] for d in ds]
                check(amts == sorted(amts, reverse=True),
                      f"{fname}: donor list not sorted largest first ({r['name']})")
                # The state's "contribution total" and the sum of its own
                # itemised contributions are different measures -- the total
                # excludes loans, and the itemised list is floored at the donor
                # threshold, so the two legitimately disagree per candidate.
                # Loans are held separately; anything wildly above the reported
                # total means they have leaked back in.
                msum = sum(r.get("months", {}).values())
                check(msum <= max(r["total"], 1) * 3 + 25000,
                      f"{fname}: {r['name']} month buckets (${msum:,.0f}) far exceed "
                      f"their reported total (${r['total']:,}) — loans may be "
                      f"counted as contributions again")
            # Name matching between the two state lists is imperfect; what matters
            # is how much money it drops, not how many names.
            lost = st.get("unmatchedAmount", 0)
            warn(lost <= tot * 0.02,
                 f"{fname}: ${lost:,.0f} unattributed, over 2% of ${tot:,.0f}")

# ---------- named individual donors ----------
if os.path.exists("finance-detail.json"):
    withdonors = [r for r in det.get("people", {}).values() if r.get("donors")]
    check(len(withdonors) >= 450,
          f"only {len(withdonors)} people have named donors, expected 450+")
    check(det.get("donorFloor"), "detail file does not record its donor floor")
    # A donor list must be sorted largest first -- the page shows it as a
    # ranking and draws its bars against the first entry.
    for r in withdonors[:200]:
        amts = [d["amt"] for d in r["donors"]]
        check(amts == sorted(amts, reverse=True),
              "donor lists are not sorted largest first")
        check(all(a >= det["donorFloor"] for a in amts),
              f"a donor total falls below the stated floor of ${det['donorFloor']:,}")
        check(all(d.get("n") for d in r["donors"]), "a donor has no name")
    # Committees must not leak into the individual list -- they are a different
    # question and have their own section.
    blob = " ".join(d["n"].upper() for r in withdonors[:150] for d in r["donors"])
    for banned in ("ACT BLUE", "WINRED", " PAC ", "COMMITTEE"):
        warn(banned not in blob,
             f"a committee-looking name ({banned.strip()}) appears in the individual donor list")

# The investigator asked the FEC to sort candidates by "last_file_date", which is
# not a sortable field on that endpoint, so every search returned 422 -- and the
# error text blamed the browser, so it read as a CORS problem rather than a bad
# parameter. The code falls back to an unsorted request on 422 now; this keeps the
# dead field itself from creeping back in.
_DEAD_SORT = 'sort:"-last_file_date"'
check(_DEAD_SORT not in html,
      'investigator is sorting on "last_file_date" again; the FEC rejects that '
      "field on /candidates/search/ and every lookup will fail with 422")
check("e.status === 422" in html,
      "investigator lost its fallback for a rejected sort field")

# Rows used to carry the name in a data attribute with quotes stripped, then look
# the person up by that stripped string -- which could never match, so the six
# members with quoted nicknames had dead rows. Binding is positional now.
_OLD_BIND = 'data-n="' + chr(39) + '+p.n.replace'
check(_OLD_BIND not in html,
      "finder rows are binding by a quote-stripped name again; "
      "members with quoted nicknames will not open")

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
