# Handoff brief

**Project:** "How Old Is the United States Government" — an interactive page on the age
of every branch of the federal government, joined to FEC campaign finance data.

**State:** Working and complete. Runs locally right now. What remains is deployment and
optional expansion. Nothing here is a rescue job.

**Owner's goal:** a live, self-refreshing public page, plus supporting material for a
presentation titled *The Aging Government and What That Means for the Next Generation*.

---

## 1. Read this first: decisions that look like bugs but aren't

Please don't "fix" these without asking. Each one is deliberate and each one took a
correction to get right.

| Thing | Why it's like that |
|---|---|
| Trend charts start at **1990**, not 1980 | FEC bulk files under-report the PAC field before 1990. Grassley showed a false 0% for 1980–84. `PAC_DATA_FROM` in `index.html`. |
| Trend charts drop cycles under **15% of a person's peak receipts** | Senators raise almost nothing between races, so off-year cycles produce meaningless PAC-share spikes. `activeCycles()`. |
| The current cycle renders as a **hollow dot** and is excluded from first-vs-last | 2026 filings are partial — they only run to the last reporting deadline. |
| ~~The roster is **not a random sample**~~ | **Resolved 2026-08-18.** Congress is now a complete census — every seated member of both chambers. The governors and the executive branch are still selections, and the caveat box says so. |
| The **caveat box** in the money section | Directly guards against the above being over-read. It is load-bearing. Do not remove it or soften it. |
| Some ages carry **`≈`** and dashed rings | Joint Chiefs birth dates aren't reliably published. Marked rather than guessed. |
| Governors and justices show **"no federal filing"** rather than $0 | They genuinely don't file with the FEC. `noFecReason()` explains why per branch. |
| `finance.json` is both **inlined and fetched** | Inlined so the file works from disk; re-fetched when served so a refresh takes effect without rebuilding the HTML. |

One framing note that matters more than any of the above: **the tool reports who wrote
the checks and stops there.** It does not assert that anyone is bought. Keep it that way —
FEC data can't see dark money, bundling, or state fundraising, so a low PAC share isn't
evidence of independence any more than a high one is evidence of corruption.

---

## 2. Repo layout

```
gov-age/
├── index.html                    the whole page, self-contained (~260 KB)
├── finance.json                  FEC dataset, 548 people, 24 cycles (~1.6 MB)
├── roster_map.json               person → FEC candidate ID(s) — generated for Congress
├── roster_overrides.json         hand curation that survives a roster rebuild
├── build_roster.py               rebuilds the roster from congress-legislators
├── build_finance.py              rebuilds finance.json from FEC bulk downloads
├── inline_data.py                re-inlines finance.json into index.html
├── verify.py                     smoke test — run after every rebuild
├── README.md                     user-facing docs
├── HANDOFF.md                    this file
├── .gitignore                    excludes raw/ (~600 MB cache)
└── .github/workflows/refresh.yml weekly rebuild + commit
```

No build step, no bundler, no dependencies. `index.html` opens in a browser as-is.
The Python scripts use only the standard library.

---

## 3. Tasks

### 3.1 Ship it (the main ask)

```bash
cd gov-age
git init && git add -A && git commit -m "Initial commit"
gh repo create <name> --public --source=. --push
```

Then in repo settings: **Pages → Source: Deploy from a branch → main / (root)**.

Verify:
- Page loads at `https://<user>.github.io/<name>/`
- The stamp next to "Who is paying for them" reads `built <timestamp>`
- Clicking a name in the Age finder opens the money drawer
- No console errors

Then trigger the Action manually (**Actions → Refresh FEC data → Run workflow**) and
confirm it completes. First run has no cache and pulls ~600 MB; budget 15–25 minutes.
Later runs restore the cache and only re-pull the live cycle.

### 3.2 Verify the one thing I could not

**`api.open.fec.gov` CORS is unconfirmed.** The DEMO_KEY rate limit was exhausted when I
built this, so I could not make a live browser call. The investigator is written
defensively and degrades with a readable message, but it is untested against a real key.

```bash
# get a free key at https://api.data.gov/signup
curl -sI "https://api.open.fec.gov/v1/candidates/search/?q=talarico&api_key=YOUR_KEY" \
  | grep -i access-control-allow-origin
```

- Header present → serve the folder over http (`python3 -m http.server`), paste the key
  into the investigator, search a name, confirm results render.
- Header absent → the browser will block it. Fall back to a tiny proxy (Cloudflare
  Worker or Netlify function) holding the key server-side, and point `api()` in
  `index.html` at it. That also removes the key-in-the-browser problem. Flag this to
  the owner before building it, since it changes the hosting story from static to
  static-plus-a-function.

### 3.3 Small fixes worth doing

- **Don Tracy (R-IL)** has no published birth date, so Illinois' open-seat range is
  one-sided. If you find a sourced date, add it to the `SWAPS` array in `index.html`
  and drop the footnote that excludes him.
- **Joint Chiefs ages** are estimates. Official DoD bios sometimes give commissioning
  year; anything sourced beats an estimate. Remove the `a:1` flag when you replace one.
- **Cabinet approximations** — Brooke Rollins, Chris Wright, Jay Clayton and Jamieson
  Greer carry `a:1`. Same treatment.

---

## 4. Backlog, roughly in value order

