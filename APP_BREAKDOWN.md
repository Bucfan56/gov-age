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
| `build_ballot.py` | Scores every candidate and renders the ballot as flip cards (`ballot-<zip>.json` + `ballot/cards_template.html` → `.html`). |
| `ballot-34221.html` | Palmetto, FL 34221 ballot report for the Nov 3, 2026 general election. |
| `ballot/crop_photos.py` | Crops every candidate photo to the card's 3:2 window around the face (OpenCV YuNet, `ballot/models/`). Run after new photos arrive, then rebuild. |
| `ballot.html` + `fl/*.json` | **Any-address Florida ballot.** Statewide races inline; U.S. House, State Senate/House and county races load per district. Built by `build_florida.py` from `ballot/app_template.html`. |
| `build_florida.py` | Assembles the any-address ballot from the day's pulls and research (see its docstring), reconciles every district race against the Division of Elections candidate list, adds the 🌾 / 🎓 / 🎯 meters. |
| `ballot/fed_money_all.py`, `ballot/fl_money_all.py` | Money for every Florida federal candidate (FEC bulk) and every Legislature district (DOE filings). |
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

### 2026-11-03 (evening, later): Records checked statewide, picks for judges and ballot questions, tap-for-why in Trade check

- **Records checked for 173 more candidates.** Seven research passes covered everyone outside the 34209 ballot who has stated positions: Congress, the Legislature and local races elsewhere. They read the actual roll calls (Florida House and Senate vote sheets, U.S. House clerk records), bills sponsored, and actions in office. 1,115 records are now held for 215 candidates, up from 91 for 42. 84 candidates' 🎯 Priorities scores changed, and 16 races changed order. Same review rules as before: statements, board seats, board votes where the person's own vote isn't found, super PAC money and unexplained No votes don't count. Two votes pointing different ways (for example, Nay on HJR 1-F but Yea on HJR 203) count as a split record rather than "says one thing, does another". A sentence that opens with the deed ("Voted…", "Cast the lone Nay…") now counts as a record even when it quotes a remark. Partington's 2021 millage vote was dropped because it was only inferred from the tally.
- **🎯 Priorities picks for judges and ballot questions** (Tyler's ask). Each one is read only against his parameters: the platform planks, his three questions, and real-world experience for judges. A pick is made when a plank clearly points one way, "leans" when something pulls the other way (shown under "What pulls the other way"), and "your call" when the planks are silent.
  - Amendment 2: Yes. Amendment 3: Yes. County land bond: leans yes. Bradenton term limits: leans yes. Holmes Beach alley giveaway: leans no. Parrish fire $68: leans no.
  - Keep Justice Muñiz. Leans keep for the four appeals judges.
  - Your call on Amendment 1, the Palmetto map and Bradenton Ref 1.
  - The race list shows each pick as a tag. Picks live in research3/recommendations.json.
- **Tap any Trade check row to see why** (Tyler's ask). Each row opens a sheet with both candidates' scores for that category, the reasons behind them and their sources, plus who's ahead and by how much (or "too close to count").
- **"Your priorities" is now "🎯 Priorities"** everywhere: the Trade check row, the card back and How it works.
- **The sign-in email shows the Star Buddy logo** instead of a 🗳️ emoji.

### 2026-11-03 (evening): The whole-app recheck under the real-work rule, and a Lakewood Ranch district fix

- **Every candidate statewide re-read under Tyler's rule.** All 131 ratings that mention a board, committee, commission, council, chamber or foundation were re-read. Elected offices and paid jobs stand, and running a nonprofit or chamber as its paid director counts as work. These no longer add: appointed boards and commissions (planning and zoning, the state wildlife commission, a transit board), civic, nonprofit, college and HOA boards, chamber and bar-association officer roles, party posts, volunteering and meeting activism, and committee or subcommittee chairs inside a legislature (the legislative service itself still counts). 28 more ratings came down, among them Eric Gray (74 to 55), Danny Nix Jr. (66 to 58), Bill Conerly (78 to 72), Liesa Priddy (66 to 60), Liz Arnold (66 to 60) and Richard Jacobs (60 to 35, the same fire-board rule as the West Manatee commissioners). The research rubrics no longer suggest committee seats, civic leadership or PTA roles as qualifications. 38 ratings have been changed under the rule in all, and each keeps its old score as `qual_was`.
- **Lakewood Ranch CDD 2 voters now see their race.** The property appraiser's map spells it "LAKEWOOD RANCH II" and the ballot says "CDD 2", so the name match missed it. The loose matching could also have shown a Lakewood Ranch I resident the CDD 2 race. Roman numerals now read as numbers, and district names must match exactly. The lookup was tested on 8 real Manatee addresses: Palmetto, Holmes Beach, Anna Maria, Lakewood Ranch, Ellenton, Parrish, downtown Bradenton and Cortez Road. None were left with "check your address".
- The 13 candidates without a qualification rating are all write-ins with no public bio, so they show "background not found" rather than a low score.

### 2026-11-03 (night, last): Qualified means real-world experience, not board seats

- **Owner's rule (Tyler):** a seat on a committee, an advisory or civic board, or a nonprofit board is not a qualification. Only real work in the job's field counts. The How-it-works page now says so.
- **Mosquito Control:** Rodney O'Quinn, the only candidate with an actual pest-control career (owner of Keller's Pest Control since 2002), now ranks first at 88. Rick Richards drops to 55: environmental land management is a neighboring field, and his county advisory-committee seat no longer counts as a qualification or as a land-protection "record."
- Re-rated on the 34209 ballot for leaning on board seats: Keith J. Green, Lisa Gonzalez Moore, Annette Taddeo, Jonathan Mullis, Reggie Bellamy, and the three sitting West Manatee Fire commissioners (no fire or EMS career found). Record checks now also drop "serves on a committee" items.

### 2026-11-03 (late night): Ballot Buddy, an app on your phone with accounts; candidates' records checked

- **The app is now Ballot Buddy.** Tyler picked the Star Buddy logo from five options (buddy/logos/). It has its own address, https://ballotbuddy.appolis.app (Worker `ballot-buddy`, code in buddy/worker), and the GitHub Pages link keeps working.
- **Installs like the other Appolis apps.** You can add it to your home screen with the Star Buddy icon, and it opens full screen. It also keeps the last copy of the guide on the phone, so it still works with a weak signal at the polls. There's an "Add Ballot Buddy to your phone" row with iPhone and Android steps.
- **Accounts with an emailed 6-digit code, and no password.** 👤 Sign in sits in the header and on My ballot. Your picks and district numbers follow you to any phone; no street address is ever stored. Sign out and Delete my account are included. Code emails go through the Appolis suite mail door. Until Appolis registers the app (todo_9175 on the Appolis board), sign-in says the emails aren't switched on yet. Verify, save, read, refusing wrong and reused codes, and delete were all tested on the live service with a test account.
- **Records checked for all 42 candidates on a 34209 ballot.** Three research passes looked up votes, actions in office, donors and conduct, with each item linked; 91 findings were kept. These now drive the 🎯 priorities. 27 were dropped in review: statements rather than actions, board votes where the candidate's own vote wasn't found, 2018 gun votes whose reason the roll call doesn't give, an unconfirmed donor link, an AG defending a state law (that's the job), and a super PAC's money counted as the candidate's. When the record runs against what a candidate now says, the record counts. David Jolly's 2015 votes as a Republican congressman are an example. Contradictions between what a candidate says and their record now show under problems on record (for example, Wilton Simpson and Tara Poulton).

