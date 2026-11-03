#!/usr/bin/env python3
"""
Build the any-address Florida ballot: ballot.html plus per-district data files in fl/.

    py build_florida.py SCRATCH

SCRATCH holds today's pulls and research (see ballot/README.md):
  fed_money_all.json      FEC bulk summary for every Florida federal candidate (ballot/fed_money_all.py)
  fl_all/fl_STS*.json, fl_STR*.json   Division of Elections rows per district (ballot/fl_money_all.py)
  geo/zip_districts.json  every Florida ZIP centroid -> congressional / senate / house district + county
  geo/soe.json            every county Supervisor of Elections (website, phone, address)
  research2/*.json        research slices (us_house, legislature, manatee, votes40) per research2/SCHEMA.md

The Palmetto races in ballot-34221.json are reused as-is. Scoring is build_ballot.score(), unchanged:
the Local meter's "home" is the district's own ZIP codes for U.S. House and Legislature races.
"""
import glob, json, os, re, sys, unicodedata, urllib.request
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
import build_ballot as B  # noqa: E402

S = Path(sys.argv[1])
OUT = ROOT / "fl"
PHOTOS = ROOT / "ballot" / "photos"


def load(p, default=None):
    p = Path(p)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:          # a research slice mid-rewrite: say so, never pretend it was empty
        print(f"!! {p.name} is not valid JSON right now ({e}); skipped this run", file=sys.stderr)
        return default


def fold(s):
    return unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()


def lastname(n):
    w = re.sub(r'"[^"]*"|\([^)]*\)', " ", fold(n))
    w = [x for x in re.split(r"[^a-z'-]+", w) if x and x not in ("jr", "sr", "ii", "iii", "iv", "md", "facs", "dr", "mr", "mrs", "ms")]
    return w[-1] if w else ""


def slug(n):
    return re.sub(r"[^a-z]+", "-", re.sub(r'"[^"]*"', "", fold(n))).strip("-")


ZIPS = load(S / "geo" / "zip_districts.json", {})
SOE = load(S / "geo" / "soe.json", {})
FED = load(S / "fed_money_all.json", {})
FED_BY_ID = {v["fec_id"]: v for v in FED.values()}
VOTES40 = (load(S / "research2" / "votes40.json", {}) or {}).get("candidates", {})


def zips_where(**kw):
    return {z for z, v in ZIPS.items() if all(v.get(k) == x for k, x in kw.items())}


# ---------------- photos ----------------
photo_map = load(ROOT / "ballot" / "photos.json", {})


def photo(c):
    if c["name"] in photo_map:
        return photo_map[c["name"]]
    p = c.get("photo") or {}
    url = p.get("url") if isinstance(p, dict) else None
    if not url or "SubmitPhoto" in url or "BP-Initials" in url:
        return None
    ext = (re.search(r"\.(png|jpe?g|webp)(\?|$)", url, re.I) or [None, "jpg"])[1].lower().replace("jpeg", "jpg")
    f = slug(c["name"]) + "." + ext
    if not (PHOTOS / f).exists():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "gov-age-ballot/1.0 (tyler@spartanstudios.com)"})
            data = urllib.request.urlopen(req, timeout=30).read()
            if len(data) < 1500:
                return None
            (PHOTOS / f).write_bytes(data)
        except Exception as e:
            print("   photo failed", c["name"], e, file=sys.stderr)
            return None
    photo_map[c["name"]] = {"f": f, "credit": p.get("credit") or "public source", "page": url}
    return photo_map[c["name"]]


