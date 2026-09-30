"""Sanity-check the generated API page: tag balance, structure counts, spot checks."""
from __future__ import annotations

import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


class Dom(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = {"tag": "#root", "attrs": {}, "kids": []}
        self.stack = [self.root]
        self.errors: list[str] = []

    def handle_starttag(self, tag, attrs):
        node = {"tag": tag, "attrs": dict(attrs), "kids": []}
        self.stack[-1]["kids"].append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1]["kids"].append({"tag": tag, "attrs": dict(attrs), "kids": []})

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if len(self.stack) == 1:
            self.errors.append(f"stray </{tag}>")
            return
        if self.stack[-1]["tag"] != tag:
            self.errors.append(f"expected </{self.stack[-1]['tag']}> but found </{tag}>")
            for i in range(len(self.stack) - 1, 0, -1):
                if self.stack[i]["tag"] == tag:
                    del self.stack[i:]
                    return
            return
        self.stack.pop()

    def handle_data(self, data):
        self.stack[-1]["kids"].append({"tag": "#text", "attrs": {}, "kids": [], "text": data})


BLOCK = {
    "p", "div", "li", "ul", "ol", "table", "tr", "td", "th", "pre", "details",
    "summary", "section", "h1", "h2", "h3", "h4", "h5", "h6", "aside", "main",
}


def text_of(node) -> str:
    if node["tag"] == "#text":
        return node.get("text", "")
    if node["tag"] in ("script", "style"):
        return ""
    inner = "".join(text_of(k) for k in node["kids"])
    return f"\n{inner}\n" if node["tag"] in BLOCK else inner


def find_by_id(node, target):
    if node.get("attrs", {}).get("id") == target:
        return node
    for kid in node.get("kids", []):
        hit = find_by_id(kid, target)
        if hit:
            return hit
    return None


def walk(node, tag):
    if node["tag"] == tag:
        yield node
    for kid in node.get("kids", []):
        yield from walk(kid, tag)


def tidy(text: str, width: int = 100) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    lines = [l.strip() for l in text.split("\n")]
    return "\n".join(l for l in lines if l)[:width]


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "api.html")
    raw = path.read_text(encoding="utf-8")
    dom = Dom()
    dom.feed(raw)

    print(f"file            : {path}  ({len(raw):,} chars)")
    print(f"unclosed tags   : {[n['tag'] for n in dom.stack[1:]] or 'none'}")
    print(f"parse errors    : {dom.errors[:10] or 'none'}")
    print(f"modules         : {sum(1 for n in walk(dom.root, 'section') if 'module' in n['attrs'].get('class','').split())}")
    print(f"categories      : {sum(1 for n in walk(dom.root, 'section') if 'cat' in n['attrs'].get('class','').split())}")
    print(f"api items       : {sum(1 for n in walk(dom.root, 'div') if 'api-item' in n['attrs'].get('class',''))}")
    print(f"param rows      : {sum(1 for n in walk(dom.root, 'div') if 'param' == n['attrs'].get('class',''))}")
    print(f"doc sections    : {sum(1 for n in walk(dom.root, 'div') if 'doc-section' in n['attrs'].get('class',''))}")
    print(f"undocumented    : {raw.count('No description provided.')}")
    print(f"suspicious NUL  : {raw.count(chr(0))}")
    stray = re.findall(r"&(?!amp;|lt;|gt;|quot;|#\d+;|#x[0-9a-fA-F]+;)", raw)
    print(f"stray entity    : {len(stray)}")
    for m in list(re.finditer(r"&(?!amp;|lt;|gt;|quot;|#\d+;|#x[0-9a-fA-F]+;)", raw))[:6]:
        print(f"    ...{raw[max(0, m.start()-60):m.start()+40]!r}")
    print(f"utf8 arrows     : {raw.count(chr(0x2192))}  em-dashes: {raw.count(chr(0x2014))}")

    # --- leak / malformation detectors -------------------------------------
    print(f"nav modules     : {raw.count('class=\"nav-module\"')}")
    print(f"empty <code>    : {raw.count('<code></code>')}")
    leaked = {h: raw.count(f"{h}:") for h in ("Args", "Arguments", "Parameters", "Returns", "Raises", "Attributes", "Example", "Examples", "Note", "Notes")}
    print(f"leaked headers  : { {k: v for k, v in leaked.items() if v} }")
    sections: dict[str, int] = {}
    for m in re.finditer(r'<div class="doc-section"><h5>([^<]+)</h5>', raw):
        sections[m.group(1)] = sections.get(m.group(1), 0) + 1
    print(f"section titles  : {dict(sorted(sections.items(), key=lambda kv: -kv[1]))}")
    names = [m.group(1) for m in re.finditer(r'<div class="pname"><code>([^<]*)</code>', raw)]
    blank = [n for n in names if not n.strip()]
    longest = sorted(names, key=len, reverse=True)[:3]
    print(f"param names     : {len(names)}  blank={len(blank)}  longest={longest}")
    print(f"empty pdesc     : {raw.count('<p></p>')}")

    # --- link integrity: every nav/anchor target must resolve -----------------
    ids = re.findall(r'\sid="([^"]+)"', raw)
    hrefs = re.findall(r'href="#([^"]+)"', raw)
    id_set = set(ids)
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    missing = sorted({h for h in hrefs if h not in id_set})
    print(f"anchor ids      : {len(ids)} total, {len(id_set)} unique, duplicates={dupes[:5] or 'none'}")
    print(f"internal links  : {len(hrefs)} hrefs, broken={len(missing)} {missing[:8]}")
    api_items = sum(1 for n in walk(dom.root, "div") if "api-item" in n["attrs"].get("class", ""))
    nav_syms = raw.count('class="nav-sym ')
    print(f"nav syms vs api : {nav_syms} nav links vs {api_items} api items")

    for anchor in sys.argv[2:]:
        node = find_by_id(dom.root, anchor)
        print("\n" + "=" * 100)
        if not node:
            print(f"[MISSING] #{anchor}")
            continue
        sig = ""
        for n in walk(node, "h4") or []:
            sig = tidy(text_of(n), 300)
            break
        if not sig:
            for tag in ("h5", "h6", "h3"):
                found = list(walk(node, tag))
                if found:
                    sig = tidy(text_of(found[0]), 300)
                    break
        print(f"#{anchor}\n  SIG: {sig}")
        print("-" * 100)
        print(tidy(text_of(node), 2600))


if __name__ == "__main__":
    main()
