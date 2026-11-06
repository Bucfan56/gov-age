"""Collect the free public pages for each person on a state's roster, so the AI reads them instead of paying to search.
Run: py buddy/research/gather.py AL NJ CA NC           (everyone; picks up where it stopped, and retries what a site refused last time)
     py buddy/research/gather.py AL --only "Joan Friedlander"
     py buddy/research/gather.py clean AL NJ CA NC     (runs the page checks on what's saved, says what it dropped; fetches nothing)
Writes buddy/research/pages/<ST>/<person file>.json, git-ignored. Waits 2 seconds between Ballotpedia requests, as its robots.txt asks."""
import html, json, re, sys, time, unicodedata, urllib.error, urllib.parse, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_prompt import person_file, shares_name  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "buddy" / "research" / "pages"
NAMES = {"AL": "Alabama", "NJ": "New Jersey", "CA": "California", "NC": "North Carolina"}
UA = "Mozilla/5.0 (compatible; BallotBuddyResearch/1.0; +https://ballotbuddy.app; voter guide)"
CAP = {"ballotpedia": 40000, "wikipedia": 20000, "campaign": 12000}
SKIP_HOSTS = ("ballotpedia.org", "wikipedia.org", "facebook.com", "twitter.com", "x.com", "instagram.com", "youtube.com", "linkedin.com")
# Two people in one state with the same name: the race pages can't tell them apart, so each one's page is named here (Ballotpedia page, may use Wikipedia).
SHARED_NAME = {("CA", "ushouse-42"): ("https://ballotpedia.org/Robert_Garcia_(California)", True),
               ("CA", "sthouse-50"): ("https://ballotpedia.org/Robert_Garcia_(California_state_representative)", False)}
# Pages a person read and found to be about someone else with the same name, in their un-escaped form. Collection skips them.
WRONG_PAGES = {"https://ballotpedia.org/Bob_Smith_(California)"}      # a Bakersfield city councilman, not the U.S. House candidate
SPAM = re.compile(r"slot\s*gacor|situs\s+(toto|slot|judi)|bandar\s+(toto|slot|togel)|agen\s+slot", re.I)
POLITICS = re.compile(r"politic|represent|senat|assembly|legislat|congress|governor|council|mayor|candidate|commissioner|supervisor|attorney general|treasurer|secretary of state", re.I)


class Blocked(SystemExit):
    """A site answered with its bot check. Stop the whole run: never push past it, and never read its page as if it were the person's."""


def fetch(url, timeout=30):
    url = urllib.parse.quote(url, safe=":/?&=%#,()_-.~+")      # a page name can hold an accent, which can't be sent as is
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read(6000000).decode("utf-8", "replace")
    if r.status == 202 or "awsWafCookieDomainList" in raw[:3000]:
        raise Blocked(f"STOPPED: {urllib.parse.urlparse(url).netloc} answered with its bot check at {url[:90]}. Wait, go slower, and run one process at a time. Don't try to get past it.")
    return raw


def to_text(raw):
    raw = re.sub(r"(?is)<(script|style|noscript|nav|footer|svg)\b.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<(br|/p|/div|/li|/tr|/h\d)\b[^>]*>", "\n", raw)
    txt = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    txt = re.sub(r"[ \t\r\f\v]+", " ", txt)
    return re.sub(r"\s*\n\s*(\n\s*)*", "\n", txt).strip()


def clean_text(text):
    """A site can link a PDF as its about page, and a hacked site can hide a gambling ad inside real text. Neither is the person's words, and nothing after the ad can be trusted."""
    text = re.sub(r"%PDF-.*?(%%EOF|\Z)", " ", text, flags=re.S)
    spam = SPAM.search(text)
    return text[:spam.start()].rsplit("\n", 1)[0] if spam else text


def office_words(p):
    """What a page about this person should say. Same names are common, so a page that names neither the district nor the office gets a human look."""
    k = p["key"]
    m = re.search(r"-(\d+)$", k)
    if m:
        return [rf"District {int(m.group(1))}\b", rf"\b{int(m.group(1))}(st|nd|rd|th)\b"]
    return [re.escape(w) for w in re.findall(r"[A-Za-z]{4,}", p["race"])] or [re.escape(p["race"])]


