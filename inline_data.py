#!/usr/bin/env python3
"""Re-inline finance.json into index.html so the page also works offline."""
import re, sys
html = open("index.html", encoding="utf-8").read()
data = open("finance.json", encoding="utf-8").read().strip()
# The replacement is passed as a FUNCTION, not a string. re.sub interprets
# backslash escapes in a string replacement, and the data is JSON written with
# ensure_ascii=True, so any non-ASCII name -- Jesus G. "Chuy" Garcia, Pablo
# Jose Hernandez -- arrives as a \uXXXX sequence and raises "bad escape \u".
# A function replacement is inserted literally, with no escape processing.
new, n = re.subn(r'<script>var FINANCE_DATA = .*?;</script>',
                 lambda _m: '<script>var FINANCE_DATA = ' + data + ';</script>',
                 html, count=1, flags=re.S)
if not n:
    sys.exit("FINANCE_DATA block not found in index.html")
open("index.html", "w", encoding="utf-8", newline="").write(new)
print("inlined %d KB" % (len(data) // 1024))
