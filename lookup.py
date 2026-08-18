#!/usr/bin/env python3
"""
Deep drill-down on one candidate, from the FEC bulk files already on disk.

    python3 lookup.py --name gleason
    python3 lookup.py --id S6FL00848
    python3 lookup.py --name "ocasio" --min 1000

The page shows a summary. This shows the receipts underneath it: every itemised
committee cheque with the donor committee's type and connected organisation, and
every itemised individual contribution with employer and occupation. No API key,
no rate limit -- it reads the same bulk files the pipeline downloads.

Coverage is bounded by what is cached in raw/:
  weball{cy}   candidate summaries, every cycle 1980-2026
  itpas2{cy}   committee -> candidate transactions, 2018-2026
  itcont{cy}   individual contributions, whichever cycles were fetched
  cm{cy}       committee master, for donor names and types
  ccl{cy}      candidate -> committee linkage
Anything outside those cycles is simply not on disk, and is reported as such
rather than as an absence of money.
"""
import argparse, glob, io, json, os, sys, zipfile
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAW = "raw"
ORG_TP = {"C": "Corporate", "L": "Labor", "M": "Membership", "T": "Trade assoc",
          "V": "Cooperative", "W": "Corp w/o stock"}
CMTE_TP = {"Q": "Non-connected PAC", "N": "Non-qualified PAC", "O": "Super PAC",
           "Y": "Party", "X": "Party", "V": "Hybrid PAC", "W": "Hybrid PAC",
           "H": "House campaign", "S": "Senate campaign", "P": "Presidential",
           "U": "Single-candidate IE", "I": "IE filer", "D": "Delegate cmte",
           "E": "Electioneering", "Z": "Party non-federal"}
TXN = {"24K": "direct contribution", "24Z": "in-kind", "24E": "independent expenditure FOR",
       "24A": "independent expenditure AGAINST", "24C": "coordinated expenditure",
       "24F": "communication cost FOR", "24N": "communication cost AGAINST"}


def usd(v):
    return f"${v:,.0f}"


def dt(raw):
    raw = (raw or "").strip()
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[4:]}-{raw[:2]}-{raw[2:4]}"
    return raw or "—"


def cycles_on_disk(stem):
    out = []
    for p in glob.glob(os.path.join(RAW, f"{stem}*")):
        tag = os.path.basename(p).replace(".zip", "")
        yy = tag[len(stem):]
        if yy.isdigit():
            out.append(2000 + int(yy) if int(yy) < 50 else 1900 + int(yy))
    return sorted(set(out))


def read_lines(stem, cycle):
    """Yield decoded lines for a cached bulk file, zipped or extracted."""
    d = os.path.join(RAW, f"{stem}{str(cycle)[2:]}")
    if os.path.isdir(d):
        hits = glob.glob(os.path.join(d, "*.txt"))
        if hits:
            with open(hits[0], encoding="latin-1") as fh:
                yield from fh
            return
    z = d + ".zip"
    if os.path.exists(z):
        with zipfile.ZipFile(z) as zf:
            names = [n for n in zf.namelist() if n.endswith(".txt") and "/" not in n]
            if names:
                with zf.open(names[0]) as fh:
                    yield from io.TextIOWrapper(fh, encoding="latin-1")


def find_candidates(needle_name, needle_id):
    """Search every cached candidate-summary file."""
    found = {}
    for cy in cycles_on_disk("weball"):
        for ln in read_lines("weball", cy):
            p = ln.rstrip("\n").split("|")
            if len(p) < 20:
                continue
            cid, nm = p[0].strip(), p[1].strip()
            if needle_id and cid.upper() != needle_id.upper():
                continue
            if needle_name and needle_name.upper() not in nm.upper():
                continue
            rec = found.setdefault(cid, {"name": nm, "party": p[4].strip(),
                                         "state": p[18].strip(), "district": p[19].strip(),
                                         "cycles": {}})
            def f(x):
                try: return float(x)
                except (TypeError, ValueError): return 0.0
            rec["cycles"][cy] = {
                "receipts": f(p[5]), "indiv": f(p[17]), "pac": f(p[25]),
                "party": f(p[26]), "self": f(p[11]), "disb": f(p[7]),
                "cash": f(p[10]), "ici": p[2].strip(),
            }
    return found


def committee_master():
    cm = {}
    for cy in cycles_on_disk("cm"):
        for ln in read_lines("cm", cy):
            p = ln.rstrip("\n").split("|")
            if len(p) < 15:
                continue
            cm[p[0].strip()] = {"nm": p[1].strip(), "tp": p[9].strip(),
                                "org": p[12].strip(), "conn": p[13].strip()}
    return cm


