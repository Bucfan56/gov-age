"""AIPAC money read live from the FEC through the Appolis data door, set over what aipac_ties.py found in the bulk files. No AI cost.
Run: APPOLIS_SHIFT_FILE=<proof file> py buddy/research/aipac_live.py pull <out.json>
     py buddy/research/aipac_live.py merge <out.json> FL NJ AL CA NC
Why: AIPAC's PAC lists every gift it passes on, candidate by candidate. Many campaigns' own reports never name the PAC, so counting from the campaign's side alone misses them.
Passed-through money takes whichever side shows more: they're two views of the same gifts, so they're never added. 2022 and 2024 passed-through money is kept in its own field.
Reads totals only. No donor name is printed or kept."""
import json, os, sys, time, urllib.error, urllib.parse, urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOOR = "https://appolis.app/id/data/datagov/api.open.fec.gov/v1"
PAC, UDP = "C00797670", "C00799031"
CYCLES = (2022, 2024, 2026)
WAITS = (429, 500, 502, 503, 504)


def get(path, **q):
    proof = Path(os.environ["APPOLIS_SHIFT_FILE"]).read_text(encoding="utf-8").strip()
    url = f"{DOOR}/{path.strip('/')}/?" + urllib.parse.urlencode(q, doseq=True)
    req = urllib.request.Request(url, headers={"x-appolis-shift": proof, "User-Agent": "ballot-buddy-check"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code not in WAITS or attempt == 5:
                raise SystemExit(f"{e.code} on {path}: {e.read().decode('utf-8', 'replace')[:200]}")
            time.sleep(30 * (attempt + 1))
        except OSError:
            if attempt == 5:
                raise
            time.sleep(15 * (attempt + 1))


def walk(path, **q):
    """Every row, following the FEC's keyset pages."""
    seen, last = 0, {}
    while True:
        d = get(path, per_page=100, **q, **last)
        rows = d.get("results") or []
        yield from rows
        seen += len(rows)
        page = d["pagination"]
        if not rows or not page.get("last_indexes") or seen >= page["count"]:
            return
        last = page["last_indexes"]


def all_ids(states):
    return sorted({i for st in states for p in ties(st).values() for i in p["fec_ids"]})


def ties(st):
    return json.loads((ROOT / "ballot" / "inputs" / st / "aipac_ties.json").read_text(encoding="utf-8"))


def pull(out, states=("FL", "NJ", "AL", "CA", "NC")):
    ids = all_ids(states)
    comm_of = {i: sorted({c["committee_id"] for c in get(f"candidate/{i}/committees", per_page=100)["results"] if c.get("designation") in ("P", "A")}) for i in ids}
    owner = {c: i for i, cs in comm_of.items() for c in cs}
    comms = sorted(owner)
    direct, earmark = defaultdict(lambda: defaultdict(float)), defaultdict(lambda: defaultdict(float))
    for cy in CYCLES:
        for k in range(0, len(comms), 50):
            for r in walk("schedules/schedule_b", committee_id=PAC, two_year_transaction_period=cy, recipient_committee_id=comms[k:k + 50]):
                i = owner.get(r.get("recipient_committee_id"))
                if i is None:
                    continue
                text = " ".join(str(r.get(f) or "") for f in ("disbursement_description", "memo_text")).upper()
                (earmark if "EARMARK" in text else direct)[i][cy] += r.get("disbursement_amount") or 0
    # Regular reports and 24- and 48-hour notices hold the same spending, so they're kept apart and never added.
    udp = {False: defaultdict(lambda: defaultdict(float)), True: defaultdict(lambda: defaultdict(float))}
    for cy in CYCLES:
        for r in walk("schedules/schedule_e", committee_id=UDP, cycle=cy, most_recent="true"):
            if r.get("memo_code") != "X":
                side = "for" if (r.get("support_oppose_indicator") or "").upper() == "S" else "against"
                udp[bool(r.get("is_notice"))][r.get("candidate_id")][f"{side}|{cy}"] += r.get("expenditure_amount") or 0
    plain = lambda d: {k: {str(c): round(v, 2) for c, v in x.items()} for k, x in d.items()}
    out.write_text(json.dumps({"comm_of": comm_of, "direct": plain(direct), "earmark": plain(earmark), "udp_report": plain(udp[False]), "udp_notice": plain(udp[True])}, indent=1), encoding="utf-8")


def merge(live, states):
    for st in states:
        f = ROOT / "ballot" / "inputs" / st / "aipac_ties.json"
        data = ties(st)
        for a in data.values():
            ids = a["fec_ids"]
            if not ids:
                continue
            side = lambda g, c: round(sum(live[g].get(i, {}).get(str(c), 0) for i in ids), 2)
            spent = lambda s, c: round(sum(max(live["udp_report"].get(i, {}).get(f"{s}|{c}", 0), live["udp_notice"].get(i, {}).get(f"{s}|{c}", 0)) for i in ids), 2)
            campaign = a.get("passed_campaign_report_2026", a["passed_through_aipac_pac_2026"])
            a["passed_campaign_report_2026"] = campaign
            a["passed_pac_report_2026"] = side("earmark", 2026)
            a["passed_through_aipac_pac_2026"] = max(campaign, a["passed_pac_report_2026"])
            a["passed_through_aipac_pac_2022_2024"] = round(side("earmark", 2022) + side("earmark", 2024), 2)
            a["passed_older"] = {"2022": side("earmark", 2022), "2024": side("earmark", 2024)}    # shown on the card's money history, never counted
            for c in CYCLES:
                a["aipac_pac_gifts"][str(c)] = side("direct", c)
                a["udp_spent_for"][str(c)] = spent("for", c)
                a["udp_spent_against"][str(c)] = spent("against", c)
        f.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(st, "merged", len(data))


if __name__ == "__main__":
    if sys.argv[1] == "pull":
        pull(Path(sys.argv[2]))
    else:
        merge(json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")), sys.argv[3:])