# ---------------- money ----------------
def fed_money(fid, home):
    v = FED_BY_ID.get(fid)
    if not v or not v.get("summary"):
        return None
    s, sh = v["summary"], v["share"]
    t = v["itemized_indiv"]["amt"] or 1
    loc = round(100 * sum(a for z, a in sh.get("fl_zips", {}).items() if z in home) / t, 1)
    pacs = [[B_tc(x["name"])[:70], x["amt"], (x["org_type"] or x["giver_type"])] for x in v["committee_money"] if x["type"] == "24K"][:12]
    return {"raised": s["receipts"], "through": f"FEC totals through {s['through']}",
            "fl_pct": sh["florida"], "out_pct": sh["out_of_state"], "local_pct": loc,
            "big_pct": sh["donors_2000plus_share"],
            "org_pct": round(100 * (s["pac"] + s["party"]) / s["receipts"], 1) if s["receipts"] else None,
            "top": [[B_tc(x["name"]), x["amt"], f"{x['occ'] or x['emp']} · {B_tc(x['city'])}, {x['st']}"] for x in v["top_donors"][:10]],
            "pacs": pacs, "outside": [[o["spender"], o["support_oppose"], o["amt"]] for o in v["outside_spending_24_48hr"][:10]],
            "note": f"Individuals gave ${s['indiv']:,.0f}; PAC money ${s['pac']:,.0f}; candidate's own money ${s['self']:,.0f}. "
                    "Percentages describe itemized individual gifts, which the FEC has processed through about July 2026.",
            "source": "FEC bulk files downloaded Nov 2, 2026", "source_url": f"https://www.fec.gov/data/candidate/{fid}/?cycle=2026"}


def B_tc(s):
    s = str(s or "").strip()
    return " ".join(w if (len(w) <= 3 and w.isupper() and w in ("PAC", "LLC", "USA", "GOP", "II", "III", "PA", "LP")) else w.capitalize() for w in s.split())


SUFFIX = re.compile(r"\s*\([A-Z]{2,4}\)\s*\([A-Z]{2,4}\)\s*$")
ORG = re.compile(r"\b(LLC|L\.L\.C|INC|CORP|CORPORATION|COMPANY|CO\.|P\.?A\.?|PLLC|LLP|LP|LTD|PAC|COMMITTEE|ASSOCIATION|ASSN|PARTY|FUND|GROUP|"
                 r"HOLDINGS|PARTNERS|TRUST|FOUNDATION|ENTERPRISES|INDUSTRIES|SERVICES|SOLUTIONS|FLORIDA|COUNCIL|UNION|FEDERATION|CHAMBER)\b", re.I)
DEV = re.compile(r"\b(HOMES?|BUILDERS?|BUILDING|DEVELOP\w*|CONSTRUCT\w*|LAND|LANDS|REALTY|REAL ESTATE|REALTOR\w*|PAVING|EXCAVAT\w*|"
                 r"ENGINEER\w*|CONCRETE|ASPHALT|PROPERT(Y|IES)|COMMUNITIES)\b", re.I)


