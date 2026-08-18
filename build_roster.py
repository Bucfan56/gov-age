#!/usr/bin/env python3
"""
Rebuilds the congressional roster from @unitedstates/congress-legislators.

  python3 build_roster.py

Writes roster_map.json (person -> FEC candidate IDs) and splices a freshly
generated SENATE/HOUSE block into the PEOPLE array in index.html.

Why a script and not a hand-edited list: there are 535 voting members, their
birthdays are published, and their FEC candidate IDs are published alongside
them. Maintaining that by hand guarantees it goes stale.

THE JOIN IS BY FEC CANDIDATE ID, NEVER BY NAME. Name forms differ between
sources -- 'Bernie Sanders' vs 'Bernard Sanders', 'Hal Rogers' vs
'Harold Rogers' -- and 15 of the original 48 tracked people differ this way.
Joining on the name string would silently create a second copy of the same
person, splitting their money across two rows and corrupting every
generation statistic on the page. Hand curation is keyed by bioguide id in
roster_overrides.json for the same reason.
"""
import argparse, json, os, re, sys, urllib.request
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SRC = "https://unitedstates.github.io/congress-legislators/legislators-current.json"
UA = {"User-Agent": "gov-age-roster/1.0 (public data research)"}
DELEGATE_STATES = {"DC", "PR", "VI", "GU", "AS", "MP"}
PARTY = {"Democrat": "D", "Republican": "R", "Independent": "I"}

# Senate terms are staggered in three classes; the term end date says when a
# seat is next contested. House seats are all contested every two years.
TERM_BY_END = {"2027-01-03": "ballot26", "2029-01-03": "y2028", "2031-01-03": "y2030"}


def fetch(cache="raw/legislators-current.json", refresh=False):
    if not refresh and os.path.exists(cache):
        return json.load(open(cache, encoding="utf-8"))
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    raw = urllib.request.urlopen(urllib.request.Request(SRC, headers=UA), timeout=120).read()
    open(cache, "wb").write(raw)
    return json.loads(raw.decode("utf-8"))


