"""Render a self-contained HTML API reference for the watermarklab package.

Input : api_dump.json (produced by extract_api.py)
Output: one standalone .html file -- inline CSS/JS, no CDN, works offline.
"""
from __future__ import annotations

import base64
import html
import json
import re
import textwrap
from pathlib import Path
import sys

from highlight import highlight as highlight_code

VERSION = "0.1.22"

# ---------------------------------------------------------------- text utils

SECTION_NAMES = {
    "args": "Parameters",
    "arguments": "Parameters",
    "parameters": "Parameters",
    "params": "Parameters",
    "keyword args": "Parameters",
    "keyword arguments": "Parameters",
    "other parameters": "Parameters",
    "returns": "Returns",
    "return": "Returns",
    "yields": "Yields",
    "raises": "Raises",
    "attributes": "Attributes",
    "methods": "Methods",
    "example": "Examples",
    "examples": "Examples",
    "note": "Notes",
    "notes": "Notes",
    "warning": "Warnings",
    "warnings": "Warnings",
    "see also": "See Also",
    "references": "References",
    "todo": "Todo",
}

ENTRY_SECTIONS = {"Parameters", "Attributes", "Returns", "Yields", "Raises", "Methods"}


def inline(text: str) -> str:
    """Escape HTML then apply lightweight inline markup."""
    out = html.escape(text, quote=False)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<![\w*])\*([^*\s][^*]*)\*(?![\w*])", r"<em>\1</em>", out)
    return out


def indent_of(line: str) -> int:
    return len(line) - len(line.lstrip())


def render_paragraph_block(lines: list[str]) -> str:
    """Render free text: paragraphs, bullets, fenced and indented code."""
    out: list[str] = []
    buf: list[str] = []
    bullets: list[str] = []
    code: list[str] = []
    in_fence = False
    fence_lang = ""

    def flush_para() -> None:
        nonlocal buf
        if buf:
            text = " ".join(x.strip() for x in buf if x.strip())
            if text:
                out.append(f"<p>{inline(text)}</p>")
            buf = []

    def flush_bullets() -> None:
        nonlocal bullets
        if bullets:
            items = "".join(f"<li>{inline(b)}</li>" for b in bullets)
            out.append(f"<ul>{items}</ul>")
            bullets = []

    def flush_code() -> None:
        nonlocal code, fence_lang
        if code:
            raw = "\n".join(code)
            lang = "bash" if fence_lang.lower() in ("bash", "sh", "shell", "console") else "python"
            cls = f' class="language-{fence_lang}"' if fence_lang else ""
            out.append(f"<pre><code{cls}>{highlight_code(raw, lang)}</code></pre>")
            code = []
            fence_lang = ""

    for raw in lines:
        stripped = raw.strip()

        if stripped.startswith("```"):
            if in_fence:
                in_fence = False
                flush_code()
            else:
                flush_para()
                flush_bullets()
                in_fence = True
                fence_lang = stripped[3:].strip()
            continue

        if in_fence:
            code.append(raw)
            continue

        # indented code block (4+ spaces) that is not a bullet continuation
        if stripped and indent_of(raw) >= 4 and not stripped.startswith(("-", "*", "+")):
            if not code:
                flush_para()
                flush_bullets()
            code.append(raw[4:] if raw[:4].strip() == "" else raw)
            continue

        if code:
            flush_code()

        if not stripped:
            flush_para()
            flush_bullets()
            continue

        m = re.match(r"^[-*\u2022]\s+(.*)$", stripped)
        if m:
            flush_para()
            bullets.append(m.group(1))
            continue

        flush_bullets()
        buf.append(stripped)

    if in_fence:
        flush_code()
    flush_para()
    flush_bullets()
    return "\n".join(out)


_NAME = r"[A-Za-z_*][\w.*]*"


def entry_start(s: str) -> tuple[str, str, str] | None:
    """Recognise the leading line of a parameter entry across docstring dialects."""
    s = re.sub(r"^[-*\u2022]\s+", "", s, count=1)

    # NumPy style:  name : type      (conventionally a space before the colon)
    m = re.match(rf"^({_NAME})\s+:\s*(.*)$", s)
    if m and m.group(1).lstrip("*"):
        return m.group(1).lstrip("*"), m.group(2), ""

    # Google style with type:  name (type): desc
    m = re.match(rf"^({_NAME})\s*\(([^)]*)\)\s*:\s*(.*)$", s)
    if m and m.group(1).lstrip("*"):
        return m.group(1).lstrip("*"), m.group(2), m.group(3)

    # Callable header:  name(a, b) -> ret: desc
    m = re.match(rf"^({_NAME})\s*\([^)]*\)\s*(?:->\s*[^:]+)?\s*:\s*(.*)$", s)
    if m and m.group(1).lstrip("*"):
        return m.group(1).lstrip("*") + "()", "", m.group(2)

    # Google style without type, incl. generics:  name: desc  |  List[int]: desc
    m = re.match(rf"^({_NAME}(?:\[[^\]]*\])?)\s*:\s*(.*)$", s)
    if m and m.group(1).lstrip("*"):
        return m.group(1).lstrip("*"), "", m.group(2)

    return None


