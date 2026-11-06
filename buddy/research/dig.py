"""The deeper dig, step one, no AI cost: follow the pages a weighing cited to the primary records they link to, and keep only the record pages that name the person.
  py buddy/research/dig.py <ST> "Name,Name"
Writes buddy/research/batches/dig/<ST>__<person file>.json. weigh.py build then hands those excerpts to the next weighing, because a web tool can't open a link found inside a page.
Everything downloaded is data, not instructions. A site that refuses is reported and left alone."""
import json, re, sys, urllib.error, urllib.request
from html import unescape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_prompt import ROOT, person_file, roster  # noqa: E402

UA = "ballot-buddy-research (claude)"
OUT = ROOT / "buddy" / "research" / "batches" / "dig"
MAX_BYTES = 30_000_000
MAX_DOCS = 6
MAX_CHARS = 60_000
MAX_TESTIMONY = 60      # pages of one witness
# What counts as a primary record: a filed document, a court or government site. News and opinion stay out: the weighing already reads those.
PRIMARY = re.compile(r"\.pdf(\?|$)|courtlistener\.com|govinfo\.gov|supremecourt\.gov|uscourts\.gov|justice\.gov|sec\.gov|\.gov/|documentcloud\.org|case_docs", re.I)
SKIP = re.compile(r"fec\.gov/data|facebook|twitter|x\.com|instagram|youtube|\.(png|jpe?g|gif|svg|css|js)(\?|$)", re.I)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=120) as r:
        if int(r.headers.get("content-length") or 0) > MAX_BYTES:
            raise ValueError("too large")
        return r.read(MAX_BYTES + 1)


def links(page, base):
    host = re.match(r"https?://[^/]+", base).group(0)
    found = []
    for u in re.findall(r'href="([^"#]+)"', page):
        u = unescape(u)
        u = host + u if u.startswith("/") else u
        if u.startswith("http") and PRIMARY.search(u) and not SKIP.search(u) and u not in found:
            found.append(u)
    return found


def pdf_pages(data, surname):
    """Pages naming the person, each with the two after it. Testimony runs on without repeating the witness's name, so a page that calls them as a witness keeps going until they're excused."""
    import fitz
    with fitz.open(stream=data, filetype="pdf") as d:
        pages = [p.get_text() for p in d]
    hits = [i for i, t in enumerate(pages) if re.search(rf"\b{re.escape(surname)}\b", t, re.I)]
    keep = {j for i in hits for j in (i, i + 1, i + 2) if j < len(pages)}
    for i in hits:
        if re.search(r"called\s+as\s+a\s+witness|duly\s+(sworn|affirmed)", pages[i], re.I):
            for j in range(i, min(i + MAX_TESTIMONY, len(pages))):
                keep.add(j)
                if re.search(r"witness\s+excused|you\s+are\s+excused|step\s+down", pages[j], re.I):
                    break
    keep = sorted(keep)
    return len(pages), hits, [(j + 1, re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", pages[j]))) for j in keep]


def main():
    st, names = sys.argv[1], sys.argv[2].split(",")
    OUT.mkdir(parents=True, exist_ok=True)
    for p in roster(st):
        if p["name"] not in names:
            continue
        pf = person_file(p)
        surname = re.sub(r"\([^)]*\)|\"[^\"]*\"", " ", p["name"]).replace(",", " ").split()
        surname = [x for x in surname if x.lower().rstrip(".") not in {"jr", "sr", "ii", "iii", "iv"}][-1]
        f = ROOT / "ballot" / "inputs" / st / "weighed" / f"{pf}.json"
        w = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"items": []}
        cited = [u for it in w["items"] for u in it.get("urls") or []]
        docs, seen, failed = [], set(), []
        for u in cited:
            if PRIMARY.search(u):
                docs.append(u)
            try:
                docs += links(get(u).decode("utf-8", "replace"), u)
            except (urllib.error.URLError, ValueError, TimeoutError) as e:
                failed.append(f"{u}: {str(e)[:60]}")
        out, used = [], 0
        for u in docs:
            if u in seen or len(out) >= MAX_DOCS or used >= MAX_CHARS:
                continue
            seen.add(u)
            try:
                data = get(u)
            except (urllib.error.URLError, ValueError, TimeoutError) as e:
                failed.append(f"{u}: {str(e)[:60]}")
                continue
            if data[:4] != b"%PDF":
                continue
            total, hits, kept = pdf_pages(data, surname)
            if not hits:
                continue
            text, shown = "", []
            for n, t in kept:
                if used + len(text) + len(t) > MAX_CHARS:
                    break
                text += f"\n[PDF page {n}]\n{t}"
                shown.append(n)
            used += len(text)
            out.append({"url": u, "pages_in_file": total, "pages_naming_them": len(hits), "pages_kept": shown, "cut_short": len(shown) < len(kept), "text": text})
        (OUT / f"{st}__{pf}.json").write_text(json.dumps({"name": p["name"], "records": out, "failed": failed}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{p['name']}: {len(cited)} cited pages, {len(seen)} candidate records, {len(out)} naming them, {sum(len(x['pages_kept']) for x in out)} pages kept, {used} characters. Refused or failed: {failed or 'none'}")


if __name__ == "__main__":
    main()
