# Executed inside assemble.py — defines the ballot, in the order it is printed on the official sample ballot.

def compare(cands, local_label="From Manatee County"):
    rows = []
    for c in cands:
        m = c.get("money") or {}
        big = ""
        if m.get("committee"):
            t = m["committee"]["top"][:1]
            big = f"{t[0][0]} {usd(t[0][1])} (to their committee)" if t else ""
        elif m.get("groups"):
            g = m["groups"][0]; big = f"{g[1]} entities at one address: {usd(g[0])}"
        elif m.get("top"):
            big = f"{m['top'][0][0]} {usd(m['top'][0][1])}"
        out = [o for o in (m.get("outside") or []) if o[1] == "S"][:1]
        rows.append([c["name"],
                     usd(m["raised"]) if m.get("raised") is not None else "—",
                     usd(m["committee"]["total"]) if m.get("committee") and m["committee"].get("total") else "—",
                     f"{m['local_pct']:.0f}%" if m.get("local_pct") is not None else "—",
                     f"{m['out_pct']:.0f}%" if m.get("out_pct") is not None else "—",
                     f"{m['org_pct']:.0f}%" if m.get("org_pct") is not None else "—",
                     big or "—",
                     f"{out[0][0]} {usd(out[0][2])}" if out else "—"])
    return {"head": ["Candidate", "Campaign raised", "Their PAC/committee", local_label, "Out of state",
                     "Business / PAC / party share", "Largest single source", "Biggest outside group FOR them"],
            "rows": rows,
            "note": "Facts only, so you can weigh them yourself. A high business or out-of-state share is not proof of "
                    "anything, and a low one is not proof of independence — money also moves in ways no filing shows."}


def race(id, title, short, scope, cands, note=None, scope_note=None, local_label="From Manatee County", **kw):
    r = {"id": id, "title": title, "short": short, "scope": scope, "candidates": cands, "note": note,
         "scope_note": scope_note, "compare": compare(cands, local_label) if len(cands) > 1 else None}
    r.update(kw)
    return r


# ---------- federal ----------
moody = cand("Ashley Moody", F("Ashley Moody"), incumbent=True)
fix_hope(moody, "later chaired by James Uthmeier", "said then-Attorney General Moody knew of the plan")
sen = race("senate", "United States Senator", "U.S. Senate", "all",
           [moody, cand("Angie Nixon", F("Angie Nixon")), cand("Neil J. Gillespie", F("Neil J. Gillespie"))],
           local_label="From Sarasota–Manatee zips",
           note="Statewide. Federal candidates file with the FEC; super PACs can spend unlimited amounts for or against them.")
house = race("house16", "U.S. Representative, District 16", "U.S. House 16", "all",
             [cand("Sydney Gruters", F("Sydney Gruters")), cand("Kelly Kirschner", F("Kelly Kirschner")),
              cand("Mark Davis", F("Mark Davis"))], local_label="From Sarasota–Manatee zips",
             note="Open seat — Vern Buchanan is not running. District 16 covers all of Manatee County.")

# ---------- governor ----------
def gov(name, mate, key, committee=None, brief=False):
    c = cand(name, ST(key, committee) if key in fl else None, running_mate=mate, brief=brief)
    m = R.get(mate)
    if m:
        c["record"] = (c.get("record") or []) + [{"text": f"Running mate {mate}: {m.get('bio', '')}", "url": ""}]
        cm = clean(m)
        c["controversies"] = (c.get("controversies") or []) + [dict(x, text=f"(Running mate {mate}) {x['text']}") for x in cm["controversies"]]
        seen = {h.get("url") for h in c.get("owner_sources") or []}
        c["owner_sources"] = (c.get("owner_sources") or []) + [h for h in cm["owner_sources"] if h.get("url") not in seen]
    return c

