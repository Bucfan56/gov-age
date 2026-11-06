"""Portraits and social links, by script, for no AI cost. The collected page text has no links or images, so this reads each person's pages once more.
Run: py buddy/research/links.py AL NJ CA NC           (picks up where it stopped)
     py buddy/research/links.py audit AL NJ CA NC     (reads what's collected and lists pages that may be about someone else; fetches nothing)
Writes buddy/research/pages/<ST>/_links.json, git-ignored: {person file: {"photo": {"url", "credit"}, "social": {...}}}. batch.py copies these into the research files."""
import json, re, sys, time, urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gather import OUT, fetch, office_words, wiki_json  # noqa: E402
from make_prompt import STATE_NAMES, person_file, roster  # noqa: E402

KINDS = {"facebook": "facebook", "instagram": "instagram", "x": "x", "twitter": "x"}
RANK = ("campaign", "official", "personal")


def infobox(raw):
    """Only the person's own box at the top of the page. Race tables further down carry other people's photos."""
    i = raw.find('class="infobox person"')
    return raw[i: i + 12000] if i >= 0 else ""


def from_ballotpedia(raw):
    box = infobox(raw)
    photo = None
    for tag in re.findall(r"<img\b[^>]*>", box):
        src = re.search(r'src="(https?://[^"]+)"', tag)
        if src and "SubmitPhoto" not in src.group(1) and "Placeholder" not in tag:
            photo = {"url": src.group(1), "credit": "Ballotpedia"}
            break
    found = {}
    for url, rank, kind in re.findall(r'<a\b[^>]*href="(https?://[^"]+)"[^>]*>\s*(Campaign|Official|Personal)\s+(website|Facebook|Instagram|X|Twitter)\s*</a>', box, re.I):
        kind, rank = kind.lower(), RANK.index(rank.lower())
        key = "website" if kind == "website" else KINDS[kind]
        if key not in found or rank < found[key][0]:
            found[key] = (rank, url)
    return photo, {k: v[1] for k, v in found.items()}


def wiki_portrait(url):
    """The lead picture of their Wikipedia article, when it has one on Wikimedia Commons. Prefer this: it's larger and openly licensed."""
    title = urllib.parse.unquote(url.rsplit("/", 1)[1])
    q = "https://en.wikipedia.org/w/api.php?format=json&action=query&prop=pageimages&piprop=original&titles=" + urllib.parse.quote(title)
    page = next(iter(wiki_json(q)["query"]["pages"].values()))
    src = (page.get("original") or {}).get("source", "").split("?")[0]
    return {"url": src, "credit": "Wikimedia Commons"} if "/commons/" in src and re.search(r"\.(jpe?g|png)$", src, re.I) else None


def collect(states):
    for st in states:
        out = OUT / st / "_links.json"
        links = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
        links = {k: v for k, v in links.items() if v.get("social")}      # read again if no social link came back: that run may have met a bot check
        people, photos, socials = roster(st), 0, 0
        try:
            read_state(st, people, links, out)
        finally:
            out.write_text(json.dumps(links, ensure_ascii=False), encoding="utf-8")
        photos = sum(bool(v.get("photo")) for v in links.values())
        socials = sum(bool(v.get("social")) for v in links.values())
        print(st, len(links), "of", len(people), "read,", photos, "photos,", socials, "with social links", flush=True)


def read_state(st, people, links, out):
    for n, p in enumerate(people, 1):
        name = person_file(p)
        d = json.loads((OUT / st / f"{name}.json").read_text(encoding="utf-8"))
        if not links.get(name) and d["sources"]:      # new pages since the last run count too
            entry, bp = {}, next((s for s in d["sources"] if s["kind"] == "ballotpedia"), None)
            try:
                if bp:
                    photo, social = from_ballotpedia(fetch(bp["url"]))
                    entry = {"photo": photo, "social": social}
                    time.sleep(2)
                wiki = next((s for s in d["sources"] if s["kind"] == "wikipedia"), None)
                if wiki:
                    entry["photo"] = wiki_portrait(wiki["url"]) or entry.get("photo")
                    time.sleep(1)
            except Exception as e:      # left out of the file on purpose, so the next run tries this person again
                print("  could not read", st, p["name"], str(e)[:80], flush=True)
                continue
            links[name] = entry
            if n % 10 == 0:
                out.write_text(json.dumps(links, ensure_ascii=False), encoding="utf-8")


def audit(states):
    total = flagged = 0
    for st in states:
        for p in roster(st):
            d = json.loads((OUT / st / f"{person_file(p)}.json").read_text(encoding="utf-8"))
            for s in d["sources"]:
                total += 1
                surname = p["name"].replace(",", " ").split()[-1 if p["name"].split()[-1].lower().strip(".") not in ("jr", "sr", "ii", "iii", "iv") else -2]
                has_name = re.search(re.escape(surname), s["text"], re.I)
                has_office = any(re.search(w, s["text"], re.I) for w in office_words(p))
                if not has_name or (s["kind"] == "ballotpedia" and not has_office):
                    flagged += 1
                    print(f"{st} {p['name']} ({p['race']}) {s['kind']} {s['url']} name:{bool(has_name)} office:{bool(has_office)} | {s['text'][:90]!r}")
    print(f"{flagged} of {total} pages to look at")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:]
    states = [a for a in args if a in STATE_NAMES]
    (audit if "audit" in args else collect)(states)