def page_problem(s, person):
    """Why a collected page can't be used, or None. Wikipedia only needs the state somewhere to get this far, and that let in a Chief Justice, an actor and a geologist."""
    if urllib.parse.unquote(s["url"]) in WRONG_PAGES:
        return "checked by hand: someone else"
    text = clean_text(s["text"])
    if s["kind"] == "campaign":
        if SPAM.search(s["text"][:300]):
            return "the site has been taken over by gambling spam"
        if sum(c == "\ufffd" or (ord(c) < 32 and c not in "\n\t\r") for c in text) > len(text) * 0.02:
            return "unreadable"
        if len(text.strip()) < 200:
            return "almost nothing on the page"
    if s["kind"] == "wikipedia":
        lead = text[:600]
        if re.search(r"may refer to", text[:300], re.I):
            return "a list of people with this name"
        if not POLITICS.search(lead):
            return "not about a person in politics"
        if NAMES[person["st"]].lower() not in lead.lower() and not any(re.search(w, text, re.I) for w in office_words(person)):
            return "names neither the state up front nor the office"
    return None


def norm(name):
    name = "".join(c for c in unicodedata.normalize("NFKD", name) if not unicodedata.combining(c))      # Barragán and Barragan are one person
    name = re.sub(r"\b(jr|sr|ii|iii|iv|mr|mrs|ms|dr|hon)\b\.?", "", re.sub(r"\([^)]*\)", "", name.lower())).strip()
    return re.sub(r"[^a-z ]", "", re.sub(r"\s+[a-z]\.?\s+", " ", name.replace(",", " "))).split()


def race_index(st):
    """Ballotpedia's 2026 race pages link every candidate's exact page. Build name -> page once per state, so same-name people resolve right."""
    f = OUT / st / "_index.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    state = NAMES[st]
    pages = [f"United_States_House_of_Representatives_elections_in_{state}", f"United_States_Senate_election_in_{state}", f"{state}_gubernatorial_election",
             f"{state}_State_Senate_elections", f"{state}_House_of_Representatives_elections", f"{state}_State_Assembly_elections"]
    index = {}
    for p in pages:
        try:
            raw = fetch("https://ballotpedia.org/" + urllib.parse.quote(p.replace(" ", "_") + ",_2026"))
        except Exception as e:
            print("  race page", p, str(e)[:60], flush=True)
            time.sleep(2)
            continue
        for path, text in re.findall(r'<a\b[^>]*href="(?:https://ballotpedia\.org)?/([^"#:?/]+)"[^>]*>\s*([A-Z][^<]{3,45}?)\s*</a>', raw):
            words = norm(html.unescape(text))
            if 2 <= len(words) <= 4 and "_" in path and "," not in path and "election" not in path.lower():
                index.setdefault(" ".join(words), "https://ballotpedia.org/" + path)
        time.sleep(2)
    if not index:
        raise SystemExit(f"{st}: the race pages gave no names, so nothing was saved")
    (OUT / st).mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    print(st, "race pages list", len(index), "names", flush=True)
    return index


def spellings(name):
    """A ballot name can carry a nickname or an initial the pages leave out: 'Donald P. (Don) Wagner' is also Don Wagner and Donald Wagner."""
    nick = re.search(r'\(([^)]+)\)|"([^"]+)"', name)
    bare = re.sub(r'\([^)]*\)|"[^"]*"', " ", name)
    bare = re.sub(r"\b[A-Z]\.?(?=\s)", " ", bare).replace(",", " ")
    words = bare.split()
    out = [name]
    if len(words) >= 2:
        out.append(f"{words[0]} {words[-1]}")
        if len(words) > 2:
            out.append(" ".join(words))
        if nick:
            out.append(f"{nick.group(1) or nick.group(2)} {words[-1]}")
    return list(dict.fromkeys(out))