def parse_entries(body: list[str]) -> tuple[list[str], list[dict]]:
    """Split a section body into leading prose plus (name, type, description) entries."""
    preamble: list[str] = []
    entries: list[dict] = []
    cur: dict | None = None

    for raw in body:
        if not raw.strip():
            if cur is not None:
                cur["desc"].append("")
            elif preamble:
                preamble.append("")
            continue
        indent = indent_of(raw)
        stripped = raw.strip()
        parsed = entry_start(stripped)

        if parsed and (cur is None or indent <= cur["indent"]):
            name, typ, rest = parsed
            cur = {"name": name, "type": typ, "desc": [rest] if rest else [], "indent": indent}
            entries.append(cur)
        elif cur is None:
            preamble.append(stripped)
        else:
            cur["desc"].append(stripped)

    return preamble, entries


def render_section(title: str, body: list[str]) -> str:
    if title in ENTRY_SECTIONS:
        preamble, entries = parse_entries(body)
        chunks = []
        if preamble:
            chunks.append(render_paragraph_block(preamble))
        for e in entries:
            desc_lines = list(e["desc"])
            while desc_lines and not desc_lines[-1].strip():
                desc_lines.pop()
            desc = render_paragraph_block(desc_lines) if desc_lines else ""
            label = html.escape(e["name"])
            if e["type"]:
                label += f'<span class="ptype">{html.escape(e["type"])}</span>'
            chunks.append(
                f'<div class="param"><div class="pname"><code>{label}</code></div>'
                f'<div class="pdesc">{desc}</div></div>'
            )
        inner = "".join(chunks) or render_paragraph_block(body)
    else:
        inner = render_paragraph_block(body)
    return f'<div class="doc-section"><h5>{html.escape(title)}</h5>{inner}</div>'


def split_sections(lines: list[str]) -> tuple[list[str], list[tuple[str, list[str]]]]:
    marks: list[tuple[int, str, int]] = []
    i = 0
    while i < len(lines):
        m = re.fullmatch(r"\s*([A-Za-z][A-Za-z ]*):\s*", lines[i])
        if m and m.group(1).strip().lower() in SECTION_NAMES:
            underline = i + 1 < len(lines) and re.fullmatch(r"\s*-{3,}\s*", lines[i + 1])
            marks.append((i, SECTION_NAMES[m.group(1).strip().lower()], 2 if underline else 1))
            i += 2 if underline else 1
            continue
        i += 1

    if not marks:
        return lines, []

    summary = lines[: marks[0][0]]
    sections: list[tuple[str, list[str]]] = []
    for idx, (start, title, skip) in enumerate(marks):
        end = marks[idx + 1][0] if idx + 1 < len(marks) else len(lines)
        sections.append((title, lines[start + skip : end]))
    return summary, sections


def render_docstring(doc: str | None) -> str:
    if not doc or not doc.strip():
        return '<p class="nodesc">No description provided.</p>'
    lines = textwrap.dedent(doc).strip("\n").split("\n")
    summary, sections = split_sections(lines)
    parts = []
    head = render_paragraph_block(summary)
    if head:
        parts.append(f'<div class="doc-summary">{head}</div>')
    for title, body in sections:
        parts.append(render_section(title, body))
    return "\n".join(parts) or '<p class="nodesc">No description provided.</p>'


# ---------------------------------------------------------------- signature

DECORATOR_LABELS = {
    "staticmethod": "static",
    "classmethod": "classmethod",
    "property": "property",
    "abstractmethod": "abstract",
}


def render_decorators(decs: list[str]) -> str:
    badges = []
    for d in decs:
        key = d.split("(")[0].strip().split(".")[-1]
        if key in ("overload", "abstractmethod", "staticmethod", "classmethod", "property"):
            badges.append(f'<span class="badge">{DECORATOR_LABELS.get(key, key)}</span>')
    return "".join(badges)


TYPE_WORDS = (
    "int|str|float|bool|None|dict|list|tuple|set|bytes|Any|List|Dict|Tuple|Set|Optional|Union|Callable|"
    "Sequence|Iterable|Literal|Type|torch\\.Tensor|torch\\.device|Tensor|DataLoader|"
    "BaseWatermarkModel|BaseMetric|BaseDiffAttackModel|BaseDiffNoiseModel|AttackerWithFactors"
)

_STR_RE = re.compile(r"(&#x27;|&#39;|')([^']*)\1|\"([^\"]*)\"")


def color_signature(name: str, sig: str) -> str:
    """Escape a signature and add light token colouring.

    String literals are protected first so that digits or type words inside them
    (e.g. 'MS-COCO-2017-VAL') are never re-coloured.
    """
    text = html.escape(name + sig, quote=False)

    protected: list[str] = []

    def stash(m: re.Match) -> str:
        protected.append(m.group(0))
        return f"\x00{len(protected) - 1}\x00"

    text = _STR_RE.sub(stash, text)
    text = re.sub(rf"\b({TYPE_WORDS})\b", r'<span class="ty">\1</span>', text)
    # only colour numeric literals used as default values / indices
    text = re.sub(r"([=\[(,]\s*)(\d+\.?\d*)", r'\1<span class="nu">\2</span>', text)

    def restore(m: re.Match) -> str:
        return f'<span class="st">{protected[int(m.group(1))]}</span>'

    return re.sub(r"\x00(\d+)\x00", restore, text)


# ---------------------------------------------------------------- page build

