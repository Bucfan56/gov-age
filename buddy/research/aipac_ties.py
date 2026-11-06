"""AIPAC's involvement with every federal candidate, from official records, for no AI cost. Also every privately paid trip abroad a House member filed.
Run: py buddy/research/aipac_ties.py <fec26 folder> <older pas2 folder> <travel folder> NJ AL CA NC
  fec26 folder: the FEC's 2025-26 bulk files (itpas2.txt, ie26.csv, indiv26.zip, cm.txt).
  older pas2 folder: pas222.zip and pas224.zip from fec.gov/files/bulk-downloads.
  travel folder: <year>.zip for each year's Travel.zip from disclosures-clerk.house.gov/GiftTravelFilings.
Writes ballot/inputs/<ST>/aipac_ties.json, keyed by person file. It reports what the records say and stops there.
Covered: AIPAC PAC gifts 2021-26; gifts from individuals passed through AIPAC PAC, 2025-26 only; United Democracy Project spending for and against 2021-26; House travel filed 2021-26.
Then run aipac_live.py merge: many campaigns never name the PAC in their own reports, so the PAC's own report sets the money.
Not covered: Senate travel (Senate.gov refuses scripts), and anything no public record shows."""
import csv, io, json, re, sys, unicodedata, zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_prompt import ROOT, person_file, roster  # noqa: E402
from us_attendance import senator_id  # noqa: E402
from us_votes import MEMBERS, get, member_id  # noqa: E402

AIPAC_PAC, UDP = "C00797670", "C00799031"
AIEF = re.compile(r"American\s+Israel\s+Education\s+(Foundation|Fund)|\bAIEF\b|^\s*Israel\s+Education\s+Foundation", re.I)
US_PLACE = re.compile(r"\b(AL|AK|AZ|AR|CA|CO|CT|DE|DC|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|PR|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\b"
                      r"|\b(Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Puerto Rico|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming|United States|USA)\b")
TRAVEL_SOURCE = "https://disclosures-clerk.house.gov/GiftTravelFilings"
FEC_SOURCE = "https://www.fec.gov/data/committee/C00797670/"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def plain(s):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()).strip()


def name_parts(name):
    """(last name, first name) from a ballot name, ignoring suffixes, quoted nicknames and middle names."""
    n = re.sub(r"\([^)]*\)|\"[^\"]*\"", " ", plain(name)).replace(",", " ")
    w = [x for x in n.split() if x.lower().rstrip(".") not in {"jr", "sr", "ii", "iii", "iv"}]
    return w[-1].lower(), w[0].lower()


def pas2_rows(fh, cycle, pac, udp):
    for line in fh:
        p = line.rstrip("\r\n").split("|")
        if p[0] == AIPAC_PAC and p[5] in ("24K", "24Z"):
            # The PAC also lists some gifts from individuals that it passed on. Those aren't its own money, and they're counted from the candidate's side.
            if "EARMARK" not in p[20].upper():
                pac[p[16]][cycle] += float(p[14] or 0)
        elif p[0] == UDP and p[5] in ("24E", "24A"):
            udp[p[16]][("for" if p[5] == "24E" else "against", cycle)] += float(p[14] or 0)


