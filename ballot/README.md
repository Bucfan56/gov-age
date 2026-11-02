# Ballot report pipeline (first built for Palmetto, FL 34221 — Nov 3, 2026)

Run from a scratch folder `S` (bulk downloads stay out of the repo):

1. `fed_money.py S/fec26` — FEC 2026 bulk files (weball, cm, ccl, cn, itpas2, indiv26.zip, ie26.csv) -> `fed_money.json`
2. `fl_money.py S/fl` then `fl_analyze.py S/fl S/fl_money.json` — Florida candidate accounts. Watch the 32,000-row cap; slice by dollar band.
3. `pc_money.py S/pc/pc.json "Committee Name" ...` — candidate-controlled political committees (unlimited money).
4. `local_money.py all.csv local_money.json` — county/city, from the Supervisor of Elections VoterFocus CSV export.
5. Research passes write `S/research/*.json` per `BRIEF.md`.
6. `assemble.py S ballot-34221.json` (execs `races.py`, the per-ballot race layout), then `py build_ballot.py ballot-34221.json`.

A new zip code = new `races.py` (races from that county's sample ballot) + the county's local-finance export.