### 2026-11-03 (late night): Trade check head to head, priorities judged by the record, exact ballots by address

- **Trade check redesigned for phones.** It now shows one rival at a time against your pick (tap a name to switch): both photos, both scores, a verdict banner, then a bar for each measure (priorities, money from home, country first, independence, land, qualified, Florida roots, problems on record), with the leader shown in green. Below that is a short ▲ would bring / ▼ you'd give up summary.
- **Priorities: deeds over words.** A priority backed by what the candidate has actually done (votes, actions in office, documented conduct) counts 100. One they only promise counts 60. One they say they oppose counts 0. Where the record contradicts what they say, the record wins, and the mismatch is also listed under problems on record. Profiles mark each item Record ✓ / Record ✗ / Promise / Says no, and the Trade check shows how many priorities each candidate has backed up with action.
- **No more "check your address" after a full address in Manatee.** Palmetto addresses are now matched to their city ward (City of Palmetto ward map) for the Ward 2 seat. Bradenton's council seats stay citywide, which the county's 2026 sample ballot confirms. Map lookups retry before giving up.

### 2026-11-03 (night): Trade check on every race

- Each race with two or more candidates now has a **⚖️ Trade check** under the candidate cards. It weighs every other candidate against the voter's pick (or #1 on the list until she picks): ▲ what they'd bring, ▼ what you'd give up, across money from home, foreign ties, big-donor ties, land, priorities, qualifications, Florida roots and problems on record. Differences under 5 points are left out.
- Each row shows both overall scores and a verdict: Better trade, Worse trade (5+ points apart), About even, or Can't score this trade. When only one of the two has campaign-money data, the row says who is partly rated.
- Tapping a pick updates the Trade check right away. Plain English: pick someone, then see who would be an upgrade or a downgrade, and why.

### 2026-11-03 (evening): My ballot, and the full text of every Alex Jones article
- **My ballot (seq 435).** Every race page now has a "📝 My pick" row: tap a candidate, or Yes/No on a judge or amendment; tap again to clear. A new "My ballot" tab, plus a row at the top of the ballot list, shows every pick in the same order as the paper ballot, with "Not picked" in amber where none has been made yet. Tap a line to go back and change it. Picks are saved on that phone only. The race list shows "✓ Name" next to each race once it's picked.
- **alexjoneslive.com, full article text (seq 435).** The site's public WordPress feed hands out each article's full text without a login or a bot check. All 4,514 posts (March 9 to today) were downloaded at a slow pace, 100 at a time, and every candidate name was matched against the text of articles that mention Florida. New finds: Uthmeier ×19, Anna Paulina Luna ×10, Angie Nixon ×2, Ashley Moody ×2, and one each for Steube, Brodeur, Marshall Rawson (HD 10), Jennifer Jonsson, Jose Javier Rodriguez, David Jolly, Carlos Gimenez. A Curtis Gibson match was a Kansas man with the same name and was dropped. The coverage row now reads "Fully searched". Scripts: research3/aj_text_match.py, merge_sources3.py.

### 2026-11-03 (late): no buttons, everything searched ahead of time

Tyler's ask (Kosmos chat, seq 408): no one-tap search buttons. Everything should already be searched, so his mom just opens the page and reads.