CATEGORY_COLORS = {
    "watermarks": "#7c3aed",
    "attackers": "#ea580c",
    "metrics": "#0d9488",
    "tools": "#db2777",
    "datasets": "#0891b2",
    "laboratories": "#2563eb",
    "draw": "#65a30d",
    "steganography": "#0284c7",
    "other": "#64748b",
}

# The seven core modules of the framework, following the order used in the paper
# ("WatermarkLab adopts a modular and extensible architecture ... it consists of
# seven core modules").
MAJOR_CATEGORIES = [
    {
        "id": "watermarks",
        "icon": "\u25C8",
        "title": "watermarks",
        "desc": "Ten reference methods for comparative studies \u2014 seven post-generation and three "
                "in-generation.",
        "groups": [
            ("Post-generation (PGW)", ["watermarklab.watermarks.PGWs"]),
            ("In-generation (IGW)", ["watermarklab.watermarks.IGWs"]),
        ],
    },
    {
        "id": "attackers",
        "icon": "\u26A1",
        "title": "attackers",
        "desc": "TestAttacker for benchmarking robustness, and differentiable DiffAttacker for adversarial "
                "training and the development of new methods. The default <code>AttackersWithFactorsModel()"
                "</code> ships 44 attack configurations; the paper's benchmark evaluates 34 of them.",
        "groups": [
            ("Attacker collection", ["watermarklab.attackers.attackerloader"]),
            ("Test attackers", ["watermarklab.attackers.testattackers"]),
            ("Differentiable attackers", ["watermarklab.attackers.diffattackers"]),
        ],
    },
    {
        "id": "metrics",
        "icon": "\u25A4",
        "title": "metrics",
        "desc": "Robustness metrics (BER, EA, TPR@x%FPR) and imperceptibility metrics (PSNR, SSIM, LPIPS, FID), "
                "plus a base class for custom metrics.",
        "groups": [("Robustness & visual quality", ["watermarklab.metrics"])],
    },
    {
        "id": "tools",
        "icon": "\u2726",
        "title": "tools",
        "desc": "Auxiliary utilities such as compression coding and reversible data hiding, supporting the "
                "development of robust reversible watermarking.",
        "groups": [("Coding & reversible data hiding", ["watermarklab.tools"])],
    },
    {
        "id": "datasets",
        "icon": "\u25A6",
        "title": "datasets",
        "desc": "Mainstream benchmarks \u2014 MS-COCO 2017 images and captions, Kodak24 and USC-SIPI \u2014 with the "
                "batched loader that pairs data with watermark bits.",
        "groups": [
            ("Benchmark datasets", ["watermarklab.datasets"]),
            ("Batched loading", ["watermarklab.utils.data"]),
        ],
    },
    {
        "id": "laboratories",
        "icon": "\u2699",
        "title": "laboratories",
        "desc": "The evaluation platform for PGW and IGW methods, together with the base interfaces you "
                "implement to plug in your own model, attacker or metric.",
        "groups": [
            ("Evaluation entry points", ["watermarklab.laboratories"]),
            (
                "Base interfaces & configuration",
                ["watermarklab.utils.basemodel", "watermarklab.utils.parameters"],
            ),
        ],
    },
    {
        "id": "draw",
        "icon": "\u25E7",
        "title": "draw",
        "desc": "Visualization and interactive analysis: robustness curves, model and attacker rankings, "
                "visual-quality plots and stego / attack comparisons.",
        "groups": [("Visualization", ["watermarklab.draw"])],
    },
    {
        "id": "steganography",
        "icon": "\u25A3",
        "title": "steganography",
        "desc": "iSteganoGAN, an improved SteganoGAN model that uses L-BFGS for more accurate and stable "
                "watermark extraction. It ships with the library and subclasses "
                "<code>BaseWatermarkModel</code>, but is not one of the seven modules enumerated in the "
                "paper.",
        "groups": [("Steganography models", ["watermarklab.steganography"])],
    },
]

ATTACKER_CALLOUT = (
    '<div class="callout"><strong>Research and defensive use only</strong>'
    "The attack implementations exist to measure watermark robustness. The project licence explicitly "
    "forbids using them to strip watermarks from content you are not authorised to modify. "
    'See <a href="license.html">License</a>.</div>'
)

IMPORT_SURFACE = [
    ("watermarklab.evaluate", "function", "Run a full benchmark for one watermarking model."),
    ("watermarklab.WLab", "class", "Configurable evaluation orchestrator (PGW + IGW)."),
    ("watermarklab.draw", "module", "Plotting helpers: robustness, visual quality, rankings."),
    ("watermarklab.tools", "module", "Arithmetic coding and prediction-error-expansion utilities."),
    (
        "watermarklab.metrics",
        "module",
        "Function-style metrics: `ssim`, `psnr`, `neb`, `ber`, `extraction_accuracy`, "
        "`normalized_correlation`, `lpips`. Metric *classes* such as `PSNR()` and `SSIM()` "
        "live in `watermarklab.metrics.metrics4test`.",
    ),
    (
        "watermarklab.set_load_from_local",
        "function",
        "Sets the module-level `LOAD_FROM_LOCAL` flag, which some IGW models read as their "
        "`local_files_only` default.",
    ),
]


def slug(text: str) -> str:
    s = re.sub(r"[^\w.\-]+", "-", text).strip("-")
    return s.lower() or "x"


def hidden_method(name: str) -> bool:
    """A member is hidden when it is private and is not a public dunder."""
    if name in ("__init__", "__call__"):
        return False
    return name.startswith("_")


