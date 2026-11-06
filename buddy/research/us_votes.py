"""Sitting U.S. House members' votes, read from the House Clerk's official roll calls, for no AI cost.
Run: py buddy/research/us_votes.py AL NJ CA NC
Writes ballot/inputs/<ST>/us_votes.json: {person file: [votes]}, and updates any research file already saved. batch.py read copies them in too.
People are matched to the Clerk's member id through the current-members list, never by surname, because states have members and candidates who share one.
The list is the same 10 votes Florida's U.S. House cards use. Senate votes aren't done yet."""
import json, re, sys, time, unicodedata, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gather import ROOT, UA  # noqa: E402
from make_prompt import STATE_NAMES, person_file, roster, shares_name  # noqa: E402

MEMBERS = "https://unitedstates.github.io/congress-legislators/legislators-current.json"
ROLLS = [
    (2026, 53, "H.R. 7148 (2026) Consolidated Appropriations Act, 2026 (final)", "Final FY2026 spending package funding most remaining federal agencies through September 30, 2026."),
    (2025, 320, "S. 1071 / FY2026 National Defense Authorization Act (final)", "Final FY2026 defense policy and funding-authorization bill (about $900 billion), carried in the House on the vehicle S. 1071."),
    (2025, 285, "H.R. 5371 (2025) Continuing Appropriations and Extensions Act, 2026 (Nov. 12 final, ended the shutdown)", "Ended the 43-day federal shutdown: funds government through Jan. 30, 2026 and three full-year spending bills."),
    (2025, 281, "H.R. 5371 (2025) Continuing Appropriations and Extensions Act, 2026 (Sept. 19 House passage)", "House-passed stopgap funding bill to keep government open through Nov. 21, 2025; stalled in the Senate and a shutdown began Oct. 1."),
    (2025, 190, "H.R. 1 (2025) One Big Beautiful Bill Act (final passage)", "The 2025 reconciliation law: extends the 2017 tax cuts, adds new tax breaks, cuts Medicaid and food-assistance spending, and raises defense and border spending and the debt limit."),
    (2025, 120, "H.R. 881 (2025) DHS Restrictions on Confucius Institutes and Chinese Entities of Concern Act", "Bars Homeland Security funds going to Confucius Institutes and entities tied to the Chinese government."),
    (2025, 102, "H.R. 22 (2025) SAVE Act", "Requires documentary proof of U.S. citizenship to register to vote in federal elections."),
    (2025, 70, "H.R. 1968 (2025) Full-Year Continuing Appropriations and Extensions Act, 2025", "Funds the federal government through September 30, 2025 at roughly prior-year levels (March 2025 stopgap)."),
    (2025, 9, "H.R. 152 (2025) Federal Disaster Assistance Coordination Act", "Streamlines coordination among federal agencies delivering disaster aid (hurricane/flood recovery)."),
    (2025, 6, "H.R. 29 (2025) Laken Riley Act", "Requires federal detention of undocumented immigrants charged with theft, burglary or assault of a police officer, and lets states sue over immigration enforcement."),
]
VOTE = {"Yea": "Yea", "Aye": "Yea", "Nay": "Nay", "No": "Nay", "Present": "Present", "Not Voting": "Not voting"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
        return r.read()


def fold(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower().strip()


def member_id(person, members):
    """The Clerk's id for a sitting representative of this person's state with this last and first name, or the same last name in their own district. Otherwise None."""
    if shares_name(person) and not person["key"].startswith("ushouse"):      # California has a congressman and an Assembly candidate both named Robert Garcia
        return None
    words = re.sub(r"\([^)]*\)|\"[^\"]*\"", " ", fold(person["name"])).replace(",", " ").replace(".", " ").split()
    words = [w for w in words if w not in ("jr", "sr", "ii", "iii", "iv")]
    hits = []
    for m in members:
        term, name = m["terms"][-1], m["name"]
        if term["type"] != "rep" or term["state"] != person["st"]:
            continue
        last = fold(name["last"]).replace(".", "").split()
        if words[-len(last):] != last:
            continue
        firsts = [fold(name.get(k, "")) for k in ("first", "nickname") if name.get(k)]
        if any(f[:3] == words[0][:3] for f in firsts) or person["key"] == f"ushouse-{term['district']}":
            hits.append(m["id"]["bioguide"])
    return hits[0] if len(hits) == 1 else None


def read_roll(year, roll, bill, what):
    root = ET.fromstring(get(f"https://clerk.house.gov/evs/{year}/roll{roll:03d}.xml"))
    meta = root.find("vote-metadata")
    totals = meta.find("vote-totals/totals-by-vote")
    yeas, nays = totals.findtext("yea-total").strip(), totals.findtext("nay-total").strip()
    date = time.strftime("%Y-%m-%d", time.strptime(meta.findtext("action-date").strip(), "%d-%b-%Y"))
    base = {"bill": bill, "what": what, "date": date, "chamber": "U.S. House", "result": f"{meta.findtext('vote-result').strip().lower()} {yeas}-{nays}",
            "url": f"https://clerk.house.gov/Votes/{year}{roll:03d}"}
    return base, {r.find("legislator").get("name-id"): r.findtext("vote").strip() for r in root.findall("vote-data/recorded-vote")}


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    members = json.loads(get(MEMBERS))
    rolls = []
    for year, roll, bill, what in ROLLS:
        rolls.append(read_roll(year, roll, bill, what))
        time.sleep(1)
    for st in [a for a in sys.argv[1:] if a in STATE_NAMES]:
        out = {}
        for p in roster(st):
            mid = member_id(p, members)
            if not mid:
                continue
            votes = [dict(base, vote=VOTE[cast[mid]]) for base, cast in rolls if mid in cast]
            if votes:
                out[person_file(p)] = votes
                f = ROOT / "ballot" / "inputs" / st / "research" / f"{person_file(p)}.json"
                if f.exists():
                    r = json.loads(f.read_text(encoding="utf-8"))
                    r["votes"] = votes
                    f.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
            print(st, p["race"], "|", p["name"], "|", mid, "|", len(votes), "votes", flush=True)
        (ROOT / "ballot" / "inputs" / st / "us_votes.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(st, len(out), "sitting House members with votes", flush=True)


if __name__ == "__main__":
    main()
