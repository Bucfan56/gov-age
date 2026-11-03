"""Match every candidate name against the full text of every alexjoneslive.com article (from the site's public WordPress feed)."""
import glob, html, json, re
from pathlib import Path
SP = Path(__file__).parent
names = json.loads((SP / "cand_names.json").read_text(encoding="utf-8"))
posts = {}
for f in glob.glob(str(SP / "ajtext" / "p*.json")):
    for p in json.loads(Path(f).read_text(encoding="utf-8")):
        posts[p["id"]] = p
def plain(h):
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", h or "", flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()
FL = re.compile(r"\bFlorida\b|\bFla\.|\bTallahassee\b|\bTampa\b|\bMiami\b|\bOrlando\b|\bSarasota\b|\bBradenton\b|\bManatee\b|\bJacksonville\b")
SURNAME_ONLY = {"Byron Donalds": "Donalds", "James Uthmeier": "Uthmeier", "James Fishback": "Fishback"}
pats = {}
for n in names:
    parts = re.sub(r'"[^"]*"|\([^)]*\)', " ", n).split()
    parts = [p for p in parts if p.rstrip(".,") not in ("Jr", "Sr", "II", "III", "IV")]
    if len(parts) < 2: continue
    first, last = re.escape(parts[0].rstrip(",")), re.escape(parts[-1].rstrip(","))
    pats[n] = re.compile(rf"\b{first}(?:\s+[A-Z]\.|\s+\"?[A-Z][a-z]+\"?)?\s+{last}\b" + (rf"|\b{SURNAME_ONLY[n]}\b" if n in SURNAME_ONLY else ""))
hits, cnt = {}, 0
for p in posts.values():
    title = plain(p["title"]["rendered"]); body = plain(p["content"]["rendered"]); txt = title + " . " + body
    if not FL.search(txt): continue
    for n, rx in pats.items():
        m = rx.search(txt)
        if not m: continue
        a = txt.rfind(". ", 0, m.start()) + 2; b = txt.find(". ", m.end())
        snip = txt[max(a, m.start() - 220): (b + 1 if b != -1 else m.end() + 220)][:360]
        hits.setdefault(n, []).append({"date": p["date"][:10], "title": title, "desc": snip, "url": p["link"], "where": "title" if rx.search(title) else "text"})
        cnt += 1
for v in hits.values(): v.sort(key=lambda x: x["date"], reverse=True)
dates = sorted(p["date"][:10] for p in posts.values())
json.dump({"posts": len(posts), "range": [dates[0][:7], dates[-1]], "hits": hits}, open(SP / "aj_text_hits.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("posts", len(posts), dates[0], dates[-1], "| matches", cnt, "| candidates", len(hits))
for n, v in sorted(hits.items(), key=lambda x: -len(x[1])):
    print(f"{n}: {len(v)} ({sum(1 for x in v if x['where']=='text')} text-only)")