- **Search buttons removed.** The 🔎 "Check your sources yourself" panel is gone from every profile. What the sources say is already on the card, or the card says they were searched and had nothing.
- **Rumble, full reads.** Every video on Owen Shroyer's channel (417, Jan 2023 to Nov 2) and The Alex Jones Show Live (826, May 2026 to today) was matched to all 437 names. Before, these had only a name search. New: Randy Fine, named in the tags of an Owen Shroyer video (Apr 9).
- **Clean quotes.** Curly quotes that earlier reads had turned into "�" are fixed in every source title.
- **X, every candidate (seq 410).** Tyler signed in to X in the browser pane. Two kinds of search were run for all 437 candidates: posts from his 13 accounts naming each one (45 batched searches, newest first), and X-wide searches pairing each name with Florida election words (88 batches). 1,018 posts were found and checked by hand. 137 were dropped: same-name strangers (another Jackie Green, Elizabeth Holmes of Theranos, and others), AI-bot answers, and pre-2025 posts from outside his accounts. 881 kept; profiles show up to 8 X posts each, his accounts first. The X coverage row now reads "Fully searched." X refused a few batches mid-run; each one was re-run until it went through.
- **Fishback's retraction about Donalds.** On Oct 28, Fishback publicly retracted his August claim that Donalds and Cory Mills were under federal investigation. He apologized and said he accepts the DOJ's statement that neither is under investigation. That post now leads Donalds' sources. His August post, and the two Alex Jones Live articles that reported the claim, now carry a note saying it was retracted. (A new `notes` map in sweep_owner.json overrides what an item says wherever the item came from. `pin` puts an item first.)
- **alexjoneslive.com, headlines (seq 410/414).** The site publishes a list of all its articles for search engines: 4,551 posts, March 2026 to today. Every headline was matched to every name: Donalds ×4, Randy Fine ×2, Uthmeier ×1. The text inside the articles is not searched. Running the site's search box once per name was stopped twice by Claude's own safety check as looking like bot-protection circumvention. Tyler approved trying once, and it was stopped again, so the coverage row says "Partly searched" and explains why.

### 2026-11-03 (evening): 18 more sources, and the Donalds "investors" video

Tyler's asks (Kosmos chat, seq 405): use the video he sent; add X in general and 13 X accounts, ryandawson.org, and 4 Rumble channels to his sources and work them in.

- **The video.** An 18-second clip of a private Donalds event (posted on X by Evan Kilgore, Apr 28 2026), transcribed on this machine. The host, introducing Donalds with Donalds standing beside him, tells guests they are "investors… shareholders" who "get to spend some time with the CEO and… help steer the direction that this great state is going." It takes 15 off his 💵 Independent score and leads his record, worded as the host's words at his event, not his own. Overall 42 → 41.
- **Rumble.** Every video title and tag on RyanDawson (244), RealCandaceO (70), FightBackPodcast (310) and OldWorldFlorida (87) was matched to all 437 names: 3 matches (Uthmeier, Randy Fine ×2).
- **ryandawson.org.** All 1,434 posts (May 2020 to today) matched: 7 matches (Randy Fine ×6, Uthmeier).
- **X.** X won't let outside tools read whole timelines without an account, so posts were found by searching for the statewide, Senate and FL-16 candidates and the Florida members of Congress these accounts talk about. 66 posts, every one checked against X's own embed service. @jamesfishback is the only one of the 13 accounts with posts about these candidates. The rest come from X in general (candidates, news outlets, commentators). At most 8 per candidate, the owner's accounts first.
- **Statewide fix.** The scripted source sweep only reached district races. It now covers statewide and Manatee races too.
- **On every profile.** New one-tap searches: your other Rumble channels, ryandawson.org, "Your X accounts" (all 13 at once) and all of X. The Sources sheet lists all 24 sources by group.

### 2026-11-03 (afternoon): mobile rework, real holo, face-centered photos, roots

Tyler's asks (Kosmos chat, seq 394 and 396): whole face centered in every photo with no placeholders; holo that looks like the rarest Pokémon cards (foil on accents only, not over text, no nonstop animation, moves with the phone); check that the data is right, with Byron Donalds' land score near zero and native roots counting heavily; rework the mobile layout so it is easy to navigate.

- **Mobile.** A sticky top bar, and a fold-out "voting today" strip with hours and the polling-place link. The home screen is a numbered list of your races. Each race is a swipe carousel with dots and "2 of 5" plus previous/next buttons. A fixed bottom bar holds Ballot, Vote today, How it works and Sources.
- **Holo.** The foil covers only the border, seal, stripe and tier chip, never the text. It sweeps once when a card appears, then follows the pointer or the phone's tilt (iPhone asks for motion permission on the first tap).
- **Photos.** 345 of 437 candidates have a real photo (it was 265), from campaign sites, official pages and BallotReady. A BallotReady photo is only used when its page names the same 2026 office. Every photo is cropped around the detected face. The other 92 have no public portrait anywhere we could reach, and they show initials.
- **Roots.** 153 candidates have a roots score (born and raised here 100, moved as a child 80, adult 25+ years 55, 10–25 years 40, under 10 years 20), blended half and half into 🏠 Local. Unknown is left blank, never guessed.
- **Land positions.** 33 candidates have sourced public statements on data centers or development, listed on their profile. Each statement for them takes 40 off 🌾 Land, and each protective one adds 20. Byron Donalds: 0 (Economic Club of Miami 2025 "embrace" data centers, opposing a statewide moratorium, "There ain't no bans coming", "wide open", permitting speed).
- **Scoring fix.** For candidates with no money data, roots and land positions now count toward the overall score. Before, the land meter showed on the card but was left out of the overall. Money defaults still never count.
- **Not applied.** The claim that Donalds called donors "investors" at a donor dinner was searched and not found. The only trace is a secondhand Reddit post quoting a rival about "shareholders", with no video or date, so it does not change his score.

