#!/usr/bin/env python3
"""
Rebuilds finance.json from FEC bulk downloads. No API key required.

  python3 build_finance.py --out finance.json

Data sources (all public, all keyless):
  weball{cy}.zip  candidate financial summaries, every cycle 1980-present
  pas2{cy}.zip    itemized committee-to-candidate transactions
  cm{cy}.zip      committee master (names, org type, connected organization)

Run it on a schedule. The FEC refreshes bulk files nightly.
"""
import argparse, glob, io, json, os, sys, zipfile, urllib.request
from collections import defaultdict

BULK = "https://www.fec.gov/files/bulk-downloads"
UA = {"User-Agent": "gov-age-finance/1.0 (public data research)"}

SUMMARY_CYCLES = list(range(1980, 2027, 2))     # weball: cheap, take everything
DETAIL_CYCLES  = [2018, 2020, 2022, 2024, 2026] # pas2 + cm: heavier, recent only

ORG_TP = {"C": "Corporate", "L": "Labor", "M": "Membership", "T": "Trade association",
          "V": "Cooperative", "W": "Corp. without capital stock"}
CMTE_TP = {"Q": "Non-connected PAC", "N": "Non-qualified PAC", "O": "Super PAC",
           "Y": "Party committee", "X": "Party committee", "V": "Hybrid PAC",
           "W": "Hybrid PAC", "H": "House campaign", "S": "Senate campaign",
           "P": "Presidential campaign", "U": "Single-candidate independent",
           "I": "Independent-expenditure filer", "D": "Delegate committee",
           "E": "Electioneering communication", "Z": "Party non-federal"}

WEBALL = ["CAND_ID", "CAND_NAME", "CAND_ICI", "PTY_CD", "CAND_PTY_AFFILIATION", "TTL_RECEIPTS",
          "TRANS_FROM_AUTH", "TTL_DISB", "TRANS_TO_AUTH", "COH_BOP", "COH_COP", "CAND_CONTRIB",
          "CAND_LOANS", "OTHER_LOANS", "CAND_LOAN_REPAY", "OTHER_LOAN_REPAY", "DEBTS_OWED_BY",
          "TTL_INDIV_CONTRIB", "CAND_OFFICE_ST", "CAND_OFFICE_DISTRICT", "SPEC_ELECTION",
          "PRIM_ELECTION", "RUN_ELECTION", "GEN_ELECTION", "GEN_ELECTION_PRECENT",
          "OTHER_POL_CMTE_CONTRIB", "POL_PTY_CONTRIB", "CVG_END_DT", "INDIV_REFUNDS",
          "CMTE_REFUNDS"]


CURRENT_CYCLE = 2026     # the only cycle whose files still change

def fetch(cycle, stem, cache="raw", force=False):
    """Download and unzip one bulk file, caching locally.

    Historical cycles are immutable, so the cache is always safe for them.
    Pass force=True to re-pull the live cycle."""
    os.makedirs(cache, exist_ok=True)
    tag = f"{stem}{str(cycle)[2:]}"
    local = os.path.join(cache, tag)
    stale = force and cycle == CURRENT_CYCLE
    if not stale and os.path.isdir(local) and glob.glob(os.path.join(local, "*.txt")):
        return glob.glob(os.path.join(local, "*.txt"))[0]
    url = f"{BULK}/{cycle}/{tag}.zip"
    try:
        raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600).read()
        zipfile.ZipFile(io.BytesIO(raw)).extractall(local)
    except Exception as e:
        print(f"  ! {tag}: {e}", file=sys.stderr)
        return None
    hits = glob.glob(os.path.join(local, "*.txt"))
    return hits[0] if hits else None


def f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def month_of(raw):
    """FEC transaction dates are MMDDYYYY with no separators.

    Returned as YYYY-MM so the page can filter and chart by period. Blank and
    malformed dates are common in bulk data -- they are dropped rather than
    guessed, so a month bucket is always a real reported date. Amounts still
    count toward the career and per-cycle totals either way, which is why the
    sum of the months can come in under the cycle total."""
    raw = (raw or "").strip()
    if len(raw) != 8 or not raw.isdigit():
        return None
    mm, yyyy = raw[:2], raw[4:]
    if not ("01" <= mm <= "12") or not (1980 <= int(yyyy) <= 2100):
        return None
    return f"{yyyy}-{mm}"