# Modules that exist purely as internal implementation support.
INTERNAL_MODULES = {
    "watermarklab.attackers.diffattackers.utils_printcapture",
    "watermarklab.utils.logger",
}


def filter_modules(dump: dict) -> dict:
    """Restrict the dump to the documented public API surface.

    A module-level symbol is public when its module declares ``__all__`` and lists
    it, or when the module declares no ``__all__`` at all (convention: everything
    at module level is the API). Modules in INTERNAL_MODULES are dropped entirely,
    as are nested classes, which are implementation detail in this codebase.
    """
    kept_modules = []
    for module in dump["modules"]:
        if module["module"] in INTERNAL_MODULES:
            continue
        exported = module.get("all")

        def is_exported(name: str, exported=exported) -> bool:
            return True if exported is None else name in exported

        classes = []
        for cls in module.get("classes", []):
            if not is_exported(cls["name"]) or hidden_method(cls["name"]):
                continue
            clone = dict(cls)
            clone["methods"] = [m for m in cls.get("methods", []) if not hidden_method(m["name"])]
            clone["nested_classes"] = []
            classes.append(clone)

        functions = [
            f for f in module.get("functions", [])
            if is_exported(f["name"]) and not hidden_method(f["name"])
        ]
        if not classes and not functions:
            continue

        clone = dict(module)
        clone["classes"] = classes
        clone["functions"] = functions
        kept_modules.append(clone)

    out = dict(dump)
    out["modules"] = kept_modules
    return out


def collect_modules(dump: dict) -> dict[str, dict]:
    return {m["module"]: m for m in dump["modules"]}


def module_sort_key(module: dict) -> tuple:
    return (module["module"].count("."), module["module"])


def render_class(cls: dict, module_name: str, depth: int = 2) -> str:
    bases = f"({', '.join(html.escape(b) for b in cls['bases'])})" if cls["bases"] else ""
    anchor = slug(f"{module_name}.{cls['name']}")
    parts = [
        f'<div class="api-item class-item" id="{anchor}" data-kind="class" '
        f'data-name="{html.escape(cls["name"].lower())}">'
    ]
    parts.append(
        f'<h{4 if depth == 2 else 5} class="api-name"><span class="kind kind-class">class</span>'
        f'<span class="sig">{color_signature(cls["name"], bases)}</span>'
        f"{render_decorators(cls['decorators'])}"
        f'<a class="anchor" href="#{anchor}" title="Permalink">#</a></h{4 if depth == 2 else 5}>'
    )
    parts.append(f'<div class="api-doc">{render_docstring(cls.get("docstring"))}</div>')

    methods = [m for m in cls.get("methods", []) if not hidden_method(m["name"])]
    documented_init = [m for m in methods if m["name"] == "__init__"]
    if methods:
        parts.append('<div class="methods">')
        for m in methods:
            manchor = slug(f"{module_name}.{cls['name']}.{m['name']}")
            label = "Constructor" if m["name"] == "__init__" else m["name"]
            parts.append(
                f'<div class="api-item method-item" id="{manchor}" data-kind="method" '
                f'data-name="{html.escape(m["name"].lower())}">'
            )
            parts.append(
                f'<h6 class="api-name">{render_decorators(m["decorators"])}'
                f'<span class="sig sig-method">{color_signature(label, m["signature"])}</span>'
                f'<a class="anchor" href="#{manchor}" title="Permalink">#</a></h6>'
            )
            parts.append(f'<div class="api-doc">{render_docstring(m.get("docstring"))}</div>')
            parts.append("</div>")
        parts.append("</div>")

    for inner in cls.get("nested_classes", []):
        parts.append(render_class(inner, module_name, depth + 1))

    parts.append("</div>")
    return "\n".join(parts)


def render_function(fn: dict, module_name: str) -> str:
    anchor = slug(f"{module_name}.{fn['name']}")
    return "\n".join(
        [
            f'<div class="api-item" id="{anchor}" data-kind="function" data-name="{html.escape(fn["name"].lower())}">',
            f'<h4 class="api-name"><span class="kind kind-function">function</span>'
            f"{render_decorators(fn['decorators'])}"
            f'<span class="sig">{color_signature(fn["name"], fn["signature"])}</span>'
            f'<a class="anchor" href="#{anchor}" title="Permalink">#</a></h4>',
            f'<div class="api-doc">{render_docstring(fn.get("docstring"))}</div>',
            "</div>",
        ]
    )


def render_module(module: dict) -> str:
    name = module["module"]
    short = name.replace("watermarklab.", "")
    anchor = slug(name)
    parts = [
        f'<section class="module" id="{anchor}" data-module="{html.escape(name)}" '
        f'data-text="{html.escape((name + " " + (module.get("docstring") or "")).lower())}">',
        f'<div class="module-head"><h3><code>{html.escape(name)}</code></h3>'
        f'<span class="src">{html.escape(module["file"])}</span></div>',
    ]
    if module.get("docstring"):
        parts.append(f'<div class="module-doc">{render_docstring(module["docstring"])}</div>')

    parts.append('<div class="api-body">')
    for fn in module.get("functions", []):
        parts.append(render_function(fn, name))
    for cls in module.get("classes", []):
        parts.append(render_class(cls, name))
    parts.append("</div></section>")
    return "\n".join(parts)


