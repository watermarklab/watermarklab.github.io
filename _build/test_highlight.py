"""Verify the highlighter only inserts span tags and escapes everything else."""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

import highlight as H

STRIP = re.compile(r"</?span[^>]*>")

samples = [
    ("python", "import watermarklab as wl\nx = wl.evaluate('p', m, a, d, noise_save=True)  # go\n"),
    ("python", "class Foo(Base):\n    \"\"\"Doc.\"\"\"\n    def bar(self, n: int = 3) -> dict:\n        return {'k': [i for i in range(n)]}\n"),
    ("python", ">>> frequencies = {symbol: 1 for symbol in frequencies}\n>>> cumsum.get_low_high('a')\n(0, 1)\n"),
    ("python", "if a < b and c > d:\n    print(f\"{a} < {b}\")\n"),
    ("bash", "pip install watermarklab  # install\nhuggingface-cli download chenoly/watermarklab\n"),
]

fail = 0
for lang, code in samples:
    out = H.highlight(code, lang)
    back = html.unescape(STRIP.sub("", out))
    ok = back == code
    spans = out.count("<span")
    print(f"[{'ok ' if ok else 'FAIL'}] {lang:6s} spans={spans:3d}  roundtrip={'match' if ok else 'MISMATCH'}")
    if not ok:
        fail += 1
        print("   in :", repr(code[:90]))
        print("   out:", repr(back[:90]))

for f in sorted(Path("content").glob("*.txt")):
    code = f.read_text(encoding="utf-8").strip("\n")
    out = H.highlight(code, "python")
    back = html.unescape(STRIP.sub("", out))
    ok = back == code
    print(f"[{'ok ' if ok else 'FAIL'}] content/{f.name:24s} spans={out.count('<span'):4d} roundtrip={'match' if ok else 'MISMATCH'}")
    if not ok:
        fail += 1

print(f"\nfailures: {fail}")
sys.exit(1 if fail else 0)
