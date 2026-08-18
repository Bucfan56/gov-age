#!/usr/bin/env python3
"""
Adds named individual donors to finance-detail.json.

    python3 build_donors.py --roster roster_map.json

The FEC publishes every itemised personal contribution in indiv{cy}.zip. It is
by far the largest file they release -- 5.7 GB of text for the 2026 cycle alone,
about 8 GB for 2024 -- so this streams it straight out of the zip and never
extracts it to disk or holds it in memory.

TWO JOINS ARE NEEDED, and the second one is the awkward part:

  1. Individual contributions carry a COMMITTEE id and never a candidate id, so
     ccl{cy}.zip (the candidate-committee linkage) maps committee -> candidate.
     Only the candidate's own committees count: designation P (principal) and
     A (authorized). Leadership PACs and joint fundraising committees are
     deliberately excluded -- money there is not money to the campaign.

  2. Donors are free text. "SMITH, JOHN" and "SMITH, JOHN A." are the same
     person to a reader and different strings to a computer, and nothing in the
     data resolves them. Totals here are per name-as-filed, which undercounts
     anyone who filed inconsistently. That is a real limitation, stated on the
     page, not something to quietly paper over.

WHAT IS AND IS NOT HERE: federal law only requires itemisation above $200, so
small-dollar donors are invisible by law rather than by omission. This script
additionally ignores anything under --floor to keep the working set sane. The
floor ships in the output so the page can say what it is.
"""
import argparse, io, json, os, sys, time, zipfile
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# indiv layout, pipe separated:
#  0 CMTE_ID  6 ENTITY_TP  7 NAME  8 CITY  9 STATE  11 EMPLOYER
# 12 OCCUPATION  13 TRANSACTION_DT  14 TRANSACTION_AMT
I_ENTITY, I_NAME, I_CITY, I_STATE = 6, 7, 8, 9
I_EMP, I_OCC, I_DT, I_AMT = 11, 12, 13, 14

# Individuals and the candidate themselves. Excludes committees and
# organisations, which arrive through the committee pipeline instead.
PERSONISH = {b"IND", b"CAN"}

# P principal campaign committee, A authorized by the candidate.
GOOD_DSGN = {"P", "A"}


def committee_map(cycle, roster_ids, cache="raw"):
    """committee id -> tracked person, via the candidate-committee linkage."""
    path = os.path.join(cache, f"ccl{str(cycle)[2:]}.zip")
    if not os.path.exists(path):
        return {}
    out = {}
    with zipfile.ZipFile(path) as z:
        name = z.namelist()[0]
        with z.open(name) as fh:
            for raw in io.TextIOWrapper(fh, encoding="latin-1"):
                p = raw.rstrip("\n").split("|")
                if len(p) < 6:
                    continue
                cand, cmte, dsgn = p[0].strip(), p[3].strip(), p[5].strip()
                who = roster_ids.get(cand)
                if who and dsgn in GOOD_DSGN and cmte:
                    out[cmte] = who
    return out