def build_nav(modules: list[dict]) -> str:
    items = []
    for module in modules:
        name = module["module"]
        anchor = slug(name)
        symbols = []
        for cls in module.get("classes", []):
            symbols.append((cls["name"], slug(f"{name}.{cls['name']}"), "class"))
            for m in cls.get("methods", []):
                if not hidden_method(m["name"]):
                    symbols.append((f"{cls['name']}.{m['name']}", slug(f"{name}.{cls['name']}.{m['name']}"), "method"))
        for fn in module.get("functions", []):
            symbols.append((fn["name"], slug(f"{name}.{fn['name']}"), "function"))

        sub = "".join(
            f'<a class="nav-sym nav-{kind}" href="#{sym_anchor}" data-search="{html.escape((name + "." + label).lower())}">'
            f"{html.escape(label)}</a>"
            for label, sym_anchor, kind in symbols
        )
        items.append(
            f'<div class="nav-module" data-search="{html.escape(name.lower())}">'
            f'<a class="nav-module-link" href="#{anchor}"><code>{html.escape(name.replace("watermarklab.", ""))}</code>'
            f'<span class="count">{len(symbols)}</span></a>'
            f'<div class="nav-syms">{sub}</div></div>'
        )
    return "".join(items)


def logo_data_uri(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if len(raw) > 200_000:
        return None
    return "data:image/svg+xml;base64," + base64.b64encode(raw).decode("ascii")


def readme_blocks(path: Path) -> list[tuple[str, str]]:
    """Extract (heading, code) pairs from the README fenced blocks."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    blocks: list[tuple[str, str]] = []
    heading = "Example"
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
        if line.strip().startswith("```"):
            lang = line.strip()[3:].strip() or "python"
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            code = "\n".join(buf).strip("\n")
            if code and "pip install" not in code and "huggingface-cli" not in code:
                blocks.append((heading, code))
        i += 1
    return blocks


CSS = """
:root{
  --bg:#ffffff; --bg-alt:#f7f8fa; --panel:#ffffff; --ink:#1b1f24; --muted:#656d76;
  --border:#e3e6ea; --accent:#2563eb; --accent-soft:#eaf1ff; --code-bg:#f4f6f8;
  --class:#7c3aed; --func:#0d9488; --method:#b45309; --shadow:0 1px 3px rgba(16,24,40,.06);
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#0f1115; --bg-alt:#14171c; --panel:#14171c; --ink:#e6e9ee; --muted:#9aa4b2;
    --border:#252a31; --accent:#6ea8fe; --accent-soft:#1b2537; --code-bg:#1a1f26;
    --class:#c4a2ff; --func:#4fd1c5; --method:#f0b46b; --shadow:none;
  }
}
*{box-sizing:border-box}
html{scroll-behavior:smooth; scroll-padding-top:80px}
body{
  margin:0; background:var(--bg); color:var(--ink);
  font:15px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,"Noto Sans",sans-serif;
}
code,pre,.sig{font-family:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,"Liberation Mono",monospace}
a{color:var(--accent); text-decoration:none}
a:hover{text-decoration:underline}
.layout{display:flex; min-height:100vh}

/* ---------- sidebar ---------- */
.sidebar{
  width:310px; flex:0 0 310px; background:var(--bg-alt); border-right:1px solid var(--border);
  position:sticky; top:0; height:100vh; display:flex; flex-direction:column;
}
.brand{padding:14px 16px 10px; border-bottom:1px solid var(--border); display:flex; align-items:center; gap:10px}
.brand img{width:30px;height:30px}
.brand b{font-size:15px; letter-spacing:.2px}
.brand small{display:block; color:var(--muted); font-weight:400; font-size:11.5px}
.searchwrap{padding:10px 12px; border-bottom:1px solid var(--border)}
.searchwrap input{
  width:100%; padding:7px 10px; border:1px solid var(--border); border-radius:7px;
  background:var(--panel); color:var(--ink); font-size:13px; outline:none;
}
.searchwrap input:focus{border-color:var(--accent)}
.searchhint{display:flex; justify-content:space-between; font-size:11px; color:var(--muted); margin-top:6px}
.nav{overflow:auto; padding:8px 8px 40px; flex:1}
.nav h4{margin:14px 8px 6px; font-size:11px; text-transform:uppercase; letter-spacing:.08em; color:var(--muted)}
.nav-module{margin-bottom:2px}
.nav-module-link{
  display:flex; justify-content:space-between; align-items:center; gap:6px;
  padding:5px 8px; border-radius:6px; color:var(--ink); font-size:12.5px;
}
.nav-module-link:hover{background:var(--accent-soft); text-decoration:none}
.nav-module-link code{font-size:12px}
.nav-module-link .count{color:var(--muted); font-size:10.5px}
.nav-syms{display:none; margin:2px 0 6px 10px; border-left:1px solid var(--border); padding-left:6px}
.nav-module.open .nav-syms{display:block}
.nav-sym{display:block; padding:2.5px 8px; border-radius:5px; color:var(--muted); font-size:12px}
.nav-sym:hover{background:var(--accent-soft); color:var(--ink); text-decoration:none}
.nav-sym::before{content:"\\2022"; margin-right:6px; opacity:.5}
.nav-class::before{color:var(--class)}
.nav-function::before{color:var(--func)}
.nav-method::before{color:var(--method)}
.nav-module.hidden,.nav-sym.hidden{display:none}