govr = race("governor", "Governor and Lieutenant Governor", "Governor", "all", [
    gov("Byron Donalds", "Bryan Avila", "Donalds, Byron", "Friends of Byron Donalds PAC"),
    gov("David Jolly", "Gwen Graham", "Jolly, David"),
    gov("Scott Eckhard Jewett", "Nicole Skelly", "Jewett, Scott Eckhard", brief=True),
    gov("Charles Burkett", "Ruben A. Coto", "Burkett, Charles", brief=True),
    gov("Frank J. Russo", "Rachel Rodriguez", "Russo, Frank J.", brief=True),
    gov('Moliere "Moe" Dimanche', "Benjiman Rojas", 'Dimanche, Moliere "Moe"', brief=True),
    gov("Dean Ocean Abrams", "Joe Van Vactor", "Abrams, Dean Ocean", brief=True),
    gov('Jeffrey Peter "Dr. Jeff" Datto', "Juan Santana", 'Datto, Jeffrey Peter "Dr. Jeff"', brief=True)],
    note="Open seat (DeSantis is term-limited). Florida limits gifts to a candidate's campaign to $3,000 per election, "
         "but a political committee the candidate controls can take unlimited amounts — so look at both columns.")
for c in govr["candidates"]:
    if c["name"] == "David Jolly":
        c["money"]["note"] += (" No political committee controlled by Jolly was found in state records under his name; "
                               "if one exists under another name it is not counted here.")

# ---------- cabinet ----------
uth = cand("James Uthmeier", ST("Uthmeier, James", "Friends of James Uthmeier"), incumbent=True)
fix_hope(uth, "Uthmeier chaired at the time", "described his committee's role")
uth["money"]["note"] += (" Keep Florida Clean, Inc. — the committee Uthmeier chaired in 2024 — took $26.1M, including "
                         "$12M from Ken Griffin and $10.6M from the two nonprofits at the centre of the Hope Florida matter.")
ag = race("ag", "Attorney General", "Attorney General", "all",
          [uth, cand("Jose Javier Rodriguez", ST("Rodriguez, Jose Javier"))],
          note="Uthmeier was appointed in 2025; this is his first election to the office.")
cfo = race("cfo", "Chief Financial Officer", "CFO", "all",
           [cand("Blaise Ingoglia", ST("Ingoglia, Blaise", "Government Gone Wild PAC"), incumbent=True),
            cand("Annette Taddeo", ST("Taddeo, Annette", "Friends of Annette Taddeo PC"))])
agr = race("agriculture", "Commissioner of Agriculture", "Agriculture", "all",
           [cand("Wilton Simpson", ST("Simpson, Wilton", "Friends of Wilton Simpson"), incumbent=True),
            cand("Joey Mendoza Atkins", ST("Mendoza Atkins, Joey"))])
for c in agr["candidates"]:
    if c["name"] == "Wilton Simpson" and "Florida Green PAC" in pc:
        p = pc["Florida Green PAC"]
        c["money"]["note"] += (f" A second committee tied to him in reporting, Florida Green PAC, has raised "
                               f"${float(p['totals'][0][2])/1e6:,.1f}M; its largest givers are Jobs for Florida "
                               f"($3.7M) and Floridians for Sustainable Agriculture ($1.5M).")

# ---------- legislature ----------
boyd = cand("Jim Boyd", ST("Boyd, Jim", "Friends of Jim Boyd"), incumbent=True)
sd20 = race("sd20", "State Senator, District 20", "State Senate 20", "all",
            [boyd, cand("Gerald Baldi", ST("Baldi, Gerald"))],
            note="Every address in 34221 that was checked falls in Senate District 20.")
hd71 = race("hd71", "State Representative, District 71", "State House 71", "district",
            [cand("Jordan Varnadore", ST("Varnadore, Jordan")), cand("Ocean Fitts", ST("Fitts, Ocean")),
             cand("Joseph Hoolihan", ST("Hoolihan, Joseph"))],
            scope_note="most of 34221 — City of Palmetto, Terra Ceia, Memphis, Ellenton",
            note="Open seat (Will Robinson is leaving). Check your sample ballot: your address is in either District 71 or 70.")
hd70 = race("hd70", "State Representative, District 70", "State House 70", "district",
            [cand("Michael Owen", ST("Owen, Michael"), incumbent=True), cand("Luther Keith Wilkins", ST("Wilkins, Luther Keith"))],
            scope_note="a northern slice of 34221 near Rubonia",
            note="Most of District 70 is Parrish and southern Hillsborough County.")

# ---------- county / local (research slice D) ----------
def lc(name, key, **kw):
    try:
        m = L(key)
    except StopIteration:
        m = None
    return cand(name, m, **kw)

cc6 = race("cc6", "County Commissioner, District 6 (At-Large)", "County Comm. 6", "all",
           [lc("Tara Poulton", "Poulton"), lc("Reggie Bellamy", "Bellamy")],
           note="Countywide seat. County candidates may take at most $1,000 per donor per election. About 1 in 10 addresses in 34221 sit in County District 3, which has no district race this year — those voters see only this county commission race.")
