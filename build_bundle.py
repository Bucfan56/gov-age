#!/usr/bin/env python3
"""Build one state's guide for the app: states/<ST>/state.json plus one file per district.

    py build_bundle.py AL

Reads buddy/results/roster/<ST>.json (who ran), ballot/inputs/<ST>/fed_money_all.json and geo/zip_districts.json,
and ballot/inputs/<ST>/research/*.json (one file per person, see buddy/research/PROMPT.md).
Scoring is Florida's own code, build_ballot.score() and build_florida.finalize(), so every state is held to the same rules.
Someone with no research yet still gets a card: their money if federal, and the meters they have no evidence for stay empty.
"""
import io, json, re, sys, time, urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).parent
ST = sys.argv[1]
INPUTS = ROOT / "ballot" / "inputs" / ST
sys.argv = [sys.argv[0], str(INPUTS)]       # build_florida reads its inputs folder from here when imported
sys.path.insert(0, str(ROOT / "buddy" / "research"))
import build_florida as F  # noqa: E402
import make_prompt as P  # noqa: E402
import rules as R  # noqa: E402

B = F.B
STATE = P.STATE_NAMES[ST]
OUT = ROOT / "states" / ST
PHOTOS = ROOT / "ballot" / "photos" / ST
PARTY = {"R": "REP", "D": "DEM", "L": "Libertarian", "G": "Green", "I": "NPA", "": "NPA"}
ORDER = {"ussen": 0, "gov": 1, "ltgov": 2, "ag": 3, "sos": 4, "treas": 5, "auditor": 6, "agcomm": 7}
# The race ids the app already knows; any other statewide office uses its result key as its id.
IDS = {"gov": "governor", "ussen": "senate", "ag": "ag", "agcomm": "agriculture"}


def research(person):
    f = INPUTS / "research" / f"{P.person_file(person)}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def fed_match(name, senate, dist=None):
    """The FEC files name people 'LAST, FIRST M', often by a legal name ('POU, NELIDA' for Nellie Pou). Inside one race, one person
    with that last name is enough. If two share it, one first name must start the other. Otherwise there's no match: wrong money is worse than none."""
    words = re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", "", F.fold(re.sub(r'\([^)]*\)|"[^"]*"', "", name))).replace(",", " ").split()
    if len(words) < 2:
        return None
    first, last = words[0], words[-1]
    same = []
    for k, v in F.FED.items():
        if not v["fec_id"].startswith("S" if senate else "H") or (dist is not None and int(v.get("district") or -1) != dist):
            continue
        family = F.fold(k.split(",")[0]).split()
        given = F.fold(k.split(",", 1)[1]).split() if "," in k else []
        if family and family[-1] == last:
            same.append((v["fec_id"], given[0] if given else ""))
    if len(same) == 1:
        return same[0][0]
    close = [i for i, g in same if g and (g.startswith(first) or first.startswith(g))]
    if len(close) > 1:      # the FEC can list one person under two ids sharing one committee (Rob Menendez). Two different people never share one.
        recs = [F.FED_BY_ID[i] for i in close]
        if set.intersection(*(set(r["committees"]) for r in recs)):
            return max(recs, key=lambda r: r["itemized_indiv"]["amt"])["fec_id"]
    return close[0] if len(close) == 1 else None


def get_photo(person, p):
    name, url = person["name"], (p or {}).get("url")
    if not url:
        return None
    f = f"{P.person_file(person)}.jpg"
    if not (PHOTOS / f).exists():
        try:
            data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "BallotBuddy/1.0 (https://ballotbuddy.app; voter guide)"}), timeout=30).read()
            time.sleep(2)      # Wikimedia refuses a fast reader
            if len(data) < 1500:
                return None
            PHOTOS.mkdir(parents=True, exist_ok=True)
            im = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
            im.thumbnail((800, 800))      # the 186 MB photo folder ships to GitHub Pages, so every portrait is kept small
            im.save(PHOTOS / f, "JPEG", quality=82, optimize=True)
        except Exception as e:
            print("   photo failed", name, str(e)[:70], file=sys.stderr)
            return None
    return {"f": f"{ST}/{f}", "credit": p.get("credit") or "public source", "page": url}


