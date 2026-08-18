#!/usr/bin/env python3
"""
Rebuilds state-level campaign finance into state-<code>.json.

    python3 build_state.py --state FL

Governors and state legislators file with their own state, not the FEC, so none
of their money appears in the federal pipeline. There is no unified national
feed -- there are fifty separate systems, and no two share a format. So each
state gets an ADAPTER: a small class that knows how to list that state's
candidates and pull their contributions, behind one interface the rest of this
script and the page can rely on.

Adding a state means writing an adapter and registering it in ADAPTERS. Nothing
else here changes.

Florida is the reference implementation. Its Division of Elections exposes a
CGI endpoint that will return tab-separated values directly, which is far better
than most states manage.
"""
import argparse, io, json, os, re, sys, time, urllib.parse, urllib.request
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

UA = {"User-Agent": "gov-age-state-finance/1.0 (public data research)"}


def post(url, fields, timeout=180):
    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=body, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read().decode("latin-1")


# Contribution rows label the recipient with the party and office appended:
# "Donalds, Byron  (REP)(GOV)". The separator is TWO spaces after most names but
# only ONE after a name ending in an initial -- "Russo, Frank J. (NPA)(GOV)" --
# so splitting on a fixed separator silently drops those candidates' donors.
# Strip the suffix by its shape instead.
SUFFIX = re.compile(r"\s*\([A-Z]{2,4}\)\s*\([A-Z]{2,4}\)\s*$")


def norm(name):
    """Compare names without punctuation or spacing getting in the way."""
    return re.sub(r"[^A-Z0-9]+", " ", (name or "").upper()).strip()


def as_last_first(name):
    """'Frank J. Russo' -> 'RUSSO FRANK J'. Totals list names first-last, the
    contributions list names last-first, so one side has to be turned around."""
    parts = (name or "").split()
    if len(parts) < 2:
        return norm(name)
    return norm(parts[-1] + " " + " ".join(parts[:-1]))