def scan(cycle, cmte_to_person, floor, keep, cache="raw", prune_every=8_000_000):
    """Stream one cycle's itemised individual contributions.

    Returns person -> {donor name -> [total, gifts, city/state, employer, occupation]}
    """
    path = os.path.join(cache, f"indiv{str(cycle)[2:]}.zip")
    if not os.path.exists(path):
        print(f"  {cycle}: no indiv file, skipped")
        return {}, 0

    wanted = {c.encode() for c in cmte_to_person}
    donors = defaultdict(dict)
    seen = hits = 0
    t0 = time.time()

    with zipfile.ZipFile(path) as z:
        # The archive also carries by_date/ slices of the same records; reading
        # them as well would double-count every contribution.
        member = "itcont.txt"
        if member not in z.namelist():
            member = [n for n in z.namelist() if n.endswith(".txt") and "/" not in n][0]
        with z.open(member) as fh:
            for raw in fh:
                seen += 1
                # CMTE_ID is the first field and always 9 characters, so this
                # rejects the ~99% of rows we do not care about with one slice
                # and one set lookup, before any splitting or decoding.
                if raw[:9] not in wanted:
                    continue
                p = raw.rstrip(b"\r\n").split(b"|")
                if len(p) < 15 or p[I_ENTITY].strip() not in PERSONISH:
                    continue
                try:
                    amt = float(p[I_AMT] or 0)
                except ValueError:
                    continue
                if amt < floor:
                    continue
                who = cmte_to_person.get(p[0].decode("latin-1"))
                if not who:
                    continue
                nm = p[I_NAME].decode("latin-1").strip()
                if not nm:
                    continue
                d = donors[who].get(nm)
                if d:
                    d[0] += amt
                    d[1] += 1
                else:
                    donors[who][nm] = [
                        amt, 1,
                        (p[I_CITY].decode("latin-1").strip() + ", "
                         + p[I_STATE].decode("latin-1").strip()).strip(", "),
                        p[I_EMP].decode("latin-1").strip(),
                        p[I_OCC].decode("latin-1").strip(),
                        p[I_DT].decode("latin-1").strip(),
                    ]
                hits += 1

                if prune_every and seen % prune_every == 0:
                    for k, v in donors.items():
                        if len(v) > keep * 8:
                            top = sorted(v.items(), key=lambda kv: -kv[1][0])[:keep * 4]
                            donors[k] = dict(top)
                    print(f"    {cycle}: {seen/1e6:.0f}M rows, {hits:,} kept "
                          f"({time.time()-t0:.0f}s)")

    print(f"  {cycle}: {seen:,} rows scanned, {hits:,} contributions kept, "
          f"{len(donors)} people, {time.time()-t0:.0f}s")
    return donors, hits


def main(roster_path, detail_path, cycles, floor, keep):
    roster = json.load(open(roster_path, encoding="utf-8"))
    roster_ids = {cid: person for person, ids in roster.items() for cid in ids}

    merged = defaultdict(dict)
    total_hits = 0
    for cy in cycles:
        cmap = committee_map(cy, roster_ids)
        print(f"cycle {cy}: {len(cmap)} candidate committees linked")
        got, hits = scan(cy, cmap, floor, keep)
        total_hits += hits
        for who, ds in got.items():
            tgt = merged[who]
            for nm, v in ds.items():
                cur = tgt.get(nm)
                if cur:
                    cur[0] += v[0]
                    cur[1] += v[1]
                else:
                    tgt[nm] = list(v)

    # ---------- fold into the detail file ----------
    detail = json.load(open(detail_path, encoding="utf-8"))
    people = detail.setdefault("people", {})
    added = 0
    for who, ds in merged.items():
        top = sorted(ds.items(), key=lambda kv: -kv[1][0])[:keep]
        if not top:
            continue
        rec = people.setdefault(who, {})
        rec["donors"] = [{
            "n": nm, "amt": round(v[0]), "gifts": v[1],
            "where": v[2], "emp": v[3], "occ": v[4],
        } for nm, v in top]
        added += 1

    detail["donorFloor"] = floor
    detail["donorCycles"] = cycles
    json.dump(detail, open(detail_path, "w", encoding="utf-8", newline=""),
              separators=(",", ":"))
    size = os.path.getsize(detail_path) / 1024
    print(f"\nwrote {detail_path}  ({size:.0f} KB)")
    print(f"  named donors for {added} of {len(roster)} tracked people, "
          f"top {keep} each, floor ${floor:,}, {total_hits:,} contributions read")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--roster", default="roster_map.json")
    ap.add_argument("--detail", default="finance-detail.json")
    ap.add_argument("--cycles", default="2026,2024")
    ap.add_argument("--floor", type=int, default=500,
                    help="ignore contributions under this (default 500)")
    ap.add_argument("--keep", type=int, default=15,
                    help="named donors kept per person (default 15)")
    a = ap.parse_args()
    main(a.roster, a.detail, [int(c) for c in a.cycles.split(",") if c],
         a.floor, a.keep)