cc1 = race("cc1", "County Commissioner, District 1", "County Comm. 1", "district",
           [lc('Elizabeth "Liz" Arnold', "Arnold, Elizabeth"), lc("Sari Lindroos-Valimaki", "Lindroos")],
           scope_note="about 6 in 10 addresses in 34221 (outside most of Palmetto city)")
cc2 = race("cc2", "County Commissioner, District 2", "County Comm. 2", "district",
           [lc("Amanda Ballard", "Ballard", incumbent=True), lc("Charles B. Smith Sr", "Smith Sr, Charles")],
           scope_note="about 3 in 10 addresses in 34221 — most of the City of Palmetto")
sb2 = race("sb2", "School Board Member, District 2 (nonpartisan)", "School Board 2", "district",
           [lc("Cindy Spray", "Spray", incumbent=True), lc("Sharon Jefferson", "Jefferson")],
           scope_note="same voters as County Commission District 2 — most of Palmetto city",
           note="School Board districts have matched County Commission districts since Dec 2024. Voters in District 1 have no School Board race this year.")
mos = race("mosquito", "Mosquito Control District, Group 1", "Mosquito Control", "all",
           [lc("Scott Johnson", "Johnson, Scott", brief=True), lc("Rodney O'Quinn", "Quinn", brief=True),
            lc('Charles "Rick" Richards', "Richards, Charles", brief=True)])
pw2 = race("palmetto2", "City of Palmetto Commissioner, Ward 2", "Palmetto Ward 2", "district",
           [lc("Sunshine Joiner", "Joiner"), lc('Sheldon "Mailman" Jones', "Jones, Sheldon")],
           scope_note="only City of Palmetto voters in Ward 2")

# Lakewood-Ranch-developer bundling note, measured from the county export.
for c in sb2["candidates"]:
    if c["name"] == "Cindy Spray" and c.get("money"):
        c["money"]["groups"] = [[14000, 12, ["Schroeder Manatee Ranch Inc", "SMR Farms", "SMR Northeast", "SMR North 70",
                                             "SMR Northwest Land", "SMR 2050", "LWR Development", "LWR Communities",
                                             "LWR Commerce Park", "Lakewood Ranch Corp Park", "…"]]]
for c in cc6["candidates"]:
    if c["name"] == "Tara Poulton" and c.get("money"):
        c["money"]["groups"] = [[9000, 9, ["VB Investments LLC", "VB Pointe West Investments LLC", "Aircraft One LLC",
                                           "Aircraft Two LLC", "Country Club Shores LLC", "Orange Park LLC",
                                           "Speedwing Investment Company", "1099 Management Company LLC",
                                           "MB Acquisition & Leasing LLC"]]]
for c in cc2["candidates"]:
    if c["name"] == "Amanda Ballard" and c.get("money"):
        c["money"]["groups"] = [[6000, 6, ["six Florida Realtors political committees"]],
                                [4000, 4, ["One Stop Housing", "One Stop Housing D&C LLC", "El Patio Apartments LLC", "Robin's Apartments LLC"]]]

# ---------- judges ----------
def judge(name):
    c = clean(R.get(name, {"name": name}))
    return {"name": name, "text": c.get("bio", ""),
            "items": (c.get("record") or [])[:5] + (c.get("controversies") or []), "owner_sources": c["owner_sources"],
            "owner_sources_searched": c["owner_sources_searched"]}

scj = {"id": "supreme", "title": "Supreme Court & District Court of Appeal — retention", "short": "Judges", "scope": "all",
       "note": "Yes/No votes on whether each judge keeps the job. No money is raised for these; no Florida appellate "
               "judge has ever lost a retention vote.",
       "candidates": [], "retention": [judge(n) for n in ("Carlos G. Muñiz", "J. Andrew (Drew) Atkinson", "Morris Silberman",
                                                          "Daniel H. Sleet", "Andrea Teves Smith")]}