def money(v):
    try:
        return float(str(v).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return 0.0


# --------------------------------------------------------------------------
#  Florida
# --------------------------------------------------------------------------
class Florida:
    code = "FL"
    name = "Florida"
    authority = "Florida Division of Elections"
    source = "https://dos.elections.myflorida.com/campaign-finance/contributions/"
    ENDPOINT = "https://dos.elections.myflorida.com/cgi-bin/contrib.exe"

    # Every office the database will report on, statewide down to water districts.
    OFFICES = {
        "PRE": "President of the United States",
        "PRN": "Presidential Minor Party Nominee",
        "USS": "United States Senator",
        "USR": "United States Representative",
        "GOV": "Governor",
        "SEC": "Secretary of State",
        "ATG": "Attorney General",
        "CMP": "Comptroller",
        "CFO": "Chief Financial Officer",
        "TRE": "Treasurer",
        "EDU": "Commissioner of Education",
        "AGR": "Commissioner of Agriculture",
        "STA": "State Attorney",
        "PUB": "Public Defender",
        "STS": "State Senator",
        "STR": "State Representative",
        "SCJ": "Supreme Court Justice",
        "DCA": "District Court of Appeal",
        "CTJ": "Circuit Judge",
        "BRC": "Babcock Ranch Community Independent Special District",
        "BGF": "Boca Grande Fire Control District",
        "CHI": "Chipola River Soil & Water Conservation District",
        "EWF": "Englewood Area Fire Control District",
        "EWC": "Englewood Water District",
        "GBA": "Gasparilla Island Bridge Authority",
        "MSL": "Lakewood Ranch Stewardship District",
        "ECW": "Lehigh Acres Municipal Services Improvement District",
        "LOX": "Loxahatchee River Environmental Control District",
        "MAN": "Manatee River Soil & Water Conservation District",
        "MED": "Mediterra Community Development District",
        "GUL": "Nature Coast Soil & Water District",
        "PLB": "Port LaBelle Community Development District",
        "SMM": "Sarasota-Manatee Airport Authority (Manatee)",
        "SMS": "Sarasota-Manatee Airport Authority (Sarasota)",
        "SEB": "Sebastian Inlet Tax District",
        "TOL": "Tolomato Community Development District",
    }

    STATEWIDE = {"GOV", "USS", "ATG", "CFO", "AGR", "SEC", "EDU", "TRE", "CMP",
                 "SCJ", "PRE", "PRN"}

    # FOUR WAYS THIS ENDPOINT FAILS SILENTLY -- all of them return HTTP 200 with a
    # header row and nothing else, so they look like "no data" rather than "bad
    # query". Each cost real time to find:
    #
    #  1. search_on picks which BRANCH of the form is read. 2 = candidate list of
    #     contributions, 3 = candidate totals, 4/5 = the committee equivalents.
    #     Passing office= with a committee branch silently matches nothing,
    #     because office is a candidate-branch field.
    #  2. party=All and committee=All must be sent explicitly. The browser form
    #     always includes them; omit them and every query returns zero rows.
    #  3. csort1 AND csort2 must both be set, or the server builds "ORDER BY a, "
    #     and echoes a raw SQL syntax error back to the client.
    #  4. queryformat=2 returns the tab-separated file. 1 returns an HTML page.
    BASE = {
        "party": "All",
        "committee": "All",
        "CanNameSrch": "2",
        "ComNameSrch": "2",
        "namesearch": "2",
        "csort1": "AMT",
        "csort2": "CAN",
        "queryformat": "2",
    }

    def __init__(self, pause=1.2):
        self.pause = pause

    def _query(self, **extra):
        fields = dict(self.BASE)
        fields.update({k: v for k, v in extra.items() if v not in (None, "")})
        text = post(self.ENDPOINT, fields)
        time.sleep(self.pause)          # the state runs this on one box; be polite
        if "Error in /cgi-bin" in text or "ODBC" in text:
            snippet = " ".join(text.split())[:160]
            raise RuntimeError(f"Florida rejected the query: {snippet}")
        rows = [r for r in text.replace("\r", "").split("\n") if r.strip()]
        if not rows:
            return []
        head = rows[0].split("\t")
        return [dict(zip(head, r.split("\t"))) for r in rows[1:]]

    def candidates(self, election, office):
        """Every candidate for one office, with their contribution total."""
        out = []
        for r in self._query(election=election, search_on="3", office=office,
                             rowlimit="3000"):
            nm = (r.get("Candidate Name") or "").strip()
            if not nm:
                continue
            out.append({
                "name": nm,
                "party": (r.get("Party") or "").strip(),
                "office": office,
                "district": (r.get("District") or "").strip(),
                "total": money(r.get("Total Amount")),
            })
        return out

    def contributions(self, election, office, min_amount, rowlimit=8000):
        """Named contributions at or above min_amount, with dates."""
        out = []
        for r in self._query(election=election, search_on="2", office=office,
                             cdollar_minimum=str(min_amount),
                             rowlimit=str(rowlimit)):
            who = (r.get("Candidate/Committee") or "").strip()
            if not who:
                continue
            out.append({
                "to": who,
                "date": (r.get("Date") or "").strip(),
                "amount": money(r.get("Amount")),
                "type": (r.get("Typ") or "").strip(),
                "from": (r.get("Contributor Name") or "").strip(),
                "where": (r.get("City State Zip") or "").strip(),
                "occupation": (r.get("Occupation") or "").strip(),
            })
        return out


ADAPTERS = {"FL": Florida}


# --------------------------------------------------------------------------
def iso_date(us):
    """Florida reports MM/DD/YYYY. Store YYYY-MM-DD so it sorts and slices."""
    p = (us or "").split("/")
    if len(p) != 3 or not all(x.isdigit() for x in p):
        return None
    m, d, y = p
    return f"{y}-{m.zfill(2)}-{d.zfill(2)}"


def build(state, elections, min_amount, top_n, offices=None, out=None):
    A = ADAPTERS[state]
    a = A()
    offices = offices or list(A.OFFICES)
    out = out or f"state-{state.lower()}.json"

    people, skipped, unmatched = {}, [], []
    print(f"{A.name} — {len(offices)} offices × {len(elections)} election(s)\n")

    for election in elections:
        for code in offices:
            label = A.OFFICES.get(code, code)
            try:
                cands = a.candidates(election, code)
            except Exception as e:
                skipped.append((election, code, f"totals: {e}"))
                print(f"  !! {election} {code:4s} {label[:34]:34s} {e}")
                continue

            try:
                gifts = a.contributions(election, code, min_amount)
            except Exception as e:
                gifts = []
                skipped.append((election, code, f"contributions: {e}"))

            # Contributions come back keyed by a display string that repeats the
            # party and office -- "DeSantis, Ron  (REP)(GOV)" -- so match on the
            # leading name only.
            by_person = defaultdict(list)
            for g in gifts:
                by_person[norm(SUFFIX.sub("", g["to"]))].append(g)

            for c in cands:
                pid = f'{c["name"]}|{code}|{c["district"]}'
                rec = people.setdefault(pid, {
                    "name": c["name"], "party": c["party"],
                    "office": code, "officeName": label,
                    "district": c["district"],
                    "statewide": code in A.STATEWIDE,
                    "elections": {}, "months": defaultdict(float), "donors": {},
                })
                rec["elections"][election] = round(c["total"])

                hits = (by_person.get(as_last_first(c["name"]))
                        or by_person.get(norm(c["name"])) or [])
                for g in hits:
                    iso = iso_date(g["date"])
                    if iso:
                        rec["months"][iso[:7]] += g["amount"]
                    d = rec["donors"].setdefault(
                        g["from"], {"n": g["from"], "amt": 0.0, "gifts": 0,
                                    "where": g["where"], "occ": g["occupation"]})
                    d["amt"] += g["amount"]
                    d["gifts"] += 1

            n_g = sum(len(v) for v in by_person.values())
            matched = set()
            for c in cands:
                for k in (as_last_first(c["name"]), norm(c["name"])):
                    if k in by_person:
                        matched.add(k)
                        break
            orphan = sorted(set(by_person) - matched)
            print(f"  {election} {code:4s} {label[:36]:36s} "
                  f"{len(cands):5d} candidates  {n_g:6d} contributions"
                  + (f"  !! {len(orphan)} unmatched" if orphan else ""))
            if orphan:
                unmatched.extend((election, code, o) for o in orphan[:20])

    # ---------- shape for the page ----------
    final = {}
    for pid, r in people.items():
        donors = sorted(r["donors"].values(), key=lambda d: -d["amt"])[:top_n]
        final[pid] = {
            "name": r["name"], "party": r["party"],
            "office": r["office"], "officeName": r["officeName"],
            "district": r["district"], "statewide": r["statewide"],
            "elections": r["elections"],
            "total": round(sum(r["elections"].values())),
            "months": {m: round(v) for m, v in sorted(r["months"].items())},
            "donors": [{"n": d["n"], "amt": round(d["amt"]), "gifts": d["gifts"],
                        "where": d["where"], "occ": d["occ"]} for d in donors],
        }

    payload = {
        "built": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "state": state,
        "stateName": A.name,
        "authority": A.authority,
        "source": A.source,
        "elections": elections,
        # Everything below this threshold is genuinely absent, not zero. Say so
        # on the page rather than letting a short donor list imply nobody gave.
        "donorFloor": min_amount,
        "offices": {k: v for k, v in A.OFFICES.items() if k in offices},
        "people": final,
    }
    json.dump(payload, open(out, "w", encoding="utf-8", newline=""),
              separators=(",", ":"))

    withmoney = sum(1 for r in final.values() if r["total"] > 0)
    grand = sum(r["total"] for r in final.values())
    print(f"\nwrote {out}  ({os.path.getsize(out)/1024:.0f} KB)")
    print(f"  {len(final)} candidates, {withmoney} with money, "
          f"${grand/1e6:.1f}M total")
    if skipped:
        print(f"  !! {len(skipped)} office/election combinations failed:")
        for e, c, why in skipped[:10]:
            print(f"     {e} {c}: {why[:110]}")
    # Contributions whose recipient matched no candidate mean money is being
    # dropped on the floor. Loud, because the symptom is a candidate who looks
    # like they raised nothing from anyone.
    if unmatched:
        print(f"  !! {len(unmatched)} contribution recipients matched no candidate:")
        for e, c, o in unmatched[:12]:
            print(f"     {e} {c}: {o[:70]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="FL", choices=sorted(ADAPTERS))
    ap.add_argument("--elections", default="20261103-GEN,20221108-GEN",
                    help="comma-separated state election ids")
    ap.add_argument("--min-amount", type=int, default=1000,
                    help="only name contributions at or above this (default 1000)")
    ap.add_argument("--top", type=int, default=25,
                    help="how many named donors to keep per candidate")
    ap.add_argument("--offices", default="",
                    help="comma-separated office codes; default is every office")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    build(a.state,
          [e for e in a.elections.split(",") if e],
          a.min_amount, a.top,
          [o for o in a.offices.split(",") if o] or None,
          a.out or None)
