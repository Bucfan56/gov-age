"""Companies a federal candidate reports owning, from House financial disclosures, checked against federal contract and grant records. No AI cost.
Run: py buddy/research/business_ties.py <download folder> NJ
  The folder keeps <year>FD.zip (the Clerk's filing index) and each filing's PDF, and DOGE's cancelled lists.
Writes ballot/inputs/<ST>/business_ties.json, keyed by person file.
A name match is a lead for a person to read, never a finding: it says a company with this name got federal money, not that the candidate's company did, and never that anything was wrong.
Covered: House members and House candidates who filed for 2025 or 2026. Not covered: Senate filers, companies held under another name, companies named only in an attachment, state and local contracts."""
import json, re, sys, time, unicodedata, urllib.error, urllib.request, zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_prompt import ROOT, person_file, roster  # noqa: E402

UA = "ballot-buddy-research (claude)"
CLERK = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs"
USA = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
DOGE = "https://api.doge.gov/savings"
NOISE = re.compile(r"^(\$|none\b|sp$|jt$|dc$|filing id|asset$|owner|income|current|filing$|preceding|year$|tx\.|partnership|rent\b|dividends|interest$|capital gains|royalties|salary|location:|description:|comments:|value of asset|\d)", re.I)
STREET = re.compile(r"\b\d{1,6}\s+\w+.*\b(ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|BLVD|LN|LANE|CT|COURT|PL|PLACE|WAY|HWY|PKWY)\b\.?|P\.?\s?O\.?\s?BOX", re.I)
COMPANY_WORDS = {"llc", "l", "c", "lp", "llp", "pllc", "pc", "p", "inc", "incorporated", "corp", "corporation", "co", "company", "ltd", "the"}
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def get(url, data=None):
    headers = {"User-Agent": UA}
    if data:
        headers["Content-Type"] = "application/json"
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=90) as r:
        return r.read()


