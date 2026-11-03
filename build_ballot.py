#!/usr/bin/env python3
"""
Render a voter's ballot from ballot-<zip>.json into ballot-<zip>.html as
scored, flippable candidate cards.

    py build_ballot.py ballot-34221.json

The JSON holds everything: the races on the official sample ballot, each
candidate's money (federal from FEC bulk files, state from the Florida Division
of Elections, county and city from the Supervisor of Elections), their public
record, and what the owner's designated sources say about them.

The score is mechanical and shown in full on the page ("How scores work"):
three meters built only from money and documented ties, on the owner's three
questions (local area, the country / foreign interest, big donors). It never
uses party, policy or the owner's sources. Framing rule, same as the main
page: a donation is a fact about the donor, not proof of what anyone will do.
"""
import json, re, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Below these totals the money meters say "too little to score": a few checks would swing everything.
MIN_RAISED = {"federal": 50000, "state": 50000, "legislature": 5000, "local": 2000}
GROUPS = [("federal", "Federal", "🦅"), ("state", "Governor & Cabinet", "🏛️"),
          ("legislature", "State Legislature", "📜"), ("local", "County & City", "🏡"),
          ("judges", "Judges", "⚖️"), ("measures", "Ballot Questions", "🗳️")]
PART_GROUP = {"Federal": "federal", "State — Governor and Cabinet": "state", "State Legislature": "legislature",
              "Judges": "judges", "County and City": "local", "Ballot measures": "measures"}

# What "home" means for each race, so the Local meter compares like with like.
HOME = {"senate": ("fl", "from Florida"), "governor": ("fl", "from Florida"), "ag": ("fl", "from Florida"),
        "cfo": ("fl", "from Florida"), "agriculture": ("fl", "from Florida"),
        "house16": ("local", "from Sarasota–Manatee zip codes (342xx)"),
        "sd20": ("region", "from Manatee, Sarasota & Hillsborough zip codes"),
        "hd70": ("region", "from Manatee, Sarasota & Hillsborough zip codes"),
        "hd71": ("region", "from Manatee, Sarasota & Hillsborough zip codes")}
LOCAL_DEFAULT = ("local", "from Manatee County")

# Foreign meter: start at 100 and subtract for each documented item. Every rule
# is printed on the page; items are matched on the research text.
FOREIGN_RULES = [
    (r"Chinese state-controlled|state-owned|foreign government (paid|gave)", 40,
     "Reported money from a company partly owned by a foreign government"),
    (r"ByteDance", 10, "A major donor's fortune is tied to a foreign company (ByteDance)"),
    (r"lobbied for .*(government|Musharraf)", 10, "A past employer lobbied for a foreign government"),
]
FOREIGN_PAC_PENALTY = 5    # per U.S. PAC of a foreign-parent company (legal, U.S.-employee money)

MEASURE_SHORT = {"m0": ("Amendment 1", "Rainy-day fund"), "m1": ("Amendment 2", "Farm equipment tax break"),
                 "m2": ("Amendment 3", "Homestead tax cut"), "m3": ("County land bond", "$75M water & land"),
                 "m4": ("Palmetto charter", "City boundary map")}


def score(c, race_id, region, floor):
    m = c.get("money") or {}
    raised = float(m.get("raised") or 0)
    kind, label = HOME.get(race_id, LOCAL_DEFAULT)

    # 🇺🇸 Country first
    pen, reasons = 0, []
    for x in m.get("foreign") or []:
        pen += FOREIGN_PAC_PENALTY
        reasons.append({"pts": FOREIGN_PAC_PENALTY, "text": x["text"].split(" — ")[0] +
                        " — U.S. PAC of a foreign-parent company"})
    for x in c.get("foreign_ties") or []:
        if re.match(r"\s*None documented", x.get("text", "")):
            continue
        for rx, pts, why in FOREIGN_RULES:
            if re.search(rx, x.get("text", ""), re.I):
                pen += pts
                reasons.append({"pts": pts, "text": why, "url": x.get("url")})
                break
    foreign = {"v": max(0, 100 - pen), "reasons": reasons}

    if raised < floor:
        return {"overall": None, "local": None, "indep": None, "foreign": foreign,
                "why": f"Raised {usd(raised)}, under ${floor:,} for this office: too little money to score fairly."}

    # 🏠 Local
    home = region if kind == "region" else m.get("fl_pct") if kind == "fl" else m.get("local_pct")
    local = {"v": round(home) if home is not None else None, "label": f"{round(home or 0)}% of money {label}"}

    # 💵 Independent: share of all money behind them that is NOT big money
    org_pct = m.get("org_pct") or 0
    big = raised * org_pct / 100
    total = raised
    parts = [f"{round(org_pct)}% of campaign money from businesses, PACs or party"]
    if m.get("big_pct") is not None:                     # federal: $2,000+ individual donors
        big += (raised - raised * org_pct / 100) * m["big_pct"] / 100
        parts.append(f"{round(m['big_pct'])}% of itemized individual money from people giving $2,000+")
    comm = (m.get("committee") or {}).get("total")
    if comm:
        big += comm
        total += comm
        parts.append(f"plus ${comm/1e6:,.1f}M in a political committee they control (no donation limit)")
    out_for = sum(float(a) for _, so, a in (m.get("outside") or []) if so == "S")
    if out_for:
        big += out_for
        total += out_for
        parts.append(f"plus ${out_for/1e6:,.1f}M spent by outside groups to help them")
    big_share = 100 * big / total if total else 0
    indep = {"v": round(100 - big_share), "label": f"{round(big_share)}% of all money behind them is big money",
             "parts": parts}

    vals = [x for x in (local["v"], indep["v"], foreign["v"]) if x is not None]
    return {"overall": round(sum(vals) / len(vals)), "local": local, "indep": indep, "foreign": foreign}