def read_fec(fec26, older):
    pac, udp = defaultdict(lambda: defaultdict(float)), defaultdict(lambda: defaultdict(float))
    with open(f"{fec26}/itpas2.txt", encoding="latin-1") as fh:
        pas2_rows(fh, "2026", pac, udp)
    for cycle, short in (("2022", "22"), ("2024", "24")):
        with zipfile.ZipFile(f"{older}/pas2{short}.zip") as z, z.open("itpas2.txt") as raw:
            pas2_rows(io.TextIOWrapper(raw, encoding="latin-1"), cycle, pac, udp)
    # Late 2026 spending reaches the 24- and 48-hour file before the bulk file, so 2026 takes whichever total is higher. Amended lines are counted once, by transaction id.
    late = {}
    with open(f"{fec26}/ie26.csv", encoding="latin-1", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["spe_id"] == UDP:
                late[r["tran_id"] or id(r)] = r
    totals = defaultdict(lambda: defaultdict(float))
    for r in late.values():
        totals[r["cand_id"]]["for" if r["sup_opp"].upper().startswith("S") else "against"] += float(r["exp_amo"] or 0)
    for cid, t in totals.items():
        for side, amt in t.items():
            udp[cid][(side, "2026")] = max(udp[cid][(side, "2026")], amt)
    return pac, udp


def read_committees(fec26):
    """Each candidate id's own campaign committee, from the FEC's candidate file."""
    with open(f"{fec26}/cn.txt", encoding="latin-1") as fh:
        return {p[0]: p[9] for p in (line.rstrip("\r\n").split("|") for line in fh) if p[9]}


def read_earmarks(fec26):
    """Gifts from individuals that the FEC records as passed through AIPAC PAC, by receiving committee. Totals only: donors are never kept."""
    tot = defaultdict(float)
    with zipfile.ZipFile(f"{fec26}/indiv26.zip") as z, z.open("itcont.txt") as raw:
        for line in io.TextIOWrapper(raw, encoding="latin-1"):
            if AIPAC_PAC not in line and "AIPAC" not in line.upper():
                continue
            p = line.rstrip("\r\n").split("|")
            if len(p) >= 21 and p[0] != AIPAC_PAC and (p[15] == AIPAC_PAC or "AIPAC" in p[19].upper()):
                tot[p[0]] += float(p[14] or 0)
    return tot


def read_travel(folder):
    """One row per trip, an amendment replacing its original. Newest filings win."""
    out = {}
    for f in sorted(Path(folder).glob("20*.zip")):
        with zipfile.ZipFile(f) as z:
            for m in ET.fromstring(z.read(next(n for n in z.namelist() if n.endswith(".xml")))):
                r = {c.tag: plain(c.text) for c in m}
                out[(r["MemberName"], r["FilerName"], r["DepartureDate"], r["ReturnDate"], r["TravelSponsor"][:20].lower())] = r
    return list(out.values())


def trip(r):
    return {"member_or_staff": r["FilerName"], "sponsor": r["TravelSponsor"], "to": r["Destination"], "left": r["DepartureDate"], "back": r["ReturnDate"], "doc": r["DocID"]}


def main():
    fec26, older, travel = sys.argv[1:4]
    pac, udp = read_fec(fec26, older)
    earmarks = read_earmarks(fec26)
    trips = read_travel(travel)
    committees = read_committees(fec26)
    members = {m["id"]["bioguide"]: m for m in json.loads(get(MEMBERS))}
    print(f"{len(trips)} trips read; {sum(not t['TravelSponsor'] for t in trips)} with no sponsor listed")
    for st in sys.argv[4:]:
        money = json.loads((ROOT / "ballot" / "inputs" / st / "fed_money_all.json").read_text(encoding="utf-8"))
        by_name = defaultdict(list)
        for k, v in money.items():
            last = plain(k.split(",")[0]).lower().split()
            if last:
                by_name[last[-1]].append((k, v))
        here = [t for t in trips if t["State"] == st]
        out, unsure = {}, []
        sitting = json.loads((ROOT / "ballot" / "inputs" / st / "us_attendance.json").read_text(encoding="utf-8"))
        for p in roster(st):
            # A sitting member of Congress running for a state office has the same record, under their House or Senate ids.
            if p["lvl"] != "fed" and person_file(p) not in sitting:
                continue
            last, first = name_parts(p["name"])
            senate = p["key"] == "ussen"
            recs = []
            for k, v in by_name.get(last, []):
                given = plain(k.split(",", 1)[1] if "," in k else "").lower()
                if v["fec_id"][0] == ("S" if senate else "H") and (given[:1] == first[:1] or first in given.split()):
                    recs.append(v)
            # Any of this person's ids can hold the money: one person can have a House id and a Senate id.
            shared = {c for v in recs for c in v["committees"]}
            ids = {v["fec_id"] for v in money.values() if set(v["committees"]) & shared} | {v["fec_id"] for v in recs}
            if p["lvl"] != "fed":
                member = members[member_id(p, list(members.values())) or senator_id(p, list(members.values()))]
                ids |= set(member["id"].get("fec") or [])
                shared |= {committees[i] for i in ids if i in committees}
            gifts = {c: round(sum(pac[i].get(c, 0) for i in ids), 2) for c in ("2022", "2024", "2026")}
            for_ = {c: round(sum(udp[i].get(("for", c), 0) for i in ids), 2) for c in ("2022", "2024", "2026")}
            against = {c: round(sum(udp[i].get(("against", c), 0) for i in ids), 2) for c in ("2022", "2024", "2026")}
            passed = round(sum(earmarks.get(c, 0) for c in shared), 2)

            mine = []
            for t in here:
                tl, tf = name_parts(t["MemberName"].split(",", 1)[1] + " " + t["MemberName"].split(",")[0]) if "," in t["MemberName"] else (t["MemberName"].lower(), "")
                if tl == last and tf[:1] == first[:1]:
                    mine.append(t)
            own = [t for t in mine if last in plain(t["FilerName"]).lower() or not t["FilerName"]]
            staff = [t for t in mine if t not in own]
            abroad = lambda t: t["Destination"] and not US_PLACE.search(t["Destination"])
            row = {"race": p["race"], "fec_ids": sorted(ids),
                   "aipac_pac_gifts": gifts, "passed_through_aipac_pac_2026": passed,
                   "udp_spent_for": for_, "udp_spent_against": against,
                   "aipac_trips": [trip(t) for t in own if AIEF.search(t["TravelSponsor"])],
                   "aipac_staff_trips": [dict(trip(t), member_or_staff="staff") for t in staff if AIEF.search(t["TravelSponsor"])],      # Staff names aren't needed on a voter guide.
                   "other_trips_abroad": [trip(t) for t in own if abroad(t) and not AIEF.search(t["TravelSponsor"])],
                   "trips_filed": len(own), "trips_filed_no_sponsor": sum(not t["TravelSponsor"] for t in own),
                   "sources": {"money": FEC_SOURCE, "travel": TRAVEL_SOURCE}}
            if not recs and not mine:
                unsure.append(p["name"])
            out[person_file(p)] = row
        f = ROOT / "ballot" / "inputs" / st / "aipac_ties.json"
        f.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{st}: {len(out)} people; no FEC record or travel filing found for {len(unsure)}: {unsure}")


if __name__ == "__main__":
    main()