def plain(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def same_name(name):
    """A company's name without its company words, so "Acme LLC" and "Acme, L.L.C." match."""
    return " ".join(w for w in re.sub(r"[^a-z0-9]+", " ", plain(name)).split() if w not in COMPANY_WORDS)


def clean_company(name):
    return re.sub(r",?\s*\d+(\.\d+)?\s*%.*$", "", name).strip(" ,")


def index(folder):
    rows = []
    for year in ("2025", "2026"):
        z = folder / f"{year}FD.zip"
        if not z.exists():
            z.write_bytes(get(f"{CLERK}/{year}FD.zip"))
        with zipfile.ZipFile(z) as zz:
            for line in zz.read(f"{year}FD.txt").decode("utf-8", "replace").splitlines()[1:]:
                p = line.split("\t")
                if len(p) >= 9 and p[4] in ("C", "O", "A"):
                    rows.append({"last": plain(p[1]), "first": plain(p[2]), "type": p[4], "state": p[5][:2], "dist": p[5][2:], "year": p[6], "filed": p[7], "doc": p[8]})
    return rows


def filing_for(rows, person):
    """The person's newest annual or candidate filing, by state, last name and first initial."""
    n = re.sub(r"\([^)]*\)|\"[^\"]*\"", " ", plain(person["name"])).replace(",", " ").split()
    n = [x for x in n if x.rstrip(".") not in {"jr", "sr", "ii", "iii", "iv"}]
    hits = [r for r in rows if r["state"] == person["st"] and r["last"].split()[-1:] == n[-1:] and r["first"][:1] == n[0][:1]]
    return max(hits, key=lambda r: (r["year"], time.strptime(r["filed"], "%m/%d/%Y"))) if hits else None


def unscramble(text):
    """Filings print their small-capital headings in odd letters, starting at U+0283 for a. Put them back."""
    return "".join(chr(ord(c) - 0x222) if 0x283 <= ord(c) <= 0x29C else c for c in text)


def holdings(path):
    """Businesses from a filing: assets coded as an LLC or partnership [OL], other ownership interest [OI] or stock not publicly traded [PS], and any office held (Schedule E). Typed filings only: a scan returns None."""
    import fitz
    with fitz.open(path) as d:
        text = unscramble("\n".join(p.get_text() for p in d))
    if len(text.strip()) < 200 or "Schedule A" not in text:
        return None
    lines = [re.sub(r"\s+", " ", l).strip() for l in text.splitlines()]
    out = []
    for i, l in enumerate(lines):
        m = re.search(r"\[(OL|OI|PS)\]\s*$", l)
        if not m:
            continue
        name = l[:m.start()].strip()
        j = i - 1
        while j >= 0 and j > i - 3 and lines[j] and not NOISE.match(lines[j]) and "[" not in lines[j] and (not name or name[0].islower() or lines[j].endswith((",", "&", "%")) or len(name) < 12):
            name = (lines[j] + " " + name).strip()
            j -= 1
        block = lines[i + 1:i + 9]
        desc = next((x.split(":", 1)[1].strip() for x in block if x.startswith("Description:")), "")
        desc = "" if STREET.search(desc) else desc      # Street addresses are never stored.
        place = next((x.split(":", 1)[1].strip() for x in block if x.startswith("Location:")), "")
        out.append({"name": clean_company(name), "code": m.group(1), "description": desc[:160], "place": place})
    sec = re.search(r"Schedule E: Positions(.*?)(Schedule F:|$)", "\n".join(lines), re.S)
    positions = []
    if sec:
        rows = [x for x in sec.group(1).splitlines() if x and not re.match(r"(Position|Name of Organization|None disclosed|Filing ID)", x)]
        positions = [{"title": rows[k], "organization": rows[k + 1]} for k in range(0, len(rows) - 1, 2)]
    return {"companies": out, "positions": positions}


def federal_money(name):
    """Contracts and grants to a recipient of this name, since 2019, from USAspending."""
    out = []
    for kind, codes, amount, start in (("contract", ["A", "B", "C", "D"], "Award Amount", "Start Date"), ("grant", ["02", "03", "04", "05"], "Award Amount", "Start Date")):
        body = json.dumps({"filters": {"recipient_search_text": [name], "award_type_codes": codes, "time_period": [{"start_date": "2019-01-01", "end_date": "2026-12-31"}]},
                           "fields": ["Award ID", "Recipient Name", amount, "Awarding Agency", start], "limit": 25}).encode()
        for r in json.loads(get(USA, body)).get("results") or []:
            if same_name(r["Recipient Name"]) == same_name(name):
                out.append({"kind": kind, "recipient": r["Recipient Name"], "amount": r.get(amount), "agency": r.get("Awarding Agency"), "started": r.get(start), "award": r.get("Award ID")})
    return out


def doge_lists(folder):
    """Every contract and grant DOGE lists as cancelled, kept on disk. DOGE's search can't look up a vendor, so the whole list comes down."""
    f = folder / "doge.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    out = {}
    for kind, vendor in (("contracts", "vendor"), ("grants", "recipient")):
        rows, page = [], 1
        while True:
            d = json.loads(get(f"{DOGE}/{kind}?per_page=500&page={page}"))
            rows += [{"name": r.get(vendor), "value": r.get("value"), "agency": r.get("agency"), "savings": r.get("savings")} for r in d["result"][kind]]
            if page >= d["meta"]["pages"]:
                break
            page += 1
            time.sleep(1)
        out[kind] = rows
        print(f"DOGE {kind}: {len(rows)}", flush=True)
    f.write_text(json.dumps(out), encoding="utf-8")
    return out


def main():
    folder = Path(sys.argv[1])
    folder.mkdir(parents=True, exist_ok=True)
    rows = index(folder)
    cancelled = {}
    for kind, data in doge_lists(folder).items():
        for r in data:
            cancelled.setdefault(same_name(r["name"]), []).append(dict(r, kind=kind))
    for st in sys.argv[2:]:
        out = {}
        for p in roster(st):
            if p["lvl"] != "fed" or "Senate" in p["race"]:
                continue
            f = filing_for(rows, p)
            row = {"race": p["race"], "filing": None, "readable": False, "companies": [], "positions": [], "source": None}
            out[person_file(p)] = row
            if f:
                pdf = folder / f"{f['doc']}.pdf"
                if not pdf.exists():
                    try:
                        pdf.write_bytes(get(f"{CLERK}/{f['year']}/{f['doc']}.pdf"))
                    except urllib.error.HTTPError as e:
                        print(f"  {p['name']}: filing {f['doc']} answered {e.code}", flush=True)
                        continue
                    time.sleep(1)
                row["filing"] = {"doc": f["doc"], "type": f["type"], "year": f["year"], "filed": f["filed"]}
                row["source"] = f"{CLERK}/{f['year']}/{f['doc']}.pdf"
                h = holdings(pdf)
                if h:
                    row["readable"] = True
                    row["positions"] = h["positions"]
                    for c in h["companies"]:
                        try:
                            c["federal_awards"] = federal_money(c["name"])
                        except (urllib.error.URLError, TimeoutError) as e:
                            c["federal_awards"] = None
                            c["error"] = str(e)[:100]
                        c["doge_cancelled"] = cancelled.get(same_name(c["name"]), [])
                        row["companies"].append(c)
                        time.sleep(0.5)
            print(f"  {p['name']}: filing {f and f['doc']} readable={row['readable']} companies={len(row['companies'])} with federal awards={sum(bool(c.get('federal_awards')) for c in row['companies'])} on DOGE's list={sum(bool(c['doge_cancelled']) for c in row['companies'])} lookups failed={sum('error' in c for c in row['companies'])}", flush=True)
        (ROOT / "ballot" / "inputs" / st / "business_ties.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
