#!/usr/bin/env python3
"""Re-inline finance.json into index.html so the page also works offline."""
import re, sys
html = open("index.html", encoding="utf-8").read()
data = open("finance.json", encoding="utf-8").read().strip()
new, n = re.subn(r'<script>var FINANCE_DATA = .*?;</script>',
                 '<script>var FINANCE_DATA = ' + data + ';</script>',
                 html, count=1, flags=re.S)
if not n:
    sys.exit("FINANCE_DATA block not found in index.html")
open("index.html", "w", encoding="utf-8", newline="").write(new)
print("inlined %d KB" % (len(data) // 1024))
