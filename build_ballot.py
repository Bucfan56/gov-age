#!/usr/bin/env python3
"""
Render a voter's ballot report from ballot-<zip>.json into ballot-<zip>.html.

    py build_ballot.py ballot-34221.json

The JSON holds everything: the races on the official sample ballot, each
candidate's money (federal from FEC bulk files, state from the Florida Division
of Elections, county and city from the Supervisor of Elections), their public
record, and -- in a separate, labelled box -- what the owner's designated
sources say about them.

Framing rule, same as the main page: this reports who paid for whom and what
the public record shows. It does not tell anyone how to vote, and it never
treats a donation as proof of anything beyond the donation.
"""
import html, json, sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def e(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def usd(v):
    if v is None:
        return "—"
    v = float(v)
    if abs(v) >= 1e6:
        return f"${v / 1e6:,.1f}M"
    if abs(v) >= 1e4:
        return f"${v / 1e3:,.0f}k"
    return f"${v:,.0f}"


def pct(v):
    return "—" if v is None else f"{float(v):.0f}%"


def link(text, url):
    if not url:
        return e(text)
    return f'<a href="{e(url)}" target="_blank" rel="noopener">{e(text)}</a>'


def items(rows, cls=""):
    if not rows:
        return ""
    out = []
    for r in rows:
        if isinstance(r, str):
            out.append(f"<li>{e(r)}</li>")
            continue
        status = r.get("status")
        tag = f'<span class="tag {e(status)}">{e(status)}</span> ' if status else ""
        src = f' <a class="src" href="{e(r["url"])}" target="_blank" rel="noopener">source</a>' if r.get("url") else ""
        out.append(f"<li>{tag}{e(r.get('text', ''))}{src}</li>")
    return f'<ul class="{cls}">' + "".join(out) + "</ul>"


def section(title, body):
    if not body:
        return ""
    return f'<div class="sec"><h5>{e(title)}</h5>{body}</div>'


def money_block(m):
    if not m:
        return '<p class="none">No campaign-finance filing found for this candidate.</p>'
    rows = []
    def stat(label, val, hint=""):
        rows.append(f'<div class="stat"><b>{val}</b><span>{e(label)}</span>'
                    + (f'<i>{e(hint)}</i>' if hint else "") + "</div>")
    stat("raised" + (" (campaign account)" if m.get("committee") else ""), usd(m.get("raised")), m.get("through", ""))
    if m.get("local_pct") is not None:
        stat(m.get("local_label", "from Manatee County"), pct(m["local_pct"]))
    if m.get("fl_pct") is not None:
        stat("from Florida", pct(m["fl_pct"]))
    if m.get("out_pct") is not None:
        stat("from out of state", pct(m["out_pct"]))
    if m.get("org_pct") is not None:
        stat(m.get("org_label", "from businesses, PACs & committees"), pct(m["org_pct"]))
    if m.get("build_land_pct") is not None:
        stat("from building / land / real-estate names", pct(m["build_land_pct"]),
             "tagged only when the donor's own filed name or occupation says so")
    if m.get("big_pct") is not None:
        stat(m.get("big_label", "from donors giving $2,000+"), pct(m["big_pct"]))
    if m.get("loans"):
        stat("loans (repayable, not donations)", usd(m["loans"]))
    h = '<div class="stats">' + "".join(rows) + "</div>"
    if m.get("note"):
        h += f'<p class="mnote">{e(m["note"])}</p>'
    if m.get("committee"):
        c = m["committee"]
        h += (f'<div class="pc"><h6>Their political committee: {e(c["name"])} — {usd(c.get("total"))} raised'
              f'{(" (" + e(c["span"]) + ")") if c.get("span") else ""}</h6>'
              '<p class="mnote">Florida caps gifts to a candidate\'s own campaign, but not to a political committee '
              'the candidate controls. For statewide and legislative candidates this is usually where the large money is.</p>'
              + table(c.get("top", []), ["Giver", "Amount", "Where"]) + "</div>")
    if m.get("groups"):
        h += '<div class="flag"><h6>Several companies giving from one address</h6><ul>' + "".join(
            f"<li>{usd(g[0])} from {g[1]} separately named entities at the same address: {e(', '.join(g[2]))}</li>"
            for g in m["groups"]) + ("</ul><p class=\"mnote\">Contribution limits apply per entity, so one owner with "
            "several companies can give several times the limit. This is legal; it is listed so you can see it.</p></div>")
    if m.get("top"):
        h += "<h6>Largest givers</h6>" + table(m["top"], ["Giver", "Amount", "Detail"])
    if m.get("pacs"):
        h += "<h6>PAC and party cheques</h6>" + table(m["pacs"], ["Committee", "Amount", "Kind"])
    if m.get("outside"):
        h += ('<h6>Outside groups spending on this race</h6>' + table(
            [[o[0], o[2], "FOR this candidate" if o[1] == "S" else "AGAINST this candidate"] for o in m["outside"]],
            ["Group", "Spent", ""]) + '<p class="mnote">Independent spending — legally the candidate may not '
            "coordinate with it. It shows who wants this person to win or lose.</p>")
    if m.get("foreign"):
        h += '<div class="flag"><h6>Foreign-connected money</h6>' + items(m["foreign"]) + "</div>"
    if m.get("source"):
        h += f'<p class="msrc">Money source: {link(m["source"], m.get("source_url"))}</p>'
    return h


def table(rows, head):
    if not rows:
        return ""
    th = "".join(f"<th>{e(x)}</th>" for x in head)
    tr = []
    for r in rows:
        cells = []
        for i, c in enumerate(r[:len(head)]):
            cells.append(f'<td class="{"amt" if i == 1 else ""}">{usd(c) if i == 1 and isinstance(c, (int, float)) else e(c)}</td>')
        tr.append("<tr>" + "".join(cells) + "</tr>")
    return f'<div class="tw"><table><thead><tr>{th}</tr></thead><tbody>{"".join(tr)}</tbody></table></div>'


def owner_box(c):
    hits = c.get("owner_sources") or []
    searched = c.get("owner_sources_searched") or []
    if not hits and not searched:
        return ""
    if hits:
        body = "<ul>" + "".join(
            f'<li><b>{e(h.get("source"))}</b>{(" · " + e(h.get("date"))) if h.get("date") else ""} — '
            f'{link(h.get("title") or "item", h.get("url"))}: {e(h.get("says"))}</li>' for h in hits) + "</ul>"
    else:
        body = "<p>Searched; no mention of this candidate found.</p>"
    return ('<div class="owner"><h5>Owner-designated sources</h5>'
            '<p class="olabel">Sources the owner of this guide chose to include. What they say is reported as '
            'they say it — it has not been checked against public records here.</p>' + body
            + (f'<p class="osearched">Searched: {e("; ".join(searched))}</p>' if searched else "") + "</div>")


def candidate(c):
    party = f'<span class="party">{e(c.get("party"))}</span>' if c.get("party") else ""
    inc = '<span class="inc">incumbent</span>' if c.get("incumbent") else ""
    mate = f'<p class="mate">Running mate: {e(c["running_mate"])}</p>' if c.get("running_mate") else ""
    brief = " brief" if c.get("brief") else ""
    return (f'<article class="cand{brief}" id="{e(c.get("id", ""))}"><header><h4>{e(c["name"])}</h4>{party}{inc}</header>{mate}'
            + (f'<p class="bio">{e(c["bio"])}</p>' if c.get("bio") else "")
            + section("Ties to here", f'<p>{e(c["local_ties"])}</p>' if c.get("local_ties") else "")
            + section("Money", money_block(c.get("money")))
            + section("Record", items(c.get("record")))
            + section("Stance on growth & development", items(c.get("local_issue_stance")))
            + section("Controversies, cases, complaints", items(c.get("controversies"), "contro"))
            + section("Foreign ties (documented)", items(c.get("foreign_ties")))
            + section("Endorsed by", items(c.get("endorsements")))
            + section("What newspapers said (opinion, not fact)", items(c.get("press_opinion")))
            + owner_box(c)
            + (f'<p class="gaps">Not found: {e(c["gaps"])}</p>' if c.get("gaps") else "")
            + "</article>")


def race(r):
    scope = ('<span class="scope all">every voter in 34221</span>' if r.get("scope") == "all"
             else f'<span class="scope dist">{e(r.get("scope_note", "only some addresses in 34221"))}</span>')
    cmp_ = ""
    if r.get("compare"):
        cmp_ = '<div class="compare"><h5>Side by side, on your three questions</h5>' + table(
            r["compare"]["rows"], r["compare"]["head"]) + (f'<p class="mnote">{e(r["compare"]["note"])}</p>' if r["compare"].get("note") else "") + "</div>"
    body = "".join(candidate(c) for c in r.get("candidates", []))
    if r.get("retention"):
        body += '<div class="ret">' + "".join(
            f'<div class="retj"><h4>{e(j["name"])}</h4><p>{e(j.get("text", ""))}</p>{items(j.get("items"))}{owner_box(j)}</div>'
            for j in r["retention"]) + "</div>"
    return (f'<section class="race" id="{e(r["id"])}"><div class="rhead"><h3>{e(r["title"])}</h3>{scope}</div>'
            + (f'<p class="rnote">{e(r["note"])}</p>' if r.get("note") else "") + cmp_
            + f'<div class="cands">{body}</div></section>')


def measure(m):
    return (f'<section class="race measure" id="{e(m["id"])}"><div class="rhead"><h3>{e(m["name"])}</h3>'
            f'<span class="scope {"all" if m.get("scope") == "all" else "dist"}">{e(m.get("scope_note", "every voter"))}</span></div>'
            f'<p>{e(m.get("summary", ""))}</p>'
            + section("A YES vote means", f'<p>{e(m["yes"])}</p>' if m.get("yes") else "")
            + section("A NO vote means", f'<p>{e(m["no"])}</p>' if m.get("no") else "")
            + section("Who is paying for YES", items(m.get("who_funds_yes")))
            + section("Who is paying for NO", items(m.get("who_funds_no")))
            + section("Cost / fiscal impact", items(m.get("fiscal")))
            + section("Supporters", items(m.get("supporters")))
            + section("Opponents", items(m.get("opponents")))
            + owner_box(m) + "</section>")


CSS = r"""
:root{--paper:#E6E8E0;--paper-2:#DCDFD5;--card:#F1F2EC;--ink:#14201D;--ink-soft:#4C5A54;--ink-faint:#8A968F;
--over:#8A2F26;--under:#1F5E5C;--amber:#8A5A00;--amber-bg:#F3E7C8;--rule:rgba(20,32,29,.16);--rule-hard:rgba(20,32,29,.42)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--paper:#121816;--paper-2:#1A2220;--card:#18201E;--ink:#E4E8E2;
--ink-soft:#A9B4AE;--ink-faint:#748079;--over:#E08A80;--under:#7CC2BF;--amber:#E8B85A;--amber-bg:#2B2516;--rule:rgba(228,232,226,.14);--rule-hard:rgba(228,232,226,.4)}}
:root[data-theme="dark"]{--paper:#121816;--paper-2:#1A2220;--card:#18201E;--ink:#E4E8E2;--ink-soft:#A9B4AE;--ink-faint:#748079;
--over:#E08A80;--under:#7CC2BF;--amber:#E8B85A;--amber-bg:#2B2516;--rule:rgba(228,232,226,.14);--rule-hard:rgba(228,232,226,.4)}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font-family:"Newsreader",Georgia,serif;font-size:17px;line-height:1.5;font-variant-numeric:tabular-nums}
a{color:var(--under)}.wrap{max-width:1180px;margin:0 auto;padding:0 16px}
.mast{border-bottom:2px solid var(--ink);padding:28px 0 18px}
.mast h1{font-family:"Archivo",Helvetica,Arial,sans-serif;font-weight:800;font-size:clamp(2rem,6vw,3.6rem);line-height:.95;margin:6px 0 10px;letter-spacing:-.02em}
.kick,.mono{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:.72rem;letter-spacing:.12em;text-transform:uppercase}
.lede{max-width:780px;color:var(--ink-soft)}
.box{border:1px solid var(--rule-hard);background:var(--card);padding:14px 16px;margin:16px 0;border-radius:4px}
.box h2{font-family:"Archivo",sans-serif;font-size:1.05rem;margin:0 0 6px}
.box.warn{border-color:var(--over)}
nav.toc{position:sticky;top:0;z-index:5;background:var(--paper);border-bottom:1px solid var(--rule);padding:8px 0;overflow-x:auto;white-space:nowrap}
nav.toc a{font-family:"IBM Plex Mono",monospace;font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;margin-right:14px;text-decoration:none;color:var(--ink-soft)}
nav.toc a:hover{color:var(--ink)}
h2.part{font-family:"Archivo",sans-serif;font-size:1.6rem;margin:38px 0 6px;border-top:2px solid var(--ink);padding-top:12px}
.race{border-top:1px solid var(--rule-hard);padding:22px 0 8px;scroll-margin-top:42px}
.rhead{display:flex;flex-wrap:wrap;gap:10px;align-items:baseline}
.rhead h3{font-family:"Archivo",sans-serif;font-size:1.35rem;margin:0}
.scope{font-family:"IBM Plex Mono",monospace;font-size:.66rem;text-transform:uppercase;letter-spacing:.08em;padding:2px 7px;border-radius:3px}
.scope.all{background:var(--under);color:var(--paper)}.scope.dist{border:1px solid var(--amber);color:var(--amber)}
.rnote{color:var(--ink-soft);max-width:860px}
.cands{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px;margin-top:12px}
.cand{background:var(--card);border:1px solid var(--rule);border-radius:4px;padding:14px 15px;min-width:0}
.cand.brief{opacity:.94}
.cand header{display:flex;flex-wrap:wrap;gap:8px;align-items:baseline;border-bottom:1px solid var(--rule);padding-bottom:6px}
.cand h4{font-family:"Archivo",sans-serif;font-size:1.15rem;margin:0}
.party,.inc{font-family:"IBM Plex Mono",monospace;font-size:.66rem;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-soft)}
.inc{color:var(--under)}
.mate{margin:6px 0 0;font-size:.92rem;color:var(--ink-soft)}
.bio{margin:8px 0}
.sec{margin-top:10px}
.sec h5,.owner h5,.compare h5{font-family:"IBM Plex Mono",monospace;font-size:.68rem;letter-spacing:.1em;text-transform:uppercase;margin:0 0 4px;color:var(--ink-soft)}
h6{font-family:"Archivo",sans-serif;font-size:.86rem;margin:10px 0 4px}
.sec ul,.owner ul{margin:0;padding-left:18px}.sec li,.owner li{margin:3px 0;font-size:.95rem}
.src{font-family:"IBM Plex Mono",monospace;font-size:.62rem;text-transform:uppercase;letter-spacing:.06em}
.tag{font-family:"IBM Plex Mono",monospace;font-size:.6rem;text-transform:uppercase;padding:1px 5px;border-radius:2px;border:1px solid var(--rule-hard)}
.tag.allegation{border-color:var(--amber);color:var(--amber)}.tag.established{border-color:var(--over);color:var(--over)}
.tag.dismissed,.tag.resolved{color:var(--ink-faint)}.tag.fact-checked{border-color:var(--under);color:var(--under)}
.stats{display:grid;grid-template-columns:repeat(auto-fill,minmax(118px,1fr));gap:6px}
.stat{border:1px solid var(--rule);padding:6px 8px;border-radius:3px;background:var(--paper)}
.stat b{display:block;font-family:"IBM Plex Mono",monospace;font-size:1.02rem}
.stat span{display:block;font-size:.78rem;color:var(--ink-soft);line-height:1.25}
.stat i{display:block;font-size:.66rem;color:var(--ink-faint);font-style:normal;margin-top:2px}
.mnote,.msrc,.gaps,.osearched,.olabel{font-size:.82rem;color:var(--ink-soft);margin:6px 0}
.tw{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:.86rem;margin:4px 0}
th{text-align:left;font-family:"IBM Plex Mono",monospace;font-size:.62rem;text-transform:uppercase;letter-spacing:.06em;color:var(--ink-soft);border-bottom:1px solid var(--rule-hard);padding:4px 6px}
td{border-bottom:1px solid var(--rule);padding:4px 6px;vertical-align:top}td.amt{font-family:"IBM Plex Mono",monospace;white-space:nowrap;text-align:right}
.pc{border-left:3px solid var(--over);padding-left:10px;margin-top:10px}
.flag{border-left:3px solid var(--amber);padding-left:10px;margin-top:10px}
.owner{margin-top:12px;background:var(--amber-bg);border:1px dashed var(--amber);border-radius:4px;padding:10px 12px}
.owner h5{color:var(--amber)}
.none{color:var(--ink-faint);font-style:italic}
.compare{margin-top:10px;background:var(--paper-2);padding:10px 12px;border-radius:4px}
.ret{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin-top:10px}
.retj{background:var(--card);border:1px solid var(--rule);border-radius:4px;padding:12px}.retj h4{font-family:"Archivo",sans-serif;margin:0 0 4px}
footer{border-top:2px solid var(--ink);margin-top:40px;padding:18px 0 40px;color:var(--ink-soft);font-size:.9rem}
@media print{nav.toc{display:none}.cand,.race{break-inside:avoid-page}body{font-size:12px}}
@media (max-width:420px){.cands{grid-template-columns:1fr}}
"""


def main(path):
    d = json.load(open(path, encoding="utf-8"))
    parts = d["parts"]
    toc = "".join(f'<a href="#{e(r["id"])}">{e(r.get("short", r.get("title", r.get("name"))))}</a>'
                  for p in parts for r in p["races"])
    body = []
    for p in parts:
        body.append(f'<h2 class="part">{e(p["title"])}</h2>' + (f'<p class="rnote">{e(p["note"])}</p>' if p.get("note") else ""))
        for r in p["races"]:
            body.append(measure(r) if r.get("measure") else race(r))
    boxes = "".join(f'<div class="box {e(b.get("cls", ""))}"><h2>{e(b["title"])}</h2>{b["html"]}</div>' for b in d.get("boxes", []))
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(d["title"])}</title>
<meta name="description" content="{e(d["description"])}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;700;800&family=IBM+Plex+Mono:wght@400;500&family=Newsreader:ital,opsz,wght@0,6..72,400..700;1,6..72,400&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>
<div class="wrap"><header class="mast"><div class="kick">{e(d["kicker"])}</div><h1>{e(d["headline"])}</h1>
<p class="lede">{e(d["lede"])}</p></header>{boxes}</div>
<nav class="toc"><div class="wrap">{toc}</div></nav>
<main class="wrap">{"".join(body)}</main>
<footer class="wrap">{d["footer"]}<p>Built {e(d["built"])}. <a href="index.html">How old is the US government?</a></p></footer>
</body></html>"""
    out = path.replace(".json", ".html")
    open(out, "w", encoding="utf-8", newline="\n").write(page)
    print("wrote", out, len(page), "bytes")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ballot-34221.json")
