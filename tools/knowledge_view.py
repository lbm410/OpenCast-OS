"""Build deterministic offline and GitHub views from the actual knowledge graph."""

from __future__ import annotations

import argparse
from collections import deque
import html
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import textwrap
from urllib.parse import unquote, urlsplit

from tools.knowledge import Bundle, load_bundle

GROUPS = ["product", "execution", "platform", "engineering"]
ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]*(?:/[a-z0-9][a-z0-9_-]*)*\Z")


def source_href(concept_id: str, resource: str) -> str | None:
    """Allow manual links only to visible Markdown within known repo roots."""
    if not ID_PATTERN.fullmatch(concept_id) or not isinstance(resource, str):
        return None
    if any(ord(char) < 32 for char in resource) or "\\" in resource:
        return None
    try:
        parsed = urlsplit(resource)
    except ValueError:
        return None
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        return None
    decoded = unquote(parsed.path)
    if not re.fullmatch(r"[A-Za-z0-9_./-]+\.md", decoded):
        return None
    if decoded.startswith("/"):
        candidate = posixpath.normpath("knowledge/" + decoded.lstrip("/"))
    else:
        candidate = posixpath.normpath("knowledge/" + str(PurePosixPath(concept_id).parent) + "/" + decoded)
    if candidate.startswith("../") or any(part.startswith(".") for part in candidate.split("/")):
        return None
    if candidate != "AGENTS.md" and not candidate.startswith(("docs/", "knowledge/")):
        return None
    return posixpath.relpath(candidate, "knowledge")


def plain_body(body: str) -> str:
    text = re.sub(r"^\[\^[^]]+\]:.*$", "", body, flags=re.M)
    text = re.sub(r"\[([^]\n]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[\^[^]]+\]", "", text)
    text = re.sub(r"^\s*# [^\n]+\n", "", text, count=1)
    return text.strip()


def graph_data(bundle: Bundle) -> dict:
    if any(issue["severity"] == "error" for issue in bundle.issues):
        raise ValueError("Invalid bundle; run tools.knowledge validate")
    edges, unresolved = bundle.edges()
    if unresolved:
        raise ValueError("Resolve concept links before exporting the view")
    nodes = []
    for cid, concept in sorted(bundle.concepts.items()):
        if not ID_PATTERN.fullmatch(cid):
            raise ValueError("Unsupported concept ID for safe exported links")
        node = concept.summary()
        evidence = concept.metadata.get("opencast_evidence", [])
        node.update({"group": cid.split("/", 1)[0], "body": plain_body(concept.body),
                     "evidence": evidence if isinstance(evidence, list) and all(isinstance(x, str) for x in evidence) else [],
                     "href": cid + ".md",
                     "sources": [{"id": source.get("id", "source"), "resource": source["resource"],
                                  "href": source_href(cid, source["resource"])}
                                 for source in concept.metadata.get("sources", [])]})
        nodes.append(node)
    return {"nodes": nodes, "edges": sorted(edges, key=lambda edge: (edge["from"], edge["to"], edge["kind"])),
            "groups": [group for group in GROUPS if any(node["group"] == group for node in nodes)] +
                      sorted({node["group"] for node in nodes} - set(GROUPS))}


def script_json(data: dict) -> str:
    # JSON data is inside a script raw-text element. Escape HTML delimiters even
    # when they occur in a JSON string; JSON escaping quotes alone is insufficient.
    return json.dumps(data, ensure_ascii=True, sort_keys=True, separators=(",", ":")).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def overview_edges(data: dict) -> list[dict]:
    """Actual-edge spanning forest; readable overview rather than 63-edge tangle."""
    adjacency: dict[str, list[tuple[str, dict]]] = {node["id"]: [] for node in data["nodes"]}
    for edge in data["edges"]:
        adjacency[edge["from"]].append((edge["to"], edge))
        adjacency[edge["to"]].append((edge["from"], edge))
    roots = (["product/shell"] if "product/shell" in adjacency else []) + sorted(adjacency)
    seen, result = set(), []
    for root in roots:
        if root in seen:
            continue
        seen.add(root)
        queue = deque([root])
        while queue:
            current = queue.popleft()
            for target, edge in sorted(adjacency[current], key=lambda pair: (pair[0], pair[1]["from"])):
                if target not in seen:
                    seen.add(target)
                    result.append(edge)
                    queue.append(target)
    return result