/* ---------- main ---------- */
.main{flex:1; min-width:0; padding:0 0 120px}
.hero{padding:34px 44px 24px; border-bottom:1px solid var(--border); background:var(--bg-alt)}
.hero h1{margin:0 0 6px; font-size:27px; letter-spacing:-.3px}
.hero p{margin:0; color:var(--muted); max-width:760px}
.hero .pills{margin-top:14px; display:flex; flex-wrap:wrap; gap:8px}
.pill{
  background:var(--panel); border:1px solid var(--border); border-radius:999px;
  padding:4px 12px; font-size:12px; color:var(--muted)
}
.pill b{color:var(--ink); font-weight:600}
.content{padding:8px 44px 0; max-width:1180px}
h2.group-title{
  margin:38px 0 4px; font-size:19px; padding-bottom:8px; border-bottom:2px solid var(--accent);
  display:inline-block
}
.group-desc{color:var(--muted); margin:6px 0 14px; max-width:820px}
section.module{margin:26px 0 40px; scroll-margin-top:24px}
.module-head{display:flex; flex-wrap:wrap; align-items:baseline; gap:12px; margin-bottom:8px}
.module-head h3{margin:0; font-size:16px}
.module-head h3 code{background:var(--code-bg); padding:3px 9px; border-radius:6px; font-size:13.5px}
.src{color:var(--muted); font-size:11.5px; font-family:ui-monospace,monospace}
.module-doc{color:var(--muted); margin:0 0 14px}
.module-doc p{margin:6px 0}