def fl_district_money(path, home):
    """Same arithmetic as ballot/fl_analyze.py, with 'home' = the district's ZIP codes."""
    blob = load(path)
    if not blob:
        return {}
    out = {}
    for r in blob["rows"]:
        to = SUFFIX.sub("", (r.get("Candidate/Committee") or "").strip()).strip()
        if not to:
            continue
        typ = (r.get("Typ") or "").strip()
        try:
            amt = float((r.get("Amount") or "0").replace("$", "").replace(",", ""))
        except ValueError:
            continue
        o = out.setdefault(to, {"gift": 0.0, "loans": 0.0, "home": 0.0, "fl": 0.0, "out": 0.0, "org": 0.0, "dev": 0.0,
                                "donors": defaultdict(lambda: [0.0, 0, ""]), "last": ""})
        if typ == "LOA":
            o["loans"] += amt
            continue
        if typ == "INT":
            continue
        name = (r.get("Contributor Name") or "").strip()
        csz = (r.get("City State Zip") or "").strip()
        m = re.search(r"\b([A-Z]{2})\s+(\d{5})", csz)
        st, z = (m.group(1), m.group(2)) if m else ("", "")
        o["gift"] += amt
        dt = r.get("Date") or ""
        if len(dt) == 10:
            o["last"] = max(o["last"], dt[6:] + "-" + dt[:2] + "-" + dt[3:5])
        if z in home:
            o["home"] += amt
        if st == "FL":
            o["fl"] += amt
        elif st:
            o["out"] += amt
        if ORG.search(name):
            o["org"] += amt
        if DEV.search(name) or DEV.search(r.get("Occupation") or ""):
            o["dev"] += amt
        d = o["donors"][(name.upper(), z)]
        d[0] += amt; d[1] += 1; d[2] = csz
    res = {}
    for to, o in out.items():
        g = o["gift"] or 1
        res[to] = {"raised": round(o["gift"]), "through": f"campaign account, reports through {o['last']}",
                   "local_pct": round(100 * o["home"] / g, 1), "fl_pct": round(100 * o["fl"] / g, 1),
                   "out_pct": round(100 * o["out"] / g, 1), "org_pct": round(100 * o["org"] / g, 1),
                   "build_land_pct": round(100 * o["dev"] / g, 1), "loans": round(o["loans"]) or None,
                   "top": [[B_tc(k[0]), round(v[0]), f"x{v[1]} · {B_tc(v[2])}"] for k, v in sorted(o["donors"].items(), key=lambda kv: -kv[1][0])[:10]],
                   "note": "Includes primary and general. 'State of Florida' lines are public matching funds; party-committee lines are mostly in-kind staff and mail.",
                   "source": "Florida Division of Elections, pulled Nov 3, 2026",
                   "source_url": "https://dos.elections.myflorida.com/campaign-finance/contributions/"}
    return res


def match_fl(c, pool):
    ln = lastname(c.get("fl_doe_name") or c["name"])
    hits = [k for k in pool if ln and ln in re.findall(r"[a-z'-]+", fold(k))]
    if len(hits) > 1:
        fn = fold(c["name"]).split()[0]
        hits = [k for k in hits if fn in fold(k)] or hits[:1]
    return pool[hits[0]] if hits else None


# ---------------- candidates from research slices ----------------
KEEP = ("name", "party", "incumbent", "bio", "local_ties", "record", "money_notes", "controversies", "foreign_ties",
        "endorsements", "local_issue_stance", "owner_sources", "owner_sources_searched", "gaps", "press_opinion", "votes", "social", "running_mate")


def norm_cand(c):
    o = {k: c[k] for k in KEEP if c.get(k) not in (None, "", [], {})}
    o.setdefault("party", "")
    for k in ("record", "money_notes", "controversies", "foreign_ties", "endorsements", "press_opinion", "local_issue_stance"):
        if isinstance(o.get(k), list):
            o[k] = [x if isinstance(x, dict) else {"text": str(x)} for x in o[k]]
    o["votes"] = [v for v in (c.get("votes") or []) + (c.get("votes_state") or []) if isinstance(v, dict) and v.get("vote") and v.get("url")]
    return o


def score_race(rid, group, cands, home_label):
    B.HOME[rid] = ("local", home_label)
    for c in cands:
        c["score"] = B.score(c, rid, None, B.MIN_RAISED[group])
    ranked = sorted(cands, key=lambda c: -(c["score"]["overall"] if c["score"]["overall"] is not None else -1))
    for i, c in enumerate(ranked):
        c["rank"] = i + 1 if c["score"]["overall"] is not None else None
    return ranked


# The Division of Elections' own 2026 General candidate list (canlist.asp, statuses Qualified + Elected/Unopposed)
# is the authority on WHO is on the ballot; research only adds what we know about them.
CANLIST = load(S / "geo" / "canlist.json", [])
OFFICE = {"usr": "United States Representative", "sts": "State Senator", "str": "State Representative"}


def official(k, n):
    return [o for o in CANLIST if o["office"] == OFFICE[k] and o["district"] == n]


