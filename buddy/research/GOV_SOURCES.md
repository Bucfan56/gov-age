# Ballot Buddy: government APIs and data feeds (research 2026-11-05)

Tests: one GET each, UA "ballot-buddy-research (claude)", no keys, no sign-ups. "Not tested" = documented only.
Some tests used a 3 KB range request (-r 0-3000), so status 206 means the file exists and starts downloading.

## One shared api.data.gov key (free instant signup at https://api.data.gov/signup/, a person must do it with an email)
Same key works on: api.open.fec.gov, api.congress.gov, api.govinfo.gov (api.data.gov key; also accepts DEMO_KEY), api.regulations.gov, api.sam.gov (SAM has its OWN key from a sam.gov account, not data.gov), api.census.gov (separate Census key), DOJ and many others.
Careful: api.data.gov keys cover FEC, Congress.gov, GovInfo, Regulations.gov, NREL, USDA, etc. Census (api.census.gov/data/key_signup.html) and SAM.gov (account + key in profile) are separate. One key = 1,000 requests/hour per key by default (FEC can be raised to 7,200/h by emailing; ask is the person's).
The owner's "use the FEC API properly" = register one api.data.gov key; that same key then unlocks Congress.gov, GovInfo, Regulations.gov. (Strongest single sign-up.)

## A. Federal

| Name | URL | Holds | Key / how | Rate limit | Tested | Ballot Buddy use | Value |
|---|---|---|---|---|---|---|---|
| LDA lobbying (Senate) | https://lda.senate.gov/api/v1/filings/ (now redirects to lda.gov/api/v1/) ; also /contributions/ , /registrants/, /clients/, /lobbyists/ | Every LD-1/LD-2 filing (client, registrant, lobbyists, issues, amounts, covered positions) and LD-203 contributions incl. lawmaker honoree contributions and gifts | None for read (anonymous allowed, throttled); free token raises limit via lda.gov account (person does) | Anonymous low; documented ~15/min anon, higher with token | filings 200 JSON, count 2,003,390; contributions 200 JSON, count 676,888 | Who lobbies, who pays, which firms give to which member, revolving-door lobbyists | HIGH |
| FARA eFile API | https://efile.fara.gov/api/v1/Registrants/json/Active | Active registrants, foreign principals, short forms (people), docs, bulk | None | Not documented | Registrants/Active 200 JSON (102 KB); ForeignPrincipals/json/Active path guessed returned 404 (my guess wrong, see https://efile.fara.gov/ords/fara/r/ords/fara-data-api docs); bulk zip URL guess 404 | Members/staff tied to foreign agents; foreign-agent clients | MEDIUM-HIGH |
| Congress.gov API | https://api.congress.gov/v3/ | Members, bills, sponsors/cosponsors, amendments, committees, House roll-call votes (v3 house-vote since 2025), nominations, CRS reports, summaries | api.data.gov key | 5,000/hour | 403 API_KEY_MISSING (confirms needs key) | Sponsorship records, bill text links, member bio cross-ID (bioguide), committee roster | HIGH |
| GovInfo API | https://api.govinfo.gov/ | Bills, Congressional Record, Federal Register, CFR, Statutes, hearings, GAO reports, **Congressional Directory**; bulk at https://www.govinfo.gov/bulkdata | api.data.gov key (DEMO_KEY works) | 1,000/h per key | no key 401 API_KEY_MISSING; with DEMO_KEY 200 JSON listing collections (BILLS 291,982 pkgs) | Congressional Record speeches, GAO reports, bill text; bulkdata needs no key | MEDIUM-HIGH |
| Senate roll-call votes | https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_119_1.xml | Official Senate vote XML | none | n/a | 403 Akamai block (as owner said). NOT worked around. Official alternatives: Congress.gov API senate votes is NOT offered as of my knowledge (House only; not tested); Voteview already in use | Senate votes | (blocked) |
| Senate financial disclosures (eFD) | https://efdsearch.senate.gov/search/home/ | Annual reports and PTRs (scanned PDFs / HTML) | none, but requires clicking an agreement (session cookie); no API | n/a | home page 200 HTML. Not scraped (agreement gate; not tested beyond home) | Senate stock trades and assets; no official bulk. Non-gov mirrors exist (Senate Stock Watcher, unofficial) | MEDIUM (manual/scrape only) |
| Senate gift/travel | https://www.ethics.senate.gov / Secretary of Senate lobbying-disclosure site | PDFs | none | n/a | not tested | low-value, PDF only | LOW |
| SEC EDGAR | https://data.sec.gov/submissions/CIK##########.json ; /api/xbrl/companyfacts/ ; bulk https://www.sec.gov/dera/data | Filings index per company/person (CIK), Form 4 insider trades, 13D/G ownership, proxy (DEF 14A), Schedule 13, Ex-21 subsidiaries lists | None; UA with contact required by SEC | 10 requests/second | submissions/CIK0000320193.json 200 JSON 164 KB. company_tickers.json and insider datasets zip returned 403 (my UA has no contact email; SEC requires one. I did NOT retry or add an email). efts full-text search 403 same reason | Officers/directors and Form 4 insider holdings: links people to companies; candidates who are insiders; sub lists show shells | HIGH |
| SAM.gov Entity / Exclusions / Contract Awards | https://api.sam.gov/entity-information/v3/entities ; /v4/exclusions ; extracts https://api.sam.gov/data-services/v1/extracts | Entities (UEI, legal name, address, **POC names**, business types, CAGE), exclusions (debarred firms/people), FPDS-like contract awards, subawards via other API | Free SAM.gov account then personal API key (person does). Entity extracts public; "FOUO/sensitive" fields need role | 10/day non-federal without role; 1,000/day with registered entity role | 404 with DEMO_KEY (bad auth gives 404 here; real key needed). Not tested successfully | Exclusion check: are candidate-tied firms debarred; contractor POC names match donors/officers | MEDIUM-HIGH |
| USAspending | (already used) | | | | | Better route: bulk "award data archive" per agency/FY at https://files.usaspending.gov/award_data_archive/ ; recipient parent/UEI fields and `/api/v2/recipient/` also cover owners for named parents | | | |
| IRS Tax-Exempt (Pub 78 / BMF / Form 990) | https://apps.irs.gov/pub/epostcard/data-download-pub78.zip ; https://apps.irs.gov/pub/epostcard/990/xml/YYYY/ index CSV; BMF https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf | Every 501(c) and its 990 (officers, directors, key employees, compensation, grants, related orgs), Schedule L insider transactions | None | None stated (large files) | Pub78 zip 200 (30 MB); 2024 990 index CSV 200 (91 MB, 10 cols incl EIN, object id) | Candidates/relatives who run nonprofits, compensation, grants to connected groups; 527/501c4 dark money | HIGH |
| ProPublica Nonprofit Explorer API (non-gov, wraps IRS) | https://projects.propublica.org/nonprofits/api/v2/search.json?q= | Same IRS 990 data, searchable by name/officer | none | not stated | 200 JSON, total_results 190 | Easy officer-name lookup route over IRS data | MEDIUM (non-gov) |
| IRS 527 political org | https://forms.irs.gov/app/pod/dataDownload/dataDownload | 527 filings (contributors, expenditures) | none | n/a | not tested | Political org money outside FEC | MEDIUM |
| Court records | PACER (paid, $0.10/page, not used). CourtListener/RECAP https://www.courtlistener.com/api/rest/v4/ (**non-gov**, Free Law Project): dockets, opinions, judges, **financial-disclosures** | | Free account token for most endpoints (person does) | 5,000/h auth | /courts/ 200 JSON count 3,359 (anonymous). /financial-disclosures/ 401 needs token | Lawsuits naming candidates/firms; judge disclosures | MEDIUM (non-gov) |
| Federal Register API | https://www.federalregister.gov/api/v1/documents.json | All FR docs incl. presidential docs, agency rules, nominations/appointments | None | generous | 200 JSON (10,000 results) | Appointees, pardons/EOs, enforcement notices | MEDIUM |
| Regulations.gov API v4 | https://api.regulations.gov/v4/documents | Dockets, comments (commenter names, orgs) | api.data.gov key (DEMO_KEY works) | 1,000/h; DEMO low | 200 JSON with DEMO_KEY (documents list) | Which firms/members lobby agencies by comment letters | LOW-MEDIUM |
| OFAC sanctions (SDN) | https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.CSV, .XML; legacy https://www.treasury.gov/ofac/downloads/sdn.csv; also Consolidated list | Sanctioned people/entities with aliases, IDs, owners (50% rule text) | None | none stated | SDN.CSV 200 (5.8 MB); SDN.XML 206 ok; legacy path 200 | Screen donors, contractors, foreign principals against sanctions | MEDIUM |
| Trade.gov Consolidated Screening List | https://data.trade.gov (api.trade.gov) | Merged export/sanction lists | free key | | connection failed (000) | Use OFAC instead | LOW |
| DOJ API | https://www.justice.gov/api/v1/press_releases.json | Press releases (indictments, pleas, settlements), all components incl. USAOs | None | n/a | 200 JSON count 275,488 | Search for candidate/official names in DOJ releases (convictions, FCA settlements, FARA/lobbying cases) | MEDIUM-HIGH |
| GAO | https://www.gao.gov/rss/reports.xml (+ GovInfo GAOREPORTS collection) | Reports, bid protests, legal decisions | none | n/a | RSS 200 | Context reports on agencies; weak person link | LOW |
| Inspectors General: Oversight.gov | https://www.oversight.gov (CIGIE) | All IG reports, recommendations; has downloadable/CSV export and a documented-but-undocumented JSON used by site | none | n/a | /api/ 406 "Bad request" (guessed path; no documented public API found). Not further tested | Reports naming contractors/agency misconduct | LOW-MEDIUM |
| House Ethics Committee | https://ethics.house.gov/ | Investigative reports, press statements | none | n/a | 200 HTML only, no API | Public statements on members under review; scrape page lists | MEDIUM |
| Office of Congressional Conduct (formerly OCE) | https://conduct.house.gov/ | Referral reports published after Ethics review | none | n/a | 200 HTML only | Same | MEDIUM |
| Census API | https://api.census.gov/data/2023/acs/acs5?...&for=congressional district | ACS by congressional district; geography; TIGER shapefiles bulk | Census key free (person does) | 500/day w/o key, more w/ key | unkeyed request returned "Missing Key" HTML page (status 200 w/ error page) | District demographics; shapefiles https://www2.census.gov/geo/tiger/ (no key) not tested | MEDIUM |
| OGE (Office of Govt Ethics) | https://www.oge.gov/ | Executive-branch Form 278 / 201 | none | n/a | 200 HTML; no API. Check https://extapps2.oge.gov/201/Presiden.nsf for president/VP (not tested) | Exec appointees disclosure; PDFs | LOW-MEDIUM |
| Treasury Fiscal Data | https://api.fiscaldata.treasury.gov | Debt, spending summary | none | n/a | my path guess 404 (not tested right) | none for BB | LOW |
| CFPB complaints | https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/ | Complaints per company | none | n/a | 200 JSON (18.9M complaints) | Conduct of firms tied to officials | LOW |
| GLEIF LEI (international, **not US gov**) | https://api.gleif.org/api/v1/lei-records | Legal entity ownership: direct/ultimate parent relationships | none | 60/min | 200 JSON, 3.49M records | Corporate parent chains (best free "who owns this company" for big firms) | MEDIUM (non-gov) |
| Beneficial ownership (FinCEN BOI) | FinCEN | Not public; domestic companies exempted by 2025 rule | n/a | n/a | not tested | Not usable | none |
| Google Civic Information (non-gov) | https://civicinfo.googleapis.com/civicinfo/v2/elections | Election dates, polling/contests by address | Google Cloud key | | 403 needs key | Ballot contests by address; representatives endpoint shut 2025 | MEDIUM |
| Open States (Plural, non-gov) | https://v3.openstates.org | 50-state legislators, bills, votes, committees | Free key (person does, openstates.org account) | 10/min default free | 403 needs key | The multi-state legislature route (covers NJ, AL, CA, NC, FL votes) | HIGH (non-gov, but wraps official legislative sites) |

## B. States

| State / item | URL | Real API or bulk? | Tested | Notes | Value |
|---|---|---|---|---|---|
| **CA campaign finance (Cal-Access)** | https://campaignfinance.cdn.sos.ca.gov/dbwebexport.zip | BULK download of whole Cal-Access DB (daily), no key | 206 zip (CalAccess folder), starts downloading | Best state money source here. New CA "Power Search" has no public API | HIGH |
| CA legislature | https://downloads.leginfo.legislature.ca.gov/ (PUBINFO zips: bills, votes, members, committee hearings) | BULK, no key | 200 directory index | Roll call votes included in `vote_tbl`/`bill_motion` data | HIGH |
| CA open data | https://data.ca.gov/api/3/action/package_list (CKAN) | API, no key | 200 JSON | Includes state spending, checkbook-like datasets, controller; search for "Form 700" not tested | MEDIUM |
| CA elections results | https://api.sos.ca.gov/returns/... | Statement of Vote results API (sos.ca.gov results pages) | 500 on my guessed path (not tested properly) | Certified SOV as downloadable xlsx/csv at https://elections.cdn.sos.ca.gov | MEDIUM |
| CA business entities | https://bizfileonline.sos.ca.gov | Search only; paid API (CA SOS "California Business Search API" needs approved key) | Incapsula/bot block page returned; not worked around | Bulk Master Unload paid | LOW (blocked) |
| CA ethics / Form 700 | https://netfile.com/... FPPC | Search pages (FPPC public search), some via Cal-Access | not tested | | LOW-MEDIUM |
| **NC elections results** | https://s3.amazonaws.com/dl.ncsbe.gov/ (ENRS/, Data/, Campaign Finance) | BULK on public S3 bucket, listing works | 200 XML bucket listing | Candidate filing lists, voter files, results by precinct (dl.ncsbe.gov) | HIGH |
| NC campaign finance | https://cf.ncsbe.gov/CFOrgLkup/ | Search + "Export" CSV per query; reports downloads | 200 HTML | No true API; export links per search | MEDIUM-HIGH |
| NC legislature | https://www.ncleg.gov (roll call pages) ; ftp.ncleg.gov | Pages + FTP bulk (bill data/votes) | web 200 HTML; ftp host connect failed (000) | Votes in HTML per bill, scrape | MEDIUM |
| NC business (SOS) | https://www.sosnc.gov | Search only; Cloudflare challenge ("Just a moment") returned 403. NOT worked around | 403 | Bulk by paid request | LOW (blocked) |
| **FL Division of Elections** | https://dos.fl.gov/elections/data-statistics/elections-data/ | Page links to downloads (candidate lists, results files) | 200 HTML; candidate-list path guess 404 | Results at results.elections.myflorida.com has downloadable files | MEDIUM-HIGH |
| FL campaign finance | https://dos.elections.myflorida.com/campaign-finance/ | Database download (tab-delimited extracts) + search | 200 HTML; extract itself not downloaded | Documented "Database Download" tool | HIGH |
| FL Sunbiz business entities | https://dos.fl.gov/sunbiz/other-services/data-downloads/ | BULK quarterly corporate file + daily files (SFTP public creds posted on page) incl. **officers/registered agents** | 200 HTML page | Strong person-to-company link; fixed-width files | HIGH |
| FL legislature | https://www.flsenate.gov ; floridahouse.gov | Pages; FL Senate offers XML/data downloads on some pages | flsenate bills page 200 HTML; api.floridahouse.gov host failed | Voting records in PDFs/pages; no clear API | MEDIUM-LOW |
| FL fiscal / contracts | https://floridafiscalportal.state.fl.us ; FACTS contract system | Search pages; transparency "Florida Has a Right to Know" | host failed (000) | | LOW-MEDIUM |
| **NJ ELEC** (campaign finance) | https://www.elec.nj.gov/publicinformation/gadownload.htm | Downloadable bulk CSVs (contributions, expenditures) | Incapsula bot-block page returned; not worked around | Documented bulk, but guarded; a person in a browser can fetch | MEDIUM-HIGH (blocked to scripts) |
| NJ election results | https://nj.gov/state/elections/election-information-results.shtml | Page with downloadable results files (pdf/xlsx/csv) | 200 HTML | No API | MEDIUM |
| NJ legislature | https://pub.njleg.gov/ ; https://www.njleg.state.nj.us/downloads | Downloads page (bill data, roll call votes files); also NJ Legislature has data files in DBF/Access | 200 HTML (both) | Downloads page documented; files not fetched | MEDIUM-HIGH |
| NJ open data | https://data.nj.gov/ (Socrata) | API, no key (app token optional) | 200 JSON views list | State datasets (some payroll, contracts) | MEDIUM |
| NJ business | https://www.njportal.com/DOR/BusinessNameSearch/ | Search only; no bulk | 200 HTML | Free web search; business records via paid request | LOW |
| NJ checkbook | https://www.nj.gov/treasury/omb/ (NJ Open Public Records / "Transparency Center" spending) | Search pages | 200 HTML | Not confirmed API | LOW-MEDIUM |
| NJ ethics (SEC) | https://www.nj.gov/state/ethics/ | Page path 404; financial disclosure PDFs on SEC site | 404 | | LOW |
| **AL** elections/finance | https://www.alabamavotes.gov ; https://fcpa.alabamavotes.gov/PublicSite/Homepage.aspx | FCPA public site has search + CSV download of results (documented, not tested); Alabama Votes has candidate/qualified lists and results pages | both 200 HTML | No API found | MEDIUM |
| AL legislature | https://alison.legislature.state.al.us | Web app; open data feed not confirmed | 200 HTML | Use Open States | LOW-MEDIUM |
| AL open data | https://open.alabama.gov ; Alabama Open Data portal data.alabama.gov | Checkbook (state spending / contracts) via open.alabama.gov | open.alabama.gov 200 HTML; data.alabama.gov host failed | Search pages, some downloads | MEDIUM |
| AL business | https://arc-sos.state.al.us/CGI/CORPNAME.MBR/INPUT | Search only | 206 HTML | | LOW |
| AL Ethics Commission | https://ethics.alabama.gov | Statement of Economic Interests search | 200 HTML | Search only | LOW-MEDIUM |

## C. MCP servers

| Server | Official? | Evidence | Tested |
|---|---|---|---|
| Census Bureau Data API MCP | YES, published under the agency's own GitHub org (github.com/uscensusbureau/us-census-bureau-data-api-mcp, "connects AI assistants with official Census Bureau statistics"). It is code you run yourself (Docker/Node) with a Census API key; NOT a hosted agency endpoint | GitHub API 200 confirmed repo + org + description | Repo existence only; server not run |
| GovInfo MCP (GPO) | CLAIMED official by a secondary blog; I could not confirm any usgpo repo or hosted endpoint | blog only | Not tested; treat as unverified |
| data.gouv.fr MCP | Official French government (mcp.data.gouv.fr), irrelevant to US | search result | not tested |
| api.congress.gov/mcp | I guessed this URL; returned the same 403 key error as any path (no evidence an MCP exists) | | tested guess only |
| Unofficial (NOT agency-run) | cyanheads/congressgov-mcp-server, bsmi021 Congress.gov, AshwinSundar congress_gov_mcp, brockwebb Open Census MCP, Pipeworx gateway (LoC + 960 sources), a community Data.gov CKAN MCP, GovSpend (commercial, procurement) | search results | not tested |

## Better routes for already-used sources
- FEC: register an api.data.gov key; use /schedules/schedule_a/ with keyset pagination; bulk files for historical. Also FEC "candidate-committee linkage" and Schedule B for vendor payments.
- USAspending: bulk award archive files for FY dumps avoids API throttling.
- Senate votes: Congress.gov API is House-vote only (documented); Voteview remains the road since senate.gov is firewalled.

## Shell / owner-linking highlights
- Person-to-company: Sunbiz officers (FL), SEC EDGAR Forms 3/4/13D + DEF14A, IRS 990 officers, SAM.gov entity POCs, LDA registrants (clients/lobbyists), GLEIF parents. No public beneficial-ownership registry exists (CTA reports are not public).
- Contracts to connected firms: USAspending + SAM entities + FEC Schedule A/B linking by employer/name.

## Not verified
CA/NJ/NC/AL/FL "tested" = landing pages mostly; no state bulk file was parsed. Rate limits are documented values, not measured. Dollar/paid items (PACER, state paid bulk) not tested.