def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def build(refresh=False):
    leg = fetch(refresh=refresh)
    conf = json.load(open("roster_overrides.json", encoding="utf-8"))
    ovr = conf["members"]
    dropped = set(conf.get("_removed", {}))

    people, roster, skipped = [], {}, []
    seen_names = {}

    for p in leg:
        t = p["terms"][-1]
        bio = p["id"]["bioguide"]
        o = ovr.get(bio, {})
        state, typ = t["state"], t["type"]
        delegate = state in DELEGATE_STATES

        name = o.get("name") or p["name"].get("official_full") \
               or f'{p["name"]["first"]} {p["name"]["last"]}'

        # A duplicate display name would collide in the finance join, which is
        # keyed by name. Nothing in the current data trips this, but a future
        # roster could, and it must fail loudly rather than silently merge.
        if name in seen_names:
            sys.exit(f"FATAL: duplicate display name {name!r} "
                     f"({seen_names[name]} and {bio}). Add a distinguishing "
                     f"'name' override for one of them in roster_overrides.json.")
        seen_names[name] = bio

        party = PARTY.get(t["party"], t["party"][:1])
        if delegate:
            role = f'Delegate ({party}-{state})'
        elif typ == "sen":
            role = f'Senator ({party}-{state})'
        else:
            role = f'Representative ({party}-{state}-{t.get("district", "")})'
        if o.get("title"):
            role += ", " + o["title"]

        term = o.get("term") or (
            "ballot26" if typ == "rep" else TERM_BY_END.get(t["end"], "ballot26"))

        rec = {
            "n": name,
            "r": role,
            "b": p["bio"]["birthday"],
            "g": "senate" if typ == "sen" else "house",
            "t": term,
            # First year in either chamber -- terms are ordered, so terms[0] is
            # the start of their service, not of the current term.
            "sy": int(p["terms"][0]["start"][:4]),
        }
        if delegate:
            rec["d"] = 1          # non-voting; excluded from chamber medians
        people.append((rec, t, typ, delegate))

        # congress-legislators does not always list every FEC id a member holds,
        # and the FEC's own files disagree with each other about which one is
        # current -- weball can summarise under one id while pas2 records the
        # cheques under another. Missing one makes a member read as $0 raised.
        fec = list(dict.fromkeys((p["id"].get("fec") or []) + (o.get("fec") or [])))
        if fec:
            roster[name] = fec
        else:
            skipped.append((name, role))

    # ---------- roster_map.json: keep everyone who is not in Congress ----------
    old = json.load(open("roster_map.json", encoding="utf-8"))
    congress_fec = {f for p in leg for f in (p["id"].get("fec") or [])}
    # Anyone whose FEC ids are absent from the current Congress is someone the
    # page tracks in another branch (cabinet, president) and must be kept --
    # UNLESS they are explicitly retired in _removed, which is how a former
    # member who is genuinely gone leaves the dataset instead of lingering as
    # an orphaned finance record with no row on the page.
    preserved = {n: ids for n, ids in old.items()
                 if not any(i in congress_fec for i in ids) and n not in dropped}
    removed = sorted(set(old) - set(preserved) - set(roster))
    merged = dict(sorted({**preserved, **roster}.items()))
    json.dump(merged, open("roster_map.json", "w", encoding="utf-8", newline=""), indent=1)

    # ---------- splice the PEOPLE block ----------
    html = open("index.html", encoding="utf-8").read()
    # Match the marker prefix, not the whole comment: this script rewrites the
    # comment text as well as the entries, so anchoring on the exact original
    # string would make it a one-shot tool. It has to stay re-runnable -- that
    # is the entire point of generating the roster rather than typing it.
    def anchor(marker):
        i = html.find("  /* ---- " + marker)
        if i == -1:
            sys.exit(f"FATAL: cannot find the {marker} marker in index.html. "
                     f"The PEOPLE array structure changed; update build_roster.py.")
        return i
    start, end = anchor("SENATE"), anchor("GOVERNORS")

    def fmt(recs):
        w = max(len(r["n"]) for r in recs) + 3
        out = []
        for r in recs:
            line = f'  {{n:"{esc(r["n"])}",'.ljust(w + 6)
            line += f' r:"{esc(r["r"])}",'.ljust(max(len(x["r"]) for x in recs) + 8)
            line += f' b:"{r["b"]}", g:"{r["g"]}", t:"{r["t"]}", sy:{r["sy"]}'
            if r.get("d"):
                line += ", d:1"
            out.append(line + "},")
        return "\n".join(out)

    sen = sorted([r for r, *_ in people if r["g"] == "senate"], key=lambda r: r["b"])
    hou = sorted([r for r, *_ in people if r["g"] == "house"], key=lambda r: r["b"])

    block = (
        "  /* ---- SENATE (complete: all 100 seats) ---- */\n"
        f"{fmt(sen)}\n\n"
        "  /* ---- HOUSE (complete: every seated member; d:1 marks the six\n"
        "         non-voting delegates, excluded from chamber medians) ---- */\n"
        f"{fmt(hou)}\n\n"
    )
    open("index.html", "w", encoding="utf-8", newline="").write(html[:start] + block + html[end:])

    # ---------- report ----------
    n_sen = len(sen)
    n_del = sum(1 for r in hou if r.get("d"))
    print(f"senate       {n_sen}")
    print(f"house        {len(hou) - n_del} voting + {n_del} delegates")
    print(f"roster_map   {len(merged)} entries "
          f"({len(roster)} in Congress + {len(preserved)} preserved elsewhere)")
    if removed:
        print(f"dropped from roster_map: {', '.join(removed)}")
    if skipped:
        print(f"no FEC id yet (age tracked, no finance): "
              f"{', '.join(n for n, _ in skipped)}")
    print(f"terms        {dict(Counter(r['t'] for r, *_ in people))}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true",
                    help="re-download congress-legislators instead of using the cache")
    build(**vars(ap.parse_args()))