def ballotpedia(name, state, index, pinned=None):
    """The page's text and its listed campaign site. A page is taken only when it names the state, and a disambiguation page is refused."""
    same_first = lambda a, b: a.startswith(b) or b.startswith(a) or a[:3] == b[:3]      # Rosie on the ballot, Rosemary on the page. The surname must match too, within this state's races.
    url = pinned
    for form in spellings(name):
        words = norm(form)
        url = url or index.get(" ".join(words)) or next((u for k, u in index.items() if k.split()[-1] == words[-1] and same_first(k.split()[0], words[0])), None)
    tries = [url] * bool(url) + [u for form in spellings(name) for plain in ["https://ballotpedia.org/" + urllib.parse.quote(form.replace(" ", "_"))]
                               for u in (plain, plain + "_" + urllib.parse.quote(f"({state})".replace(" ", "_")))]
    status = 404
    for t in tries:
        if urllib.parse.unquote(t) in WRONG_PAGES:
            continue
        try:
            raw = fetch(t)
        except urllib.error.HTTPError as e:
            status = e.code
            time.sleep(2)
            continue
        time.sleep(2)
        if re.search(r"disambiguation|may refer to", raw[:60000], re.I):
            status = "disambiguation"
            continue
        site = re.search(r'href="(https?://[^"]+)"[^>]*>\s*Campaign website', raw, re.I) or re.search(r'Campaign website.{0,200}?href="(https?://[^"]+)"', raw, re.I | re.S)
        # The vote tables are the bulk of a page and we already hold results, so they're dropped to leave room for the biography and survey.
        body = re.sub(r"(?is)<table\b(?:(?!</table>).)*?(Vote %|Total votes|Incumbents are bolded)(?:(?!</table>).)*?</table>", " ", raw)
        txt = to_text(body)
        if "From Ballotpedia" in txt:
            txt = txt.split("From Ballotpedia", 1)[1]
        txt = re.split(r"\n(?:Footnotes|See also|External links)\n", txt)[0]
        if state.lower() not in txt.lower():      # a namesake from elsewhere: keep looking
            status = "other state"
            continue
        return {"status": 200, "url": t, "kind": "ballotpedia", "text": txt[:CAP["ballotpedia"]]}, (site.group(1) if site else None)
    return {"status": status}, None


def wiki_json(url):
    """Wikipedia refuses a fast reader with a 429. Wait as long as it asks, then try again. If it still refuses, the failure is kept so the next run retries this person."""
    for wait in (10, 30, 90, None):
        try:
            return json.loads(fetch(url))
        except urllib.error.HTTPError as e:
            if e.code != 429 or wait is None:
                raise
            time.sleep(max(wait, int(e.headers.get("Retry-After") or 0)))


def wikipedia(person):
    name, state = person["name"], NAMES[person["st"]]
    api = "https://en.wikipedia.org/w/api.php?format=json&action=query&list=search&srlimit=3&srsearch=" + urllib.parse.quote(f'"{name}" {state}')
    for hit in wiki_json(api)["query"]["search"]:
        title = hit["title"]
        if not re.fullmatch(re.escape(name) + r"( \((American )?politician\)| \([^)]*politician\))?", title, re.I):
            continue
        q = "https://en.wikipedia.org/w/api.php?format=json&action=query&prop=extracts&explaintext=1&redirects=1&titles=" + urllib.parse.quote(title)
        page = next(iter(wiki_json(q)["query"]["pages"].values()))
        text = page.get("extract", "")
        found = {"status": 200, "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_")), "kind": "wikipedia", "text": text[:CAP["wikipedia"]]}
        if state.lower() in text.lower() and not page_problem(found, person):
            return found
    return None


def campaign(url):
    if any(h in urllib.parse.urlparse(url).netloc for h in SKIP_HOSTS):
        return None
    raw = fetch(url, 20)
    text = to_text(raw)
    # Add the about and issues pages when the home page links them.
    for m in list(dict.fromkeys(re.findall(r'href="([^"#?]*(?:about|issue|meet|priorit|platform|bio)[^"#?]*)"', raw, re.I)))[:2]:
        try:
            text += "\n\n" + to_text(fetch(urllib.parse.urljoin(url, m), 20))
        except Exception:
            pass
    return {"status": 200, "url": url, "kind": "campaign", "text": clean_text(text)[:CAP["campaign"]], "hacked": bool(SPAM.search(text))}