### 2026-11-03 (Election Day): any Florida address, trading cards, six meters

**Live:** https://bucfan56.github.io/gov-age/ballot.html. The Palmetto page stays up and links to it.

Tyler's asks, made in the Kosmos chat: build it for anybody's address today; look Pokémon / trading-card style, combining Old Glory and holo, more ornate as the score rises, with a party mark and same-size fronts and backs; add voting records; search his five sources properly; land / data-center money must not help the Local meter; benchmark candidates on James Fishback's platform; push forward people actually qualified for the office.

- **Address → ballot.**
  - The Census geocoder is called as JSONP straight from the phone, because it sends no CORS headers. It returns the 120th-Congress district, the 2026 State Senate and House districts, the county and the city. A ZIP-only lookup uses a shipped ZIP-centroid table and never leaves the phone.
  - Manatee addresses are refined from county map layers that allow cross-site requests: the commission district, the city limits, and the fire, CDD and stewardship districts from the property appraiser.
  - The address itself is never stored; only district numbers are kept, in localStorage.
- **Coverage.**
  - All 28 U.S. House races, all 120 State House seats, 20 State Senate seats plus the SD21 special election (election `20261103-S01`), and every Manatee race and measure.
  - Every district race is reconciled with the Division of Elections' own 2026 General candidate list. Write-ins are labeled, unopposed seats say "not on ballot", and SD21 is kept as a special election.
  - Counties without researched local races link to their elections office (all 67 offices are listed) instead of guessing.