def markdown_view(data: dict) -> str:
    identifiers = {node["id"]: f"n{index}" for index, node in enumerate(data["nodes"])}
    selected = overview_edges(data)
    lines = ["# Explore the OpenCast knowledge graph", "",
             f"**{len(data['nodes'])} concepts · {len(data['edges'])} directed relationships · {len(data['groups'])} groups.** Built from the actual OKF bundle, not a hand-drawn architecture claim.", "",
             "[Open the bundle index](../knowledge/index.md) or [download the interactive graph](../knowledge/graph.html). GitHub displays the HTML source; save the repository and open `knowledge/graph.html` locally for search, filters and selectable connections. No hosting, CDN, installation or network fetch is required. Keep the repository layout for its manual Markdown/report links.", "",
             f"The navigation overview below includes all concepts and {len(selected)} actual relationships selected as a spanning forest. Arrow direction is preserved. The local viewer contains all {len(data['edges'])} relationships and shows only the selected node's connections to keep the map readable. A link means a knowledge relationship; its surrounding concept prose explains the dependency or evidence context.", "",
             "All current summaries are draft and unverified in OKF's review-event sense. Their evidence labels distinguish physical observations, static results and open hypotheses; they do not imply a working replacement OS.", "", "```mermaid", "flowchart LR"]
    for group in data["groups"]:
        lines.append(f'  subgraph {group}["{group.title()}"]')
        for node in data["nodes"]:
            if node["group"] == group:
                label = re.sub(r"[^A-Za-z0-9 -]", " ", node["title"])
                lines.append(f'    {identifiers[node["id"]]}["{label}"]')
        lines.append("  end")
    for edge in selected:
        lines.append(f'  {identifiers[edge["from"]]} --> {identifiers[edge["to"]]}')
    for node in data["nodes"]:
        lines.append(f'  click {identifiers[node["id"]]} "../knowledge/{node["href"]}" "Open concept"')
    lines += ["```", "", "If a renderer disables Mermaid click actions, use these ordinary links:", ""]
    for group in data["groups"]:
        lines.extend([f"## {group.title()}", ""])
        for node in data["nodes"]:
            if node["group"] == group:
                title = markdown_text(node["title"])
                description = markdown_text(node["description"])
                lines.append(f"- [{title}](../knowledge/{node['href']}) — {description}")
        lines.append("")
    lines += ["## Rebuild the views", "", "```sh", "python3 -m tools.knowledge_view", "python3 -m tools.knowledge_view --check",
              "python3 -m unittest discover -s tests -p 'test_knowledge_view.py' -v", "```", "",
              "The generator reads concepts and graph edges without fetching source resources. Concept text is displayed as text, never interpreted as HTML. Generated views are deterministic; detailed reports remain the evidence record.", "",
              "The initial 2026-11-14 export passed six generator tests covering script-termination injection, unsafe links, deterministic HTML/Markdown/SVG, real graph counts and malformed concept relationships. Local isolated Chrome checks confirmed search, category filtering, node selection and neighbor navigation, with no JavaScript exceptions. Desktop (1600 × 1150) and mobile-width (390 × 844) screenshots were inspected; neither layout had horizontal overflow. These checks validate the documentation viewer on the host, not the TV runtime.", ""]
    return "\n".join(lines)


def markdown_text(value: str) -> str:
    text = html.escape(" ".join(value.split()), quote=True)
    return re.sub(r"([\\`*\[\]{}()!#])", r"\\\1", text)


HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'">
<title>OpenCast OS · Knowledge map</title>
<style>
:root{color-scheme:dark;--bg:#0a1118;--panel:#111d28;--line:#263643;--text:#edf4f5;--muted:#97adb9;--mint:#8ce3c0;--purple:#c2b5fb}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}button,input,select{font:inherit}button,a,input,select{outline-offset:4px}a{color:var(--mint)}button{cursor:pointer}header{padding:28px 32px 20px;border-bottom:1px solid var(--line);background:linear-gradient(110deg,#132731,#0b151e 65%)}.eyebrow{font-size:11px;font-weight:750;letter-spacing:.19em;color:var(--mint);text-transform:uppercase}h1{font-size:clamp(28px,3vw,42px);line-height:1.15;margin:7px 0 9px;font-weight:650;letter-spacing:-.04em}.intro{margin:0;color:var(--muted);max-width:780px}.headerline{display:flex;align-items:flex-start;justify-content:space-between;gap:24px}.stats{display:flex;gap:24px;white-space:nowrap;padding-top:8px}.stats strong{display:block;color:var(--text);font-size:25px;font-weight:600}.stats span{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}.toolbar{display:flex;gap:12px;padding:18px 32px;align-items:center;flex-wrap:wrap;border-bottom:1px solid var(--line)}input,select{color:var(--text);border:1px solid #344958;border-radius:8px;background:#111d28;padding:10px 12px}input{width:320px;max-width:100%}select{min-width:165px}.plainbutton{border:1px solid #344958;background:transparent;color:var(--muted);border-radius:8px;padding:10px 14px}.toolbar label{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}#resultCount{font-size:12px;color:var(--muted);margin-left:auto}main{display:grid;grid-template-columns:minmax(660px,1fr) 380px;min-height:700px}.map-area{padding:22px 28px 28px;min-width:0}.map-caption{display:flex;gap:18px;flex-wrap:wrap;align-items:center;color:var(--muted);font-size:11px;margin-bottom:20px}.legendline{display:inline-block;width:22px;border-top:2px solid var(--mint);margin-right:6px;vertical-align:middle}.legendline.in{border-top:2px dashed var(--purple)}#map{position:relative}.groups{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:18px;position:relative;z-index:1;pointer-events:none}.group h2{color:var(--muted);font-size:11px;font-weight:650;text-transform:uppercase;letter-spacing:.12em;margin:0 0 16px}.node{display:block;width:100%;min-height:76px;text-align:left;padding:12px;border:1px solid #2b3b49;border-radius:10px;background:#101b25;color:var(--text);margin-bottom:10px;position:relative;pointer-events:auto;transition:border-color .12s,background .12s}.node:hover{border-color:#718e9f;background:#172634}.node:focus-visible{outline:2px solid var(--mint)}.node .title{display:block;font-size:12px;font-weight:650;line-height:1.35}.node .meta{display:block;font-size:10px;color:#8ea5b2;margin-top:7px}.node.selected{border-color:var(--mint);background:#17342f;box-shadow:0 0 0 1px #8ce3c033}.node.neighbor{border-color:#54766e}.node.incoming{border-color:#655c8f}.node.dim{opacity:.68}.node[hidden]{display:none}#connections{position:absolute;inset:0;width:100%;height:100%;overflow:visible;pointer-events:none;z-index:0}.edge{fill:none;stroke:var(--mint);stroke-width:1.6;opacity:.68}.edge.incoming{stroke:var(--purple);stroke-dasharray:4 5;opacity:.48}.empty{display:none;border:1px dashed var(--line);padding:28px;color:var(--muted);text-align:center;border-radius:12px}.detail{border-left:1px solid var(--line);padding:24px;background:#0d1720;min-width:0}.detail-inner{position:sticky;top:20px}.detail .category{color:var(--mint);font-size:11px;letter-spacing:.12em;text-transform:uppercase}h3{font-size:25px;line-height:1.2;letter-spacing:-.025em;margin:8px 0 12px}.badges{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px}.badge{font-size:10px;padding:3px 8px;border-radius:5px;background:#26313c;color:#c3ced6;border:1px solid #36434f}.body{font-size:12px;line-height:1.65;white-space:pre-wrap;color:#c1d0d9;margin:14px 0 18px}.detail h4{font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin:20px 0 9px}.evidence{list-style:none;padding:0;margin:0}.evidence li{font-size:11px;color:#b6c8d0;padding:5px 0;border-bottom:1px solid #1b2a35}.neighbors{display:flex;flex-wrap:wrap;gap:6px}.neighbor-button{font-size:10px;line-height:1.35;padding:6px 8px;border:1px solid #385348;border-radius:6px;background:#14251f;color:#bce6d2;text-align:left}.neighbor-button.in{border-color:#4c4269;background:#211e30;color:#d2c9f1}.sources{list-style:none;padding:0;font-size:11px;overflow-wrap:anywhere}.sources li{margin-bottom:9px}.source-kind{display:block;color:var(--muted);font-size:10px}.open{display:inline-block;font-size:12px;text-decoration:none;padding:8px 11px;border:1px solid #4b7868;border-radius:7px;background:#143126;color:#b9f5da}footer{padding:18px 32px;border-top:1px solid var(--line);color:#7f97a5;font-size:11px}noscript{display:block;padding:30px;color:var(--mint)}@media(max-width:1150px){main{grid-template-columns:minmax(550px,1fr) 320px}.map-area{padding:20px}.groups{gap:10px}.node{padding:9px}.detail{padding:20px}}@media(max-width:900px){main{display:block}.detail{border-left:0;border-top:1px solid var(--line)}.detail-inner{position:static}.groups{grid-template-columns:repeat(2,minmax(0,1fr));gap:22px}.headerline{display:block}.stats{margin-top:18px}header,.toolbar{padding-left:20px;padding-right:20px}#resultCount{margin-left:0}.map-area{padding:20px}.node{min-height:65px}.detail .body{max-width:760px}}@media(prefers-reduced-motion:reduce){.node{transition:none}}
</style></head><body>
<header><div class="headerline"><div><div class="eyebrow">OpenCast OS / Research atlas</div><h1>Follow the evidence.</h1><p class="intro">Explore what we know, what each decision depends on, and what still needs a real test.</p></div><div class="stats"><div><strong id="nodeTotal">—</strong><span>Concepts</span></div><div><strong id="edgeTotal">—</strong><span>Connections</span></div><div><strong id="groupTotal">—</strong><span>Areas</span></div></div></div></header>
<div class="toolbar"><label for="search">Search concepts</label><input id="search" type="search" placeholder="Search concepts, evidence, tags…" autocomplete="off"><label for="groupFilter">Filter area</label><select id="groupFilter"><option value="all">All areas</option></select><button id="reset" class="plainbutton">Reset view</button><span id="resultCount" role="status" aria-live="polite"></span></div>
<main><section class="map-area" aria-label="Knowledge graph"><div class="map-caption"><span><i class="legendline"></i>Selected concept points to</span><span><i class="legendline in"></i>Other concept points here</span><span>Choose a card to trace its immediate connections.</span></div><div id="map"><svg id="connections" aria-hidden="true"><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#8ce3c0"></path></marker><marker id="arrowIn" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#c2b5fb"></path></marker></defs><g id="edgePaths"></g></svg><div class="groups" id="groups"></div></div><div id="empty" class="empty">No matching concepts. Try another term or reset the view.</div></section>
<aside class="detail" aria-label="Selected concept"><div class="detail-inner"><div class="category" id="detailCategory"></div><h3 id="detailTitle"></h3><div class="badges" id="badges"></div><a class="open" id="openConcept">Read concept ↗</a><div class="body" id="detailBody"></div><h4>Evidence scope</h4><ul class="evidence" id="evidence"></ul><h4 id="outgoingTitle">Points to</h4><div class="neighbors" id="outgoing"></div><h4 id="incomingTitle">Referenced by</h4><div class="neighbors" id="incoming"></div><h4>Source reports · open manually</h4><ul class="sources" id="sources"></ul></div></aside></main>
<footer>Offline snapshot of the OKF bundle · draft summaries are not independent verification · firmware evidence is not physical validation.<br>Nothing is fetched automatically. Keep this file within the repository to follow local concept and report links.</footer>
<noscript>This map needs JavaScript for local filtering. The Markdown bundle index remains readable without it.</noscript>
<script id="graph-data" type="application/json">__GRAPH_DATA__</script>
<script>
(function(){'use strict';
var data=JSON.parse(document.getElementById('graph-data').textContent), byId=Object.create(null), cards=Object.create(null), selected='', ns='http://www.w3.org/2000/svg';
function el(id){return document.getElementById(id);}function clear(node){while(node.firstChild){node.removeChild(node.firstChild);}}
function element(tag,text,cls){var n=document.createElement(tag);if(text!==undefined){n.textContent=text;}if(cls){n.className=cls;}return n;}
function safeHref(value){return typeof value==='string' && /^(?:[a-z0-9][a-z0-9_\/-]*\.md|\.\.\/(?:docs\/[A-Za-z0-9_\/-]+\.md|knowledge\/[A-Za-z0-9_\/-]+\.md|AGENTS\.md))$/.test(value) && value.indexOf('/../')===-1;}
function neighbors(id,direction){return data.edges.filter(function(e){return direction==='out'?e.from===id:e.to===id;}).map(function(e){return direction==='out'?e.to:e.from;}).filter(function(v,i,a){return a.indexOf(v)===i;}).sort();}
function draw(){clear(el('edgePaths'));var bounds=el('map').getBoundingClientRect();if(!cards[selected]||cards[selected].hidden){return;}data.edges.forEach(function(edge){if(edge.from!==selected&&edge.to!==selected){return;}var from=cards[edge.from],to=cards[edge.to];if(!from||!to||from.hidden||to.hidden){return;}var a=from.getBoundingClientRect(),b=to.getBoundingClientRect(),same=Math.abs(a.left-b.left)<10,x1,y1,x2,y2,c1,c2;if(same){x1=a.right-bounds.left;y1=a.top+a.height/2-bounds.top;x2=b.right-bounds.left;y2=b.top+b.height/2-bounds.top;c1=x1+15;c2=x2+15;}else{var right=b.left>a.left;x1=(right?a.right:a.left)-bounds.left;x2=(right?b.left:b.right)-bounds.left;y1=a.top+a.height/2-bounds.top;y2=b.top+b.height/2-bounds.top;var bend=Math.max(25,Math.abs(x2-x1)*.45);c1=x1+(right?bend:-bend);c2=x2+(right?-bend:bend);}var p=document.createElementNS(ns,'path');p.setAttribute('d','M '+x1+' '+y1+' C '+c1+' '+y1+', '+c2+' '+y2+', '+x2+' '+y2);p.setAttribute('class','edge'+(edge.to===selected?' incoming':''));p.setAttribute('marker-end',edge.to===selected?'url(#arrowIn)':'url(#arrow)');el('edgePaths').appendChild(p);});}
function filter(){var q=el('search').value.toLowerCase().trim(),group=el('groupFilter').value,count=0,outs=neighbors(selected,'out'),ins=neighbors(selected,'in');data.nodes.forEach(function(node){var card=cards[node.id],match=(group==='all'||group===node.group)&&(!q||(node.title+' '+node.description+' '+node.tags.join(' ')+' '+node.evidence.join(' ')).toLowerCase().indexOf(q)!==-1);card.hidden=!match;if(match){count++;}card.className='node'+(node.id===selected?' selected':outs.indexOf(node.id)!==-1?' neighbor':ins.indexOf(node.id)!==-1?' incoming':' dim');card.setAttribute('aria-pressed',node.id===selected?'true':'false');});el('resultCount').textContent=count+' of '+data.nodes.length+' concepts shown';el('empty').style.display=count?'none':'block';requestAnimationFrame(draw);}
function neighborButtons(ids,target,cls){clear(el(target));if(!ids.length){el(target).appendChild(element('span','None','source-kind'));return;}ids.forEach(function(id){var b=element('button',byId[id].title,'neighbor-button'+cls);b.addEventListener('click',function(){el('search').value='';el('groupFilter').value='all';select(id);cards[id].focus();});el(target).appendChild(b);});}
function select(id){selected=id;var node=byId[id],outs=neighbors(id,'out'),ins=neighbors(id,'in');el('detailCategory').textContent=node.group+' / '+node.type;el('detailTitle').textContent=node.title;el('detailBody').textContent=node.body;clear(el('badges'));el('badges').appendChild(element('span',node.status,'badge'));el('badges').appendChild(element('span',node.declared_trust,'badge'));if(safeHref(node.href)){el('openConcept').setAttribute('href',node.href);}else{el('openConcept').removeAttribute('href');}clear(el('evidence'));node.evidence.forEach(function(value){el('evidence').appendChild(element('li',value));});neighborButtons(outs,'outgoing','');neighborButtons(ins,'incoming',' in');el('outgoingTitle').textContent='Points to · '+outs.length;el('incomingTitle').textContent='Referenced by · '+ins.length;clear(el('sources'));node.sources.forEach(function(source){var li=element('li'),link;if(safeHref(source.href)){link=element('a',source.id);link.setAttribute('href',source.href);}else{link=element('span',source.id);}li.appendChild(link);li.appendChild(element('span',source.resource,'source-kind'));el('sources').appendChild(li);});filter();}
el('nodeTotal').textContent=data.nodes.length;el('edgeTotal').textContent=data.edges.length;el('groupTotal').textContent=data.groups.length;data.nodes.forEach(function(node){byId[node.id]=node;});data.groups.forEach(function(group){var section=element('section',undefined,'group'),heading=element('h2',group);section.appendChild(heading);var option=element('option',group.charAt(0).toUpperCase()+group.slice(1));option.value=group;el('groupFilter').appendChild(option);data.nodes.filter(function(node){return node.group===group;}).forEach(function(node){var button=element('button',undefined,'node');button.type='button';button.dataset.id=node.id;button.appendChild(element('span',node.title,'title'));button.appendChild(element('span',node.status+' · '+neighbors(node.id,'out').length+' links','meta'));button.addEventListener('click',function(){select(node.id);});cards[node.id]=button;section.appendChild(button);});el('groups').appendChild(section);});el('search').addEventListener('input',filter);el('groupFilter').addEventListener('change',filter);el('reset').addEventListener('click',function(){el('search').value='';el('groupFilter').value='all';select(byId['product/shell']?'product/shell':data.nodes[0].id);});window.addEventListener('resize',draw);if(data.nodes.length){select(byId['product/shell']?'product/shell':data.nodes[0].id);}
})();
</script></body></html>
'''


def html_view(data: dict) -> str:
    return HTML.replace("__GRAPH_DATA__", script_json(data))


def svg_view(data: dict) -> str:
    """Script-free overview for README embeds; full graph remains in the viewer."""
    columns = len(data["groups"])
    width = max(760, columns * 340 + 64)
    rows = max((sum(node["group"] == group for node in data["nodes"]) for group in data["groups"]), default=0)
    height = 218 + rows * 82 + 80
    positions = {}
    for column, group in enumerate(data["groups"]):
        for row, node in enumerate(node for node in data["nodes"] if node["group"] == group):
            positions[node["id"]] = (32 + column * 340, 198 + row * 82)
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
             '<title id="title">OpenCast OS knowledge graph</title>',
             f'<desc id="desc">{len(data["nodes"])} concepts and {len(data["edges"])} directed relationships. A readable spanning overview of {len(overview_edges(data))} actual links; the local interactive viewer contains every relationship.</desc>',
             '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0L10 5L0 10z" fill="#7bbfa7"/></marker></defs>',
             f'<rect width="{width}" height="{height}" rx="20" fill="#0a1118"/>',
             '<g font-family="system-ui,-apple-system,Segoe UI,sans-serif">',
             '<text x="32" y="43" font-size="11" font-weight="700" letter-spacing="3" fill="#8ce3c0">OPENCAST OS / KNOWLEDGE ATLAS</text>',
             '<text x="32" y="91" font-size="36" font-weight="650" fill="#edf4f5">Follow the evidence.</text>',
             f'<text x="32" y="123" font-size="14" fill="#97adb9">{len(data["nodes"])} concepts · {len(data["edges"])} relationships · linked research, explicit unknowns.</text>']
    for edge in overview_edges(data):
        a, b = positions[edge["from"]], positions[edge["to"]]
        right = b[0] > a[0]
        if a[0] == b[0]:
            x1, x2, c1, c2 = a[0] + 310, b[0] + 310, a[0] + 326, b[0] + 326
        else:
            x1, x2 = a[0] + (310 if right else 0), b[0] + (0 if right else 310)
            bend = max(30, abs(x2 - x1) * .45)
            c1, c2 = x1 + (bend if right else -bend), x2 + (-bend if right else bend)
        y1, y2 = a[1] + 35, b[1] + 35
        lines.append(f'<path d="M{x1} {y1} C{c1} {y1},{c2} {y2},{x2} {y2}" fill="none" stroke="#7bbfa7" stroke-opacity=".42" stroke-width="1.4" marker-end="url(#arrow)"/>')
    for column, group in enumerate(data["groups"]):
        lines.append(f'<text x="{32 + column * 340}" y="177" font-size="11" font-weight="650" letter-spacing="2" fill="#97adb9">{html.escape(group.upper())}</text>')
    for node in data["nodes"]:
        x, y = positions[node["id"]]
        selected = node["id"] == "product/shell"
        fill, stroke = ("#17342f", "#8ce3c0") if selected else ("#111d28", "#344957")
        lines.append(f'<a href="../../knowledge/{node["href"]}"><rect x="{x}" y="{y}" width="310" height="70" rx="9" fill="{fill}" stroke="{stroke}"/>')
        labels = textwrap.wrap(node["title"], width=36)[:2]
        for index, label in enumerate(labels):
            lines.append(f'<text x="{x + 13}" y="{y + 25 + index * 16}" font-size="13" font-weight="600" fill="#edf4f5">{html.escape(label)}</text>')
        count = sum(edge["from"] == node["id"] for edge in data["edges"])
        lines.append(f'<text x="{x + 13}" y="{y + 57}" font-size="10" fill="#97adb9">{html.escape(node["status"])} · {count} outgoing links</text></a>')
    lines.append(f'<text x="32" y="{height - 43}" font-size="12" fill="#97adb9">Overview: {len(overview_edges(data))} actual links. Open the interactive map to search and trace all {len(data["edges"])} relationships.</text>')
    lines.append(f'<text x="32" y="{height - 22}" font-size="11" fill="#8298a6">Draft summaries. Static firmware evidence does not establish physical validation or an installable replacement OS.</text>')
    lines.extend(["</g></svg>", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = graph_data(load_bundle(args.root / "knowledge"))
    exports = {"knowledge/graph.html": html_view(data), "docs/knowledge-graph.md": markdown_view(data),
               "docs/assets/knowledge-graph.svg": svg_view(data)}
    stale = []
    for relative, content in exports.items():
        path = args.root / relative
        if args.check:
            if not path.is_file() or path.read_text() != content:
                stale.append(relative)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
    print(json.dumps({"concepts": len(data["nodes"]), "relationships": len(data["edges"]),
                      "overview_relationships": len(overview_edges(data)), "stale": stale,
                      "mode": "check" if args.check else "write"}))
    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
