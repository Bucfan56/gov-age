"""Alabama campaign money for everyone on the 2026 roster, from the state's public yearly files.
Files: https://fcpa.alabamavotes.gov/page.request.do?page=page.acfPublicDownloadData (Cash, In-Kind, Other Receipts for 2023-2026, the cycle for this election).
Run: py ballot/al_money.py RAW_FOLDER     Downloads into RAW_FOLDER if empty. That folder holds street addresses and must stay out of the repo.
Writes ballot/inputs/AL/state_money.json with city, state and ZIP only: street addresses are never kept."""
import csv, io, json, re, sys, time, urllib.parse, urllib.request, zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "buddy" / "research"))
from make_prompt import roster  # noqa: E402

SITE = "https://fcpa.alabamavotes.gov/page.request.do?page="
UA = {"User-Agent": "Mozilla/5.0 (compatible; BallotBuddyResearch/1.0; +https://ballotbuddy.app; voter guide)"}
YEARS = (2023, 2024, 2025, 2026)
KINDS = {"Cash Contribution": "Cash", "In-Kind Contribution": "InKind", "Other Receipts": "Other"}
SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv)\b\.?", re.I)


def download(raw):
    raw.mkdir(parents=True, exist_ok=True)
    listing = json.load(urllib.request.urlopen(urllib.request.Request(
        SITE + "com.acf.common.page.transactiondatadownloadsresults&pageSize=200&pageNumber=1&sortDirection=DESC&sortBy=YEAR", headers=UA), timeout=60))
    for x in listing["data"]["list"]:
        if x["YEAR"] in YEARS and x["DATATYPE"] in KINDS:
            f = raw / f"{x['YEAR']}_{KINDS[x['DATATYPE']]}.zip"
            if not f.exists():
                f.write_bytes(urllib.request.urlopen(urllib.request.Request(SITE + f"getTransactionData&id={x['DOWNLOAD']}", headers=UA), timeout=300).read())
                time.sleep(2)


def rows(path):
    """The files aren't clean CSV: an address can hold a line break or a stray quote, and a normal reader then swallows thousands of rows into one.
    So each line is read alone, and a short line is joined to the next until it has every column. Anything still broken is counted, never guessed."""
    z = zipfile.ZipFile(path)
    text = io.TextIOWrapper(z.open(z.namelist()[0]), encoding="latin-1", newline="")
    head = next(csv.reader([text.readline()]))
    bad, held = [], ""
    for line in text:
        line = held + line.rstrip("\r\n")
        cells = next(csv.reader([line.replace('"', "") if line.count('"') % 2 else line]), [])
        if len(cells) < len(head) and len(held) < 2000:
            held = line + " "
            continue
        held = ""
        if len(cells) == len(head) and re.fullmatch(r"-?\d+(\.\d+)?", cells[1]):
            yield dict(zip(head, cells))
        else:
            bad.append(cells[1:3])
    if held or bad:
        print(f"   {path.name}: {len(bad) + bool(held)} unreadable rows dropped", file=sys.stderr)


def registered():
    """Every campaign committee the state has on file. Filings carry legal names ('THOMAS TUBERVILLE', 'Nehemiah Wahl'), so people are matched by office and district first."""
    out, page = [], 1
    crit = json.dumps([{"field_key": "committeeType", "comparison_type": "equalTo", "comparison_value_1": "1"}])
    while True:
        q = urllib.parse.urlencode({"pageNumber": page, "pageSize": 200, "sortDirection": "ASC", "sortBy": "candidateLastName", "criteria": crit})
        d = json.load(urllib.request.urlopen(urllib.request.Request(SITE + "com.acf.common.page.committeesearchresults&" + q, headers=UA), timeout=60))["data"]
        out += d["list"]
        if not d["list"] or len(out) >= d["totalRecords"]:
            return out
        page += 1
        time.sleep(1)


def words(name):
    return re.sub(r"[^a-z ]", "", SUFFIX.sub("", re.sub(r'\([^)]*\)|"[^"]*"', "", name.lower())).replace(",", " ")).split()


