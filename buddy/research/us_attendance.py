"""How often sitting members of Congress showed up to vote this Congress (2025-26), for no AI cost. House: the Clerk's official roll calls. Senate: Voteview, because Senate.gov refuses scripts.
Run: py buddy/research/us_attendance.py <folder to keep downloads in> AL NJ CA NC       (safe to rerun; a file already downloaded isn't fetched again)
Writes ballot/inputs/<ST>/us_attendance.json: {person file: {"chamber", "roll_calls", "missed", "missed_pct", "longest_run", "run_from", "run_to", "source"}}.
A roll call counts only if the member is listed on it, so someone sworn in mid-term isn't charged for votes before they arrived. "Present" is not a miss."""
import csv, io, json, re, sys, time, urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gather import ROOT  # noqa: E402
from make_prompt import STATE_NAMES, person_file, roster  # noqa: E402
from us_votes import MEMBERS, fold, get, member_id  # noqa: E402

MISS = {"Not Voting"}


def fetch(folder, name, url, tag):
    """The roll call as parsed XML, or None if the site has no real roll call at this number. Only real ones are saved."""
    f = folder / name
    if f.exists():
        return ET.fromstring(f.read_bytes())
    try:
        data = get(url)
        root = ET.fromstring(data)
    except (urllib.error.HTTPError, ET.ParseError):
        time.sleep(1)
        return None
    time.sleep(1)
    if root.tag != tag:      # the House Clerk answers some missing numbers with <xml>Error sanitizing file</xml>
        return None
    f.write_bytes(data)
    return root


def walk(folder, prefix, url, tag):
    """Every real roll call in order. One bad answer doesn't end the year: three in a row do, and the numbers skipped before a later real one are reported."""
    n = bad = 0
    gaps, found = [], []
    while bad < 3:
        n += 1
        root = fetch(folder, f"{prefix}_{n:05d}.xml", url.format(n=n), tag)
        if root is None:
            bad += 1
            continue
        gaps += list(range(n - bad, n))
        bad = 0
        found.append(root)
    if gaps:
        print(f"  {prefix}: no real file at numbers {gaps}", flush=True)
    return found


def house_rolls(folder):
    """{member id: [(date, cast), ...]}, oldest first."""
    seen = {}
    for year in (2025, 2026):
        rolls = walk(folder, f"h{year}", f"https://clerk.house.gov/evs/{year}/roll{{n:03d}}.xml", "rollcall-vote")
        for root in rolls:
            date = time.strftime("%Y-%m-%d", time.strptime(root.find("vote-metadata").findtext("action-date").strip(), "%d-%b-%Y"))
            for r in root.findall("vote-data/recorded-vote"):
                seen.setdefault(r.find("legislator").get("name-id"), []).append((date, r.findtext("vote").strip()))
        print("House", year, len(rolls), "roll calls", flush=True)
        if not rolls:
            sys.exit(f"No House roll calls for {year}: stopping rather than counting nothing.")
    return seen


def senate_rolls(folder):
    """{Bioguide id: [(date, cast), ...]}, oldest first. Senate.gov's firewall refuses scripts (403), so this reads Voteview (UCLA), which publishes every roll call.
    Codes: 1 yea, 2 paired yea, 3 announced yea, 4 announced nay, 5 paired nay, 6 nay, 7 and 8 present, 9 not voting, 0 not in the Senate that day. 2 to 5 weren't cast, so they count as not voting, as the Senate's own record lists them."""
    def table(name):
        f = folder / name
        if not f.exists():
            f.write_bytes(get(f"https://voteview.com/static/data/out/{'votes' if '_votes' in name else 'rollcalls' if 'rollcalls' in name else 'members'}/{name}"))
        return list(csv.DictReader(io.StringIO(f.read_text(encoding="utf-8"))))
    bioguide = {r["icpsr"]: r["bioguide_id"] for r in table("S119_members.csv")}
    dates = {r["rollnumber"]: r["date"] for r in table("S119_rollcalls.csv")}
    seen = {}
    rows = sorted(table("S119_votes.csv"), key=lambda r: int(float(r["rollnumber"])))
    for r in rows:
        code = int(float(r["cast_code"]))
        if code and r["icpsr"] in bioguide:
            seen.setdefault(bioguide[r["icpsr"]], []).append((dates[r["rollnumber"]], "Not Voting" if code in (2, 3, 4, 5, 9) else "Voted"))
    print("Senate", len(dates), "roll calls (Voteview)", flush=True)
    if not dates:
        sys.exit("No Senate roll calls: stopping rather than counting nothing.")
    return seen


def summary(rows, chamber, source):
    missed = longest = run = 0
    start = best = None
    for date, cast in rows:
        if cast in MISS:
            missed += 1
            run += 1
            start = start or date
            if run > longest:
                longest, best = run, (start, date)
        else:
            run, start = 0, None
    return {"chamber": chamber, "roll_calls": len(rows), "missed": missed, "missed_pct": round(100 * missed / len(rows), 1),
            "longest_run": longest, "run_from": best[0] if best else None, "run_to": best[1] if best else None, "through": max(d for d, _ in rows), "source": source}


def senator_id(person, members):
    words = re.sub(r"\([^)]*\)|\"[^\"]*\"", " ", fold(person["name"])).replace(",", " ").replace(".", " ").split()
    words = [w for w in words if w not in ("jr", "sr", "ii", "iii", "iv")]
    for m in members:
        term, name = m["terms"][-1], m["name"]
        if term["type"] == "sen" and term["state"] == person["st"] and fold(name["last"]) == words[-1] and any(fold(name.get(k, ""))[:3] == words[0][:3] for k in ("first", "nickname") if name.get(k)):
            return m["id"]["bioguide"]
    return None


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    folder = Path(sys.argv[1])
    folder.mkdir(parents=True, exist_ok=True)
    members = json.loads(get(MEMBERS))
    house, senate = house_rolls(folder), senate_rolls(folder)
    for st in [a for a in sys.argv[2:] if a in STATE_NAMES]:
        out = {}
        for p in roster(st):
            mid = member_id(p, members)
            if mid and house.get(mid):
                out[person_file(p)] = summary(house[mid], "U.S. House", "https://clerk.house.gov/Votes")
            sid = senator_id(p, members)
            if sid and senate.get(sid):
                out[person_file(p)] = summary(senate[sid], "U.S. Senate", "https://voteview.com/congress/senate")
        (ROOT / "ballot" / "inputs" / st / "us_attendance.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(st, len(out), "sitting members", flush=True)
        for name, a in sorted(out.items(), key=lambda kv: -kv[1]["missed"])[:12]:
            print(f"  {name}: missed {a['missed']} of {a['roll_calls']} ({a['missed_pct']}%), longest run {a['longest_run']} ({a['run_from']} to {a['run_to']})", flush=True)


if __name__ == "__main__":
    main()
