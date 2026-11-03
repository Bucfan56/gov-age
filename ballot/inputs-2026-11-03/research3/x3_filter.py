"""Turn the raw X sweep (x3_raw.json, read in the owner's logged-in browser) into x3_hits.json for merge_sources3.py.
Hand review dropped: same-name strangers, AI-bot answers, and pre-2025 posts from accounts other than the owner's 13."""
import json, sys
from pathlib import Path

SP = Path(__file__).parent
raw = json.loads((SP / "x3_raw.json").read_text(encoding="utf-8"))
MINE = {h.lower() for h in "jamesfishback RealAlexJones alexstein99 OwenShroyer1776 OldWorldFL IanCarrollShow RealCandaceO realstewpeters StewPetersNet RyLiberty rexjonesnewz jakeshieldsajj MyronGainesX".split()}
# every post found for these was about someone else with the same name
STRANGERS = {'Charles "Rick" Richards', "Elizabeth Holmes", "Jackie Green", "Jacob Guerrero", "Stephanie Leonard", "James Batley",
             "Hunter Stone", "Zach Funkhouser", "Angie Boone", "Patricia Gonzalez"}
SKIP_HANDLES = {"grok"}
SKIP_URLS = {"https://x.com/23TylerDavis1/status/", "https://x.com/socialistdogmom/status/"}

hits, kept, dropped = {}, 0, 0
for name, posts in raw["hits"].items():
    for p in posts:
        mine = p["handle"].lower() in MINE
        bad = (name in STRANGERS or p["handle"].lower() in SKIP_HANDLES or any(p["url"].startswith(u) for u in SKIP_URLS)
               or (not mine and p.get("date", "") < "2025-01-01"))
        if bad:
            dropped += 1
            continue
        hits.setdefault(name, []).append(p)
        kept += 1

failed = sys.argv[1:]  # names whose searches X refused, if any
text = ("Searched X for all 437 candidates with your login: every post from your 13 accounts that names a candidate, "
        "plus X-wide searches pairing each name with Florida election words. Posts about other people with the same name were removed by hand")
if failed:
    text += f". X refused the searches for {len(failed)} candidates: " + ", ".join(failed)
json.dump({"hits": hits, "coverage": {"status": "partial" if failed else "full", "text": text}},
          open(SP / "x3_hits.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("kept", kept, "dropped", dropped, "candidates", len(hits))
