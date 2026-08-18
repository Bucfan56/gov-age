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
| `roster_map.json` | Maps each tracked person to their FEC candidate ID(s). Edit this to add people. |
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

## Adding someone to the roster

1. Find their FEC candidate ID at https://www.fec.gov/data/candidates/
2. Add a line to `roster_map.json`. Use a list — people who served in both chambers
   have separate IDs and both should be included so the career arc is complete:

```json
"Jane Doe": ["S4XX00123", "H8XX01456"]
```

3. Add a matching entry to the `PEOPLE` array inside `index.html` with their date
   of birth, so the age and finance data join up.
4. Rebuild.

---

## What the data does and doesn't cover

**Covered.** Every dollar reported to the FEC by federal candidates: total receipts,
individual contributions, PAC contributions, party money and self-funding for every
cycle since 1980; itemised committee-to-candidate cheques since 2018 with the donor's
organisation type; and independent expenditures spent supporting each candidate.

**Not covered, and this matters:**

- **Dark money.** 501(c)(4) groups spend heavily and never disclose donors. None of
  it appears here.
- **Bundling.** One person collecting fifty capped cheques shows up as fifty donors.
- **State and local money.** Governors file with their states. There are fifty
  separate systems and no unified feed, so no governor finance appears here.
- **Appointed officials.** Supreme Court justices, the Joint Chiefs and most cabinet
  secretaries have never run for federal office and file nothing with the FEC.
- **Employer fields** on individual contributions are self-reported and inconsistent.
- **Pre-1990 PAC totals** are incomplete in FEC bulk files. The trend charts start
  at 1990 for that reason.
- **The current cycle is partial** — 2026 filings only run through the most recent
  reporting deadline.

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
