"""Pour the current app template over the data already in ballot.html, so a screen change doesn't need the research inputs.
build_florida.py stays the way to change the data. Run: py buddy/rerender.py"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
page = (ROOT / "ballot.html").read_text(encoding="utf-8")
data = re.search(r"^const D = (\{.*\});$", page, re.M)
title = re.search(r"<title>(.*?)</title>", page)
desc = re.search(r'<meta name="description" content="(.*?)">', page)
if not (data and title and desc):
    raise SystemExit("ballot.html doesn't have the shape this script expects; nothing was written")
tpl = (ROOT / "ballot" / "app_template.html").read_text(encoding="utf-8")
out = tpl.replace("__TITLE__", title.group(1)).replace("__DESC__", desc.group(1)).replace("__DATA__", data.group(1))
(ROOT / "ballot.html").write_text(out, encoding="utf-8", newline="\n")
print("ballot.html:", len(out) // 1024, "KB")