def committee_cheques(cand_ids):
    """Every itemised committee -> candidate transaction."""
    rows = []
    for cy in cycles_on_disk("itpas2") or cycles_on_disk("pas2"):
        stem = "itpas2" if os.path.exists(os.path.join(RAW, f"itpas2{str(cy)[2:]}")) else "pas2"
        for ln in read_lines(stem, cy):
            p = ln.rstrip("\n").split("|")
            if len(p) < 22 or p[16].strip() not in cand_ids:
                continue
            try:
                amt = float(p[14] or 0)
            except ValueError:
                continue
            rows.append({"cycle": cy, "cmte": p[0].strip(), "tp": p[5].strip(),
                         "name": p[7].strip(), "date": p[13].strip(), "amt": amt})
    return rows


def own_committees(cand_ids):
    out = {}
    for cy in cycles_on_disk("ccl"):
        for ln in read_lines("ccl", cy):
            p = ln.rstrip("\n").split("|")
            if len(p) < 6:
                continue
            if p[0].strip() in cand_ids:
                out[p[3].strip()] = p[5].strip()
    return out


def individual_gifts(cmte_ids, floor):
    rows = []
    want = {c.encode() for c in cmte_ids}
    if not want:
        return rows, []
    scanned = []
    for cy in cycles_on_disk("indiv"):
        scanned.append(cy)
        z = os.path.join(RAW, f"indiv{str(cy)[2:]}.zip")
        with zipfile.ZipFile(z) as zf:
            member = "itcont.txt"
            if member not in zf.namelist():
                member = [n for n in zf.namelist() if n.endswith(".txt") and "/" not in n][0]
            with zf.open(member) as fh:
                for raw in fh:
                    if raw[:9] not in want:
                        continue
                    p = raw.rstrip(b"\r\n").split(b"|")
                    if len(p) < 15:
                        continue
                    try:
                        amt = float(p[14] or 0)
                    except ValueError:
                        continue
                    if amt < floor:
                        continue
                    g = lambda i: p[i].decode("latin-1").strip()
                    rows.append({"cycle": cy, "cmte": g(0), "tp": g(5), "entity": g(6),
                                 "name": g(7), "city": g(8), "state": g(9),
                                 "emp": g(11), "occ": g(12), "date": g(13), "amt": amt})
    return rows, scanned