def gather(person, index):
    state, name, srcs, misses = NAMES[person["st"]], person["name"], [], {}
    site = None
    pinned, wiki_ok = SHARED_NAME.get((person["st"], person["key"]), (None, True))
    if shares_name(person) and not pinned:
        raise SystemExit(f"{name} in {person['st']} shares a name with someone else on the roster: add both to SHARED_NAME")
    try:
        bp, site = ballotpedia(name, state, index, pinned)
        if bp["status"] == 200:
            srcs.append(bp)
        else:
            misses["ballotpedia"] = bp["status"]
    except Exception as e:
        misses["ballotpedia"] = str(e)[:80]
    try:
        w = wikipedia(person) if wiki_ok else None
        if w:
            srcs.append(w)
    except Exception as e:
        misses["wikipedia"] = str(e)[:80]
    if site:
        try:
            c = campaign(site)
            why = c and page_problem(c, person)
            if why:
                misses["campaign"] = f"{site}: {why}"
            elif c:
                srcs.append(c)
        except Exception as e:
            misses["campaign"] = f"{site}: {str(e)[:60]}"
    return {"name": name, "st": person["st"], "key": person["key"], "sources": srcs, "misses": misses, "chars": sum(len(s["text"]) for s in srcs)}


def refill(d, index, person):
    """Retry what a site refused last time, keeping everything already collected."""
    if "ballotpedia" in d["misses"]:
        return gather(person, index)
    if "wikipedia" in d["misses"]:
        del d["misses"]["wikipedia"]
        try:
            w = wikipedia(person)
            if w:
                d["sources"].insert(sum(s["kind"] == "ballotpedia" for s in d["sources"]), w)
        except Exception as e:
            d["misses"]["wikipedia"] = str(e)[:80]
        d["chars"] = sum(len(s["text"]) for s in d["sources"])
        time.sleep(1)
    return d


def clean(states):
    """Run the page checks on what's already saved. A dropped Wikipedia page is retried by the next run with the stricter picker; its portrait and links are read again."""
    dropped = kept = 0
    for st in states:
        people = json.loads((ROOT / "buddy" / "results" / "roster" / f"{st}.json").read_text(encoding="utf-8"))
        links_file = OUT / st / "_links.json"
        links = json.loads(links_file.read_text(encoding="utf-8")) if links_file.exists() else {}
        for p in people:
            f = OUT / st / f"{person_file(p)}.json"
            d = json.loads(f.read_text(encoding="utf-8"))
            good = []
            for s in d["sources"]:
                why = page_problem(s, p)
                if why:
                    dropped += 1
                    print(f"{st} {p['name']} ({p['race']}) {s['kind']} {s['url']}: {why}")
                    d["misses"][s["kind"]] = why
                    if s["kind"] != "campaign":
                        links.pop(person_file(p), None)
                else:
                    kept += 1
                    s["text"] = clean_text(s["text"])
                    good.append(s)
            d["sources"], d["chars"] = good, sum(len(s["text"]) for s in good)
            f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        if links_file.exists():
            links_file.write_text(json.dumps(links, ensure_ascii=False), encoding="utf-8")
    print(f"Dropped {dropped}, kept {kept}")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:]
    only = args[args.index("--only") + 1] if "--only" in args else None
    states = [a for a in args if a in NAMES]
    if "clean" in args:
        return clean(states)
    for st in states:
        people = json.loads((ROOT / "buddy" / "results" / "roster" / f"{st}.json").read_text(encoding="utf-8"))
        (OUT / st).mkdir(parents=True, exist_ok=True)
        index = race_index(st)
        done = found = chars = 0
        for p in people:
            if only and p["name"] != only:
                continue
            f = OUT / st / f"{person_file(p)}.json"
            if f.exists() and not only:
                d = json.loads(f.read_text(encoding="utf-8"))
                if "wikipedia" in d["misses"] or "ballotpedia" in d["misses"]:
                    d = refill(d, index, p)
                    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
            else:
                d = gather(p, index)
                f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
                time.sleep(2)
            done += 1
            found += bool(d["sources"])
            chars += d["chars"]
            if only:
                print(d["name"], d["misses"], [(s["kind"], len(s["text"]), s["url"]) for s in d["sources"]])
            elif done % 25 == 0:
                print(st, done, "of", len(people), "with pages", found, "chars", chars, flush=True)
        print(st, "done", done, "with pages", found, "chars", chars, flush=True)
    still = sum("wikipedia" in json.loads(f.read_text(encoding="utf-8"))["misses"] for f in OUT.glob("*/*.json") if not f.name.startswith("_"))
    print("Wikipedia still refusing for", still, "people" + ("; run again to retry them" if still else ""), flush=True)


if __name__ == "__main__":
    main()