def usd(v):
    return f"${v/1e3:,.1f}k" if v >= 1e4 else f"${v:,.0f}"


def region_for(name, shares):
    last = re.sub(r"[^A-Za-z' -]", "", name).replace(" Sr", "").split()[-1].lower()
    for k, v in shares.items():
        if k.split(",")[0].strip().lower() == last:
            return v
    return None


def build(d, shares):
    races = []
    for p in d["parts"]:
        g = PART_GROUP[p["title"]]
        for r in p["races"]:
            if r.get("measure"):
                t, sub = MEASURE_SHORT.get(r["id"], (r["short"], ""))
                races.append({"kind": "measure", "group": g, "id": r["id"], "title": r["name"], "short": t, "sub": sub,
                              "everyone": r.get("scope") == "all", "scope_note": r.get("scope_note"), "m": r})
                continue
            if r.get("retention"):
                races.append({"kind": "judges", "group": g, "id": r["id"], "title": r["title"], "short": "Judges",
                              "sub": f"{len(r['retention'])} keep-or-remove votes", "everyone": True,
                              "note": r.get("note"), "judges": r["retention"]})
                continue
            cands = []
            for c in r["candidates"]:
                region = region_for(c["name"], shares) if HOME.get(r["id"], LOCAL_DEFAULT)[0] == "region" else None
                cands.append(dict(c, score=score(c, r["id"], region, MIN_RAISED[g])))
            ranked = sorted(cands, key=lambda c: -(c["score"]["overall"] if c["score"]["overall"] is not None else -1))
            for i, c in enumerate(ranked):
                c["rank"] = i + 1 if c["score"]["overall"] is not None else None
            races.append({"kind": "race", "group": g, "id": r["id"], "title": r["title"], "short": r["short"],
                          "sub": f"{len(cands)} candidates", "everyone": r.get("scope") == "all",
                          "scope_note": r.get("scope_note"), "note": r.get("note"), "cands": ranked})
    return races


def main():
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "ballot-34221.json")
    d = json.loads(src.read_text(encoding="utf-8"))
    sp = Path(__file__).with_name("ballot") / "region_share.json"
    shares = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
    pp = Path(__file__).with_name("ballot") / "photos.json"
    photos = json.loads(pp.read_text(encoding="utf-8")) if pp.exists() else {}
    for part in d["parts"]:
        for r in part["races"]:
            for c in r.get("candidates") or []:
                if c["name"] in photos:
                    c["photo"] = photos[c["name"]]
    data = {"title": d["title"], "kicker": d["kicker"], "built": d["built"], "boxes": d["boxes"], "footer": d["footer"],
            "groups": [{"id": a, "label": b, "icon": c} for a, b, c in GROUPS], "races": build(d, shares),
            "rules": {"min": MIN_RAISED, "pac": FOREIGN_PAC_PENALTY,
                      "foreign": [{"pts": p, "text": t} for _, p, t in FOREIGN_RULES]}}
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    page = TEMPLATE.replace("__TITLE__", d["title"]).replace("__DESC__", d["description"]).replace("__DATA__", blob)
    out = src.with_suffix(".html")
    out.write_text(page, encoding="utf-8")
    n = sum(len(r.get("cands", [])) for r in data["races"])
    print(f"wrote {out} — {len(data['races'])} ballot items, {n} scored candidates, {len(page)//1024} KB")
    for r in data["races"]:
        for c in r.get("cands", []):
            s = c["score"]
            print(f"  {r['short'][:18]:18} #{c['rank'] or '-'} {c['name'][:28]:28} {s['overall']}  "
                  f"L{(s['local'] or {}).get('v')} I{(s['indep'] or {}).get('v')} F{s['foreign']['v']}")


TEMPLATE = Path(__file__).with_name("ballot").joinpath("cards_template.html").read_text(encoding="utf-8")

if __name__ == "__main__":
    main()