def reconcile(k, n, cands, raw):
    """Keep research candidates the state lists, add listed ones research missed, label write-ins."""
    offl = official(k, n)
    if not CANLIST:
        return cands, ""
    if not offl:
        print(f"   {k}-{n}: not on the 2026 general list; dropped", file=sys.stderr)
        return [], ""
    keep, used = [], set()
    for c in cands:
        ln = lastname(c["name"])
        o = next((o for i, o in enumerate(offl) if i not in used and ln in re.findall(r"[a-z'-]+", fold(o["last"]))), None)
        if not o:
            print(f"   {k}-{n}: {c['name']} not on the state list; dropped", file=sys.stderr)
            continue
        used.add(offl.index(o))
        if o["party"] == "WRI":
            c["party"] = "Write-in"
        elif o["party"]:
            c["party"] = o["party"]
        c["incumbent"] = o["inc"] or c.get("incumbent", False)
        keep.append(c)
    for i, o in enumerate(offl):
        if i in used:
            continue
        nm = f"{o['first']} {o['last']}"
        print(f"   {k}-{n}: added {nm} from the state list", file=sys.stderr)
        keep.append({"name": nm, "party": "Write-in" if o["party"] == "WRI" else o["party"], "incumbent": o["inc"],
                     "gaps": "On the state's candidate list; not yet researched for this guide."})
        raw[nm] = {"name": nm, "fl_doe_name": nm}
    unopp = all(o["general"] == "Unopposed" for o in offl)
    return keep, "Unopposed: this seat was decided without a general-election contest, so it won't be on your ballot." if unopp else ""


def research_races(fname, kind):
    blob = load(S / "research2" / fname, {}) or {}
    races = []
    for r in blob.get("races", []):
        rid = r.get("id", "")
        m = re.match(r"fl-(usr|sts|str)-0*(\d+)$", rid)
        if not m:
            continue
        k, n = m.group(1), int(m.group(2))
        raw = {c["name"]: c for c in r.get("candidates", []) if c.get("name")}
        cands, unopp_note = reconcile(k, n, [norm_cand(c) for c in r.get("candidates", []) if c.get("name")], raw)
        if not cands:
            continue
        if unopp_note:
            r["note"] = unopp_note
        if k == "usr":
            home = zips_where(cd=n)
            for c in cands:
                c["money"] = fed_money(raw[c["name"]].get("fec_id"), home) or {}
            group, title, short, where, label = "federal", f"U.S. House, District {n}", f"U.S. House {n}", {"cd": n}, f"from District {n} ZIP codes"
        else:
            home = zips_where(**({"sd": n} if k == "sts" else {"hd": n}))
            pool = fl_district_money(S / "fl_all" / f"fl_{k.upper()}{n}.json", home)
            for c in cands:
                c["money"] = match_fl(raw[c["name"]], pool) or {}
            group = "legislature"
            title = f"State {'Senate' if k == 'sts' else 'House'}, District {n}"
            short = f"State {'Senate' if k == 'sts' else 'House'} {n}"
            where = {"sd": n} if k == "sts" else {"hd": n}
            label = f"from District {n} ZIP codes"
        for c in cands:
            ph = photo(dict(raw[c["name"]], name=c["name"]))
            if ph:
                c["photo"] = ph
        key = f"{k}-{n}"
        ranked = score_race(key, group, cands, label)
        wi = sum(1 for c in cands if c.get("party") == "Write-in")
        sub = "Unopposed: not on ballot" if unopp_note else f"{len(cands) - wi} on ballot" + (f" + {wi} write-in" if wi else "")
        races.append({"kind": "race", "group": group, "id": key, "title": title, "short": short, "sub": sub, "everyone": True,
                      "where": where, "note": r.get("note") or ("Write-in candidates aren't printed on the ballot: you'd write their name on the blank line." if wi else ""),
                      "cands": ranked})
    return races, blob.get("done"), blob.get("notes", [])


