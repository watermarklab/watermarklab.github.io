# watermarklab.github.io

Documentation site for **WatermarkLab**, served by GitHub Pages at
<https://watermarklab.github.io/>.

    index.html               landing page
    404.html                 not-found page
    pages/api-document.html  quick start, guides and the full API reference
    pages/paper.html         paper summary, attacker table, metrics, results, BibTeX
    pages/license.html       licence text
    _build/                  the generator that produces the HTML above

## Regenerating

The HTML is generated from the library source by static AST analysis:

    python _build/extract_api.py <path-to>/watermarklab _build/api_dump.json
    python _build/build_site.py _build/api_dump.json <path-to>/figures/logo.svg . <path-to>/LICENSE

`_build/README.md` describes every script, and `_build/verify_docs.py` sanity-checks
the generated pages.

## History

This site replaced an earlier interactive visualisation platform, which remains
recoverable from git history (see the commit that introduced this README).
