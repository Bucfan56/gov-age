# How Old Is the United States Government

An interactive page on the age of every branch of the U.S. federal government, joined
to campaign finance data from the Federal Election Commission.

Everything renders from one HTML file. The finance data is rebuilt from FEC bulk
downloads by a Python script that needs no API key.

> **Handing this to a developer or a coding agent?** Start with `HANDOFF.md` —
> it covers deployment, the deliberate design decisions that shouldn't be undone,
> the one thing that still needs verifying, and the backlog.

---

## Files

| File | What it is |
|---|---|
| `index.html` | The page. Self-contained — the finance data is inlined, so it works from disk. |
| `finance.json` | The finance dataset. If it's served next to `index.html`, the page loads it and overrides the inlined copy. |
| `build_finance.py` | Rebuilds `finance.json` from FEC bulk files. No API key. |
| `inline_data.py` | Re-inlines `finance.json` into `index.html` after a rebuild. |
| `roster_map.json` | Maps each tracked person to their FEC candidate ID(s). **Generated** for Congress — hand-edit only for people outside it. |
| `build_roster.py` | Rebuilds the congressional roster from `congress-legislators`. Re-runnable. |
| `roster_overrides.json` | The hand curation that survives a roster rebuild, keyed by bioguide ID. |
| `build_donors.py` | Adds named individual donors from the FEC's itemised contribution files. |
| `build_state.py` | Pulls state-level campaign finance. One adapter per state. |
| `finance-detail.json` | Month-by-month figures and named donors. Fetched on demand, not inlined. |
| `state-fl.json` | Florida campaign finance, all offices. Fetched on demand. |
| `verify.py` | Smoke test. Run after every rebuild; CI runs it before committing. |
| `HANDOFF.md` | Brief for whoever picks this up next. |
| `.github/workflows/refresh.yml` | Weekly GitHub Action that rebuilds, verifies and commits. |

---

## Refreshing the data

```bash
python3 build_finance.py --roster roster_map.json --out finance.json
python3 inline_data.py
python3 verify.py
```

First run downloads about 600 MB of FEC bulk files into `raw/` and takes several
minutes. Historical cycles never change, so after that the cache makes it fast.
Add `--fresh-current` to re-pull just the live cycle, or delete `raw/` for a clean rebuild.

The FEC regenerates bulk files nightly, but campaign finance moves on quarterly
filing deadlines, so **weekly is plenty**. Daily just burns bandwidth.

### Automatic refresh

Push this folder to a GitHub repo and the included Action runs every Monday,
rebuilds the data, and commits it. Turn on GitHub Pages and the live page updates
itself. Nothing else to run, nothing to pay for.

Other options that work the same way:

- **Cloudflare Pages / Netlify** — point at the repo, they redeploy on each commit.
- **Your own box** — a weekly cron running the two commands above.
- **Kosmos hub** — note that hub documents are CSP-sandboxed, which will block the
  live FEC lookups in the investigator. The rest of the page works fine there.

---

## Who represents me

Pick a state and optionally a district to get the governor, both senators and the
representative for that district, each a clickable profile.

**This asks for a state, not an address, on purpose.** The Census Bureau geocoder resolves
a street address to a congressional district correctly, but sends no CORS header, so a
static page cannot call it. Proxying it would turn this into a service that receives
people's home addresses. Both chambers are tracked in full here, so a picker is equally
exact and nothing about the visitor leaves their browser. Adding address lookup is a
hosting decision, not a coding problem.

## The candidate investigator

The pre-built roster covers the people on the page. The investigator searches the
FEC directly, so it reaches **anyone who has ever filed to run for federal office**.

It needs a free key from **https://api.data.gov/signup** (about thirty seconds).
The key is stored in your browser's local storage and is sent only to the FEC.
Personal keys allow 1,000 calls an hour.

Two caveats:

- Opening `index.html` straight from disk will block the FEC requests. Serve the
  folder instead: `python3 -m http.server` then visit `localhost:8000`.
- A key embedded in a browser page is visible to anyone using that page. That's
  fine for a personal or public research tool with a free rate-limited key. Don't
  reuse a key you care about.

---

## The roster

**Congress is generated, not hand-maintained.** Both chambers come from the
`@unitedstates/congress-legislators` dataset, which publishes a bioguide ID, a
birthday, party, state, district and FEC candidate IDs for every seated member.

```bash
python3 build_roster.py            # uses the cached copy
python3 build_roster.py --refresh  # re-downloads it
```

That rewrites `roster_map.json` and the Senate and House blocks of the `PEOPLE`
array in `index.html`. It is idempotent — running it twice gives the same file.

### The join is by FEC ID, never by name

Fifteen of the originally tracked members are spelled differently in the two
sources: *Bernie* against *Bernard* Sanders, *Hal* against *Harold* Rogers,
*Dick* against *Richard J.* Durbin. Matching on the name string would have
created a second copy of each of them, split their money across two rows, and
quietly corrupted every generation figure on the page. The FEC candidate ID is
the join key, and the hand curation in `roster_overrides.json` is keyed by
bioguide ID for the same reason.

### Changing what a member is called, or how they are labelled

Edit `roster_overrides.json`, keyed by bioguide ID:

```json
"S000033": { "name": "Bernie Sanders" },
"P000197": { "title": "Speaker Emerita", "term": "retiring" }
```

- `name` — preferred display name. It must match the `roster_map.json` key,
  because the finance join is by name.
- `title` — leadership role, appended after the party and state.
- `term` — overrides the term derived from Senate class or House cycle. Only
  needed for members leaving early; the classes derive correctly by themselves.

### Adding someone outside Congress

Justices, cabinet officials and governors are still maintained by hand. Add the
FEC ID to `roster_map.json` (a list — members who served in both chambers have
separate IDs, and both belong there so the career arc is complete), add a
matching entry to `PEOPLE` in `index.html` with a date of birth, and rebuild.
`build_roster.py` preserves anyone whose IDs are not in the current Congress.

---

## What the data does and doesn't cover

**Covered.** Every dollar reported to the FEC by federal candidates: total receipts,
individual contributions, PAC contributions, party money and self-funding for every
cycle since 1980; itemised committee-to-candidate cheques since 2018 with the donor's
organisation type; and independent expenditures spent supporting each candidate.

**Coverage.** Congress is complete — all 100 senators, all 431 seated
representatives and the 6 non-voting delegates. The Supreme Court, the Joint
Chiefs and the serving cabinet are complete. The governors are a selection.

**Not covered, and this matters:**

- **Dark money.** 501(c)(4) groups spend heavily and never disclose donors. None of
  it appears here.
- **Bundling.** One person collecting fifty capped cheques shows up as fifty donors.
- **State and local money, except Florida.** Governors file with their states.
  There are fifty separate systems and no unified feed. Florida is covered —
  all 37 offices it reports on, from Governor down to fire and water districts —
  and other states need an adapter each. Everywhere else still shows nothing.
- **Appointed officials.** Supreme Court justices, the Joint Chiefs and most cabinet
  secretaries have never run for federal office and file nothing with the FEC.
- **Employer fields** on individual contributions are self-reported and inconsistent.
- **Pre-1990 PAC totals** are incomplete in FEC bulk files. The trend charts start
  at 1990 for that reason.
- **The current cycle is partial** — 2026 filings only run through the most recent
  reporting deadline.
- **Whether an incumbent is running again** is not published in machine-readable
  form. A badge reading "On the ballot" means the seat is up, not that the sitting
  member is seeking it. Announced retirements are entered by hand and only a
  handful are recorded.

**On interpretation.** A high PAC share is a fact about who funds a campaign. It is
not evidence of wrongdoing, a vote traded, or a promise made. Treat it as a question
worth asking, not an answer.

---

## Sources

- Federal Election Commission bulk downloads — https://www.fec.gov/data/browse-data/?tab=bulk-data
- OpenFEC API — https://api.open.fec.gov/developers/
- Pew Research Center, Congressional Research Service and Ballotpedia — age and generation data
- Eagleton Center on the American Governor, Rutgers — governor data
- Wikipedia and Wikidata — 2026 election status and candidate birth dates

All source data is public. Verify anything that matters at fec.gov before you publish it.

---

## State-level money

Governors and state legislators file with their own state, never the FEC, so
none of their money is in the federal pipeline. There is no national feed —
fifty states, fifty systems, no shared format. So each state gets an **adapter**
behind one interface:

```bash
python3 build_state.py --state FL          # every office, current + last cycle
python3 build_state.py --state FL --offices GOV,STS,STR
```

**Florida** is the reference implementation, covering all 37 offices its
Division of Elections reports on — Governor, Cabinet, legislature, judges,
State Attorney, Public Defender, and about twenty special districts (fire
control, water, soil and water conservation, bridge and airport authorities).

Adding another state means writing an adapter class with two methods —
`candidates()` and `contributions()` — registering it in `ADAPTERS`, and adding
one line to `STATE_FILES` in `index.html`. Nothing else changes.

### Two things Florida's data will catch you out on

**Loans are not contributions.** Type `LOA` is borrowed money and repayable.
One state house candidate loaned his own campaign $5,000,000; counted as a
donation it made his donor list nonsense and his monthly totals ten times his
reported receipts. Loans are tracked separately. `INT` is bank interest on the
campaign account and is not a donation either.

**The two views disagree, legitimately.** The state's "contribution total" and
the sum of its own itemised contribution list are different measures — the
total excludes loans, and the itemised list is floored at the donor threshold.
Expect them to differ per candidate, and do not "fix" it by making one equal
the other.

## Named individual donors

```bash
python3 build_donors.py --cycles 2026,2024 --floor 500 --keep 15
```

Reads `indiv{cycle}.zip`, the largest file the FEC publishes — 5.7 GB of text
for 2026 alone. It streams out of the zip and is never extracted.

Individual contributions carry a **committee** id and never a candidate id, so
`ccl{cycle}.zip` maps committee to candidate. Only the candidate's own
committees count (designations `P` and `A`), which excludes leadership PACs and
joint fundraising committees.

Donor names are free text and nothing in the data resolves them, so
`SMITH, JOHN` and `SMITH, JOHN A.` are counted as two people. Totals are per
name-as-filed. The page says so.