LOCAL = load(S / "local_money_all.json", {})


def local_money(name):
    ln = lastname(name)
    hits = [(k, v) for k, v in LOCAL.items() if ln and ln in re.findall(r"[a-z'-]+", fold(k.split(",")[0]))]
    if len(hits) > 1:
        fn = fold(name).split()[0]
        hits = [h for h in hits if fn in fold(h[0])] or []
    if len(hits) != 1:          # ambiguous or none: show no money rather than someone else's
        return {}
    v = hits[0][1]
    return {"raised": v["raised"], "through": f"county reports, last item {v.get('last_report_item', '')}",
            "local_pct": v["pct_manatee"], "out_pct": v["pct_out_state"], "org_pct": v["pct_business_committee"],
            "build_land_pct": v["pct_building_land_tagged"], "loans": v["loans"] or None,
            "top": [[B_tc(re.sub(r"\s*\[.*?\]", "", a)), b, re.search(r"\](.*)", a).group(1).strip() if "]" in a else ""] for a, b, n in v["top_donors"][:10]],
            "source": "Manatee County Supervisor of Elections campaign reports, pulled Nov 2, 2026",
            "source_url": "https://www.votemanatee.gov/search-financial-reports/"}


def manatee_races(have_ids):
    blob = load(S / "research2" / "manatee.json", {}) or {}
    out = []
    for r in blob.get("races", []):
        w = r.get("where")
        if not isinstance(w, dict) or not r.get("id") or r["id"] in have_ids:
            continue
        w = dict(w, county="Manatee")
        if r.get("kind") == "measure":
            m = r.get("m") or r
            out.append({"kind": "measure", "group": "measures", "id": r["id"], "title": m.get("name") or r.get("office", ""),
                        "short": r.get("short") or (m.get("name") or "")[:18], "sub": r.get("sub", ""), "everyone": True, "where": w, "m": m})
            continue
        cands = [norm_cand(c) for c in r.get("candidates", []) if c.get("name")]
        if not cands:
            continue
        raw = {c["name"]: c for c in r.get("candidates", []) if c.get("name")}
        for c in cands:
            c["money"] = local_money(c["name"])
            ph = photo(dict(raw[c["name"]], name=c["name"]))
            if ph:
                c["photo"] = ph
        ranked = score_race(r["id"], "local", cands, "from Manatee County")
        out.append({"kind": "race", "group": "local", "id": r["id"], "title": r.get("office") or r.get("title") or r["id"],
                    "short": r.get("short") or (r.get("office") or r["id"])[:18], "sub": f"{len(cands)} candidates", "everyone": True,
                    "where": w, "note": r.get("note", ""), "cands": ranked})
    return out


