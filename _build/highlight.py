"""Dependency-free syntax highlighting for the generated documentation.

Python sources are tokenised with the standard-library ``tokenize`` module, so the
colouring follows real lexical analysis rather than regex guesswork. Fragments that
are not valid Python (doctest transcripts, ``>>>`` snippets, pseudo-code) fall back
to a regex highlighter that never raises.
"""
from __future__ import annotations

import builtins
import html
import io
import keyword
import re
import tokenize

BUILTIN_NAMES = frozenset(dir(builtins))
SKIP_TOKENS = {
    tokenize.NEWLINE,
    tokenize.NL,
    tokenize.INDENT,
    tokenize.DEDENT,
    tokenize.ENDMARKER,
    tokenize.ENCODING,
}

PY_KEYWORDS = (
    "def|class|return|if|elif|else|for|while|import|from|as|with|try|except|finally|raise|"
    "pass|break|continue|lambda|yield|global|nonlocal|assert|del|in|is|not|and|or|async|await|"
    "None|True|False|print"
)
PY_BUILTINS = (
    "abs|all|any|bool|bytes|callable|dict|dir|enumerate|filter|float|format|frozenset|getattr|"
    "hasattr|hash|id|int|isinstance|issubclass|iter|len|list|map|max|min|next|object|open|ord|"
    "pow|range|repr|reversed|round|set|setattr|slice|sorted|str|sum|super|tuple|type|vars|zip"
)

PY_FALLBACK = re.compile(
    rf"""
      (?P<c>\#[^\n]*)
    | (?P<s>\"\"\"[\s\S]*?\"\"\"|'''[\s\S]*?'''|\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*')
    | (?P<k>\b(?:{PY_KEYWORDS})\b)
    | (?P<b>\b(?:{PY_BUILTINS})\b)
    | (?P<self>\b(?:self|cls)\b)
    | (?P<f>(?<=def\s)[A-Za-z_]\w*|(?<=class\s)[A-Za-z_]\w*)
    | (?P<n>\b\d+\.?\d*\b)
    | (?P<o>[+\-*/%=<>!&|^~:,.\[\]{{}}()@])
    """,
    re.VERBOSE | re.MULTILINE,
)

BASH_RE = re.compile(
    r"""
      (?P<c>\#[^\n]*)
    | (?P<s>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')
    | (?P<variable>\$\{?\w+\}?)
    | (?P<flag>(?<=\s)--?[A-Za-z][\w-]*)
    | (?P<cmd>(?<=^)[a-z][\w.-]*|(?<=\| )[a-z][\w.-]*)
    | (?P<n>\b\d+\b)
    """,
    re.VERBOSE | re.MULTILINE,
)


def _emit(code: str, marks: list[tuple[int, int, str]]) -> str:
    """Wrap the given character ranges in span tags, in document order."""
    marks = sorted(marks, key=lambda m: (m[0], -(m[1] - m[0])))
    out: list[str] = []
    cursor = 0
    for start, end, cls in marks:
        if start < cursor or end <= start:
            continue
        out.append(html.escape(code[cursor:start]))
        out.append(f'<span class="t-{cls}">{html.escape(code[start:end])}</span>')
        cursor = end
    out.append(html.escape(code[cursor:]))
    return "".join(out)


def _classify(ttype: int, text: str, prev: str | None) -> str | None:
    if ttype == tokenize.COMMENT:
        return "c"
    if ttype == tokenize.STRING:
        return "s"
    if ttype == tokenize.NUMBER:
        return "n"
    if ttype == tokenize.OP:
        return "o"
    if ttype == tokenize.NAME:
        if keyword.iskeyword(text):
            return "k"
        if text in ("self", "cls"):
            return "self"
        if prev == "def":
            return "f"
        if prev == "class":
            return "d"
        if text in BUILTIN_NAMES:
            return "b"
        return None
    return None


def _tokenize_python(code: str) -> str:
    offsets = [0]
    for line in code.split("\n"):
        offsets.append(offsets[-1] + len(line) + 1)

    def pos(row: int, col: int) -> int:
        return offsets[min(row - 1, len(offsets) - 1)] + col

    marks: list[tuple[int, int, str]] = []
    prev: str | None = None
    for tok in tokenize.generate_tokens(io.StringIO(code).readline):
        ttype, text, start, end, _ = tok
        if ttype in SKIP_TOKENS:
            continue
        cls = _classify(ttype, text, prev)
        if cls:
            marks.append((pos(*start), pos(*end), cls))
        if text.strip():
            prev = text
    return _emit(code, marks)


def _regex_python(code: str) -> str:
    marks = []
    for m in PY_FALLBACK.finditer(code):
        cls = m.lastgroup
        if cls:
            marks.append((m.start(), m.end(), cls))
    return _emit(code, marks)


def highlight_python(code: str) -> str:
    try:
        return _tokenize_python(code)
    except Exception:
        return _regex_python(code)


def highlight_bash(code: str) -> str:
    marks = []
    for m in BASH_RE.finditer(code):
        cls = m.lastgroup
        if cls:
            marks.append((m.start(), m.end(), cls))
    return _emit(code, marks)


def highlight(code: str, lang: str = "python") -> str:
    lang = (lang or "python").lower()
    if lang in ("bash", "sh", "shell", "console", "text"):
        return highlight_bash(code) if lang != "text" else html.escape(code)
    return highlight_python(code)
