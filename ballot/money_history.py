"""Each federal candidate's money, two-year period by two-year period, back to their first federal race. Shown on the card only: it never moves a score. No AI cost.
Run: py ballot/money_history.py <folder of FEC weballYY.zip files> FL NJ AL CA NC
     py ballot/money_history.py <folder> --find FL NJ AL CA NC    lists other FEC ids with the same name and state, to review by hand
Reads the FEC's all-candidate summary files (1980 on) and each state's aipac_ties.json. Writes ballot/inputs/<ST>/money_history.json, keyed by person file.
A person who ran for two offices has two FEC ids. OTHER_IDS holds the ones reviewed by hand, because the FEC doesn't link them and a name alone can be a different person."""
import json, re, sys, zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CYCLES = range(1980, 2028, 2)
# weballYY columns, from the FEC's own file description.
RECEIPTS, SPENT, OWN_GAVE, OWN_LOANED, INDIV, PACS, PARTY = 5, 7, 11, 12, 17, 25, 26
# Reviewed against name, party, office and city on each id. Left out on purpose: Rob Menendez's S6NJ00289 is his father's; Raul Ruiz's H0CA36177 is a different party and city; Larry Thompson's H0CA37175 can't be confirmed.
OTHER_IDS = {"michaelangelo-hamilton": ["H2FL23153"], "phil-felipe-ehr": ["H8FL01107"], "mike-haridopolos": ["S2FL00193"], "justin-murphy": ["H8NJ03180"], "thomas-kean-jr": ["H0NJ07089", "S6NJ00271"], "frank-pallone": ["S6NJ00263"],
             "tom-mcclintock": ["H6CA21135"], "kyle-kirkland": ["H4CA20223"], "deborah-k-ross": ["S6NC00266"], "mark-harris": ["S4NC00154"]}
NO_ID_ON_FILE = {"tyler-davis": "H6FL01549", "ralph-groves": "H4FL11089", "salomon-hernandez": "H4FL14166", "michaelangelo-hamilton": "H6FL23105", "eddy-rojas": "H6FL28021", "todd-schaefer": "H4FL04068",
                 "william-upham": "H6FL05292", "robin-littau": "H6CA02309", "jeff-frese": "H6CA10187", "charles-hoelter": "H6CA15194", "pedro-casas": "H4CA31212", "ricardo-cabrera": "H6CA51140", "eugene-douglass": "H4NC02135"}


# Ids on file in aipac_ties.json that belong to someone else: Marshall L. Davis Sr. of Hollywood and Vincent Michael Arias of Miami. Neither holds AIPAC money, and the cards use the right id.
NOT_THEM = {"mark-davis": {"H6FL24129"}, "victor-arias": {"H4FL27028"}}
# The FEC filed Rob Menendez's 2026 committee under H2NJ13075 too, but that id's filings through 2006 are his father's.
ONLY_FROM = {("rob-menendez", "H2NJ13075"): 2022}


def read_cycles(folder):
    """{id: {cycle: columns}} and {id: (names seen, state)}"""
    rows, who = defaultdict(dict), defaultdict(lambda: [set(), ""])
    for cy in CYCLES:
        name = f"weball{cy % 100:02d}"
        with zipfile.ZipFile(Path(folder) / f"{name}.zip") as z, z.open(z.namelist()[0]) as fh:
            for line in fh.read().decode("latin-1").splitlines():
                p = line.split("|")
                if len(p) < 27:
                    continue
                rows[p[0]][cy] = p
                who[p[0]][0].add(p[1].strip().upper())
                who[p[0]][1] = p[18]
    return rows, who


def number(p, i):
    try:
        return float(p[i] or 0)
    except ValueError:
        return 0.0


def ties(st):
    return json.loads((ROOT / "ballot" / "inputs" / st / "aipac_ties.json").read_text(encoding="utf-8"))


def ids_of(key, a):
    return sorted((set(a["fec_ids"]) | set(OTHER_IDS.get(key, [])) | ({NO_ID_ON_FILE[key]} if key in NO_ID_ON_FILE else set())) - NOT_THEM.get(key, set()))


def base_name(n):
    """LAST, FIRST with titles, suffixes and middle names off."""
    n = re.sub(r"\b(MR|MRS|MS|DR|HON|REV|JR|SR|II|III|IV)\b\.?", "", n.upper())
    last, _, first = n.partition(",")
    return last.strip(), (first.split() or [""])[0].strip(".")


def find(folder, states):
    rows, who = read_cycles(folder)
    by_name = defaultdict(set)
    for i, (names, st) in who.items():
        for n in names:
            by_name[(base_name(n), st)].add(i)
    for st in states:
        for key, a in ties(st).items():
            have = ids_of(key, a)
            if not have:
                continue
            more = {o for i in have for n in who[i][0] for o in by_name[(base_name(n), who[i][1])]} - set(have)
            for o in sorted(more):
                print(st, key, "on file", have, "| also", o, sorted(who[o][0])[:2], "cycles", sorted(rows[o])[:1], "to", sorted(rows[o])[-1:], "raised", round(sum(number(p, RECEIPTS) for p in rows[o].values())))


def aipac_rows(a):
    older = a.get("passed_older") or {}
    out = {}
    for cy in (2022, 2024, 2026):
        c = str(cy)
        row = {"gifts": a["aipac_pac_gifts"].get(c, 0), "passed": a["passed_through_aipac_pac_2026"] if cy == 2026 else older.get(c, 0),
               "for": a["udp_spent_for"].get(c, 0), "against": a["udp_spent_against"].get(c, 0)}
        if any(row.values()):
            out[cy] = {k: round(v) for k, v in row.items()}
    return out


def build(folder, states):
    rows, _ = read_cycles(folder)
    for st in states:
        out = {}
        for key, a in ties(st).items():
            ids = ids_of(key, a)
            if not ids:
                continue
            period = defaultdict(lambda: defaultdict(float))
            for i in ids:
                for cy, p in rows.get(i, {}).items():
                    if cy < ONLY_FROM.get((key, i), 0):
                        continue
                    t = period[cy]
                    t["raised"] += number(p, RECEIPTS)
                    t["spent"] += number(p, SPENT)
                    t["people"] += number(p, INDIV)
                    t["pacs"] += number(p, PACS)
                    t["own"] += number(p, OWN_GAVE) + number(p, OWN_LOANED)
                    t["party"] += number(p, PARTY)
            aipac = aipac_rows(a)
            years = sorted({cy for cy, t in period.items() if t["raised"] > 0} | set(aipac), reverse=True)
            if years:
                out[key] = {"ids": ids, "periods": [{"y": cy, **{k: round(v) for k, v in period[cy].items()}, **({"aipac": aipac[cy]} if cy in aipac else {})} for cy in years]}
        f = ROOT / "ballot" / "inputs" / st / "money_history.json"
        f.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(st, len(out), "people,", sum(len(v["periods"]) for v in out.values()), "periods")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--find" in args:
        args.remove("--find")
        find(args[0], args[1:])
    else:
        build(args[0], args[1:])