# ---------------- assemble ----------------
def main():
    d = json.loads((ROOT / "ballot-34221.json").read_text(encoding="utf-8"))
    shares = load(ROOT / "ballot" / "region_share.json", {})
    for part in d["parts"]:
        for r in part["races"]:
            for c in r.get("candidates") or []:
                if c["name"] in photo_map:
                    c["photo"] = photo_map[c["name"]]
                v = VOTES40.get(c["name"])
                if v and v.get("votes"):
                    c["votes"] = [x for x in v["votes"] if x.get("vote") and x.get("url")]
    base = B.build(d, shares)
    WHERE = {"senate": {"all": 1}, "governor": {"all": 1}, "ag": {"all": 1}, "cfo": {"all": 1}, "agriculture": {"all": 1},
             "m0": {"all": 1}, "m1": {"all": 1}, "m2": {"all": 1},
             "house16": {"cd": 16}, "sd20": {"sd": 20}, "hd70": {"hd": 70}, "hd71": {"hd": 71},
             "cc6": {"county": "Manatee"}, "mosquito": {"county": "Manatee"}, "m3": {"county": "Manatee"},
             "cc1": {"county": "Manatee", "cc": 1}, "cc2": {"county": "Manatee", "cc": 2}, "sb2": {"county": "Manatee", "sb": 2},
             "palmetto2": {"county": "Manatee", "city": "Palmetto", "ward": 2}, "m4": {"county": "Manatee", "city": "Palmetto"}}
    races = []
    for r in base:
        if r["kind"] == "judges":       # split: Supreme Court is statewide; the appeals-court judges only verified for Manatee
            sc = [j for j in r["judges"] if "Mu" in j["name"]]
            dca = [j for j in r["judges"] if j not in sc]
            races.append(dict(r, id="supreme", short="Supreme Court", sub=f"{len(sc)} keep-or-remove vote", judges=sc, where={"all": 1},
                              note="Every Florida voter decides whether this Supreme Court justice stays."))
            races.append(dict(r, id="dca2", short="Appeals judges", sub=f"{len(dca)} keep-or-remove votes", judges=dca,
                              where={"county": "Manatee"}, note="Second District Court of Appeal judges on Manatee ballots."))
            continue
        r["where"] = WHERE.get(r["id"], {"county": "Manatee"})
        races.append(r)

    notes = []
    for fname in ("us_house.json", "legislature.json"):
        extra, done, n = research_races(fname, fname)
        have = {json.dumps(x["where"]) for x in races}
        for x in extra:
            if json.dumps(x["where"]) not in have:
                races.append(x)
        notes.append(f"{fname}: {len(extra)} races, done={done}")
    extra = manatee_races({r["id"] for r in races})
    races += extra
    notes.append(f"manatee.json: {len(extra)} new county/city items")

    OUT.mkdir(exist_ok=True)
    state = [r for r in races if r["where"].get("all")]
    buckets = defaultdict(list)
    for r in races:
        w = r["where"]
        if w.get("all"):
            continue
        key = f"cd-{w['cd']}" if "cd" in w else f"sd-{w['sd']}" if "sd" in w else f"hd-{w['hd']}" if "hd" in w else "county-" + slug(w["county"])
        buckets[key].append(r)
    for f in OUT.glob("*.json"):
        f.unlink()
    for k, rs in buckets.items():
        (OUT / f"{k}.json").write_text(json.dumps({"races": rs}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    zipt = {z: [v["cd"], v["sd"], v["hd"], v["county"], v.get("city")] for z, v in ZIPS.items()}
    soe = {k: [v.get("web"), v.get("phone"), v.get("addr")] for k, v in SOE.items()}
    data = {"title": "Your Florida Ballot · Nov 3, 2026", "built": d["built"], "boxes": d["boxes"], "footer": d["footer"],
            "groups": [{"id": a, "label": b, "icon": c} for a, b, c in B.GROUPS], "races": state, "files": sorted(buckets),
            "zips": zipt, "soe": soe,
            "rules": {"min": B.MIN_RAISED, "pac": B.FOREIGN_PAC_PENALTY, "foreign": [{"pts": p, "text": t} for _, p, t in B.FOREIGN_RULES]}}
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    tpl = (ROOT / "ballot" / "app_template.html").read_text(encoding="utf-8")
    page = tpl.replace("__TITLE__", data["title"]).replace("__DESC__", "Type your address and see every race on your Florida ballot, scored on local roots, foreign ties and big money.").replace("__DATA__", blob)
    (ROOT / "ballot.html").write_text(page, encoding="utf-8")
    (ROOT / "ballot" / "photos.json").write_text(json.dumps(photo_map, ensure_ascii=False, indent=1), encoding="utf-8")
    n = sum(len(r.get("cands", [])) for r in races)
    print(f"wrote ballot.html ({len(page)//1024} KB): {len(state)} statewide items, {len(buckets)} district files, {len(races)} items, {n} candidates")
    for x in notes:
        print("  ", x)


if __name__ == "__main__":
    main()
