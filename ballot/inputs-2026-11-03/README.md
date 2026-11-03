# Inputs for the Nov 3, 2026 any-address ballot

`py build_florida.py ballot/inputs-2026-11-03` rebuilds `ballot.html` and `fl/` from these files, except
Legislature money. The raw Division of Elections rows (`fl_all/`, 25 MB) hold donors' street addresses and are
deliberately not committed. Regenerate them with `py ballot/fl_money_all.py <dir>/fl_all` before a rebuild.

- `fed_money_all.json`: FEC bulk summary for every Florida federal candidate (`ballot/fed_money_all.py`)
- `local_money_all.json`: Manatee SOE export summary (`ballot/local_money.py all.csv out --all`)
- `geo/`: ZIP centroid → districts, the 67 county elections offices, and the DOE official 2026 General candidate list
- `research2/`, `research3/`: research slices (shape in `research2/SCHEMA.md`); `sweep_owner.json` is the owner-source sweep