def build(roster_path, out_path, force=False):
    roster = json.load(open(roster_path, encoding="utf-8"))
    owner = {cid: person for person, ids in roster.items() for cid in ids}

    # ---------- 1. career summaries, every cycle ----------
    series = defaultdict(dict)
    print("candidate summaries:")
    for cy in SUMMARY_CYCLES:
        path = fetch(cy, "weball", force=force)
        if not path:
            continue
        hit = 0
        for line in open(path, encoding="latin-1"):
            p = line.rstrip("\n").split("|")
            if len(p) < 27:
                continue
            r = dict(zip(WEBALL, p))
            cid = r["CAND_ID"].strip()
            who = owner.get(cid)
            if not who:
                continue
            d = series[who].setdefault(cy, {"receipts": 0, "indiv": 0, "pac": 0,
                                            "party": 0, "self": 0, "ici": "", "office": ""})
            d["receipts"] += f(r["TTL_RECEIPTS"])
            d["indiv"]    += f(r["TTL_INDIV_CONTRIB"])
            d["pac"]      += f(r["OTHER_POL_CMTE_CONTRIB"])
            d["party"]    += f(r["POL_PTY_CONTRIB"])
            d["self"]     += f(r["CAND_CONTRIB"]) + f(r["CAND_LOANS"])
            d["ici"]       = r["CAND_ICI"].strip() or d["ici"]
            d["office"]    = cid[0]
            hit += 1
        print(f"  {cy}: {hit}")

    # ---------- 2. committee master ----------
    cm = {}
    print("committee master:")
    for cy in DETAIL_CYCLES:
        path = fetch(cy, "cm", force=force)
        if not path:
            continue
        n = 0
        for line in open(path, encoding="latin-1"):
            p = line.rstrip("\n").split("|")
            if len(p) < 15:
                continue
            cm[p[0]] = {"nm": p[1].strip(), "tp": p[9].strip(),
                        "org": p[12].strip(), "conn": p[13].strip()}
            n += 1
        print(f"  {cy}: {n}")

    # ---------- 3. itemized committee money ----------
    # 24K direct contribution · 24Z in-kind · 24E independent expenditure supporting
    direct  = defaultdict(lambda: defaultdict(float))          # person -> cmte -> $
    dircyc  = defaultdict(lambda: defaultdict(float))          # person -> cycle -> $
    outside = defaultdict(lambda: defaultdict(float))          # person -> cmte -> $
    months  = defaultdict(lambda: defaultdict(float))          # person -> YYYY-MM -> $
    outmon  = defaultdict(lambda: defaultdict(float))          # person -> YYYY-MM -> $
    print("itemized transactions:")
    for cy in DETAIL_CYCLES:
        path = fetch(cy, "pas2", force=force)
        if not path:
            continue
        n = 0
        for line in open(path, encoding="latin-1"):
            p = line.rstrip("\n").split("|")
            if len(p) < 22:
                continue
            who = owner.get(p[16].strip())
            if not who:
                continue
            tp, amt, cmte = p[5].strip(), f(p[14]), p[0].strip()
            when = month_of(p[13])
            if tp in ("24K", "24Z"):
                direct[who][cmte] += amt
                dircyc[who][cy]   += amt
                if when:
                    months[who][when] += amt
            elif tp == "24E":
                outside[who][cmte] += amt
                if when:
                    outmon[who][when] += amt
            else:
                continue
            n += 1
        print(f"  {cy}: {n}")

    # ---------- 4. assemble ----------
    def label(cmte):
        c = cm.get(cmte)
        if not c:
            return {"nm": cmte, "org": "", "tp": ""}
        return {"nm": c["conn"] or c["nm"],
                "org": ORG_TP.get(c["org"], ""),
                "tp": CMTE_TP.get(c["tp"], "")}

    people = {}
    for who in roster:
        cyc = series.get(who, {})
        career = {"receipts": 0, "indiv": 0, "pac": 0, "party": 0, "self": 0}
        for d in cyc.values():
            for k in career:
                career[k] += d[k]

        mix = defaultdict(float)
        top = []
        for cmte, amt in sorted(direct[who].items(), key=lambda x: -x[1]):
            L = label(cmte)
            mix[L["org"] or L["tp"] or "Other"] += amt
            if len(top) < 15:
                top.append({"n": L["nm"], "o": L["org"], "t": L["tp"], "a": round(amt)})

        out_top = []
        for cmte, amt in sorted(outside[who].items(), key=lambda x: -x[1])[:8]:
            L = label(cmte)
            out_top.append({"n": L["nm"], "t": L["tp"], "a": round(amt)})

        people[who] = {
            "ids": roster[who],
            "career": {k: round(v) for k, v in career.items()},
            "cycles": {str(y): {k: round(v) if isinstance(v, float) else v
                                for k, v in d.items()} for y, d in sorted(cyc.items())},
            "first": min(cyc) if cyc else None,
            "last": max(cyc) if cyc else None,
            "top": top,
            "mix": {k: round(v) for k, v in sorted(mix.items(), key=lambda x: -x[1])},
            "directTotal": round(sum(direct[who].values())),
            "directByCycle": {str(y): round(v) for y, v in sorted(dircyc[who].items())},
            "outsideTotal": round(sum(outside[who].values())),
            "outsideTop": out_top,
            "donorCount": len(direct[who]),
        }

    payload = {
        "built": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "summaryCycles": [c for c in SUMMARY_CYCLES],
        "detailCycles": DETAIL_CYCLES,
        "people": people,
    }
    json.dump(payload, open(out_path, "w", encoding="utf-8", newline=""), separators=(",", ":"))
    print(f"\nwrote {out_path}  ({os.path.getsize(out_path)/1024:.0f} KB, {len(people)} people)")

    # ---------- month-by-month detail, kept out of the core file ----------
    # The core file is inlined into index.html so the page works from disk. Month
    # buckets roughly double its size and are only read when someone opens a money
    # profile, so they ship separately and load on the first drawer open. Anything
    # added later that is large and per-person -- named donors above all -- belongs
    # in here, not in the core file.
    detail_path = os.path.splitext(out_path)[0] + "-detail.json"

    # Named donors are written into this same file by build_donors.py, which
    # runs on its own much slower schedule because it reads ~6 GB of FEC bulk
    # data. Rebuilding this file from scratch every week would delete them
    # silently -- the page would simply stop showing donors and nothing would
    # fail -- so the donor keys are carried across.
    prior = {}
    if os.path.exists(detail_path):
        try:
            prior = json.load(open(detail_path, encoding="utf-8"))
        except (ValueError, OSError):
            prior = {}
    prior_people = prior.get("people", {})

    detail = {
        "built": payload["built"],
        "people": {
            name: {
                "months": {m: round(v) for m, v in sorted(months[name].items())},
                "outMonths": {m: round(v) for m, v in sorted(outmon[name].items())},
            }
            for name in people
            if months[name] or outmon[name]
        },
    }
    carried = 0
    for name, old_rec in prior_people.items():
        if not old_rec.get("donors"):
            continue
        detail["people"].setdefault(name, {})["donors"] = old_rec["donors"]
        carried += 1
    for key in ("donorFloor", "donorCycles"):
        if key in prior:
            detail[key] = prior[key]
    if carried:
        print(f"  carried {carried} people's named donors through from the previous build")
    json.dump(detail, open(detail_path, "w", encoding="utf-8", newline=""),
              separators=(",", ":"))
    # A person with itemised cheques but no summary receipts almost always means a
    # missing FEC candidate id, not a candidate who raised nothing -- the two bulk
    # files can file the same person under different ids. Silent $0 is the failure
    # mode, so say it loudly and let verify.py fail the build.
    ghosts = [n for n, r in people.items()
              if r["career"]["receipts"] == 0 and r.get("directTotal", 0) > 0]
    if ghosts:
        print("")
        print("  !! %d tracked people have committee cheques but $0 in summary "
              "receipts -- they are probably missing a second FEC candidate id:"
              % len(ghosts))
        for n in ghosts:
            print(f"     {n}  ${people[n]['directTotal']:,.0f} itemised, ids={roster[n]}")

    print(f"wrote {detail_path}  ({os.path.getsize(detail_path)/1024:.0f} KB, "
          f"{len(detail['people'])} people with dated transactions)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--roster", default="roster_map.json")
    ap.add_argument("--out", default="finance.json")
    ap.add_argument("--fresh-current", action="store_true",
                    help="ignore the cache for the live cycle (use this in CI)")
    a = ap.parse_args()
    build(a.roster, a.out, force=a.fresh_current)