1. ~~**Expand the roster.**~~ **Done, 2026-08-18.** All 535 seats are tracked: 100
   senators, 431 seated representatives and the 6 non-voting delegates, joined to
   `congress-legislators` by FEC candidate ID. See `build_roster.py`. It changed the
   headline findings substantially — the old 48-person selection had roughly doubled
   the apparent age/PAC correlation (r = 0.64 against 0.36 across the whole chamber)
   and put the Silent-to-Millennial PAC ratio near six times when it is closer to two.
   The chamber medians are now computed from the data instead of quoted from published
   analyses. **If you touch the roster, read section 7 — those numbers move with it.**

2. ~~**Individual contributions.**~~ **Done, 2026-08-18.** See `build_donors.py`.
   Original note follows. **Individual contributions.** `indiv26.zip` is 2.1 GB but contains itemized personal
   donations with employer and occupation. That would surface the people on this page who
   appear as *donors* rather than candidates — Linda McMahon, Howard Lutnick, Scott
   Bessent. Needs streaming parse, not `read()`.

3. **Leadership PACs.** Separate from principal campaign committees and currently
   invisible. `cm.txt` marks them with `CMTE_DSGN = D`. Worth splitting out.

4. ~~**State-level governor money.**~~ **Florida done, 2026-08-18.** See
   `build_state.py` — one adapter per state, all 37 Florida offices. The other
   49 still need adapters. Original note follows. **State-level governor money.** Fifty separate systems. The National Institute on
   Money in Politics / FollowTheMoney has an API that covers it. This is the biggest
   real coverage gap and probably a project of its own.

5. **Diff view.** Since data refreshes weekly, storing prior snapshots would let the page
   show what moved — new large donors, PAC share shifts.

---

## 5. Running it locally

```bash
python3 -m http.server 8000      # serve, don't open from disk — fetch is blocked on file://
```

Rebuild the data:

```bash
python3 build_finance.py --roster roster_map.json --out finance.json
python3 inline_data.py
python3 verify.py
```

`verify.py` checks dataset shape, internal coherence (PAC ≤ receipts, sane cycle ranges),
four known-good anchor figures, that the inlined copy matches `finance.json`, and that the
page still contains its charts, drawer, caveat box and data guards. It exits non-zero on
failure and CI runs it before committing. If you change the data pipeline, extend the
anchors rather than deleting them.

---

## 6. Data sources

All public, all free, no key needed for the pipeline:

- **FEC bulk downloads** — https://www.fec.gov/data/browse-data/?tab=bulk-data
  - `weball{cy}` candidate summaries, every cycle 1980–2026
  - `pas2{cy}` itemized committee→candidate transactions, 2018–2026
  - `cm{cy}` committee master, gives donor org type and connected organization
  - Transaction types used: `24K`/`24Z` direct contributions, `24E` independent
    expenditures supporting. `24A` (spending *against*) is deliberately excluded.
- **OpenFEC API** — https://api.open.fec.gov/developers/ (investigator only, needs a key)
- Age and turnover data: Pew Research Center, Congressional Research Service, Ballotpedia,
  Rutgers Eagleton Center on the American Governor, Wikipedia/Wikidata for 2026 election
  status and candidate birth dates.

---

## 7. Headline findings, for the presentation

Keep these accurate if you touch the data — they're what the deck is built on.

- Median American **39.1**. House median **58** (431 of 435 seats filled, average 58.4),
  Senate median **66** (average 65.2), Supreme Court average **65.7**, President **80**.
  Congress as a whole: median **60**, oldest 92, youngest 29.
- **35 of 100 senators are over 70.** 26 members of Congress are 80 or older, averaging 83.
  Exactly one member of either chamber is Gen Z: Maxwell Frost.
- Three of six bodies have **no term limit and no retirement age**: House, Senate,
  Supreme Court. The Joint Chiefs are the only body with mandatory retirement — and the
  youngest group on the page.
- **Twelve of thirteen open Senate seats get younger** whichever way they vote. Departing
  senators average **70.5**; everyone on those ballots averages **53.4**. North Carolina
  is the exception; Oklahoma is a wash.
- PAC share of career money by generation, across all 532 members with a filing history:
  **Silent 42% · Boomer 34% · Gen X 27% · Millennial 21% · Gen Z 8%**. Age correlates with
  PAC share at **r = 0.36** — and first-cycle year correlates at **−0.31** on its own, so
  part of this is era, not age. Say both.
- Corporate PACs supply **39%** of itemised committee money to members born before 1981
  and **25%** to Millennials.
- Chuck Grassley, 92, is older than Social Security. His PAC share has gone *down*
  (1992: 38% → 2022: 24%), which cuts against the simple age story. Worth including —
  it's the honest version.

**These figures replaced the pre-expansion ones on 2026-08-18 and the direction of the
change matters more than any single number.** The old roster tracked only the oldest and
youngest members, and it had inflated the generation story roughly twofold: the age/PAC
correlation read **0.64** against a true **0.36**, and the Silent-to-Millennial PAC ratio
read about **five times** against a true **2.1 times**. The gradient is real and it still
runs the way you would expect. It is half as steep as the page used to imply. The old
caveat box called this exact risk, which is why it was load-bearing.

Every one of these is now computed in the page rather than typed into it, so they cannot
silently go stale again — but that also means **they will drift as the data refreshes.**
Re-read them off the live page before quoting them in a deck.
