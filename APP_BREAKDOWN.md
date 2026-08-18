# gov-age — living breakdown

**Live:** https://bucfan56.github.io/gov-age/
**Repo:** https://github.com/Bucfan56/gov-age
**Local:** `F:\Claude Code\politics-sesh`

An interactive page on the age of every branch of the U.S. federal government, joined to
Federal Election Commission campaign finance data. It supports a presentation titled
*The Aging Government and What That Means for the Next Generation*.

---

## What it is

One self-contained `index.html`. No build step, no bundler, no dependencies, no framework.
The Python pipeline that rebuilds the data uses only the standard library and needs no API
key. The page opens in a browser as a file, or serves as static hosting.

| Piece | What it does |
|---|---|
| `index.html` | The whole page. 12 sections, finance data inlined so it works offline. |
| `finance.json` | The FEC dataset. Fetched when served, overriding the inlined copy. |
| `roster_map.json` | Person → FEC candidate ID(s). Generated for Congress. |
| `build_roster.py` | Rebuilds the congressional roster from `congress-legislators`. |
| `roster_overrides.json` | Hand curation that survives a rebuild, keyed by bioguide ID. |
| `build_finance.py` | Rebuilds `finance.json` from FEC bulk downloads. |
| `inline_data.py` | Re-inlines `finance.json` into `index.html`. |
| `verify.py` | Smoke test. Gates the CI commit. |
| `.github/workflows/refresh.yml` | Weekly rebuild → verify → commit. |

**Current dataset:** 595 officials tracked for age — Congress complete at 100 senators,
431 seated representatives and 6 delegates — with 545 of them carrying FEC filings and
$13.66B in career receipts across 24 election cycles (1980–2026).

## How the refresh loop works

Mondays 09:17 UTC (and on demand from **Actions → Refresh FEC data → Run workflow**):

1. Pull FEC bulk files — candidate summaries for every cycle since 1980, itemised
   committee cheques and committee master since 2018. Cached, with only the live cycle
   re-fetched.
2. Rebuild `finance.json`, re-inline it into `index.html`.
3. Run `verify.py`. **If it fails, nothing is committed.**
4. Commit only if the data actually moved. GitHub Pages redeploys on the commit.

Nothing to run, nothing to pay for, no server.

## The framing rule

The tool reports **who wrote the checks and stops there.** It does not assert that anyone
is bought. FEC data cannot see dark money, bundling, or state fundraising, so a low PAC
share is not evidence of independence any more than a high one is evidence of corruption.
The caveat box in the money section is load-bearing — do not remove or soften it.

---

## Changelog

### 2026-08-18 — Congress became a census

Expanded the roster from 48 tracked people to every seated member of Congress: 100
senators, 431 representatives and the 6 non-voting delegates, 595 officials in total.
This was the backlog's highest-value item, and it changed what the page can honestly
claim more than it changed how it looks.

**The roster is generated now, not typed.** `build_roster.py` joins
`@unitedstates/congress-legislators` — which publishes a bioguide ID, birthday, party,
state, district and FEC candidate IDs for every member — to the finance pipeline. It is
idempotent, and `roster_overrides.json` carries the hand curation (preferred names,
leadership titles, announced retirements) keyed by bioguide ID so a rebuild cannot
flatten it. **The join is by FEC candidate ID, never by name**: fifteen of the original
48 are spelled differently across the two sources — Bernie against Bernard Sanders, Hal
against Harold Rogers — and a name join would have created a second copy of each, split
their money across two rows, and corrupted every generation figure on the page.

**Chamber figures are computed instead of quoted.** The House and Senate medians, the
count of senators over 70, the members over 80, the Gen Z count and the birth-year cards
were all static published estimates — *because a deliberate selection of the oldest and
youngest members cannot produce a median*. They are derived from the same birth dates as
the rest of the page now. The methodology note claimed "there is no public dataset of
verified birth dates for every member"; that was true when written and is no longer, so
it was rewritten rather than left standing.

**The headline finding moved, and that is the real result.** The old selection had
inflated the generation story roughly twofold:

| | Old (48-person selection) | New (census) |
|---|---|---|
| Silent PAC share | 41% | 42% |
| Boomer | 16% | **34%** |
| Gen X | 11% | **27%** |
| Millennial | 7% | **21%** |
| Silent : Millennial ratio | ~5.9x | **2.05x** |
| Age vs PAC share | r = 0.64 | **r = 0.36** |
| First-cycle year vs PAC | r = -0.42 | **r = -0.31** |

The gradient is real and runs the way you would expect. It is about half as steep as the
page used to imply. The caveat box had warned of exactly this, which is why it was
load-bearing — it was rewritten rather than removed, because Congress is a census now
but the governors and the executive branch are still selections, and three non-sampling
caveats still stand.

**Three real bugs surfaced, all latent until the data got bigger:**

- **Six members had dead rows.** The finder wrote each name into a `data-n` attribute
  with the quote characters stripped out to keep the markup valid, then looked the
  person up by that stripped string — which could never match the real name. Members
  with quoted nicknames (Robert C. "Bobby" Scott, Earl L. "Buddy" Carter and four
  others) could be clicked and nothing happened, and their `aria-label` markup was
  broken too. Rows bind by position now and names are escaped. *Verified: all six open,
  and `verify.py` fails if the old binding returns.*