# ---------- measures ----------
measures = []
for i, m in enumerate(R.get("__measures__") or []):
    def L2(v):
        if isinstance(v, list):
            return [x if isinstance(x, dict) else {"text": str(x)} for x in v]
        return [{"text": str(v)}] if v else []
    measures.append({"measure": True, "id": f"m{i}", "name": m.get("name"), "short": (m.get("name") or "")[:24],
                     "scope": "all" if "Palmetto" not in (m.get("name") or "") else "dist",
                     "scope_note": "every voter" if "Palmetto" not in (m.get("name") or "") else "City of Palmetto voters only",
                     "summary": m.get("summary"), "who_funds_yes": L2(m.get("who_funds_yes")), "who_funds_no": L2(m.get("who_funds_no")),
                     "supporters": L2(m.get("supporters")), "opponents": L2(m.get("opponents")),
                     "fiscal": L2(m.get("fiscal") or m.get("fiscal_impact")),
                     "owner_sources": [], "urls": m.get("urls")})

cov = R.get("__coverage__") or []
doc = {
    "title": "Palmetto Ballot Report",
    "description": "Every race on the Nov 3, 2026 ballot for Palmetto, FL 34221: who funds each candidate, their record, and what was found.",
    "kicker": "General election · Tuesday, November 3, 2026 · polls 7am–7pm · Palmetto, FL 34221",
    "headline": "Who is on your ballot, and who is paying for them",
    "lede": ("Every race a Palmetto (34221) voter can see, in ballot order. For each candidate: the money — how much, from "
             "where, from whom, and who is spending to help or hurt them — then their public record, cases and complaints, "
             "documented foreign ties, and what the owner's chosen sources say. Party is shown because it is printed on the "
             "ballot; nothing here is sorted or scored by it."),
    "built": "2026-11-02",
    "boxes": [
        {"title": "First: confirm which district races are on YOUR ballot",
         "html": ("<p>34221 is split. Everyone gets the statewide, U.S. House 16, State Senate 20, county-wide and judicial races. "
                  "State House (70 or 71), County Commission district, School Board district and Palmetto city races depend on "
                  "your exact address. Your personal sample ballot and polling place are at "
                  "<a href=\"https://www.votemanatee.gov/sample-ballots/\" target=\"_blank\" rel=\"noopener\">votemanatee.gov/sample-ballots</a> "
                  "(name + date of birth). On Election Day you must vote at your assigned precinct. Bring photo ID with a signature.</p>")},
        {"title": "How to read this", "cls": "warn",
         "html": ("<p>This report does not tell you who to vote for. It lays out who wrote the checks and what the public record "
                  "shows, so you can judge against your own three questions: commitment to the country and to this area, foreign "
                  "ties, and big money that could sway them. A donation is a fact about the donor; it is not proof of what the "
                  "candidate will do. Filings also miss things — dark-money groups, family money, promises.</p>"
                  "<p>Every claim carries a link. Controversies are labelled <b>allegation</b>, <b>established</b>, "
                  "<b>dismissed</b> or <b>fact-checked</b>. Newspaper editorials are shown separately as opinion. The amber "
                  "boxes hold what the owner's chosen sources (Owen Shroyer, Alex Jones, Stew Peters) say; that content is "
                  "reported as they say it and has not been checked against records here.</p>")},
    ],
    "parts": [
        {"title": "Federal", "races": [sen, house]},
        {"title": "State — Governor and Cabinet", "races": [govr, ag, cfo, agr]},
        {"title": "State Legislature", "races": [sd20, hd71, hd70],
         "note": " ".join(cov[:1])[:900] if cov else None},
        {"title": "Judges", "races": [scj]},
        {"title": "County and City", "races": [cc6, cc1, cc2, sb2, mos, pw2]},
        {"title": "Ballot measures", "races": measures},
    ],
    "footer": ("<p><b>Sources.</b> Official ballot: Manatee County Supervisor of Elections generic sample ballot (Nov 3, 2026). "
               "Federal money: FEC bulk files and 24/48-hour independent-expenditure reports, downloaded Nov 2, 2026. State money: "
               "Florida Division of Elections contribution records, pulled Nov 2, 2026. County and city money: Manatee County "
               "Supervisor of Elections reports, pulled Nov 2, 2026. Records and controversies: linked per item.</p>"
               "<p><b>Known limits.</b> FEC itemized donor detail is processed only through about July 2026 even though totals run to "
               "Oct 14. 'Building / land' tags are literal matches on the donor's own filed name or occupation, so they miss "
               "developers who give personally and can catch unrelated names containing a word like 'land'. Same-address groupings "
               "show companies sharing an address, not proven common ownership.</p>"),
}
json.dump(doc, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("wrote", OUT)
