"""Round 3: full reads of the Owen Shroyer and Alex Jones Rumble channels, the full X sweep (x3_hits.json if present),
coverage rows rewritten so nothing points the reader at a button. Idempotent."""
import html, json, re
from pathlib import Path

SP = Path(__file__).parent
INP = Path(r"F:\Claude Code\politics-sesh\ballot\inputs-2026-11-03")
sw = json.loads((INP / "sweep_owner.json").read_text(encoding="utf-8"))


def fix(t):
    # earlier reads lost curly quotes as U+FFFD; between letters it was an apostrophe, elsewhere a double quote
    t = re.sub(r"(?<=\w)\ufffd(?=\w)", "’", t or "")
    return t.replace("\ufffd", '"')


for v in sw["hits"].values():
    for x in v:
        x["title"] = fix(x.get("title"))
        x["says"] = fix(x.get("says"))


def add(name, items, cap):
    have = {x["url"] for x in sw["hits"].get(name, [])}
    new = [x for x in items if x["url"] not in have]
    mine = sum(1 for x in sw["hits"].get(name, []) if x["source"].endswith(" on X"))
    if cap is not None:
        new = new[:max(0, cap - mine)]
    if new:
        sw["hits"].setdefault(name, []).extend(new)
    return len(new)


r3 = json.loads((SP / "rumble3_hits.json").read_text(encoding="utf-8"))
for n, v in r3["hits"].items():
    add(n, v, None)

RETRACT_URL = "https://x.com/jamesfishback/status/2115294763725238324"
RETRACT_NOTE = "Fishback publicly retracted this claim on Oct 28, 2026 and apologized, saying he accepts the DOJ's statement that neither Donalds nor Cory Mills is under investigation."
RETRACTED = {"https://x.com/jamesfishback/status/2085438648074322189",
             "https://www.alexjoneslive.com/2026/08/06/live-soon-james-fishback-reveals-damning-evidence-supposedly-implicating-rep-byron-donalds-in-felony-crime/",
             "https://www.alexjoneslive.com/2026/08/05/florida-gov-candidate-fishback-claims-he-has-damning-evidence-implicating-opponent-rep-byron-donalds-in-felony/"}
sw["notes"] = {u: RETRACT_NOTE for u in RETRACTED}
bd = sw["hits"].setdefault("Byron Donalds", [])
if not any(x["url"] == RETRACT_URL for x in bd):
    bd.insert(0, {"source": "@jamesfishback on X", "date": "2026-10-28", "url": RETRACT_URL, "pin": True,
                  "title": "“In early August, I made a terrible mistake by claiming that Byron Donalds and Cory Mills were under federal investigation… I accept the DOJ’s public statement that neither man is under investigation.”",
                  "says": "Fishback retracts his August claim about Donalds and apologizes to him."})
for x in bd:
    if x["url"] == RETRACT_URL:
        x["pin"] = True

aj = json.loads((SP / "aj_hits.json").read_text(encoding="utf-8"))
for n, v in aj["hits"].items():
    add(n, [{"source": "Alex Jones Live (alexjoneslive.com)", "title": html.unescape(x["title"]), "says": html.unescape(x["desc"]),
             "date": x["date"], "url": x["url"]} for x in v], None)
for v in sw["hits"].values():
    for x in v:
        if x["url"] in RETRACTED:
            x["says"] = RETRACT_NOTE

MINE = {h.lower() for h in "jamesfishback RealAlexJones alexstein99 OwenShroyer1776 OldWorldFL IanCarrollShow RealCandaceO realstewpeters StewPetersNet RyLiberty rexjonesnewz jakeshieldsajj MyronGainesX".split()}
nx = 0
xs = SP / "x3_hits.json"
if xs.exists():
    xh = json.loads(xs.read_text(encoding="utf-8"))
    for n, v in xh["hits"].items():
        v = sorted(v, key=lambda x: (x["handle"].lower() not in MINE, "".join(chr(255 - ord(c)) for c in x.get("date", ""))))
        items = [{"source": f"@{x['handle']} on X", "title": fix(x["text"])[:280], "says": "", "date": x.get("date", ""), "url": x["url"]} for x in v if x.get("url") and x.get("text")]
        nx += add(n, items, 8)

rg = r3["range"]
cov = {
    "rumble.com/TheAlexJonesShowLive": ["rumble.com/c/TheAlexJonesShowLive", "full", f"All {rg['TheAlexJonesShowLive'][0]:,} videos on the channel ({rg['TheAlexJonesShowLive'][1][:7]} to {rg['TheAlexJonesShowLive'][2]}): titles and tags matched to every name, plus a Rumble search for every name"],
    "rumble.com/Owen": ["rumble.com/c/Owen", "full", f"All {rg['Owen'][0]:,} videos on the channel ({rg['Owen'][1][:7]} to {rg['Owen'][2]}): titles and tags matched to every name, plus a Rumble search for every name"],
    "alexjoneslive.com": ["alexjoneslive.com", aj.get("status", "partial"), aj.get("text", f"All {aj['posts']:,} articles ({aj['range'][0]} to {aj['range'][1]}): every headline matched to every name. The text inside the articles was not searched; Alex Jones is also covered through his full Rumble channel and @RealAlexJones on X")],
}
if xs.exists():
    xc = xh.get("coverage") or {}
    cov["X: your 13 accounts and X in general"] = ["X: your 13 accounts and X in general", xc.get("status", "full"), xc.get("text", "")]
sw["coverage"] = [cov.get(c[0], c) for c in sw["coverage"]]
for old, new in [("rumble.com/TheAlexJonesShowLive", "rumble.com/c/TheAlexJonesShowLive"), ("rumble.com/Owen", "rumble.com/c/Owen")]:
    sw["sites"] = [new if s == old else s for s in sw["sites"]]
(INP / "sweep_owner.json").write_text(json.dumps(sw, ensure_ascii=False, indent=1), encoding="utf-8")
print("candidates with hits:", len(sw["hits"]), "| X posts added:", nx, "| leftover U+FFFD:", json.dumps(sw, ensure_ascii=False).count("\ufffd"))