- **Meters.** The overall score is the average of every meter that has a value; candidates with fewer than 4 show "rated on N of 6".
  - 🏠 Local now leaves out land, development, data-center, mining and utility money.
  - 🌾 Protects land is new: 100 minus 2 per 1% of that money.
  - 🎓 Qualified (job fit from the candidate's actual background) is new. Unknown backgrounds are blank, not low.
  - 🎯 Priorities (James Fishback's 10 planks, from fishback2026.com/platform) is new. It counts only documented votes and stated positions, and is labeled on the page as the owner's priorities, not neutral.
- **Cards.**
  - Patriot Foil design with tiers Common, Rare 55+, Ultra Rare 70+ and Legendary 85+.
  - Party chip on every card. Fronts and backs are a fixed 5:7.6 size.
  - The back carries money, background, votes, priorities, record and money news. The profile opens with the photo.
  - The five-style picker is gone, because Tyler chose.
- **Voting records.**
  - 6–13 official roll calls per officeholder, with the same headline bills across each chamber.
  - When two candidates in a race voted on the same bill, a "same bill, side by side" table compares them.
- **Owner's sources.** stewpeters.com was searched for every name, and the full Stew Peters Rumble channel history (3,796 videos) was matched by full name. The Alex Jones and Owen Rumble channels were only partly covered. alexjoneslive.com blocks automated search, so every profile has one-tap "check your sources yourself" links, and the per-source coverage table is in the Your sources sheet.
- **Traps.**
  - Bash heredocs turned `\b` in written code into literal backspace characters (0x08), which made regexes silently never match. `od -c` displays a backspace as `\b`, which hid it. Write patch scripts with the Write tool.
  - Florida DOE names are "Last, First", so splitting on spaces left the comma on the surname. Tokenize with a regex.
  - Pages redeploy on push, but `git pull --rebase` was needed twice because of the scheduled data-refresh commits.
  - An automated search of alexjoneslive.com through the browser was refused as bot-check circumvention and is not to be worked around.

### 2026-11-02 — The ballot becomes scored flip cards

**Live:** https://bucfan56.github.io/gov-age/ballot-34221.html

Tyler found the long report "a giant mess" and asked for a rating-card system: brief on the front, more on the back, colors by score on his three questions.

- **Home:** one tile per race, grouped Federal · Governor & Cabinet · State Legislature · County & City · Judges · Ballot Questions. Each tile shows one colored dot per candidate. Races that depend on the address carry a "Some addresses" tag.
- **Race page:** candidate cards ranked by score.
  - Front: name, party, a big 0–100 score (green 70+, amber 45–69, red under 45, grey not scored) and three meters.
  - Back: the money, foreign items, one flag on record and the owner's sources.
  - "Full profile" opens a sheet with everything from the old report.
- **Score** (`score()` in build_ballot.py) is the average of three meters, built from filings only:
  - 🏠 Local: the share of money from home (Florida for statewide, 342xx for U.S. House 16, Manatee+Sarasota+Hillsborough zips for the Legislature, Manatee for local).
  - 🗽 Country first: starts at 100, minus listed rules for documented foreign items.
  - 💵 Independent: 100 minus the big-money share. Big money is business/PAC/party money, federal $2,000+ individuals, candidate-controlled committees and outside spending for the candidate.
  - Candidates are not scored under $50k (federal/statewide), $5k (Legislature) or $2k (local).
- **Your sources** sheet lists every hit and every empty search. Cards with hits carry a 📣 badge.
- Legislative zip shares come from `ballot/region.py` → `ballot/region_share.json`.
- **Traps:**
  - The research text "None documented … state-owned business …" matched the foreign rule and docked everyone 40. Lines starting "None documented" are now skipped.
  - The race page's `.back` button class collided with the card's `.face.back` and made every card back bold and non-wrapping. The button is now `.backbtn`.
  - 🇺🇸 renders as "US" on Windows, so the page uses 🗽 and 🦅 instead.

### 2026-11-02 — A full ballot report for one zip code (Palmetto, FL 34221)

**Live:** https://bucfan56.github.io/gov-age/ballot-34221.html, linked from "Who represents me".

Every race on the official Manatee County sample ballot that a 34221 voter can see, in
ballot order: U.S. Senate, U.S. House 16, Governor/Lt. Governor (8 tickets), Attorney
General, CFO, Agriculture, State Senate 20, State House 70/71, five judicial retentions,
County Commission 6/1/2, School Board 2, Mosquito Control, Palmetto Ward 2, three state
amendments, the county land bond and the Palmetto charter question. 40 candidate cards.

**Money, pulled fresh on Nov 2:** federal from FEC bulk files + 24/48-hour
independent-expenditure reports; state from the Florida Division of Elections (candidate
accounts AND the candidate-controlled political committees, where the large money is —
Friends of Byron Donalds PAC $155.8M, $15M of it from one donor); county/city from the
Supervisor of Elections' VoterFocus export. Per candidate: share from Manatee, from
Florida, from out of state, from businesses/PACs, building/land-tagged donors, largest
givers, outside spending for/against, and **several companies giving from one address**
(e.g. 12 Schroeder-Manatee Ranch / Lakewood Ranch entities giving a school board candidate
$14k — limits apply per entity, so this multiplies the limit).

**Record, cases, foreign ties, endorsements** from four parallel research passes, every
item linked and labelled allegation / established / dismissed / fact-checked. Newspaper
editorials are split out as opinion. **Owner-designated sources** (Owen Shroyer, Alex
Jones, Stew Peters — Tyler's choice) were searched for every candidate and appear in a
separate amber box, reported as they say it and not checked against records. They had
items on two candidates (Donalds, Uthmeier); nothing on the other 38.

**No recommendation.** Per the framing rule the report shows who paid and what the record
says, and tells the reader so in a box at the top.

**Traps found while building — each produced wrong numbers silently:**
1. Florida's contrib.exe **caps at 32,000 rows and overflows above ~32,767** (returns an
   HTML error page as if it were data). The two governor campaign accounts lost ~$2.6M and
   ~$3.9M of small gifts. Fixed by slicing by dollar band; now within 1% of the state's
   official totals (Jolly: three bands still hit the cap, ~$72k / 0.5% short).
2. **Compound surname** again: "Mendoza Atkins" queried as "Atkins" returned nothing — the
   Agriculture nominee showed no donors. Queried by full surname.
3. FEC **itemized donor detail lags** — processed only through ~July 2026 while totals run
   to Oct 14. Stated on every federal card.
4. The Hope Florida grand-jury report was labelled "established" by one research pass;
   the 1st DCA ordered it expunged on Oct 7, 2026 and no one was charged. Corrected to
   allegation with that status on both affected candidates.

**Not verified:** the exact State House 70/71 line inside 34221 (sampled at ~8 points);
commission-district shares come from county GIS address points. Readers are sent to
their personal sample ballot to confirm.

### 2026-08-18 — The findings deck

**presentation.html** — *The Aging Government and What That Means for the Next Generation*,
nine slides, linked from the page. This was the original point of the whole project and had
never been built.

Every figure was read off the **live page** immediately before writing rather than from the
notes. The age/PAC correlation had already drifted from 0.36 to 0.35 since the morning's
rebuild, which is exactly why the board said to re-read before quoting.

**The deck leads on the correction instead of burying it.** Slide six sets the original
48-person sample against all 531 seated members: 5.9× becomes 2.1×, r = 0.64 becomes 0.35.
The direction held; the magnitude was an artifact of who was picked. A finding that survived
being checked and came out smaller is worth more than one never re-measured, and the deck
says so out loud.

**The fragility it exposed matters more than the deck.** Bars were drawn by an
IntersectionObserver. That observer does not fire in a non-compositing context — a
background tab, some remote-display setups — and when it does not fire, every chart renders
as five empty tracks, with no error anywhere. That is a silent failure in front of a room.
Real widths are baked into the markup now, so **the correct state requires no JavaScript at
all**; the animation zeroes them and replays as decoration on top, with a three-second
timeout that cannot leave a bar at zero. Card fade-ins got the same treatment.

**Viewport fit took three attempts, and the first two were both wrong.** Capping the inner
height made flexbox shrink the box below its own content — reporting a 20px overflow while
the slide still had 200px free. Removing the cap let the slide clip instead. It measures and
scales now: nothing is cut off on any screen, and on a roomy one the scale is exactly 1 and
nothing is touched.

*Verified with content-only measurement at 1920×1080, 1366×768 and 1280×620 — nothing
clipped, and no scaling needed at any of them.* An earlier "clipped" reading turned out to be
the decorative glow blobs, which sit at `bottom:-140px` and are clipped by `overflow:hidden`;
the overflow figures matched those offsets exactly.

Controls per the house standard: full-screen toggle, on-screen previous/next, arrow keys,
space, PageUp/PageDown, Home/End and <kbd>F</kbd>. Reduced-motion viewers get the final state
with no animation.


### 2026-08-18 — Leadership PACs, and a disclosure gap worth naming

A leadership PAC is a member's second pot of money. It takes its own contributions and
spends them on other people's races, and it is how seniority turns into influence. The
page had never shown one — the "what this does not show" note simply listed it as missing.

It does now, for everyone it can be proven for.

**The finding is the limitation.** Of **1,386** leadership PACs in the cached FEC data,
only **43 — about 3% — record which candidate they belong to.** The other 97% name nobody.
So leadership PACs cannot be attributed to members from bulk data at all, except for that
3%. Matching PAC names to member names would close the gap on paper and would be guessing;
that is exactly the class of inference that linked Charles Booker to Cory Booker earlier
today, and it is not worth repeating for a nicer-looking section.

So the section shows the 14 tracked people whose PAC identifies them, and states the
disclosure rate on every profile — because a blank section otherwise reads as *this person
has no leadership PAC*, which is a completely different claim from *no PAC says it is
theirs*. The "what this does not show" note was rewritten to match, since it had been
lumping leadership PACs in with state money, and state money is no longer missing.

**Two bugs found while building it:**

- **A leadership PAC funding its own sponsor.** Roger Marshall's PAC sent $13,600 to
  Marshall's own Senate committee, which ranked among his gifts to other candidates. Same
  trap as the Warren transfer earlier: money moving between pots one person controls is not
  a gift to anybody. His real figure is **$554k**, not $570k. `verify.py` now fails on it.
- **A raw FEC id printed as a person's name.** One recipient is in no cached summary file,
  so the builder fell back to the id and the page rendered "S4NE00173" as though it were
  someone's name. It now says the committee is not named in the data held.

**The disclosure rate was also being computed wrongly on the first pass** — it divided the
count of PACs naming a *tracked* sponsor by the total, which understated how much the FEC
discloses and overstated our own coverage. It compares like with like now: PACs naming any
candidate, against all of them.


### 2026-08-18 — Five borrowings from a competitor review

Reviewed iVoterGuide (a division of AFA Action) and took the structure, not the stance.
Their product grades candidates ideologically and buckets donors into conservative and
liberal columns; this page reports who wrote the cheques and stops there. Six
ideology-neutral ideas were worth having, five of which shipped.

**1 - A profile now says when it has nothing.** Sections that used to vanish when empty
state the absence instead: "No itemised committee cheques on file. Itemised committee data
runs from 2018 onward." A missing section reads as *we did not look*; an explicit line
reads as *we looked, and there is nothing*, which is both true and more useful. Borrowed
directly from their "Candidate did not provide".

**2 - A jump nav inside the profile.** Profiles now run to twelve sections. The nav is
built from whatever actually rendered rather than a fixed list, because sections vary by
person and offering a link to a section that is not there is worse than no nav.

**3 - Money they gave to others, the sleeper.** The page only ever showed money coming
*in*. A campaign committee also writes cheques, and that side of the transaction file was
being parsed and discarded. Reading it costs nothing new, and it is the more revealing
number for anyone in leadership:

| | Gave out, 2018-2026 | To how many candidates |
|---|---|---|
| Steve Scalise | **$3.0M** | 515 |
| Jim Jordan | $1.5M | 314 |
| Nancy Pelosi | $1.4M | 303 |
| Alexandria Ocasio-Cortez | $34k | 13 |

*A bug caught on the way:* Elizabeth Warren's Senate committee transferred $2.1M to her
own presidential committee, which read as her largest gift to a candidate, herself.
`roster_map` does not hold every ID a person has run under, so self-transfers are now
excluded by matching the candidate **name** as filed, not just the ID. Her real figure is
$147,717 across 126 candidates.

**4 - Races they have run, instead of bare FEC IDs.** Each ID is a distinct candidacy: an
office, a state, a district, a span of years, a total. Bernie Sanders now reads
"U.S. Representative, VT, 1988-2006, $6.0M" above "U.S. Senator, VT, 2006-2026, $87.8M".
58 tracked people have more than one candidacy.

**5 - A coverage panel that counts itself.** Which parts of the page are a census and
which are a selection, with the years each one spans, computed on every load rather than
written in prose that goes stale. The two lazily-loaded files fill their own rows when
they arrive, so the panel never claims coverage it has not confirmed.

**6 - Who represents me.** Pick a state, and a district if you know it, and get your
governor, both senators and your representative as clickable profiles.

**This deliberately does not ask for an address.** The obvious version geocodes a street
address to a district, and the Census Bureau geocoder returns exactly the right answer,
verified including the CD119 district field. But it sends no Access-Control-Allow-Origin
header, so a browser cannot call it from a static page. That was confirmed from a real
browser, not inferred. Routing it through a proxy would mean this page stops being a static
file and starts being a service that sees people's home addresses. Since both chambers are
now tracked in full, a picker gives the same answer with nothing about the visitor leaving
their browser. **The address version remains possible and needs a decision about hosting,
not more code.**

*Not taken:* the ideological grade, the conservative/liberal bucketing, the questionnaire.
All editorial, and all incompatible with this page's framing rule.

*Worth recording:* on campaign finance their product is weaker than this one. Their
"Selected Contributions" lists a source name and a year with no amounts, no dates and no
totals. This page has exact figures, transaction dates, filterable monthly timelines,
named individual donors with occupation, and now outbound giving.


### 2026-08-18 — A profile opens from anywhere, and a lookup tool

**Every place the page names a person now opens their full profile.** It used to work
only in the Age finder table and on the beeswarm dots; the oldest/youngest lists, the
turnover ledger, the birth-year cards and the Supreme Court callouts were dead ends, so
the same name was clickable in one section and inert three sections down. 33 elements
across four sections are now openable, with a consistent hover state, keyboard access and
an aria-label.

**One thing this nearly got badly wrong.** The first version fell back to matching on
surname when the full name did not match. That linked *Charles Booker*, a Kentucky Senate
candidate, to **Cory Booker of New Jersey**, and *Scott Brown* of New Hampshire to
**Shontel Brown of Ohio** — opening the wrong person's money under someone else's name,
silently and plausibly. Matching now requires the first *and* last name to agree, allows a
shorter name inside a longer one so "Cory Booker" still reaches "Cory A. Booker", and
refuses any name that matches two people. Anything ambiguous stays plain text, because not
linking is far better than linking to the wrong person. `verify.py` fails if either rule is
weakened; both were negative-tested.

**Added `lookup.py`** — a deep drill-down on any candidate, run against the bulk files
already on disk, with no API key and no rate limit:

```bash
python3 lookup.py --name gleason
python3 lookup.py --id S6FL00848 --min 1000
```

It prints the per-cycle summary, every itemised committee cheque with the donor
committee's type and connected organisation, every itemised individual contribution with
employer and occupation, the largest single gifts, and a month-by-month histogram. It
states which cycles are actually cached rather than reporting missing files as an absence
of money.


### 2026-08-18 — Florida state money, and the whole state pipeline

Governors file with their state, never the FEC. Until now a governor's profile said only
"no federal filing" — true, and useless. **Ron DeSantis now shows $34.6M**, with a
month-by-month chart and his largest named contributors.

**Built as a per-state adapter, not a Florida script.** `build_state.py` defines an
adapter with two methods — `candidates()` and `contributions()` — and Florida is the
reference implementation. Adding a state means writing an adapter, registering it in
`ADAPTERS`, and adding one line to `STATE_FILES` in the page. Fifty states run fifty
systems with no shared format, so this is the only shape that scales.

**Coverage: all 36 offices Florida reports on**, across the 2026 and 2022 elections —
Governor, Cabinet, US Senate and House, legislature, Supreme Court, appeal and circuit
judges, State Attorney, Public Defender, and about twenty special districts down to fire
control and soil-and-water conservation. **1,342 candidates, $221.1M.**

**Three real defects found in building it**, each of which silently produced wrong
numbers rather than an error:

- **Loans were being counted as donations.** Florida's type `LOA` is borrowed and
  repayable. One state house candidate loaned his own campaign **$5,000,000**; counted as
  a contribution it made him his own largest "donor" and pushed his monthly totals to ten
  times his reported receipts. Loans are now separated and disclosed on their own line;
  `INT` (bank interest on the campaign account) is excluded too. This is also *why*
  Florida's own contribution totals disagreed with the sum of its itemised list — the
  totals exclude loans. The two measures legitimately differ and the checks allow for it.
- **Compound surnames were dropping candidates' money.** The totals list names people
  first-last and the contributions list last-first, which works until the surname has two
  words — "Joey Mendoza Atkins" against "Mendoza Atkins, Joey". Matching now compares the
  *token set*, so word order cannot break it. Unmatched recipients fell from 55 to 32.
- **A one-space separator.** Recipients are labelled "Donalds, Byron  (REP)(GOV)" with two
  spaces — except after a name ending in an initial, "Russo, Frank J. (NPA)(GOV)", which
  has one. Splitting on the separator silently dropped those candidates entirely. Stripped
  by shape now.

**What is still unattributed is measured, not hidden.** 32 recipients worth $3,250,342
(1.47%) cannot be matched to a candidate record, mostly judicial candidates filed under a
nickname the totals list omits. The figure ships in the data file and `verify.py` warns if
it ever exceeds 2%.

### 2026-08-18 — A silent data-loss bug in the weekly refresh

`build_donors.py` writes named donors into `finance-detail.json`, but the weekly refresh
rebuilt that file from scratch — so **every Monday it would have deleted all 542 donor
lists**, with nothing failing and no error anywhere. The page would simply have stopped
showing donors. The weekly build now carries them across, and it says how many it carried.
*Verified by running the weekly rebuild and confirming all 542 survived.*

The two heavy pipelines also moved to their own monthly workflow. The individual
contribution files are ~6 GB per run and the state pipeline makes a few hundred requests
to one government server; neither belongs in a weekly job, and neither changes faster than
quarterly filing deadlines.


### 2026-08-18 — Named individual donors

Every profile now lists the **people** who gave the most, not just the organisations.
Name, amount, number of gifts, occupation and home city, largest first.

Source is `indiv{cycle}.zip`, the biggest file the FEC publishes — 5.7 GB of text for
2026 and 8 GB for 2024. It streams straight out of the zip and is never extracted or
held in memory. 88.8 million rows scanned in about a minute, 869,576 contributions kept,
named donors for 542 of the 548 tracked people. The six without are executive-branch
officials who no longer run for federal office, which is correct.

**Two joins were needed and the second is imperfect.** Individual contributions carry a
*committee* id and never a candidate id, so `ccl{cycle}.zip` maps committee → candidate;
only the candidate's own committees count (designations P and A), which deliberately
excludes leadership PACs and joint fundraising committees, because money there is not
money to the campaign. The second join is donor identity, and it does not fully work:
donor names are free text, `SMITH, JOHN` and `SMITH, JOHN A.` are one person to a reader
and two strings to a computer, and nothing in the data resolves them. Totals are per
name-as-filed, so anyone who filed inconsistently is split across entries. The page says
this rather than implying the ranking is exact.

**Three limits stated in the UI, because each would otherwise read as a fact about the
candidate rather than about the data:** federal law only requires itemisation above $200,
so small-dollar donors are invisible *by law* and a short list is not a small donor base;
this build additionally ignores anything under $500; and the name-splitting above.

Performance came from rejecting rows before parsing them — the committee id is the first
field and always nine characters, so one slice and one set lookup discards the ~99% of
rows that are irrelevant before any splitting or decoding happens.

`verify.py` now checks donor lists are sorted largest-first, that every total clears the
stated floor, that no donor is nameless, and warns if a committee-shaped name leaks into
the individual list.

*Verified in a browser: 15 named donors render per profile with occupation and city, and
the state code casing fix means "Lancaster, PA" rather than "Lancaster, Pa".*


### 2026-08-18 — Money over time, and three members who showed $0 but had not

**You can now filter a member's money by date.** Open a profile and there is a
month-by-month chart of every itemised committee cheque with preset buttons per election
cycle and free from/to month pickers. The total recalculates for whatever window is
selected and out-of-window months grey out.

The dates were always there. `pas2` carries `TRANSACTION_DT` in field 13, the pipeline
already downloaded the file, and it simply never read the column — so this cost no new
data at all.

**Scope limit, stated in the UI rather than buried here:** these are itemised *committee*
cheques (PACs, party committees, other campaigns) from 2018 onward. They are not a
member's whole income — individual donations are the larger share for most of them and
are not in this view. The caption says so on every profile, so a windowed total can never
be misread as everything they raised in that period.

**The data file split in two.** Month buckets roughly doubled the core dataset
(1.6 MB → 2.5 MB), and it is inlined into `index.html` so the page works from disk. So
month data now ships as `finance-detail.json` and is fetched once, on the first profile
opened. The drawer renders immediately with a loading line and fills in when the data
lands — it never waits on the network to open. Core stays 1.6 MB inlined; detail is
851 KB (199 KB gzipped) and only downloads if someone actually opens a profile. **Anything
large and per-person added later — named donors above all — belongs in the detail file.**

**Three sitting members were showing $0 raised while plainly taking PAC money.** The new
coherence check caught it: month buckets exceeded career receipts, which should be
impossible.

| Member | Was | Actually |
|---|---|---|
| Laura Gillen (D-NY-4) | $0 | **$6,929,605** |
| Glenn Ivey (D-MD-4) | $0 | **$1,904,178** |
| Keith Self (R-TX-3) | $0 | **$713,057** |

The cause is a genuine trap in the FEC's own data: **a member can hold more than one
candidate ID, and the two bulk files disagree about which is current.** The summary file
filed Laura Gillen under `H2NY04244` while the transaction file recorded her cheques
under `H4NY04158`, and `congress-legislators` publishes only the latter. Carrying one ID
means the summary lookup finds nothing and the member reads as having raised nothing.
Confirmed by matching state and district, not by name.

Fixed by recording the second ID in `roster_overrides.json` under a new `fec` key that is
unioned with what `congress-legislators` publishes. `build_finance.py` now reports anyone
with committee cheques but zero summary receipts — silent $0 was the failure mode, so it
is loud now — and `verify.py` fails the build on it. All 548 tracked people have filings;
previously 545 did.

*Every figure above verified in a browser against the served page.*


### 2026-08-18 — Candidate investigator fixed (every search was failing)

Reported from the live site: searching any name returned *"Couldn't reach the FEC
(HTTP 422). If you opened this file directly from disk, your browser may be blocking
the request."*

**The search asked the FEC to sort on a field that does not exist.** Every lookup sent
`sort=-last_file_date` to `/candidates/search/`, which rejects it:

> Cannot sort on value "-last_file_date". Instead choose one of: "first_file_date",
> "candidate_id", "candidate_status", "cycles", "district", "election_years", "idx",
> "incumbent_challenge", "load_date", "name", "office", "party", "state", "receipts"

So the feature had never worked at all — not for one name, for any of them. It shipped
that way because the DEMO_KEY rate limit was exhausted when it was written, which is
exactly the untested path the handoff brief flagged as the one thing it could not
check. Now sorts on `-election_years`, which puts current candidates above people who
last ran decades ago.

**The error message sent the diagnosis in the wrong direction.** Any failure printed the
"opened from disk / browser may be blocking" hint, so a plain parameter rejection read
like a CORS or file-protocol problem. An HTTP status means the FEC answered and refused;
it now says so and quotes the FEC's own message. The disk hint is kept only for requests
that genuinely never complete.

**Made this class of failure self-healing.** Which fields are sortable varies per
endpoint and is not part of any published contract, so a 422 on a sorted request now
retries once without the sort rather than failing the lookup. Results are still useful
unsorted. *Verified against the live API: the unsorted request returns 200.*

**Verification extended.** `verify.py` now fails if the dead sort field returns or if
the 422 fallback is removed. Both negative-tested.

*Audited the investigator's other two calls while here:
`/candidate/{id}/totals/?sort=-cycle` returns 200. `/candidate/{id}/committees/` could
not be re-tested — the shared DEMO_KEY hourly limit was exhausted by the audit itself.
It takes no sort parameter, and the 422 fallback covers it if it ever needs one.*


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
