"""The owner's rules for what moves a candidate's score (forms note_9360 and note_9428). No AI, no network: it reads files other steps wrote.
Every entry carries a `matter`, and one person gets one entry per matter, so the same story can't count twice. check() stops the build if it finds a repeat.
Card text states amounts, trips and records. It never says or implies anyone is bought."""
import json, re

POINTS = {"serious": -15, "medium": -8, "minor": -3}
BY_WEIGHT = {3: "serious", 2: "medium", 1: "minor"}
# Attendance and AIPAC are counted from official records for everyone, so a weighed story on either one is the same matter.
RULE_MATTERS = {"attendance": re.compile(r"\bmissed\b.*\bvotes?\b|\battendance\b|\babsen(t|ces?)\b", re.I | re.S),
                "aipac": re.compile(r"AIPAC|American Israel (Public Affairs|Education)|United Democracy Project", re.I)}
STATUS = {"against": "established", "open": "allegation", "for": "", "context": ""}
FEC_SOURCE = "https://www.fec.gov/data/committee/C00797670/"


class Repeat(Exception):
    """The same matter would count twice for one person."""


def usd(x):
    return f"${x:,.0f}"


def plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


# Passed-through money counts for one to two years only, and the window moves each year (Tyler, note_9449). Today that's 2025-26. Older money stays in its own field, uncounted.
def aipac_level(a):
    """The owner's levels (note_9428 Q2, Q3): by money through AIPAC's PAC, outside spending for them, and paid trips. A staff trip counts as minor."""
    total = sum(a["aipac_pac_gifts"].values()) + a["passed_through_aipac_pac_2026"]
    if sum(a["udp_spent_for"].values()) >= 100000 or total >= 250000:
        return "serious"
    if total >= 25000:
        return "medium"
    if total > 0 or a["aipac_trips"] or a["aipac_staff_trips"] or sum(a["udp_spent_for"].values()) > 0:
        return "minor"
    return None


def aipac_entries(a):
    out = []
    level = aipac_level(a)
    if level:
        gifts, passed, spent = sum(a["aipac_pac_gifts"].values()), a["passed_through_aipac_pac_2026"], sum(a["udp_spent_for"].values())
        bits = []
        if gifts:
            bits.append(f"{usd(gifts)} from AIPAC's PAC since 2021")
        if passed:
            bits.append(f"{usd(passed)} from individuals passed through that PAC in 2025-26")
        if spent:
            bits.append(f"{usd(spent)} spent to help them by United Democracy Project, AIPAC's super PAC, since 2021")
        if a["aipac_trips"]:
            bits.append(f"{plural(len(a['aipac_trips']), 'trip')} paid for by the American Israel Education Foundation, AIPAC's affiliate")
        if a["aipac_staff_trips"]:
            bits.append(f"{plural(len(a['aipac_staff_trips']), 'staff trip')} paid for by that foundation")
        money = gifts or passed or spent
        out.append({"matter": "aipac", "level": level, "points": POINTS[level], "text": "Federal records show " + "; ".join(bits) + ".",
                    "url": a["sources"]["money"] if money else a["sources"]["travel"], "source": "rule"})
    against = sum(a["udp_spent_against"].values())
    if against > 0:     # The owner: AIPAC spending against someone is a positive. Same scale as spending for someone, turned around.
        level = "serious" if against >= 100000 else "medium" if against >= 25000 else "minor"
        out.append({"matter": "aipac-against", "level": level, "points": -POINTS[level], "url": a["sources"]["money"], "source": "rule",
                    "text": f"Federal records show United Democracy Project, AIPAC's super PAC, spent {usd(against)} to oppose them since 2021."})
    return out


def attendance_text(a):
    run = f" Longest run of misses: {a['longest_run']}, {a['run_from']} to {a['run_to']}." if a.get("longest_run") else ""
    return f"Missed {a['missed']} of {a['roll_calls']} {a['chamber']} votes this Congress ({a['missed_pct']}%), counted from the roll calls through {a['through']}.{run}"


def attendance_entry(a):
    """More than 100 missed votes counts, whatever the reason. Under that is shown and doesn't count (note_9360 Q1)."""
    e = {"matter": "attendance", "text": attendance_text(a), "url": a["source"], "source": "rule"}
    if a["missed"] > 100:
        e.update(level="serious", points=POINTS["serious"])
    return e