- **`inline_data.py` would have broken the weekly Action.** It passed the JSON as a
  regex *replacement string*, so backslash sequences were interpreted. With non-ASCII
  names in the data — Jesús García, Pablo José Hernández — the escaped characters raised
  "bad escape". It never fired at 48 people because none of them had a non-ASCII name.
- **A former member was listed as sitting.** David Scott (D-GA) appeared as a current
  Representative but holds no seat in the 119th Congress. Removed, with the reason
  recorded in `roster_overrides.json`.

**Two estimated birth dates replaced with sourced ones.** Tim Sheehy was carried as
approximately 1985-11-01 and Yassamin Ansari as approximately 1992-04-01; the real dates
are 1985-11-18 and 1992-04-07. Their approximation flags are gone.

**A coverage gap disclosed rather than papered over.** Whether an incumbent intends to
run again is not published in machine-readable form, so retirement announcements are
hand-entered and only seven are recorded against 531 members. The page now says plainly
that "On the ballot" means the seat is up, not that the incumbent is seeking it.

**Verification extended, not replaced.** `verify.py` keeps its original anchors and adds
census-scale ones: exactly 100 senators, 425+ voting representatives, exactly 6
delegates, no duplicate display names, no orphaned finance records, and a guard against
the quote-stripped row binding. All three new guards were negative-tested — deliberately
broken to confirm they fail — and the unmodified control passes.

**The weekly Action refreshes the roster too**, ahead of the finance rebuild, so deaths,
resignations and special elections flow through on their own. `verify.py` gates the
commit, so a bad upstream release fails the run instead of shipping.

**Page weight:** 1.8 MB raw, **323 KB gzipped** — the finance dataset grew from 154 KB to
1.6 MB. The page loads in about 130 ms locally, and search across 595 rows takes under
3 ms.


### 2026-08-18 — Shipped live

First deployment. Picked up from a handoff brief as a working local page; now a live,
self-refreshing public site.

**Fixed — Windows encoding crash (real bug, would have bitten on first use).**
Every `open()` in all three Python scripts used the platform default encoding, which is
cp1252 on Windows. `verify.py` crashed outright on `index.html`; `inline_data.py` would
have written a mangled `index.html` over a good one. All file I/O now pins `utf-8`, and
`verify.py` reconfigures stdout so its report stays readable on a legacy console.
*Verified: `verify.py` passes natively on Windows with no environment overrides, and
`inline_data.py` round-trips `index.html` byte-identically.*

**Added — the weekly refresh Action, which did not exist.**
`.gitignore` and `.github/workflows/refresh.yml` were both named in the handoff's repo
layout but were absent from the delivered folder — so the self-refresh the whole goal
depends on was not there. Written from scratch: caches the FEC bulk pull, re-fetches only
the live cycle, gates the commit on `verify.py`, commits only when data moved.
*Verified: one manual run completed in 44s, pulled every cycle 1980–2026, rebuilt to the
same 48 people / $3.38B as local, and committed.*

**Added — `.gitattributes` forcing LF.**
The Action rewrites `index.html` on a Linux runner while the repo is edited on Windows.
Without a fixed line ending, every weekly refresh would have diffed as a 1,955-line
rewrite instead of a data change.

**Fixed — GitHub Pages build failing.**
Pages reported `errored` on every push; the legacy Jekyll path was failing even though
the workflow deployment happened to serve the right file anyway. Added `.nojekyll` to opt
out — nothing here is a Jekyll site, and leaving a failing build in the loop is the kind
of thing a future refresh quietly depends on. *Verified: build status went `errored` →
`built`.*

**Resolved — the handoff's one open question: FEC API CORS.**
The brief flagged `api.open.fec.gov` CORS as unconfirmed (the DEMO_KEY limit was exhausted
during the original build) and pre-planned a Cloudflare Worker proxy fallback, which would
have turned this from static hosting into static-plus-a-function. **The proxy is not
needed.** The API returns `Access-Control-Allow-Origin: *`. Confirmed three ways: curl with
an Origin header, a cross-origin fetch from a locally served page, and — the one that
actually counts — a live fetch from the deployed `https://bucfan56.github.io` origin,
which returned `TALARICO, JAMES / S6TX00479`. The hosting story stays static, and no API
key ever needs to live server-side.

**Verified on the live site:** page loads, no console errors, all 12 sections render, the
build stamp reads `built 2026-08-18T05:32Z`, the generation bars show Silent 41% /
Boomer 16% / Gen X 11%, the caveat box is present and visible, and clicking a name in the
Age finder opens the money drawer (Grassley: $49.9M career, 32.6% PAC, showing the
1992 38% → 2022 24% decline).

---

## Known gaps

- **The roster is a deliberate selection, not a sample.** It tracks the oldest and youngest
  officials, which inflates the generation gap. Expanding to all 535 members of Congress is
  the single highest-value change and would let the selection-bias caveat be dropped.
- **Some ages are estimates**, marked with `≈` and dashed rings: the Joint Chiefs, four
  cabinet members (Rollins, Wright, Clayton, Greer), and Don Tracy (R-IL), whose missing
  birth date leaves Illinois' open-seat range one-sided.
- **No governor money.** They file with fifty separate state systems, not the FEC.
- **No individual contributions, no leadership PACs.** Both are in the backlog.