STATE_FILE = F.load(INPUTS / "state_money.json", {})
SITTING = F.load(INPUTS / "us_attendance.json", {})      # today's members of Congress on this state's ballot, from buddy/research/us_attendance.py
STATE_SOURCE = {"AL": ("Alabama Fair Campaign Practices Act system", "https://fcpa.alabamavotes.gov/page.request.do?page=page.acfPublicDownloadData")}


def state_money(name, home):
    """A state candidate's money, with the same arithmetic as Florida's fl_district_money. In-kind gifts count, loans are shown apart, and street addresses were never kept."""
    rec = STATE_FILE.get(name)
    if not rec or not rec["gifts"]:
        return {}
    gift = home_amt = instate = out = org = dev = home_dev = 0.0
    last, donors = "", defaultdict(lambda: [0.0, 0, ""])
    for g in rec["gifts"]:
        amt = g["amt"]
        gift += amt
        d = g["date"]
        if len(d) == 10:
            last = max(last, f"{d[6:]}-{d[:2]}-{d[3:5]}")
        z = g["zip"]
        if z in home:
            home_amt += amt
        if g["st"] == ST:
            instate += amt
        elif g["st"].strip():
            out += amt
        if g["type"] in ("PAC", "Group/Business/Corporation") or F.ORG.search(g["donor"].upper()):
            org += amt
        if F.DEV.search(g["donor"].upper()):
            dev += amt
            if z in home:
                home_dev += amt
        x = donors[(g["donor"].upper(), z)]
        x[0] += amt
        x[1] += 1
        x[2] = f"{F.B_tc(g['city'])}, {g['st']} {z}".strip()
    if gift <= 0:
        return {}
    pct = lambda v: round(100 * v / gift, 1)
    source, url = STATE_SOURCE[ST]
    return {"raised": round(gift), "through": f"campaign account, reports through {last}", "local_pct": pct(home_amt), "fl_pct": pct(instate), "out_pct": pct(out), "org_pct": pct(org),
            "build_land_pct": pct(dev), "land_pct": pct(dev), "local_clean_pct": pct(home_amt - home_dev), "loans": round(rec["loans"]) or None,
            "top": [[F.B_tc(k[0]), round(v[0]), f"x{v[1]} · {v[2]}"] for k, v in sorted(donors.items(), key=lambda kv: -kv[1][0])[:10]],
            "note": "Covers January 2023 on, primary and general. Party-committee lines are often in-kind staff and mail.",
            "source": f"{source}, downloaded Nov 5, 2026", "source_url": url}