def weighed_entries(w):
    """(entries, numbers of the research items this weighing answered). Stories on a rule's matter stay out, and their words are kept only for attendance."""
    out, answered = [], set()
    for i, it in enumerate(w.get("items") or []):
        if it.get("item"):
            answered.add(it["item"])
        if it["verdict"] == "leave_off":
            continue
        matter = next((m for m, rx in RULE_MATTERS.items() if rx.search(it["text"])), it.get("matter") or f"weighed-{i}")
        e = {"matter": matter, "text": it["text"], "url": (it.get("urls") or [None])[0], "status": STATUS.get(it["verdict"], ""), "source": "weighed"}
        if it["verdict"] == "against" and BY_WEIGHT.get(it.get("weight")):
            e.update(level=BY_WEIGHT[it["weight"]], points=POINTS[BY_WEIGHT[it["weight"]]])
        out.append(e)
    return out, answered


def check(name, entries):
    """Stop on any repeat among what's shown: one matter twice, one page behind two counted entries, or two entries in nearly the same words."""
    seen = {}
    for e in entries:
        if e["matter"] in seen:
            raise Repeat(f"{name}: matter {e['matter']} appears twice")
        seen[e["matter"]] = e
    words = lambda t: set(re.findall(r"[a-z]{4,}", t.lower()))
    for i, a in enumerate(entries):
        for b in entries[i + 1:]:
            if a.get("points") and b.get("points") and a.get("url") and a["url"] == b["url"] and a["source"] == b["source"] == "weighed":
                raise Repeat(f"{name}: {a['matter']} and {b['matter']} count on the same page, {a['url']}")
            wa, wb = words(a["text"]), words(b["text"])
            if wa and wb and len(wa & wb) / len(wa | wb) > 0.5:
                raise Repeat(f"{name}: {a['matter']} and {b['matter']} say nearly the same thing")


def combine(rule, weighed):
    """Rule entries win on their matter. A weighed attendance story keeps its better wording, since it can carry the person's reason, and takes the rule's points."""
    out, taken = [], {e["matter"] for e in rule}
    for e in rule:
        w = next((x for x in weighed if x["matter"] == e["matter"]), None)
        out.append({**e, "text": w["text"], "url": w["url"] or e["url"]} if w and e["matter"] == "attendance" else e)
    for e in weighed:
        if e["matter"] in taken:
            if e["matter"] != "attendance":
                print(f"  covered by the {e['matter']} rule, so not shown: {e['text'][:90]}")
            continue
        taken.add(e["matter"])
        out.append(e)
    return out


def read(inputs, file_name):
    """Everything on record for one person, checked."""
    def load(name):
        f = inputs / name
        return json.loads(f.read_text(encoding="utf-8")).get(file_name) if f.exists() else None
    rule = []
    a = load("aipac_ties.json")
    if a:
        rule += aipac_entries(a)
    t = load("us_attendance.json")
    if t:
        rule.append(attendance_entry(t))
    f = inputs / "weighed" / f"{file_name}.json"
    weighed, answered, owner = [], set(), []
    if f.exists():
        w = json.loads(f.read_text(encoding="utf-8"))
        weighed, answered = weighed_entries(w)
        owner = w.get("owner_items") or []
    return combine(rule, weighed), answered, owner


def history(card, inputs, file_name):
    """The year-by-year money view (ballot/money_history.py). Shown only: nothing here moves a score."""
    f = inputs / "money_history.json"
    h = json.loads(f.read_text(encoding="utf-8")).get(file_name) if f.exists() else None
    if h:
        card["money_history"] = h


def score_foreign(card):
    return (card.get("score") or {}).get("foreign")


def apply(card, entries, answered, owner):
    """Put the entries on the card and move the score. Call after the base score is final, then re-rank the race."""
    check(card["name"], entries)
    n_c = len(card.get("controversies") or [])
    if answered:
        card["controversies"] = [x for i, x in enumerate(card.get("controversies") or [], 1) if i not in answered]
        card["foreign_ties"] = [x for i, x in enumerate(card.get("foreign_ties") or [], n_c + 1) if i not in answered]
    if owner:
        card["owner_sources"] = (card.get("owner_sources") or []) + owner
    shown = []
    for e in sorted(entries, key=lambda x: -abs(x.get("points") or 0)):
        row = {"text": e["text"], "url": e["url"], "status": e.get("status", "")}
        if e.get("points"):
            row.update(level=e["level"], points=e["points"])
            row["status"] = "established" if e["points"] < 0 else "credit"
        shown.append(row)
    card["controversies"] = shown + (card.get("controversies") or [])
    if not card["controversies"]:
        card.pop("controversies")
    if not card.get("foreign_ties"):
        card.pop("foreign_ties", None)
    if any(e["matter"] == "aipac" for e in entries) and score_foreign(card) is not None:
        card["score"]["foreign"]["note"] = "AIPAC records count separately, under Cases, complaints & controversies."
    move = sum(e.get("points") or 0 for e in entries)
    score = card["score"]
    if move and score.get("overall") is not None:
        score["before"] = score["overall"]
        score["overall"] = max(0, min(100, score["overall"] + move))
