# Research brief — 2026 general election (Nov 3, 2026), Palmetto FL 34221, Manatee County

Today is 2026-11-02. A voter in Palmetto, FL (zip 34221) votes tomorrow and wants a non-partisan
read on every candidate on their ballot: commitment to the country and to the local area, any
foreign ties, and big donors / interests that could influence them. Party does not matter to them.
You are researching ONE SLICE of the ballot (listed in your prompt). Use WebSearch and WebFetch.

## What to find for each candidate (public conduct relevant to the office only)
1. bio — who they are, current/prior jobs and offices (<= 60 words).
2. local_ties — where they live/how long, local business, service, roots in Manatee / the district.
   Note carpetbagging facts plainly if documented (moved in recently, lives outside district).
3. record — concrete things they DID: votes, bills, rulings, official actions, business conduct.
   Up to 8 bullets, each with a source URL. Prefer primary records (legislature sites, court
   records, county minutes) and established local reporting (Bradenton Herald, Tampa Bay Times,
   Sarasota Herald-Tribune, Florida Politics, Bradenton Times, Your Observer, WUSF, Florida Phoenix).
4. money_notes — big donors, affiliated political committees (in Florida, candidates' real money
   often runs through a "political committee" (PC) they control — name it and its biggest givers
   if reported), developer / industry / out-of-state money, self-funding, super PAC support.
   Each with a URL. Do NOT characterise motive; state who gave what.
5. controversies — court cases, ethics complaints, investigations, arrests, liens, firings,
   documented false statements. For EACH say whether it is an ALLEGATION or an ESTABLISHED
   finding/outcome, and the outcome if known. URL for each.
6. foreign_ties — ONLY documented facts: foreign-government payments/contracts, FARA
   registrations, foreign-paid travel, business with foreign state-owned firms, donors who are
   registered foreign agents, dual roles. If none found say "none found in public records searched".
7. endorsements — notable endorsers (unions, chambers, developers' groups, police/fire unions,
   advocacy groups, newspapers). These show which interests back them.
8. local_issue_stance — Manatee's dominant local issue is growth/development (the 2024 wetland
   buffer rollback, developer influence on the county commission, flooding after Helene/Milton,
   property taxes). Record their stated or voted position with a URL, if any.
9. owner_sources — the voter designated these five sources as their own trusted sources and wants
   them checked for EVERY candidate:
     - https://rumble.com/Owen            (Owen Shroyer)
     - https://www.alexjoneslive.com/
     - https://rumble.com/TheAlexJonesShowLive
     - https://rumble.com/c/StewPeters
     - https://stewpeters.com/
   Search each for the candidate's name (try WebSearch with site:rumble.com / site:stewpeters.com /
   site:alexjoneslive.com / site:infowars.com plus the name, and WebFetch site search pages such as
   https://stewpeters.com/?s=NAME and https://rumble.com/search/video?q=NAME — for rumble keep only
   results from those channels). For each hit record: source, title, date, URL, and what it says
   about the candidate in <= 40 words, in neutral reported speech ("The segment says ..."). You
   generally can only read titles/descriptions of videos, not watch them — say so where true.
   Do NOT verify, endorse, or debunk these; just record them accurately and attributed. If a
   primary public record directly contradicts a specific claim, add one line noting the record.
   If nothing is found, record "no mention found" for that source. Be honest: most of these are
   national shows and will often have nothing on local candidates — an empty result is a result.

## Rules
- Facts with sources. Never invent. If you cannot find something, say "not found".
- Distinguish allegation vs established. No adjectives like "corrupt", "shady", "great".
- Public conduct only: no home addresses, no family members beyond what they put in their
  campaign, no medical info.
- Be thorough but bounded: ~6-12 searches per major candidate, ~2-4 for minor/no-hope ones.

## Output — write ONE JSON file (path given in your prompt), UTF-8, shaped:
{ "slice": "...", "candidates": [ {
    "name": "", "race": "", "party": "", "incumbent": true/false,
    "bio": "", "local_ties": "",
    "record": [ {"text": "", "url": ""} ],
    "money_notes": [ {"text": "", "url": ""} ],
    "controversies": [ {"text": "", "status": "allegation|established|resolved|dismissed", "url": ""} ],
    "foreign_ties": [ {"text": "", "url": ""} ],
    "endorsements": [ {"text": "", "url": ""} ],
    "local_issue_stance": [ {"text": "", "url": ""} ],
    "owner_sources": [ {"source": "", "title": "", "date": "", "url": "", "says": ""} ],
    "owner_sources_searched": ["list of the five sources you actually searched, and how"],
    "gaps": "what you looked for and could not find"
} ] , "measures": [ ...only if your slice includes ballot measures: {"name","summary","who_funds_yes","who_funds_no","supporters","opponents","urls":[]} ] }
Then reply with ONLY: the file path, the candidate count, and up to 5 one-line notable findings.
