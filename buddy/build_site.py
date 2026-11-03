"""Copy the built app into buddy/worker/site for the ballotbuddy.appolis.app Worker.
Photos stay on GitHub Pages (186 MB); the app points at them by absolute URL when it isn't served from there."""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "buddy" / "worker" / "site"
if SITE.exists():
    shutil.rmtree(SITE)
SITE.mkdir(parents=True)
for f in ["ballot.html", "manifest.webmanifest", "sw.js"]:
    shutil.copy2(ROOT / f, SITE / f)
shutil.copytree(ROOT / "fl", SITE / "fl")
shutil.copytree(ROOT / "buddy" / "icons", SITE / "buddy" / "icons")
shutil.copytree(ROOT / "buddy" / "logos", SITE / "buddy" / "logos", ignore=shutil.ignore_patterns("*.py", "*.cjs", "png"))
(SITE / "_headers").write_text("/sw.js\n  Cache-Control: no-cache\n/ballot.html\n  Cache-Control: no-cache\n/fl/*\n  Cache-Control: no-cache\n", encoding="utf-8")
n = sum(1 for _ in SITE.rglob("*") if _.is_file())
print("site:", n, "files")