def card(person, senate=None, home=(), dist=None):
    r = research(person) or {}
    c = {"name": person["name"], "party": PARTY.get(person["party"] or "", person["party"]), "incumbent": bool(person.get("inc")), "money": {}, "_file": P.person_file(person)}
    for k in ("bio", "controversies", "foreign_ties", "endorsements", "social", "gaps"):
        if r.get(k):
            c[k] = r[k]
    c["votes"] = [v for v in r.get("votes") or [] if v.get("vote") and v.get("url")]
    ph = get_photo(person, r.get("photo"))
    if ph:
        c["photo"] = ph
    if senate is not None:
        fid = fed_match(person["name"], senate, dist)
        c["money"] = (F.fed_money(fid, home) if fid else None) or {}
        rec = F.FED_BY_ID.get(fid) or {}
        # The results feeds don't say; the FEC's candidate file does. One person can hold two ids on one committee, and only one of them says incumbent.
        # It has to be an id for this seat: a House member running for Senate (Barry Moore) isn't the Senate incumbent.
        c["incumbent"] = c["incumbent"] or any(r.get("ici") == "I" and r["fec_id"][0] == rec.get("fec_id", " ")[0] and r.get("district") == rec.get("district") and set(r.get("committees") or []) & set(rec.get("committees") or []) for r in F.FED_BY_ID.values())
        # The FEC's mark lags special-election winners and some sitting members, so the members list counts too, for the same chamber only.
        c["incumbent"] = c["incumbent"] or (SITTING.get(P.person_file(person)) or {}).get("chamber") == ("U.S. Senate" if senate else "U.S. House")
        given, sampled = (rec.get("summary") or {}).get("indiv", 0), (rec.get("itemized_indiv") or {}).get("amt", 0)
        if c["money"] and given >= 50000 and sampled < given * 0.05:      # shares built on a sliver of the gifts would read as fact
            c["money"].update({k: None for k in ("fl_pct", "out_pct", "local_pct", "local_clean_pct", "fl_clean_pct", "land_pct", "big_pct")})
            c["money"]["note"] += f" The FEC's itemized file holds only ${sampled:,.0f} of their ${given:,.0f} in individual gifts so far, so where the money came from isn't shown."
            print("   thin FEC detail, no shares:", person["name"], sampled, "of", round(given))
        if not fid:
            print("   no FEC match:", person["key"], person["name"], f"({person['pc']}%)")
    elif STATE_FILE:
        c["money"] = state_money(person["name"], home)
    n = person["name"]
    if r:
        F.QUALS[n] = {"qual": r.get("qual"), "background": r.get("qual_background"), "why": r.get("qual_why"), "sources": r.get("qual_sources") or []}
        if r.get("roots") is not None:
            ROOTS["roots"][n] = {"roots": r["roots"], "summary": r.get("roots_summary") or "", "urls": r.get("roots_urls") or []}
        if r.get("land_positions"):
            ROOTS["positions"][n] = r["land_positions"]
        if r.get("did"):
            F.VERIFY[n] = {"did": r["did"]}
        # Stated positions: several on one plank count once, and a split decides nothing.
        said = defaultdict(list)
        for x in r.get("said") or []:
            if x.get("plank") in F.PLANK_IDS and x.get("url") and x.get("match") in (1, -1):
                said[x["plank"]].append(x)
        planks = {}
        for k, xs in said.items():
            tot = sum(x["match"] for x in xs)
            if tot:
                best = next(x for x in xs if x["match"] == (1 if tot > 0 else -1))
                planks[k] = {"match": best["match"], "evidence": best["what"], "url": best["url"], "kind": "said"}
        if planks:
            F.PRIO["candidates"][n] = {"planks": planks}
    return c


def race(rid, reskey, group, title, short, where, people, home_kind, label, senate=None, home=(), dist=None):
    B.HOME[rid] = (home_kind, label)
    cands = [card(p, senate, home, dist) for p in people]
    for c in cands:
        c["score"] = B.score(c, rid, None, B.MIN_RAISED[group])
    n = len(cands)
    unopp = n == 1 and people[0].get("unopposed")
    return {"kind": "race", "group": group, "id": rid, "reskey": reskey, "title": title, "short": short, "everyone": True, "where": where,
            "sub": "Unopposed" if unopp else f"{n} candidate{'' if n == 1 else 's'}",
            "note": "The top two finishers from the Nov 3, 2026 count. Everyone else in this race is coming." if n > 1 else "", "cands": cands}


