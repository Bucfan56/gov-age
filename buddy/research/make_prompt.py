"""Fill PROMPT.md for one person on a state's roster, and shared helpers for the research runner.
Print one prompt: py buddy/research/make_prompt.py AL "Tommy Tuberville"
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
STATE_NAMES = {"AL": "Alabama", "NJ": "New Jersey", "CA": "California", "NC": "North Carolina", "FL": "Florida"}
LEG = ("Job is writing law and the state budget. High (75-95): prior legislative service or chamber leadership (a committee chair doesn't add), "
       "plus law, policy or budget careers. Middle (45-70): local elected office, lawyers, policy staff, business owners and managers. "
       "Low (10-40): student or first-time with no work record, unrelated occupation. Missing info = null.")
CONGRESS = ("Job is lawmaking, oversight, budgeting and constituent service in Washington. High (75-95): prior legislative or executive office, "
            "law, judicial or prosecutorial background, deep policy or budget experience. Middle (45-70): state legislators, senior congressional or "
            "agency staff, local elected office, executive or business management. Low (10-40): no governing experience, unrelated occupation, "
            "first-time candidate with a thin record. Missing bio = null.")
GOV = ("Chief executive of a state government: management of large organizations, budgets, emergency response, appointments, vetoes. High: prior executive "
       "office (governor, big-city mayor, agency head, statewide office), long legislative leadership, large-organization management. Middle: legislators, "
       "lawyers, entrepreneurs with real payroll and budget experience. Low: no governing or managerial experience.")
AG = ("Chief legal officer: litigation, consumer protection, criminal appeals, opinions. High: years as a prosecutor, judge, state or federal litigator or senior "
      "government counsel, in good standing with the state bar. Middle: licensed lawyer with transferable government or legislative legal work. Low: no law license or legal practice.")
STATEWIDE = ("Runs a statewide office. High (75-95): prior statewide or senior executive office, or a long career in this office's own field. Middle (45-70): legislators, "
             "local elected office, senior managers with real budget experience. Low (10-40): no governing, managerial or field experience. Missing info = null.")


def rubric(key):
    if key == "gov" or key == "ltgov":
        return GOV
    if key == "ag":
        return AG
    if key == "ussen" or key.startswith("ushouse"):
        return CONGRESS
    if key.startswith(("stsen", "sthouse")):
        return LEG
    return STATEWIDE


def platform(st):
    t = json.loads((ROOT / "ballot" / "states" / "platform_template.json").read_text(encoding="utf-8"))
    name, people = STATE_NAMES[st], t["people"][st]
    fill = lambda s: s.replace("{S}", name).replace("{P}", people)
    return {"who": t["who"], "summary": fill(t["summary"]),
            "planks": [{k: fill(v) for k, v in p.items()} for p in t["planks"]]}


def prompt_for(person):
    st = person["st"]
    planks = "\n".join(f"- {p['id']}: {p['title']}. {p['promise']} Counts for: {p['tells_for']} Counts against: {p['tells_against']}"
                       for p in platform(st)["planks"])
    result = ("Won" if person["won"] else "Lost or not yet decided") + f", {person['pc']}% of the vote" + (" (unopposed)" if person.get("unopposed") else "")
    txt = (ROOT / "buddy" / "research" / "PROMPT.md").read_text(encoding="utf-8")
    for k, v in {"{{STATE}}": STATE_NAMES[st], "{{RUBRIC}}": rubric(person["key"]), "{{PLANKS}}": planks, "{{NAME}}": person["name"],
                 "{{RACE}}": person["race"], "{{PARTY}}": person["party"] or "none listed", "{{RESULT}}": result}.items():
        txt = txt.replace(k, v)
    return txt


def roster(st):
    # Florida's comes from its built cards (florida.py extract), and stays out of the results folder the site serves.
    f = ROOT / "ballot" / "inputs" / "FL" / "roster.json" if st == "FL" else ROOT / "buddy" / "results" / "roster" / f"{st}.json"
    return json.loads(f.read_text(encoding="utf-8"))


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


_shared = {}


def shares_name(person):
    st = person["st"]
    if st not in _shared:
        seen = [slug(p["name"]) for p in roster(st)]
        _shared[st] = {n for n in seen if seen.count(n) > 1}
    return slug(person["name"]) in _shared[st]


def person_file(person):
    """The file name for a person's pages, research and photo. People in one state who share a name get their race added, so one never overwrites the other."""
    return f"{slug(person['name'])}-{person['key']}" if shares_name(person) else slug(person["name"])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    st, name = sys.argv[1], sys.argv[2]
    hit = [p for p in roster(st) if p["name"] == name]
    if len(hit) != 1:
        raise SystemExit(f"{len(hit)} people named {name} on the {st} roster")
    print(prompt_for(hit[0]))
