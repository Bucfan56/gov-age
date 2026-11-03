# Research slice output — Florida general election, TODAY Tue Nov 3 2026 (polls close 7 pm ET)

A voter guide used TODAY by real voters (the owner's mother votes in Manatee ZIP 34209 today).
Accuracy beats coverage: never guess a vote, a party, a district or a fact. If you cannot verify it, leave it out
and say so in `gaps`. Every factual bullet carries a source URL. Prefer primary records (congress.gov,
clerk.house.gov roll calls, senate.gov roll calls, flsenate.gov, myfloridahouse.gov, county minutes, FL Division
of Elections, county Supervisor of Elections) and established reporting (Tampa Bay Times, Bradenton Herald,
Sarasota Herald-Tribune, Florida Politics, Florida Phoenix, WUSF, AP, Ballotpedia).

Non-partisan: report what they did and who funds them, never characterise motive, never editorialise.
A donation is a fact about the donor, not proof of anything.

## Write JSON to the file path in your prompt, OFTEN

Rewrite the whole file after every few candidates (valid JSON every time) so partial results can be used
while you continue. Shape:

```json
{"slice": "<name>", "updated": "<ISO time>", "done": false,
 "races": [
   {"id": "fl-usr-07", "office": "U.S. House, District 7", "district": 7, "kind": "USR|STS|STR|county|city|school|special|judge|measure",
    "sample_ballot_url": "...",
    "candidates": [ <candidate>, ... ]}
 ],
 "notes": ["anything the integrator must know"]}
```

`<candidate>` (same field names as the existing guide; omit empty lists):

```json
{"name": "Full Name as on the ballot", "party": "REP|DEM|NPA|LPF|NP|...", "incumbent": true,
 "fec_id": "H6FL07123 (federal only, from FEC)", "fl_doe_name": "name as filed with FL DOE (state races)",
 "photo": {"url": "direct image URL (Wikimedia Commons preferred, else Ballotpedia s3 headshot, else official legislature/county portrait)", "credit": "Wikimedia Commons|Ballotpedia|Florida Senate|Florida House|..."},
 "bio": "<= 50 words: who they are, jobs, offices held",
 "local_ties": "where they live / how long / roots in the district",
 "votes": [ {"bill": "HB 1 (2025)", "what": "one plain sentence: what the bill does", "vote": "Yea|Nay|Not voting",
             "date": "2025-03-14", "chamber": "FL House|FL Senate|U.S. House|U.S. Senate|County Commission|City Commission|School Board",
             "result": "passed 82-30", "url": "roll call / vote record URL"} ],
 "record": [ {"text": "things they did other than votes (bills sponsored, official actions)", "url": "..."} ],
 "money_notes": [ {"text": "big donors, controlled political committees, super PAC support", "url": "..."} ],
 "controversies": [ {"text": "...", "status": "allegation|established|dismissed|resolved|fact-checked", "url": "..."} ],
 "foreign_ties": [ {"text": "documented only; otherwise omit", "url": "..."} ],
 "endorsements": [ {"text": "...", "url": "..."} ],
 "social": {"x": "url", "facebook": "url", "instagram": "url", "website": "campaign site url"},
 "owner_sources": [ {"source": "Stew Peters|Alex Jones|Owen Shroyer", "title": "headline", "says": "what they say, as they say it", "date": "...", "url": "..."} ],
 "owner_sources_searched": ["stewpeters.com", "rumble.com/c/StewPeters", "alexjoneslive.com", "rumble.com/TheAlexJonesShowLive", "rumble.com/Owen"],
 "gaps": "what you could not find"}
```

### Voting records (the owner asked for this specifically)
For anyone who has held a voting office (Congress, Legislature, county/city commission, school board):
6–10 votes that matter most to an ordinary voter — budget, taxes/property insurance/homeowners, growth &
development & wetlands, guns, immigration, abortion, education/vouchers, condo safety, hurricane recovery,
term limits/ethics, foreign influence (e.g. FL SB 264 Chinese land purchases), and any vote in the news.
Pick the SAME headline bills for everyone in a chamber where possible so voters can compare.
Each vote must come from a roll-call record you actually opened (URL to it). Never infer a vote from party.

### The owner's own sources
The voter designated five sources and wants them checked: rumble.com/Owen, alexjoneslive.com,
rumble.com/TheAlexJonesShowLive, rumble.com/c/StewPeters, stewpeters.com. For each candidate run at least one
search such as `"Full Name" site:stewpeters.com OR site:rumble.com OR site:alexjoneslive.com OR site:infowars.com`.
Record hits as reported (headline + one-line "says"), credited to the source, not checked. Record what was searched.