.api-item{border:1px solid var(--border); border-radius:10px; padding:14px 16px; margin:12px 0; background:var(--panel); box-shadow:var(--shadow)}
.api-item:target{border-color:var(--accent); box-shadow:0 0 0 3px var(--accent-soft)}
.api-name{margin:0 0 10px; display:flex; flex-wrap:wrap; align-items:center; gap:8px; font-size:14px}
h5.api-name{font-size:13.5px} h6.api-name{font-size:13px; margin-bottom:8px}
.sig{word-break:break-word; color:var(--ink)}
.sig-method{font-size:13px}
.kind{
  font-size:10px; text-transform:uppercase; letter-spacing:.06em; padding:2px 7px; border-radius:5px;
  border:1px solid currentColor; font-family:inherit
}
.kind-class{color:var(--class)} .kind-function{color:var(--func)}
.badge{font-size:10px; padding:1.5px 6px; border-radius:5px; background:var(--code-bg); color:var(--muted); border:1px solid var(--border)}
.anchor{color:var(--muted); opacity:0; font-weight:400; margin-left:2px; transition:opacity .12s}
.api-item:hover .anchor{opacity:.6}
.ty{color:var(--class)} .st{color:var(--func)} .nu{color:var(--method)}
.api-doc{color:var(--ink)}
.api-doc p{margin:7px 0}
.api-doc ul{margin:7px 0; padding-left:22px}
.api-doc li{margin:3px 0}
.doc-summary>p:first-child{font-weight:500}
.doc-section{margin:11px 0 0; border-top:1px dashed var(--border); padding-top:9px}
.doc-section h5{margin:0 0 7px; font-size:11px; text-transform:uppercase; letter-spacing:.07em; color:var(--muted)}
.param{display:grid; grid-template-columns:minmax(190px,330px) 1fr; gap:10px; padding:4px 0}
.param .pname code{background:var(--code-bg); padding:2px 6px; border-radius:5px; font-size:12.5px; word-break:normal; overflow-wrap:anywhere}
.ptype{color:var(--muted); margin-left:6px; font-size:12px}
.param .pdesc p{margin:0 0 5px}
.param .pdesc ul{margin:4px 0; padding-left:20px}
pre{background:var(--code-bg); border:1px solid var(--border); border-radius:8px; padding:11px 13px; overflow:auto; font-size:12.5px; margin:9px 0}
pre code{background:none; padding:0}
code{background:var(--code-bg); padding:1.5px 5px; border-radius:4px; font-size:12.5px}
.nodesc{color:var(--muted); font-style:italic; margin:0}
table.imports{width:100%; border-collapse:collapse; margin:12px 0; font-size:13.5px}
table.imports th,table.imports td{border:1px solid var(--border); padding:7px 11px; text-align:left; vertical-align:top}
table.imports th{background:var(--bg-alt); font-size:11.5px; text-transform:uppercase; letter-spacing:.05em; color:var(--muted)}
.quickstart details{border:1px solid var(--border); border-radius:9px; margin:9px 0; background:var(--panel)}
.quickstart summary{cursor:pointer; padding:9px 14px; font-weight:500; font-size:13.5px}
.quickstart details[open] summary{border-bottom:1px solid var(--border)}
.quickstart pre{margin:0; border:none; border-radius:0 0 9px 9px}
.totop{
  position:fixed; right:24px; bottom:24px; background:var(--accent); color:#fff; border:none;
  border-radius:50%; width:42px; height:42px; cursor:pointer; font-size:17px; display:none; box-shadow:0 4px 14px rgba(0,0,0,.18)
}
.totop.show{display:block}
.empty{color:var(--muted); padding:40px 0; text-align:center; display:none}
@media (max-width:900px){
  .sidebar{position:fixed; z-index:20; height:100%; transform:translateX(-100%); transition:transform .2s}
  .sidebar.show{transform:none}
  .content,.hero{padding-left:18px; padding-right:18px}
  .param{grid-template-columns:1fr}
  .menubtn{display:block!important}
}
.menubtn{display:none; position:fixed; left:14px; top:14px; z-index:30; background:var(--panel); border:1px solid var(--border); border-radius:8px; width:38px; height:38px; cursor:pointer; color:var(--ink)}
"""

JS = """
(function(){
  var q = document.getElementById('q');
  var nav = document.getElementById('nav');
  var hint = document.getElementById('hint');
  var modules = Array.prototype.slice.call(document.querySelectorAll('section.module'));
  var navMods = Array.prototype.slice.call(document.querySelectorAll('.nav-module'));
  var empty = document.getElementById('empty');

  // open the module that contains the current anchor
  function openFromHash(){
    var id = location.hash.slice(1);
    if(!id) return;
    var target = document.getElementById(id);
    if(!target) return;
    var mod = target.closest('section.module');
    if(mod){
      var link = nav.querySelector('.nav-module-link[href="#'+mod.id+'"]');
      if(link){ link.parentElement.classList.add('open'); }
    }
  }

  nav.addEventListener('click', function(e){
    var link = e.target.closest('.nav-module-link');
    if(link){ link.parentElement.classList.toggle('open'); }
  });

  function filter(){
    var term = (q.value || '').trim().toLowerCase();
    var shown = 0, shownMods = 0;
    navMods.forEach(function(nm){
      var name = nm.getAttribute('data-search') || '';
      var syms = Array.prototype.slice.call(nm.querySelectorAll('.nav-sym'));
      var symHit = false;
      syms.forEach(function(s){
        var hit = !term || (s.getAttribute('data-search') || '').indexOf(term) !== -1;
        s.classList.toggle('hidden', !hit);
        if(hit) symHit = true;
      });
      var selfHit = !term || name.indexOf(term) !== -1;
      var show = selfHit || symHit;
      nm.classList.toggle('hidden', !show);
      if(show) shownMods++;
      if(term && show) nm.classList.add('open');
      if(!term) nm.classList.remove('open');
    });
    modules.forEach(function(m){
      var hay = (m.getAttribute('data-text') || '') + ' ' + m.textContent.toLowerCase();
      var hit = !term || hay.indexOf(term) !== -1;
      m.style.display = hit ? '' : 'none';
      if(hit) shown++;
    });
    document.querySelectorAll('.group-block').forEach(function(g){
      var mods = Array.prototype.slice.call(g.querySelectorAll('section.module'));
      // groups without any module (e.g. "Getting started") must stay visible
      if(!mods.length) return;
      var visible = mods.some(function(m){ return m.style.display !== 'none'; });
      g.style.display = visible ? '' : 'none';
    });
    empty.style.display = shown ? 'none' : 'block';
    hint.textContent = term ? (shown + ' module' + (shown===1?'':'s') + ' matched') : (modules.length + ' modules');
  }

  q.addEventListener('input', filter);
  q.addEventListener('keydown', function(e){ if(e.key === 'Escape'){ q.value=''; filter(); } });

  // keyboard: "/" focuses search
  document.addEventListener('keydown', function(e){
    if(e.key === '/' && document.activeElement !== q){ e.preventDefault(); q.focus(); }
  });

  var top = document.getElementById('totop');
  window.addEventListener('scroll', function(){
    top.classList.toggle('show', window.scrollY > 600);
  });
  top.addEventListener('click', function(){ window.scrollTo({top:0, behavior:'smooth'}); });

  document.getElementById('menu').addEventListener('click', function(){
    document.querySelector('.sidebar').classList.toggle('show');
  });

  window.addEventListener('hashchange', openFromHash);
  openFromHash();
  filter();
})();
"""


def render_reference(dump: dict) -> tuple[str, str]:
    """Return (sidebar_nav_html, main_body_html) for the whole reference."""
    by_name = collect_modules(dump)
    used: set[str] = set()
    body_parts: list[str] = []
    nav_parts: list[str] = []

    for cat in MAJOR_CATEGORIES:
        cat_groups: list[tuple[str, list[dict]]] = []
        for group_title, prefixes in cat["groups"]:
            mods = [
                m
                for name, m in sorted(by_name.items(), key=lambda kv: kv[0])
                if name not in used and any(name == p or name.startswith(p + ".") for p in prefixes)
            ]
            if mods:
                used.update(m["module"] for m in mods)
                cat_groups.append((group_title, mods))
        if not cat_groups:
            continue

        entries = sum(
            len(m.get("classes", [])) + len(m.get("functions", []))
            for _, mods in cat_groups
            for m in mods
        )

        nav_parts.append(f'<h4>{html.escape(cat["title"])}</h4>')
        for group_title, mods in cat_groups:
            nav_parts.append(f'<div class="nav-sub">{html.escape(group_title)}</div>')
            nav_parts.append(build_nav(mods))

        inner = []
        for group_title, mods in cat_groups:
            inner.append(f'<div class="subgroup"><h3>{html.escape(group_title)}</h3>')
            inner.append("".join(render_module(m) for m in mods))
            inner.append("</div>")

        callout = ATTACKER_CALLOUT if cat["id"] == "attackers" else ""
        colour = CATEGORY_COLORS.get(cat["id"], CATEGORY_COLORS["other"])
        body_parts.append(
            f'<section class="cat" id="cat-{cat["id"]}" data-rv style="--c:{colour}">'
            '<div class="cat-head">'
            f'<div class="ico">{cat["icon"]}</div>'
            f'<div class="cat-text"><h2>{html.escape(cat["title"])}</h2><p>{cat["desc"]}</p></div>'
            f'<span class="cat-count">{entries} entries</span>'
            "</div>"
            f"{callout}{''.join(inner)}</section>"
        )

    leftovers = [m for name, m in sorted(by_name.items()) if name not in used]
    if leftovers:
        nav_parts.append("<h4>Other modules</h4>" + build_nav(leftovers))
        body_parts.append(
            '<section class="cat" id="cat-other"><div class="cat-head">'
            '<div class="ico">\u00b7</div>'
            "<div class=\"cat-text\"><h2>Other modules</h2>"
            "<p>Remaining modules in the package.</p></div></div>"
            + "".join(render_module(m) for m in leftovers)
            + "</section>"
        )
    return "".join(nav_parts), "".join(body_parts)


def main() -> None:
    dump_path = Path(sys.argv[1] if len(sys.argv) > 1 else "api_dump.json")
    readme_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("README.md")
    logo_path = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("figures/logo.svg")
    out_paths = [Path(p) for p in sys.argv[4:]] or [Path("api.html")]

    dump = json.loads(dump_path.read_text(encoding="utf-8"))
    dump = filter_modules(dump)
    nav_markup, group_markup = render_reference(dump)

    imports_rows = "".join(
        f"<tr><td><code>{html.escape(sym)}</code></td><td>{kind}</td><td>{inline(desc)}</td></tr>"
        for sym, kind, desc in IMPORT_SURFACE
    )

    blocks = readme_blocks(readme_path)
    quickstart = "".join(
        f"<details><summary>{html.escape(heading)}</summary><pre><code>{html.escape(code)}</code></pre></details>"
        for heading, code in blocks
    )

    logo = logo_data_uri(logo_path)
    logo_tag = f'<img src="{logo}" alt="WatermarkLab">' if logo else ""

    class_count = sum(len(m.get("classes", [])) for m in dump["modules"])
    function_count = sum(len(m.get("functions", [])) for m in dump["modules"])
    method_count = sum(
        len([x for x in cls.get("methods", []) if not hidden_method(x["name"])])
        for m in dump["modules"]
        for cls in m.get("classes", [])
    )

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WatermarkLab {VERSION} \u2014 API Reference</title>
<style>{CSS}</style>
</head>
<body>
<button class="menubtn" id="menu" title="Toggle navigation">\u2630</button>
<div class="layout">
  <aside class="sidebar">
    <div class="brand">{logo_tag}<div><b>WatermarkLab</b><small>API Reference \u00b7 v{VERSION}</small></div></div>
    <div class="searchwrap">
      <input id="q" type="search" placeholder="Search modules, classes, methods\u2026  ( / )" autocomplete="off">
      <div class="searchhint"><span id="hint">{dump['module_count']} modules</span><span>Esc to clear</span></div>
    </div>
    <nav class="nav" id="nav">{nav_markup}</nav>
  </aside>
  <main class="main">
    <div class="hero">
      <h1>WatermarkLab {VERSION} \u2014 API Reference</h1>
      <p>A toolkit for robust image watermarking benchmarking and development: run watermark embedding,
      visual-quality measurement, noise-attack robustness testing and result visualization behind one
      unified evaluation entry point.</p>
      <div class="pills">
        <span class="pill"><b>{dump['module_count']}</b> modules</span>
        <span class="pill"><b>{class_count}</b> classes</span>
        <span class="pill"><b>{function_count}</b> functions</span>
        <span class="pill"><b>{method_count}</b> documented methods</span>
        <span class="pill">install: <b>pip install watermarklab</b></span>
      </div>
    </div>
    <div class="content">
      <div class="group-block">
        <h2 class="group-title">Getting started</h2>
        <p class="group-desc">Everything exported by the top-level package, and the benchmark recipes from the project README.</p>
        <div class="api-item">
          <h4 class="api-name"><span class="kind kind-class">import</span><span class="sig">import watermarklab as wl</span></h4>
          <div class="api-doc">
            <table class="imports">
              <thead><tr><th>Name</th><th>Kind</th><th>Description</th></tr></thead>
              <tbody>{imports_rows}</tbody>
            </table>
            <div class="doc-section"><h5>Benchmark recipes</h5>
              <div class="quickstart">{quickstart or '<p class="nodesc">README not found.</p>'}</div>
            </div>
          </div>
        </div>
      </div>
      {group_markup}
      <div class="empty" id="empty">No symbol matches that search.</div>
      <p style="color:var(--muted);font-size:12.5px;margin-top:40px">
        Generated by static AST analysis of the source tree \u2014 every signature, default value and
        module/symbol description below is reproduced verbatim from the code's own annotations and
        docstrings. The import-surface table in <em>Getting started</em> is a hand-written summary.
      </p>
    </div>
  </main>
</div>
<button class="totop" id="totop" title="Back to top">\u2191</button>
<script>{JS}</script>
</body>
</html>
"""

    for out in out_paths:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page, encoding="utf-8")
        print(f"wrote {out}  ({len(page):,} bytes)")
    print(f"modules={dump['module_count']} classes={class_count} functions={function_count}")


if __name__ == "__main__":
    main()