def office_fits(p, c):
    office, place = (c.get("office") or "").lower(), (c.get("jurisdiction") or "").upper()
    m = re.fullmatch(r"(stsen|sthouse)-(\d+)", p["key"])
    if m:
        kind, word = ("state senator", "SENATE") if m.group(1) == "stsen" else ("state representative", "HOUSE")
        return office == kind and place == f"{word} DISTRICT {int(m.group(2))}"
    return office == {"gov": "governor", "ltgov": "lt. governor", "ag": "attorney general", "sos": "secretary of state", "auditor": "state auditor",
                      "treas": "state treasurer", "agcomm": "commissioner of agriculture & industries"}.get(p["key"])


def committees_for(p, listed, money):
    """In the same office and district, one person with that last name is enough. If two share it, a first name must fit. Otherwise no match: no money beats the wrong person's money."""
    w = words(p["name"])
    same = [c for c in listed if office_fits(p, c) and w[-1] in words(c.get("candidateLastName") or "")]
    active = [c for c in same if money[c["committeeId"]]["gifts"]]
    same = active or same       # someone's old committee from an earlier run doesn't count against this one
    if len({(c.get("candidateFirstName") or "").lower()[:3] for c in same}) > 1:
        fit = [c for c in same if any((c.get("candidateFirstName") or "").lower().startswith(x) or x.startswith((c.get("candidateFirstName") or "?").lower()) for x in w[:-1])]
        same = fit
    return same


def donor(r):
    last, first = r["LastName"].strip(), r["FirstName"].strip()
    return f"{first} {last}".strip() if first else last


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raw = Path(sys.argv[1])
    download(raw)
    people = [p for p in roster("AL") if not p["key"].startswith(("ushouse", "ussen"))]
    money = defaultdict(lambda: {"gifts": {}, "loans": 0.0})
    types = defaultdict(float)
    amended = 0
    for year in YEARS:
        for kind in ("Cash", "InKind", "Other"):
            for r in rows(raw / f"{year}_{kind}.zip"):
                if r["CommitteeType"].strip() != "Principal Campaign Committee":
                    continue
                amt = float(r.get("ContributionAmount") or r.get("ReceiptAmount") or 0)
                c = money[r["CommitteeId"].strip()]
                amended += r["Amended"].strip() == "Y"
                if kind == "Other":
                    t = r["ReceiptType"].strip()
                    types[t] += amt
                    if "loan" in t.lower():
                        c["loans"] += amt
                    continue
                rid = r.get("ContributionID") or r.get("InKindContributionID")
                c["gifts"][rid] = {"donor": donor(r), "city": r["City"].strip(), "st": r["State"].strip().upper(), "zip": r["Zip"].strip()[:5], "amt": amt,
                                   "date": r["ContributionDate"], "type": r["ContributorType"].strip(), "kind": r["ContributionType"].strip()}
    listed = registered()
    out, missing, unfiled = {}, [], []
    for p in people:
        found = committees_for(p, listed, money)
        if not found:
            missing.append(f"{p['name']} ({p['race']}, {p['pc']}%)")
            continue
        ids = [c["committeeId"] for c in found]
        gifts = [g for i in ids for g in money[i]["gifts"].values()] if ids else []
        if not gifts:
            unfiled.append(f"{p['name']} ({p['race']})")
        out[p["name"]] = {"committees": [f"{c['committeeId']} {c['candidateFirstName']} {c['candidateLastName']}" for c in found],
                          "loans": round(sum(money[i]["loans"] for i in ids), 2), "gifts": gifts}
    (ROOT / "ballot" / "inputs" / "AL" / "state_money.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(listed)} committees on file. Matched {len(out)} of {len(people)} state candidates, ${sum(g['amt'] for v in out.values() for g in v['gifts']):,.0f}. "
          f"Rows marked amended: {amended}. Other receipt types: {dict(types)}")
    print(f"No committee found for {len(missing)}:", missing)
    print(f"Committee found, no 2023-2026 gifts for {len(unfiled)}:", unfiled)


if __name__ == "__main__":
    main()
