# docs/_build — site generator

The documentation site is generated from the package source by static AST analysis.
Nothing here runs at import time; it only reads the source and writes the HTML.

Regenerate after changing any docstring, signature or module in watermarklab/:

    python docs/_build/extract_api.py watermarklab docs/_build/api_dump.json
    python docs/_build/build_site.py docs/_build/api_dump.json figures/logo.svg docs LICENSE

Optional checks:

    python docs/_build/verify_docs.py docs/pages/api-document.html
    python docs/_build/test_highlight.py

Files
-----
- extract_api.py    parses watermarklab/**/*.py and dumps signatures + docstrings to JSON
- build_docs.py     renders the API reference (categorised) and can also emit a standalone page
- build_site.py     writes docs/index.html and docs/pages/*.html
- highlight.py      dependency-free syntax highlighting (tokenize-based, regex fallback)
- verify_docs.py    sanity-checks the output: tag balance, unique anchors, broken links
- content/*.txt     the code samples shown in the Quick start section, kept as plain files
                    so their whitespace and backslashes can never be mangled by escaping

Which symbols appear is decided by the source itself: a module-level name is included when
its module declares __all__ and lists it, or when the module declares no __all__ at all.
Underscore-prefixed members are dropped, except __init__ (rendered as "Constructor") and
__call__. The internal modules attackers/diffattackers/utils_printcapture.py and
utils/logger.py are excluded entirely.

Categories
----------
The reference is grouped into five major categories, defined in MAJOR_CATEGORIES in
build_docs.py. Each entry has an id, icon, title, description, colour (CATEGORY_COLORS)
and a list of (subgroup title, module prefixes). Adding a category or moving a module
between categories is a change to that one list.
