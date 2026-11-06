"""Florida under the owner's score rules. Florida's cards were built before the other states' pipeline, so this reads them straight from the built site.
  py buddy/research/florida.py extract          writes ballot/inputs/FL/roster.json and research/<person file>.json, so aipac_ties.py, us_attendance.py and weigh.py can run on Florida
  py buddy/research/florida.py compare <folder with the old build> <folder with the new build> <out>    every card's score in both builds, written to <out>
No AI and no network here."""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_prompt import ROOT, person_file, roster  # noqa: E402

INPUTS = ROOT / "ballot" / "inputs" / "FL"
PAGE = ROOT / "ballot.html"
MARK = "const D = "


def page_data():
    t = PAGE.read_text(encoding="utf-8")
    return json.JSONDecoder().raw_decode(t[t.index(MARK) + len(MARK):])[0]


def race_lists():
    """Every list of races the site serves: the statewide ones inside the page, and one file per district or county."""
    yield page_data()["races"]
    for f in sorted((ROOT / "fl").glob("*.json")):
        yield json.loads(f.read_text(encoding="utf-8"))["races"]


def key_for(r):
    if r.get("group") == "federal" and (r.get("where") or {}).get("cd"):
        return f"ushouse-{r['where']['cd']}"
    return "ussen" if r["id"] == "senate" else r["id"]


def extract():
    if any(c["score"].get("before") is not None for races in race_lists() for r in races if r.get("kind") == "race" for c in r["cands"]):
        raise SystemExit("These cards already have the rules on them, so their item numbers no longer match the original research.")
    people = []
    for races in race_lists():
        for r in races:
            if r.get("kind") != "race":
                continue
            lvl = "fed" if r.get("group") == "federal" else "state"
            for c in r["cands"]:
                people.append({"st": "FL", "key": key_for(r), "race": r["title"], "lvl": lvl, "name": c["name"], "party": c.get("party") or "", "inc": bool(c.get("incumbent")), "unopposed": False, "won": None, "pc": None, "votes": None})
    INPUTS.mkdir(parents=True, exist_ok=True)
    (INPUTS / "roster.json").write_text(json.dumps(people, ensure_ascii=False, indent=1), encoding="utf-8")
    research = INPUTS / "research"
    research.mkdir(exist_ok=True)
    by_race = {(p["race"], p["name"]): p for p in roster("FL")}
    n = items = 0
    for races in race_lists():
        for r in races:
            for c in r.get("cands") or [] if r.get("kind") == "race" else []:
                found = {"controversies": c.get("controversies") or [], "foreign_ties": c.get("foreign_ties") or []}
                if found["controversies"] or found["foreign_ties"]:
                    (research / f"{person_file(by_race[(r['title'], c['name'])])}.json").write_text(json.dumps(found, ensure_ascii=False, indent=1), encoding="utf-8")
                    n += 1
                    items += len(found["controversies"]) + len(found["foreign_ties"])
    print(f"{len(people)} people on the roster, {n} with something to weigh, {items} items")


def cards_in(root):
    t = (Path(root) / "ballot.html").read_text(encoding="utf-8")
    races = list(json.JSONDecoder().raw_decode(t[t.index(MARK) + len(MARK):])[0]["races"])
    for f in sorted((Path(root) / "fl").glob("*.json")):
        races += json.loads(f.read_text(encoding="utf-8"))["races"]
    return [r for r in races if r.get("kind") == "race"]


def compare(before, after, out):
    """Every card in two builds. `before` is a saved copy of what's live: ballot.html and fl/."""
    old = {r["title"]: r for r in cards_in(before)}
    rows, flips = [], []
    for r in cards_in(after):
        was = {c["name"]: c for c in old[r["title"]]["cands"]}
        if sorted(was) != sorted(c["name"] for c in r["cands"]):
            raise SystemExit(f"{r['title']}: the two builds list different people")
        tops = [next((c["name"] for c in cands if c.get("rank") == 1), None) for cands in (old[r["title"]]["cands"], r["cands"])]
        if tops[0] != tops[1]:
            flips.append({"race": r["title"], "was": tops[0], "now": tops[1]})
        for c in r["cands"]:
            rows.append({"race": r["title"], "name": c["name"], "party": c.get("party"), "before": was[c["name"]]["score"]["overall"], "after": c["score"]["overall"],
                         "rule_points": sum(x.get("points") or 0 for x in c.get("controversies") or []),
                         "entries": [{"text": x["text"], "url": x.get("url"), "points": x.get("points"), "status": x.get("status")} for x in c.get("controversies") or [] if x.get("points") or x.get("status") == "allegation"]})
    Path(out).write_text(json.dumps({"rows": rows, "top_changed": flips}, ensure_ascii=False, indent=1), encoding="utf-8")
    moved = [x for x in rows if x["before"] != x["after"]]
    print(f"{len(rows)} cards, {len(moved)} scores moved, {len(flips)} races with a new top pick")
    for x in sorted(moved, key=lambda x: (x["after"] or 0) - (x["before"] or 0)):
        print(f"  {x['name']} ({x['race']}): {x['before']} to {x['after']}")
    for x in flips:
        print(f"  top pick in {x['race']}: {x['was']} to {x['now']}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.argv[1] == "extract":
        extract()
    elif sys.argv[1] == "compare":
        compare(*sys.argv[2:5])
    else:
        raise SystemExit(__doc__)