def main(a):
    cands = find_candidates(a.name, a.id)
    if not cands:
        print(f"No FEC candidate matches {a.name or a.id!r} in the cached summary files.")
        return
    if len(cands) > 1 and not a.id:
        print(f"{len(cands)} candidates match — narrow with --id:\n")
        for cid, r in cands.items():
            tot = sum(c["receipts"] for c in r["cycles"].values())
            print(f"  {cid}  {r['name']:32s} {r['party']:4s} {r['state']}-{r['district']}  "
                  f"{usd(tot)} across {len(r['cycles'])} cycle(s)")
        return

    cid, r = next(iter(cands.items()))
    ids = {cid}
    W = 78
    print("=" * W)
    print(f"  {r['name']}   ({r['party']})   {r['state']}-{r['district']}")
    print(f"  FEC candidate id {cid}")
    print("=" * W)

    # ---------- summary by cycle ----------
    print("\nCANDIDATE SUMMARY, per cycle (source: weball)")
    print(f"  {'cycle':6s} {'receipts':>12s} {'individuals':>12s} {'PACs':>11s} "
          f"{'party':>9s} {'self':>10s} {'spent':>12s}  inc/chal")
    tot = defaultdict(float)
    for cy in sorted(r["cycles"]):
        c = r["cycles"][cy]
        for k in ("receipts", "indiv", "pac", "party", "self", "disb"):
            tot[k] += c[k]
        print(f"  {cy:<6d} {usd(c['receipts']):>12s} {usd(c['indiv']):>12s} "
              f"{usd(c['pac']):>11s} {usd(c['party']):>9s} {usd(c['self']):>10s} "
              f"{usd(c['disb']):>12s}  {c['ici'] or '-'}")
    print(f"  {'TOTAL':<6s} {usd(tot['receipts']):>12s} {usd(tot['indiv']):>12s} "
          f"{usd(tot['pac']):>11s} {usd(tot['party']):>9s} {usd(tot['self']):>10s} "
          f"{usd(tot['disb']):>12s}")
    if tot["receipts"]:
        print(f"  PAC share of everything raised: "
              f"{100*tot['pac']/tot['receipts']:.1f}%")

    # ---------- committee cheques ----------
    cm = committee_master()
    rows = committee_cheques(ids)
    print(f"\nITEMISED COMMITTEE CHEQUES  ({len(rows)} transactions on disk)")
    if not rows:
        print("  none. Itemised committee data on disk covers "
              f"{cycles_on_disk('itpas2') or cycles_on_disk('pas2')}.")
    else:
        agg = defaultdict(lambda: {"amt": 0.0, "n": 0, "kinds": set(), "last": ""})
        for x in rows:
            k = x["cmte"]
            agg[k]["amt"] += x["amt"]; agg[k]["n"] += 1
            agg[k]["kinds"].add(x["tp"])
            agg[k]["last"] = max(agg[k]["last"], x["date"] or "")
        for k, v in sorted(agg.items(), key=lambda kv: -kv[1]["amt"]):
            info = cm.get(k, {})
            nm = info.get("nm") or next((x["name"] for x in rows if x["cmte"] == k), k)
            bits = []
            if info.get("tp"): bits.append(CMTE_TP.get(info["tp"], info["tp"]))
            if info.get("org"): bits.append(ORG_TP.get(info["org"], info["org"]))
            kinds = ", ".join(sorted(TXN.get(t, t) for t in v["kinds"]))
            print(f"  {usd(v['amt']):>10s}  {nm[:44]:44s} {v['n']:3d}x  {k}")
            print(f"              {' · '.join(bits) or 'type not in committee master'}"
                  f"{('  — ' + info['conn']) if info.get('conn') else ''}")
            print(f"              {kinds}   last {dt(v['last'])}")
        print(f"\n  every transaction, newest first:")
        for x in sorted(rows, key=lambda x: x["date"][4:] + x["date"][:4], reverse=True)[:a.rows]:
            nm = cm.get(x["cmte"], {}).get("nm") or x["name"]
            print(f"    {dt(x['date'])}  {usd(x['amt']):>9s}  {TXN.get(x['tp'], x['tp']):24s} {nm[:38]}")

    # ---------- individual gifts ----------
    own = own_committees(ids)
    print(f"\nTHEIR OWN COMMITTEES (from candidate-committee linkage): "
          f"{', '.join(f'{c} [{d}]' for c, d in own.items()) or 'none on disk'}")
    gifts, scanned = individual_gifts(set(own), a.min)
    print(f"\nITEMISED INDIVIDUAL CONTRIBUTIONS at {usd(a.min)}+  "
          f"({len(gifts)} on disk, cycles scanned: {scanned or 'none cached'})")
    if gifts:
        byname = defaultdict(lambda: {"amt": 0.0, "n": 0, "occ": "", "emp": "", "where": ""})
        for g in gifts:
            k = g["name"]
            byname[k]["amt"] += g["amt"]; byname[k]["n"] += 1
            byname[k]["occ"] = byname[k]["occ"] or g["occ"]
            byname[k]["emp"] = byname[k]["emp"] or g["emp"]
            byname[k]["where"] = byname[k]["where"] or f'{g["city"]}, {g["state"]}'
        print(f"  {len(byname)} distinct donors\n")
        for k, v in sorted(byname.items(), key=lambda kv: -kv[1]["amt"])[:a.rows]:
            print(f"  {usd(v['amt']):>9s}  {k[:34]:34s} {v['n']:2d}x  {v['where'][:22]:22s}"
                  f"  {v['occ'][:20]:20s} {v['emp'][:24]}")
        top = sorted(gifts, key=lambda g: -g["amt"])[:a.rows]
        print(f"\n  largest single gifts:")
        for g in top:
            print(f"    {dt(g['date'])}  {usd(g['amt']):>9s}  {g['name'][:30]:30s} "
                  f"{g['occ'][:18]:18s} {g['emp'][:22]}")
        by_m = defaultdict(float)
        for g in gifts:
            d = dt(g["date"])
            if len(d) == 10: by_m[d[:7]] += g["amt"]
        print(f"\n  by month:")
        for m in sorted(by_m):
            bar = "#" * max(1, int(28 * by_m[m] / max(by_m.values())))
            print(f"    {m}  {usd(by_m[m]):>10s}  {bar}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="")
    ap.add_argument("--id", default="")
    ap.add_argument("--min", type=float, default=0, help="floor for individual gifts")
    ap.add_argument("--rows", type=int, default=40)
    a = ap.parse_args()
    if not (a.name or a.id):
        ap.error("give --name or --id")
    main(a)