def main():
    people = json.loads((ROOT / "buddy" / "results" / "roster" / f"{ST}.json").read_text(encoding="utf-8"))
    by_key = defaultdict(list)
    for p in people:
        by_key[p["key"]].append(p)
    races = []
    for key, ps in by_key.items():
        m = re.fullmatch(r"(ushouse|stsen|sthouse)-(\d+)", key)
        if not m:
            senate = True if key == "ussen" else None
            races.append(race(IDS.get(key, key), key, "federal" if key == "ussen" else "state", ps[0]["race"], ps[0]["race"], {"all": 1}, ps,
                              "fl", f"from {STATE}", senate=senate))
            continue
        kind, n = m.group(1), int(m.group(2))
        if kind == "ushouse":
            races.append(race(f"usr-{n}", key, "federal", f"U.S. House, District {n}", f"U.S. House {n}", {"cd": n}, ps,
                              "local", f"from District {n} ZIP codes", senate=False, home=F.zips_where(cd=n), dist=n))
        else:
            is_sen = kind == "stsen"
            word = "Senate" if is_sen else "Assembly" if ST == "CA" else "House"
            races.append(race(f"{'sts' if is_sen else 'str'}-{n}", key, "legislature", f"State {word}, District {n}", f"State {word} {n}",
                              {"sd": n} if is_sen else {"hd": n}, ps, "local", f"from District {n} ZIP codes", home=F.zips_where(sd=n) if is_sen else F.zips_where(hd=n)))
    F.finalize(races)
    for r in races:
        for c in r["cands"]:
            person = c.pop("_file")
            R.apply(c, *R.read(INPUTS, person))
            R.history(c, INPUTS, person)
            F.only_owners(c)
        # The same order finalize uses, since the owner's rules can change who leads.
        r["cands"] = sorted(r["cands"], key=lambda c: (-(c["score"].get("indep") is not None), -(c["score"]["overall"] if c["score"]["overall"] is not None else -1)))
        for i, c in enumerate(r["cands"]):
            c["rank"] = i + 1 if c["score"]["overall"] is not None else None
    races.sort(key=lambda r: ORDER.get(r["reskey"], 99))

    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.json"):
        f.unlink()
    statewide, buckets = [], defaultdict(list)
    for r in races:
        w = r["where"]
        if w.get("all"):
            statewide.append(r)
        else:
            buckets[f"cd-{w['cd']}" if "cd" in w else f"sd-{w['sd']}" if "sd" in w else f"hd-{w['hd']}"].append(r)
    for k, rs in buckets.items():
        (OUT / f"{k}.json").write_text(json.dumps({"races": rs}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    how = ("<p>This report does not tell you who to vote for. It lays out who wrote the checks and what the public record shows. "
           "A donation is a fact about the donor; it is not proof of what the candidate will do.</p>")
    foot = (f"<p><b>Sources.</b> Who ran and who won: the Nov 3, 2026 results in the Results tab. Federal money: FEC bulk files, downloaded Nov 2, 2026. "
            f"Records and positions: linked per item. " + (f"State-race money: {STATE_SOURCE[ST][0]}, public files downloaded Nov 5, 2026.</p>" if STATE_FILE else
                                                             f"{STATE} state-race money isn't in the guide yet, so those candidates have no money meters.</p>"))
    data = {"st": ST, "stateName": STATE, "dir": f"states/{ST}", "title": f"Ballot Buddy · {STATE}", "built": date.today().isoformat(),
            "boxes": [{"title": "How to read this", "cls": "warn", "html": how}], "footer": foot,
            "groups": [{"id": a, "label": b, "icon": c} for a, b, c in B.GROUPS], "races": statewide, "files": sorted(buckets),
            "zips": {z: [v["cd"], v["sd"], v["hd"], v["county"], v.get("city")] for z, v in F.ZIPS.items()}, "soe": {}, "coverage": [],
            "platform": F.PRIO["platform"],
            "rules": {"min": B.MIN_RAISED, "pac": B.FOREIGN_PAC_PENALTY, "foreign": [{"pts": p, "text": t} for _, p, t in B.FOREIGN_RULES]}}
    (OUT / "state.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    cands = [c for r in races for c in r["cands"]]
    rated = sum(1 for c in cands if c["score"]["overall"] is not None)
    print(f"{ST}: {len(statewide)} statewide, {len(buckets)} district files, {len(races)} races, {len(cands)} candidates, {rated} with a score, "
          f"{sum(1 for c in cands if c.get('money'))} with money, {sum(1 for c in cands if c.get('photo'))} with photos, {sum(1 for p in people if research(p))} researched")


ROOTS = {"roots": {}, "positions": {}}
F.ROOTS = ROOTS
F.PRIO = {"platform": P.platform(ST), "candidates": {}}
F.PLANK_IDS = {x["id"] for x in F.PRIO["platform"]["planks"]}
_kind = F.plank_kind
F.plank_kind = lambda x: x.get("kind") or _kind(x)      # research marks stated positions itself

if __name__ == "__main__":
    main()
