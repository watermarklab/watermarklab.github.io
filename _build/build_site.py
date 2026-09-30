"""Generate the WatermarkLab documentation website.

Layout follows the URL declared in setup.py:
    https://watermarklab.github.io/pages/api-document.html
so the site is:  <root>/index.html  +  <root>/pages/*.html

Uses build_docs.py for the API reference rendering so both stay in sync.
"""
from __future__ import annotations

import base64
import html
import json
import sys
from pathlib import Path

import build_docs as bd
from highlight import highlight

VERSION = "0.1.22"
REPO = "https://github.com/watermarklab/watermarklab.github.io"
DOCS_URL = "https://watermarklab.github.io"

# "standalone" writes the whole site (landing + guides + reference).
# "merged" only ADDS pages to the existing interactive site, whose own
# api-document.html already carries the guides and quick-start material.
MODE = "standalone"


def merged() -> bool:
    return MODE == "merged"


def license_href() -> str:
    return "api-document.html#license" if merged() else "license.html"

# --------------------------------------------------------------------- pages

NAV_CSS = """
/* ---------- top navigation ---------- */
.topnav{
  position:sticky; top:0; z-index:60; display:flex; align-items:center; gap:22px;
  padding:0 26px; height:58px; background:var(--bg); border-bottom:1px solid var(--border);
}
.topnav .brand{display:flex; align-items:center; gap:9px; font-weight:600; color:var(--ink); font-size:14.5px}
.topnav .brand:hover{text-decoration:none}
.topnav .brand img{width:24px; height:28px}
.topnav nav{display:flex; align-items:center; gap:4px; margin-left:auto}
.topnav nav a,.topnav nav button{
  font:inherit; font-size:13.5px; color:var(--muted); padding:7px 12px; border-radius:8px;
  background:none; border:none; cursor:pointer; display:block; white-space:nowrap;
}
.topnav nav a:hover,.topnav nav button:hover{background:var(--bg-alt); color:var(--ink); text-decoration:none}
.topnav nav a.active{color:var(--accent); background:var(--accent-soft)}
.dd{position:relative}
.dd>button::after{content:"\\25BE"; margin-left:6px; font-size:11px; opacity:.75}
.dd-menu{
  display:none; position:absolute; right:0; top:calc(100% + 6px); min-width:216px; padding:6px;
  background:var(--panel); border:1px solid var(--border); border-radius:11px;
  box-shadow:0 12px 34px rgba(16,24,40,.14); z-index:70;
}
.dd.open .dd-menu{display:block}
.dd-menu a{padding:8px 11px; border-radius:7px}
footer.site{
  border-top:1px solid var(--border); background:var(--bg-alt); margin-top:60px;
  padding:28px 34px; color:var(--muted); font-size:13px;
}
footer.site .fgrid{display:flex; flex-wrap:wrap; gap:34px; max-width:1180px; margin:0 auto}
footer.site h6{margin:0 0 8px; font-size:11px; letter-spacing:.08em; text-transform:uppercase; color:var(--muted)}
footer.site a{display:block; padding:2.5px 0; color:var(--ink); opacity:.82}
footer.site .fbot{max-width:1180px; margin:20px auto 0; padding-top:16px; border-top:1px solid var(--border); font-size:12px}

/* ---------- doc page shell ---------- */
.docnav-offset{scroll-margin-top:76px}
.prose{max-width:1040px; margin:0 auto; padding:30px 44px 60px}
.prose h1{font-size:30px; margin:0 0 8px; letter-spacing:-.3px}
.prose h2{font-size:21px; margin:34px 0 10px; padding-bottom:7px; border-bottom:2px solid var(--accent); display:inline-block}
.prose h3{font-size:16.5px; margin:24px 0 8px}
.prose p,.prose li{color:var(--ink); line-height:1.72}
.prose .lead{color:var(--muted); font-size:16px; max-width:760px}
.anchor-offset{scroll-margin-top:80px}
.callout{
  border-left:3px solid var(--accent); background:var(--accent-soft); border-radius:0 9px 9px 0;
  padding:12px 16px; margin:16px 0; font-size:14px;
}
.callout strong{display:block; margin-bottom:3px}
.statgrid{display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin:18px 0}
.stat{border:1px solid var(--border); border-radius:11px; padding:14px 16px; background:var(--panel)}
.stat b{display:block; font-size:22px; letter-spacing:-.5px}
.stat span{color:var(--muted); font-size:12.5px}
.cardgrid{display:grid; grid-template-columns:repeat(auto-fit,minmax(258px,1fr)); gap:14px; margin:18px 0}
.modcard{
  border:1px solid var(--border); border-radius:12px; padding:16px 17px; background:var(--panel);
  box-shadow:var(--shadow); transition:transform .14s ease, border-color .14s ease;
}
.modcard:hover{transform:translateY(-2px); border-color:var(--accent)}
.modcard h4{margin:0 0 6px; font-size:15px}
.modcard h4 code{background:var(--code-bg); padding:2px 8px; border-radius:6px; font-size:13px}
.modcard p{margin:0 0 10px; color:var(--muted); font-size:13.5px}
.modcard .n{font-size:11.5px; color:var(--muted)}
.codebox{border:1px solid var(--border); border-radius:11px; overflow:hidden; margin:14px 0; background:var(--panel)}
.codebox .bar{
  display:flex; align-items:center; justify-content:space-between; gap:10px;
  padding:7px 12px; background:var(--bg-alt); border-bottom:1px solid var(--border);
  font-size:12px; color:var(--muted);
}
.codebox .bar button{
  font:inherit; font-size:12px; border:1px solid var(--border); background:var(--panel);
  color:var(--muted); border-radius:6px; padding:3px 10px; cursor:pointer;
}
.codebox .bar button:hover{color:var(--ink); border-color:var(--accent)}
.codebox pre{margin:0; border:none; border-radius:0; max-height:620px}
/* api page: sidebar sits below the sticky top nav */
.api-shell .sidebar{top:58px; height:calc(100vh - 58px)}
.api-shell .main{padding-top:0}
.api-shell .hero{border-radius:0}
.breadcrumb{font-size:12.5px; color:var(--muted); margin:0 0 4px}
@media (max-width:900px){
  .topnav{padding:0 14px; gap:10px}
  .topnav nav a,.topnav nav button{padding:7px 9px; font-size:13px}
  .topnav .brand span{display:none}
  .prose{padding:22px 18px 40px}
}
"""

DOC_FX_CSS = """
/* ---------- centred document shell ---------- */
.api-shell{max-width:1560px; margin:0 auto}
.api-shell .sidebar{flex:0 0 300px; width:300px}
.api-shell .main{flex:1; min-width:0}
.api-shell .hero{
  max-width:1080px; margin:0 auto; padding:30px 40px 18px;
  background:none; border-bottom:1px solid var(--border);
}
.api-shell .content{max-width:1080px; margin:0 auto; padding:8px 40px 120px}
.nav-sub{margin:10px 8px 3px; font-size:11px; color:var(--muted); letter-spacing:.04em}
.nav-module-static .nav-sym{cursor:pointer}

/* ---------- category chips (sticky) ---------- */
.catchips{
  position:sticky; top:57px; z-index:15; background:var(--bg);
  display:flex; flex-wrap:wrap; gap:8px; padding:12px 0 11px; margin:10px 0 0;
  border-bottom:1px solid var(--border);
}
.catchips a{
  padding:7px 15px; border-radius:999px; border:1px solid var(--border); background:var(--panel);
  font-size:13px; color:var(--muted); white-space:nowrap;
  transition:transform .16s ease, color .16s ease, border-color .16s ease, background .16s ease;
}
.catchips a:hover{color:var(--accent); border-color:var(--accent); transform:translateY(-2px); text-decoration:none}
.catchips a.on{color:var(--accent); border-color:var(--accent); background:var(--accent-soft)}

/* ---------- category cards ---------- */
.catgrid{display:grid; grid-template-columns:repeat(auto-fit,minmax(286px,1fr)); gap:16px; margin:20px 0 6px}
.catcard{
  position:relative; display:block; padding:20px 22px 22px; border-radius:16px; overflow:hidden;
  border:1px solid var(--border); background:var(--panel); color:var(--ink);
  transition:transform .22s cubic-bezier(.2,.8,.3,1), border-color .22s ease, box-shadow .22s ease;
}
.catcard::before{
  content:""; position:absolute; inset:0; opacity:0; pointer-events:none; transition:opacity .28s ease;
  background:radial-gradient(460px circle at var(--mx,50%) var(--my,0%), var(--accent-soft), transparent 62%);
}
.catcard:hover{transform:translateY(-5px); border-color:var(--accent); box-shadow:0 16px 38px rgba(16,24,40,.12); text-decoration:none}
.catcard:hover::before{opacity:1}
.catcard .cico{
  width:42px; height:42px; border-radius:12px; display:grid; place-items:center; margin-bottom:12px;
  font-size:19px; color:var(--accent); background:var(--accent-soft); border:1px solid var(--border);
  transition:transform .22s ease;
}
.catcard:hover .cico{transform:scale(1.08) rotate(-4deg)}
.catcard h4{margin:0 0 6px; font-size:16px}
.catcard p{margin:0 0 10px; color:var(--muted); font-size:13.5px}
.catcard .cn{font-size:11.5px; color:var(--muted)}
.catcard .arrow{position:absolute; right:18px; bottom:16px; color:var(--accent); opacity:0; transform:translateX(-6px); transition:opacity .22s ease, transform .22s ease}
.catcard:hover .arrow{opacity:1; transform:none}

/* ---------- category sections ---------- */
section.cat{margin:54px 0 8px; scroll-margin-top:72px}
.cat-head{
  position:relative; display:flex; align-items:flex-start; gap:16px; padding:20px 24px;
  border-radius:16px; border:1px solid var(--border); overflow:hidden;
  background:linear-gradient(140deg, var(--accent-soft), transparent 78%);
}
.cat-head .ico{
  width:46px; height:46px; flex:0 0 auto; border-radius:13px; display:grid; place-items:center;
  font-size:21px; color:var(--accent); background:var(--panel); border:1px solid var(--border);
  box-shadow:var(--shadow);
}
.cat-head .cat-text{min-width:0}
.cat-head h2{margin:0 0 5px; font-size:21px; letter-spacing:-.3px}
.cat-head p{margin:0; color:var(--muted); font-size:14px; max-width:720px}
.cat-count{
  margin-left:auto; flex:0 0 auto; font-size:11.5px; color:var(--muted); padding:4px 12px;
  border:1px solid var(--border); background:var(--panel); border-radius:999px;
}
.subgroup>h3{
  margin:30px 0 12px; font-size:14.5px; font-weight:600; color:var(--muted);
  text-transform:uppercase; letter-spacing:.09em;
}
.subgroup>h3::after{content:""; display:block; width:44px; height:2px; margin-top:8px; background:var(--accent); border-radius:2px}

/* ---------- motion ---------- */
.api-item{transition:border-color .2s ease, box-shadow .2s ease}
.api-item:hover{border-color:var(--accent); box-shadow:0 8px 26px rgba(37,99,235,.10)}
.rv{opacity:0; transform:translateY(18px)}
.rv.in{opacity:1; transform:none; transition:opacity .55s ease, transform .55s cubic-bezier(.2,.8,.3,1)}
@media (prefers-reduced-motion: reduce){
  .rv{opacity:1; transform:none}
  .catcard, .catcard .cico, .catchips a, .api-item{transition:none}
  .catcard:hover{transform:none}
}
@media (max-width:1100px){
  .api-shell .content{padding:8px 20px 90px}
  .api-shell .hero{padding:24px 20px 16px}
  .cat-head{flex-wrap:wrap}
  .cat-count{margin-left:0}
  .catchips{position:static}
}
"""

TOKEN_CSS = """
/* ---------- syntax highlighting (One Light) ---------- */
.codebox pre{background:#fbfcfe}
.codebox code,.api-doc pre code{color:#383a42}
.t-k{color:#a626a4;font-weight:600}
.t-b{color:#4078f2}
.t-s{color:#50a14f}
.t-n{color:#986801}
.t-c{color:#a0a1a7;font-style:italic}
.t-o{color:#6b7280}
.t-f{color:#7c3aed;font-weight:600}
.t-d{color:#0d9488;font-weight:600}
.t-self{color:#e45649;font-style:italic}
.t-variable{color:#0891b2}
.t-flag{color:#986801}
.t-cmd{color:#7c3aed;font-weight:600}
.api-doc pre{background:#fbfcfe;border-color:var(--border)}
@media (prefers-color-scheme: dark){
  /* ---------- syntax highlighting (One Dark) ---------- */
  .codebox pre,.api-doc pre{background:#12161c}
  .codebox code,.api-doc pre code{color:#abb2bf}
  .t-k{color:#c678dd}
  .t-b{color:#61afef}
  .t-s{color:#98c379}
  .t-n{color:#d19a66}
  .t-c{color:#7f848e}
  .t-o{color:#96a0b0}
  .t-f{color:#82aaff}
  .t-d{color:#56b6c2}
  .t-self{color:#e06c75}
  .t-variable{color:#56b6c2}
  .t-flag{color:#d19a66}
  .t-cmd{color:#82aaff}
}

/* ---------- code block chrome ---------- */
.codebox{box-shadow:0 1px 2px rgba(16,24,40,.05)}
.codebox .bar{background:linear-gradient(180deg,var(--bg-alt),var(--panel))}
.codebox .bar span{display:inline-flex;align-items:center;gap:7px;font-size:11.5px;letter-spacing:.03em}
.codebox .bar span::before{
  content:""; width:7px; height:7px; border-radius:50%;
  background:var(--accent); box-shadow:0 0 0 3px var(--accent-soft);
}

/* ---------- reading progress ---------- */
#progress{
  position:fixed; top:0; left:0; height:2.5px; width:0; z-index:80;
  background:linear-gradient(90deg,var(--accent),#7c3aed,#0d9488);
  transition:width .08s linear; pointer-events:none;
}

/* ---------- back to top ---------- */
#totop{
  position:fixed; right:26px; bottom:26px; z-index:45; width:42px; height:42px;
  border-radius:50%; border:1px solid var(--border); background:var(--panel); color:var(--accent);
  font-size:17px; cursor:pointer; display:grid; place-items:center; box-shadow:0 6px 20px rgba(16,24,40,.14);
  opacity:0; transform:translateY(10px) scale(.9); pointer-events:none;
  transition:opacity .22s ease, transform .22s ease;
}
#totop.show{opacity:1; transform:none; pointer-events:auto}
#totop:hover{border-color:var(--accent); transform:translateY(-2px)}

/* ---------- search field ---------- */
.searchwrap input{
  padding-left:31px;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2.2' stroke-linecap='round'%3E%3Ccircle cx='11' cy='11' r='7'/%3E%3Cpath d='M20.5 20.5 16.7 16.7'/%3E%3C/svg%3E");
  background-repeat:no-repeat; background-position:10px center; background-size:13px 13px;
}
.searchwrap input:focus{box-shadow:0 0 0 3px var(--accent-soft)}

/* ---------- per-category accent ---------- */
.catcard .cico{color:var(--c,var(--accent)); border-color:var(--c,var(--accent))}
.catcard:hover{border-color:var(--c,var(--accent))}
.catcard::before{background:radial-gradient(460px circle at var(--mx,50%) var(--my,0%), var(--c,var(--accent)), transparent 62%)}
.catcard:hover::before{opacity:.13}
.cat-head{position:relative}
.cat-head::after{
  content:""; position:absolute; inset:0; pointer-events:none; opacity:.11;
  background:linear-gradient(140deg, var(--c,var(--accent)), transparent 72%);
}
.cat-head .ico{color:var(--c,var(--accent)); border-color:var(--c,var(--accent))}
.subgroup>h3::after{background:var(--c,var(--accent))}
.catchips a.on,.catchips a:hover{color:var(--c,var(--accent)); border-color:var(--c,var(--accent))}

/* ---------- item polish ---------- */
.api-item{border-left:3px solid transparent}
.api-item:hover{border-left-color:var(--accent)}
.api-item.class-item{border-left-color:var(--c,var(--accent))}
.api-item.class-item:hover{border-left-color:var(--c,var(--accent))}
.module-head h3 code{
  background:linear-gradient(180deg,var(--accent-soft),transparent);
  border:1px solid var(--border);
}
.sig{background:transparent}
.module{border-top:1px solid var(--border); padding-top:18px}
.module:first-child{border-top:none}
table.attack-table td{vertical-align:top; font-size:13px}
table.attack-table td.at-cat{color:var(--muted); font-size:12.5px; white-space:nowrap}
table.attack-table tbody tr:hover{background:var(--bg-alt)}

/* ---------- per-API usage example ---------- */
.doc-section.example-block{
  border-top:1px solid var(--border); background:var(--bg-alt);
  border-radius:10px; padding:11px 13px; margin-top:13px;
}
.example-block h5{margin:0 0 8px; color:var(--accent)}
.example-block pre{
  margin:0; background:var(--panel); border:1px solid var(--border);
  font-size:12.5px; line-height:1.6;
}
"""

POLISH_BODY = (
    '<div id="progress"></div>'
    '<button id="totop" title="Back to top" aria-label="Back to top">\u2191</button>'
)

POLISH_JS = """
(function(){
  var bar = document.getElementById('progress');
  var top = document.getElementById('totop');
  function onScroll(){
    var h = document.documentElement.scrollHeight - window.innerHeight;
    var p = h > 0 ? (window.scrollY / h) : 0;
    if(bar) bar.style.width = (p * 100).toFixed(2) + '%';
    if(top) top.classList.toggle('show', window.scrollY > 500);
  }
  window.addEventListener('scroll', onScroll, {passive:true});
  window.addEventListener('resize', onScroll);
  if(top) top.addEventListener('click', function(){ window.scrollTo({top:0, behavior:'smooth'}); });
  onScroll();

  // colour the chips by the category they point at
  document.querySelectorAll('.catcard').forEach(function(card){
    var c = card.style.getPropertyValue('--c');
    var href = card.getAttribute('href');
    if(!c || !href) return;
    var chip = document.querySelector('.catchips a[href="' + href + '"]');
    if(chip) chip.style.setProperty('--c', c);
  });
})();
"""

DOCS_FX_JS = """
(function(){
  var targets = Array.prototype.slice.call(document.querySelectorAll('[data-rv]'));
  if(targets.length && 'IntersectionObserver' in window){
    targets.forEach(function(el){ el.classList.add('rv'); });
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(en){
        if(en.isIntersecting){ en.target.classList.add('in'); io.unobserve(en.target); }
      });
    }, {rootMargin:'0px 0px -6% 0px', threshold:0.02});
    targets.forEach(function(el){ io.observe(el); });
  }
})();

(function(){
  document.querySelectorAll('.catcard').forEach(function(el){
    el.addEventListener('mousemove', function(e){
      var r = el.getBoundingClientRect();
      el.style.setProperty('--mx', (e.clientX - r.left) + 'px');
      el.style.setProperty('--my', (e.clientY - r.top) + 'px');
    });
  });

  var chips = Array.prototype.slice.call(document.querySelectorAll('.catchips a'));
  if(!chips.length || !('IntersectionObserver' in window)) return;
  var map = {};
  chips.forEach(function(c){
    var sec = document.querySelector(c.getAttribute('href'));
    if(sec) map[sec.id] = c;
  });
  var io2 = new IntersectionObserver(function(entries){
    entries.forEach(function(en){
      if(!en.isIntersecting || !map[en.target.id]) return;
      chips.forEach(function(c){ c.classList.remove('on'); });
      map[en.target.id].classList.add('on');
    });
  }, {rootMargin:'-18% 0px -72% 0px'});
  Object.keys(map).forEach(function(id){ io2.observe(document.getElementById(id)); });
})();
"""

DD_JS = """
document.querySelectorAll('.dd>button').forEach(function(b){
  b.addEventListener('click', function(e){
    e.stopPropagation();
    var p = b.parentElement;
    document.querySelectorAll('.dd').forEach(function(o){ if(o!==p) o.classList.remove('open'); });
    p.classList.toggle('open');
  });
});
document.addEventListener('click', function(){
  document.querySelectorAll('.dd').forEach(function(o){ o.classList.remove('open'); });
});
document.querySelectorAll('.codebox .bar button').forEach(function(b){
  b.addEventListener('click', function(){
    var pre = b.closest('.codebox').querySelector('code');
    navigator.clipboard.writeText(pre.innerText).then(function(){
      var t = b.textContent; b.textContent = 'Copied';
      setTimeout(function(){ b.textContent = t; }, 1400);
    });
  });
});
"""


def nav_html(active: str, in_pages: bool, menu: bool = True) -> str:
    """Top navigation. ``menu=False`` drops the dropdowns, which duplicate the
    API page's own sidebar."""
    pre = "../" if in_pages else ""
    home = pre + "index.html"
    api = pre + "pages/api-document.html"
    lic = pre + "pages/license.html"

    def cls(key: str) -> str:
        return ' class="active"' if key == active else ""

    if merged():
        # The surrounding site already has its own navigation; keep this one minimal
        # and point the guides at the existing hand-written page.
        return (
            '<header class="topnav">'
            f'<a class="brand" href="{home}">{LOGO_IMG}<span>WatermarkLab</span></a>'
            "<nav>"
            '<a href="api-document.html">Guides &amp; quick start</a>'
            f'<a href="api-reference.html"{cls("api")}>API Reference</a>'
            f'<a href="{REPO}">GitHub</a>'
            "</nav></header>"
        )

    dropdowns = ""
    if menu:
        dropdowns = (
            '<div class="dd"><button>Getting Started</button><div class="dd-menu">'
            f'<a href="{api}#quick-start">Quick start</a>'
            f'<a href="{api}#introduction">Introduction</a>'
            f'<a href="{api}#installation">Installation</a>'
            f'<a href="{api}#core-concepts">Core Concepts</a>'
            f'<a href="{api}#eval-watermark">Evaluate Your Watermark</a>'
            f'<a href="{api}#eval-attacker">Evaluate Your Attacker</a>'
            "</div></div>"
            '<div class="dd"><button>Legal</button><div class="dd-menu">'
            f'<a href="{lic}">License</a>'
            "</div></div>"
        )

    return (
        '<header class="topnav">'
        f'<a class="brand" href="{home}">{LOGO_IMG}<span>WatermarkLab</span></a>'
        "<nav>"
        f'<a href="{api}#quick-start"{cls("api")}>API Docs</a>'
        + dropdowns
        + f'<a href="{REPO}">GitHub</a>'
        "</nav></header>"
    )


def footer_html(in_pages: bool) -> str:
    pre = "../" if in_pages else ""
    if merged():
        return (
            '<footer class="site"><div class="fgrid">'
            f'<div><h6>Documentation</h6><a href="api-document.html">Guides &amp; quick start</a>'
            '<a href="api-reference.html">API Reference</a>'
            f'<div><h6>Package</h6><a href="https://pypi.org/project/watermarklab/">PyPI</a>'
            f'<a href="{REPO}">Source</a>'
            f'<a href="{pre}index.html">Project home</a>'
            '<a href="api-document.html#license">License</a></div>'
            "<div><h6>Install</h6><a><code>pip install watermarklab</code></a>"
            f'<a>Python &ge; 3.9</a><a>Version {VERSION}</a></div>'
            "</div>"
            f'<div class="fbot">WatermarkLab {VERSION} &middot; MIT License with Additional Terms</div></footer>'
        )
    return (
        '<footer class="site"><div class="fgrid">'
        f'<div><h6>Documentation</h6><a href="{pre}pages/api-document.html#quick-start">Quick start</a>'
        f'<a href="{pre}pages/api-document.html#introduction">Introduction</a>'
        f'<a href="{pre}pages/api-document.html#installation">Installation</a>'
        f'<a href="{pre}pages/api-document.html#api-overview">API Reference</a>'
        f'<a href="{pre}pages/api-document.html#eval-watermark">Evaluate Your Watermark</a></div>'
        f'<div><h6>Package</h6><a href="https://pypi.org/project/watermarklab/">PyPI</a>'
        f'<a href="{REPO}">Source</a>'
        f'<a href="{REPO}/issues">Bug Reports</a>'
        f'<a href="{pre}pages/license.html">License</a></div>'
        "<div><h6>Install</h6><a><code>pip install watermarklab</code></a>"
        f'<a>Python &ge; 3.9</a><a>Version {VERSION}</a></div>'
        "</div>"
        f'<div class="fbot">WatermarkLab {VERSION} &middot; MIT License with Additional Terms</div></footer>'
    )


def page_shell(title: str, css: str, body: str, js: str = "", desc: str = "") -> str:
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n"
        f'<meta name="description" content="{html.escape(desc)}">\n'
        f"<style>{css}</style>\n</head>\n<body>\n{body}\n"
        f"<script>{js}</script>\n</body>\n</html>\n"
    )


def code_box(code: str, label: str = "Python") -> str:
    body = code.strip("\n")
    low = label.lower()
    if "bib" in low or "text" in low:
        inner = html.escape(body)
    else:
        inner = highlight(body, "bash" if "bash" in low else "python")
    return (
        '<div class="codebox"><div class="bar"><span>' + html.escape(label) + "</span>"
        "<button>Copy</button></div><pre><code>"
        + inner
        + "</code></pre></div>"
    )


# ------------------------------------------------------------ landing page

LANDING_CSS = """
*{box-sizing:border-box}
:root{
  --ink:#e9eef7; --dim:#8fa0bb; --line:rgba(120,150,200,.16);
  --cyan:#22d3ee; --violet:#a855f7; --red:#ff4d5e; --blue:#4d7cff;
}
html{scroll-behavior:smooth}
body{
  margin:0; background:#05070d; color:var(--ink); overflow-x:hidden;
  font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  -webkit-font-smoothing:antialiased;
}
a{color:inherit; text-decoration:none}
code,pre,.mono{font-family:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace}
.bg{position:fixed; inset:0; z-index:0; pointer-events:none}
.bg .glow1,.bg .glow2,.bg .glow3{position:absolute; border-radius:50%; filter:blur(90px); opacity:.5}
.bg .glow1{width:640px;height:640px;left:-190px;top:-220px;background:radial-gradient(circle,#1e5cff,transparent 66%);animation:drift1 22s ease-in-out infinite}
.bg .glow2{width:560px;height:560px;right:-160px;top:60px;background:radial-gradient(circle,#a855f7,transparent 66%);animation:drift2 27s ease-in-out infinite}
.bg .glow3{width:520px;height:520px;left:38%;bottom:-260px;background:radial-gradient(circle,#0ea5b7,transparent 66%);animation:drift3 31s ease-in-out infinite}
@keyframes drift1{50%{transform:translate3d(70px,60px,0) scale(1.09)}}
@keyframes drift2{50%{transform:translate3d(-80px,50px,0) scale(1.13)}}
@keyframes drift3{50%{transform:translate3d(50px,-70px,0) scale(1.07)}}
.bg .grid{
  position:absolute; inset:0;
  background-image:linear-gradient(var(--line) 1px,transparent 1px),linear-gradient(90deg,var(--line) 1px,transparent 1px);
  background-size:62px 62px;
  -webkit-mask-image:radial-gradient(ellipse 90% 62% at 50% 34%,#000 32%,transparent 76%);
  mask-image:radial-gradient(ellipse 90% 62% at 50% 34%,#000 32%,transparent 76%);
}
.wrap{position:relative; z-index:1}
header.lnav{
  position:sticky; top:0; z-index:40; display:flex; align-items:center; gap:20px;
  padding:0 30px; height:64px; backdrop-filter:blur(14px);
  background:rgba(5,7,13,.72); border-bottom:1px solid var(--line);
}
header.lnav .brand{display:flex; align-items:center; gap:10px; font-weight:650; letter-spacing:.2px}
header.lnav .brand img{width:26px;height:31px}
header.lnav nav{margin-left:auto; display:flex; align-items:center; gap:2px}
header.lnav nav a{padding:8px 13px; border-radius:9px; font-size:14px; color:var(--dim); white-space:nowrap}
header.lnav nav a:hover{color:var(--ink); background:rgba(255,255,255,.055)}
header.lnav nav a.hot{
  color:#04121a; font-weight:650; margin-left:8px;
  background:linear-gradient(135deg,var(--cyan),#7dd3fc); box-shadow:0 0 22px rgba(34,211,238,.34);
}
.hero{
  min-height:calc(100vh - 64px); display:flex; flex-direction:column;
  align-items:center; justify-content:center; gap:30px;
  padding:36px 24px 56px; max-width:1100px; margin:0 auto; text-align:center;
}
.stage{position:relative; display:flex; align-items:center; justify-content:center}
.stage canvas{display:block; width:100%; max-width:400px; height:auto; cursor:crosshair}
.stage .halo{
  position:absolute; left:50%; top:50%; transform:translate(-50%,-50%);
  width:390px; height:390px; border-radius:50%; pointer-events:none;
  background:radial-gradient(circle,rgba(34,211,238,.16),transparent 62%); filter:blur(28px);
}
.stage .hint{display:none}
.eyebrow{
  display:inline-flex; align-items:center; gap:8px; font-size:12px; letter-spacing:.16em;
  text-transform:uppercase; color:var(--cyan); border:1px solid rgba(34,211,238,.3);
  border-radius:999px; padding:5px 13px; background:rgba(34,211,238,.07); margin-bottom:16px;
}
.eyebrow i{width:6px;height:6px;border-radius:50%;background:var(--cyan);box-shadow:0 0 10px var(--cyan);animation:pulse 2s infinite}
@keyframes pulse{50%{opacity:.35}}
h1.title{
  margin:0 0 20px; font-size:clamp(34px,4.6vw,56px); line-height:1.14; letter-spacing:-1.4px; font-weight:760;
  /* the gradient is painted through background-clip:text, so the box has to be
     tall enough to contain descenders (the "g" in "image") or they get clipped */
  padding-bottom:8px;
  background:linear-gradient(112deg,#ffffff 12%,#9fd8ff 44%,#c4a2ff 78%,#ffffff 100%);
  -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent;
}
.lede{font-size:16.5px; color:var(--dim); max-width:680px; margin:0 auto 20px}
.lede b{color:#dbe6f7; font-weight:600}
.cta{display:flex; flex-wrap:wrap; gap:12px; margin-bottom:16px; justify-content:center}
.btn{
  display:inline-flex; align-items:center; gap:9px; padding:13px 25px; border-radius:11px;
  font-weight:640; font-size:15px; border:1px solid transparent; transition:transform .15s ease,box-shadow .15s ease;
}
.btn:hover{transform:translateY(-2px); text-decoration:none}
.btn.pri{background:linear-gradient(135deg,var(--cyan),#6366f1); color:#04121a; box-shadow:0 10px 34px rgba(34,211,238,.3)}
.btn.pri:hover{box-shadow:0 14px 42px rgba(34,211,238,.44)}
.btn.gho{border-color:var(--line); color:var(--ink); background:rgba(255,255,255,.035)}
.btn.gho:hover{border-color:rgba(34,211,238,.5); background:rgba(34,211,238,.08)}
.install{
  display:inline-flex; align-items:center; gap:12px; font-size:14px; color:#bcd0ea;
  background:rgba(255,255,255,.04); border:1px solid var(--line); border-radius:10px; padding:10px 15px;
}
.install .p{color:var(--cyan)}
section.band{padding:78px 60px; max-width:1400px; margin:0 auto}
h2.sec{font-size:clamp(26px,3.2vw,36px); letter-spacing:-.8px; margin:0 0 10px; font-weight:720}
p.secsub{color:var(--dim); margin:0 0 34px; max-width:640px}
.feats{display:grid; grid-template-columns:repeat(auto-fit,minmax(268px,1fr)); gap:16px}
.feat{
  position:relative; padding:22px 22px 24px; border-radius:15px; overflow:hidden;
  background:linear-gradient(158deg,rgba(255,255,255,.062),rgba(255,255,255,.018));
  border:1px solid var(--line); transition:transform .18s ease,border-color .18s ease;
}
.feat::after{
  content:""; position:absolute; inset:0; opacity:0; transition:opacity .2s ease;
  background:radial-gradient(420px circle at var(--mx,50%) var(--my,0%),rgba(34,211,238,.13),transparent 62%);
}
.feat:hover{transform:translateY(-4px); border-color:rgba(34,211,238,.42)}
.feat:hover::after{opacity:1}
.feat .ic{
  width:38px;height:38px;border-radius:10px;display:grid;place-items:center;margin-bottom:13px;
  background:rgba(34,211,238,.12); border:1px solid rgba(34,211,238,.26); color:var(--cyan); font-size:17px;
}
.feat h3{margin:0 0 7px; font-size:16.5px; font-weight:650}
.feat p{margin:0; color:var(--dim); font-size:14px}
.stats{display:grid; grid-template-columns:repeat(auto-fit,minmax(158px,1fr)); gap:16px; margin-top:14px}
.stat{padding:20px; border-radius:14px; border:1px solid var(--line); background:rgba(255,255,255,.03)}
.stat b{display:block; font-size:32px; letter-spacing:-1px; background:linear-gradient(120deg,#fff,#7dd3fc);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
.stat span{color:var(--dim); font-size:13px}
.mods{display:grid; grid-template-columns:repeat(auto-fit,minmax(252px,1fr)); gap:14px}
.mod{
  display:block; padding:19px 20px; border-radius:14px; border:1px solid var(--line);
  background:rgba(255,255,255,.032); transition:transform .16s ease,border-color .16s ease,background .16s ease;
}
.mod:hover{transform:translateY(-3px); border-color:var(--c,var(--violet)); background:rgba(255,255,255,.06); text-decoration:none}
.mod code{color:var(--c,var(--cyan)); font-size:14.5px; font-weight:650}
.mod p{margin:7px 0 0; color:var(--dim); font-size:13.5px}
.mod .c{float:right; color:var(--dim); font-size:12px}
.mod:hover .c{color:var(--c,var(--cyan))}

/* ---------- benchmark podium ---------- */
.podium{display:grid; grid-template-columns:repeat(auto-fit,minmax(228px,1fr)); gap:16px}
.pcard{
  position:relative; padding:24px 22px; border-radius:16px; text-align:center; overflow:hidden;
  border:1px solid var(--line); background:rgba(255,255,255,.035);
  transition:transform .2s ease, border-color .2s ease;
}
.pcard:hover{transform:translateY(-4px)}
.pcard .medal{font-size:34px; line-height:1; margin-bottom:10px}
.pcard h4{margin:0 0 4px; font-size:17px}
.pcard .ptag{font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:var(--dim); margin-bottom:8px}
.pcard p{margin:0; color:var(--dim); font-size:13.5px}
.pcard.gold{border-color:rgba(255,215,0,.45); background:linear-gradient(160deg,rgba(255,215,0,.10),transparent 70%)}
.pcard.silver{border-color:rgba(192,192,192,.42); background:linear-gradient(160deg,rgba(192,192,192,.10),transparent 70%)}
.pcard.bronze{border-color:rgba(205,127,50,.45); background:linear-gradient(160deg,rgba(205,127,50,.10),transparent 70%)}
.findings{margin:22px 0 0; padding-left:0; list-style:none; display:grid; gap:10px}
.findings li{
  position:relative; padding:12px 16px 12px 40px; border-radius:11px; font-size:14px; color:var(--dim);
  border:1px solid var(--line); background:rgba(255,255,255,.028);
}
.findings li::before{content:"\\2192"; position:absolute; left:16px; top:12px; color:var(--cyan); font-weight:700}
.final{
  max-width:1180px; margin:20px auto 90px; padding:56px 44px; border-radius:22px; text-align:center;
  border:1px solid var(--line); background:linear-gradient(150deg,rgba(34,211,238,.11),rgba(168,85,247,.11));
}
.final h2{margin:0 0 12px; font-size:clamp(24px,3vw,34px); letter-spacing:-.7px}
.final p{color:var(--dim); margin:0 auto 26px; max-width:560px}
footer.lfoot{
  border-top:1px solid var(--line); padding:30px 60px; color:var(--dim); font-size:13.5px;
  display:flex; flex-wrap:wrap; gap:18px; align-items:center; justify-content:center; text-align:center;
}
footer.lfoot nav{display:flex; flex-wrap:wrap; gap:18px; justify-content:center}
footer.lfoot a:hover{color:var(--cyan)}
.reveal{opacity:0; transform:translateY(22px); transition:opacity .6s ease,transform .6s ease}
.reveal.in{opacity:1; transform:none}
@media (max-width:1000px){
  .hero{padding:30px 20px 54px; gap:22px}
  section.band{padding:56px 24px}
  .final{margin:10px 24px 70px; padding:40px 22px}
  footer.lfoot{padding:26px 24px}
  header.lnav{padding:0 16px}
  header.lnav nav a{padding:8px 9px; font-size:13px}
}
"""

PARTICLES_JS = """
(function(){
  var canvas = document.getElementById('logoCanvas');
  if(!canvas) return;
  var ctx = canvas.getContext('2d', {alpha:true});
  var img = new Image();
  var particles = [];
  var W = 400, H = 400 * 120.33 / 101.32;
  var dpr = Math.min(window.devicePixelRatio || 1, 2);
  var mouse = {x:-9999, y:-9999, on:false};
  var t0 = Date.now();
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  canvas.width = Math.round(W*dpr); canvas.height = Math.round(H*dpr);
  canvas.style.width = W+'px'; canvas.style.height = H+'px';

  function fit(){
    var stage = document.querySelector('.stage');
    var stageW = (stage && stage.clientWidth) || 400;
    // Also cap by viewport height so the whole hero (logo + headline + buttons)
    // stays inside one screen on shorter displays.
    var maxW = Math.min(400, stageW, window.innerHeight * 0.40 * (W / H));
    var s = maxW / W;
    canvas.style.width = (W*s)+'px';
    canvas.style.height = (H*s)+'px';
  }

  function build(pts){
    var scale = (W*dpr) / 101.32;
    var targets = pts.map(function(p){
      return {tx:p.x*scale, ty:p.y*scale, col:p.col};
    });
    // thin out if very dense, so the animation stays smooth
    var max = 2600;
    if(targets.length > max){
      var step = targets.length/max; var keep=[];
      for(var i=0;i<targets.length;i+=step) keep.push(targets[Math.floor(i)]);
      targets = keep;
    }
    particles = targets.map(function(t){
      // Start near the target so the logo silhouette is legible from the very
      // first frame, then let the spring settle it into place.
      var a = Math.random()*Math.PI*2;
      var rad = Math.random()*Math.random()*150*dpr;
      return {
        x: t.tx + Math.cos(a)*rad, y: t.ty + Math.sin(a)*rad,
        vx:0, vy:0, tx:t.tx, ty:t.ty, col:t.col,
        r: (0.65 + Math.random()*0.75) * dpr,
        ph: Math.random()*Math.PI*2
      };
    });
  }

  function sampleLogo(){
    var off = document.createElement('canvas');
    var OW = 254, OH = Math.round(254 * 120.33 / 101.32);
    off.width = OW; off.height = OH;
    var o = off.getContext('2d');
    o.drawImage(img, 0, 0, OW, OH);
    var data;
    try{ data = o.getImageData(0,0,OW,OH).data; }
    catch(err){ return null; }
    var pts = [], step = 2;
    for(var y=0;y<OH;y+=step){
      for(var x=0;x<OW;x+=step){
        var i = (y*OW+x)*4;
        if(data[i+3] < 120) continue;
        var r=data[i], g=data[i+1], b=data[i+2];
        var col;
        if(r>120 && r>g+55 && r>b+55) col='#ff5566';
        else if(b>110 && b>r+45 && b>g+35) col='#5b8cff';
        else col='#9fe8ff';
        pts.push({x:x*(101.32/OW), y:y*(120.33/OH), col:col});
      }
    }
    return pts;
  }

  function fallback(){
    // Canvas could not be read (tainted); show the logo itself so the hero is never empty.
    ctx.setTransform(1,0,0,1,0,0);
    ctx.clearRect(0,0,canvas.width,canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  }

  function step(){
    var now = Date.now();
    ctx.setTransform(1,0,0,1,0,0);
    ctx.globalCompositeOperation = 'source-over';
    ctx.clearRect(0,0,canvas.width,canvas.height);
    ctx.globalCompositeOperation = 'lighter';

    for(var i=0;i<particles.length;i++){
      var p = particles[i];
      var jx = Math.cos(now*0.0011 + p.ph) * 1.4 * dpr;
      var jy = Math.sin(now*0.0014 + p.ph) * 1.4 * dpr;
      if(!reduce){
        p.vx += (p.tx + jx - p.x) * 0.085;
        p.vy += (p.ty + jy - p.y) * 0.085;
      } else {
        p.x = p.tx; p.y = p.ty;
      }
      if(mouse.on){
        var dx = p.x - mouse.x, dy = p.y - mouse.y;
        var d2 = dx*dx + dy*dy;
        var R = 74*dpr;
        if(d2 < R*R && d2 > 0.01){
          var d = Math.sqrt(d2);
          var f = (1 - d/R);
          p.vx += (dx/d) * f * 7.5;
          p.vy += (dy/d) * f * 7.5;
        }
      }
      p.vx *= 0.862; p.vy *= 0.862;
      p.x += p.vx; p.y += p.vy;

      var speed = Math.abs(p.vx) + Math.abs(p.vy);
      ctx.globalAlpha = Math.min(0.96, 0.5 + speed*0.06);
      ctx.fillStyle = p.col;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, 6.2832);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
    requestAnimationFrame(step);
  }

  function pointer(e){
    var r = canvas.getBoundingClientRect();
    var t = e.touches ? e.touches[0] : e;
    if(!t){ return; }
    mouse.x = (t.clientX - r.left) * (canvas.width / r.width);
    mouse.y = (t.clientY - r.top) * (canvas.height / r.height);
    mouse.on = true;
  }
  canvas.addEventListener('mousemove', pointer);
  canvas.addEventListener('touchmove', function(e){ pointer(e); e.preventDefault(); }, {passive:false});
  canvas.addEventListener('mouseleave', function(){ mouse.on = false; mouse.x = mouse.y = -9999; });
  canvas.addEventListener('touchend', function(){ mouse.on = false; });
  canvas.addEventListener('click', function(){
    for(var i=0;i<particles.length;i++){
      var p = particles[i];
      var dx = p.x - mouse.x, dy = p.y - mouse.y;
      var d = Math.sqrt(dx*dx+dy*dy) || 1;
      var f = Math.max(0, 1 - d/(210*dpr));
      p.vx += (dx/d)*f*26; p.vy += (dy/d)*f*26;
    }
  });

  img.onload = function(){
    var pts = sampleLogo();
    if(!pts || !pts.length){ fallback(); return; }
    build(pts);
    fit();
    window.addEventListener('resize', fit);
    requestAnimationFrame(step);
  };
  img.onerror = function(){ fallback(); };
  img.src = LOGO_DATA_URI;
})();

(function(){
  document.querySelectorAll('.feat').forEach(function(el){
    el.addEventListener('mousemove', function(e){
      var r = el.getBoundingClientRect();
      el.style.setProperty('--mx', (e.clientX-r.left)+'px');
      el.style.setProperty('--my', (e.clientY-r.top)+'px');
    });
  });
  var io = new IntersectionObserver(function(es){
    es.forEach(function(en){ if(en.isIntersecting){ en.target.classList.add('in'); io.unobserve(en.target); } });
  }, {rootMargin:'-60px'});
  document.querySelectorAll('.reveal').forEach(function(el){ io.observe(el); });
})();
"""

MODULE_CARDS = [
    ("laboratories", "Core evaluation frameworks that orchestrate testing pipelines for both PGW and IGW models.", "cat-evaluation"),
    ("watermarks", "Implementation of various watermarking algorithms, including both PGW and IGW approaches.", "cat-watermarks"),
    ("attackers", "Comprehensive collection of image attacks to test watermark robustness.", "cat-attacks"),
    ("metrics", "Evaluation metrics for measuring visual quality and watermark robustness.", "cat-data-metrics"),
    ("datasets", "Data loading utilities and dataset classes for handling various image data sources.", "cat-data-metrics"),
    ("steganography", "Steganographic techniques for information hiding in digital images.", "cat-utilities"),
    ("draw", "Utilities for visualizing watermarking results and generating plots.", "cat-utilities"),
    ("tools", "Various utility functions and helper classes for watermarking research.", "cat-utilities"),
]

FEATURES = [
    ("&#9673;", "One entry point",
     "A single <code>wl.evaluate()</code> call runs embedding, visual-quality measurement, the attack "
     "sweep, extraction and scoring. It reads the dataloader to decide whether your model is "
     "post-generation (images) or in-generation (prompts) and routes the run accordingly."),
    ("&#9881;", "44 attack configurations, 7 groups",
     "Compression (classic JPEG / JPEG2000 / WebP and learned BMSHJ2018 / MBT2018 / Cheng2020), "
     "adversarial embedding, noise, blur, geometric, colour and diffusion regeneration \u2014 each with a "
     "calibrated strength sweep, all built by <code>AttackersWithFactorsModel()</code>."),
    ("&#9636;", "34 differentiable attackers",
     "Drop-in <code>DiffAttacker</code> layers for end-to-end adversarial training, including "
     "differentiable JPEG (mask / polynomial / Fourier), screen-capture PIMoG and print-capture "
     "StegaStamp."),
    ("&#9788;", "11 watermark models",
     "Seven post-generation (DctDwt, DctDwtSvd, RivaGAN, StegaStamp, TrustMark, InvisMark, VINE), three "
     "in-generation (Tree-Ring, GaussianShading, StableSignature) and iSteganoGAN."),
    ("&#9635;", "10 metrics, 5 dataset loaders",
     "Robustness (BER, EA, NC, NEB, TPR@x%FPR) and imperceptibility (PSNR, SSIM, RMSE, MAE, LPIPS) "
     "metrics, plus FID for in-generation runs, over MS-COCO 2017 images and prompts, Kodak24 and "
     "USC-SIPI."),
    ("&#9638;", "21 plotting helpers, 7 base classes",
     "Robustness curves, model and attacker rankings, visual-quality and stego comparisons. Extend "
     "<code>BaseWatermarkModel</code>, <code>BaseTestAttackModel</code>, <code>BaseMetric</code> and the "
     "other base classes to plug in your own method."),
]

# Headline ranking over the benchmark attacks (cumulative RQ-AUC).
PODIUM = [
    ("gold", "\U0001F947", "GaussianShading", "IGW", "Best overall. Only five attacks reach TPR@0.1%FPR = 0.8 against it."),
    ("silver", "\U0001F948", "StegaStamp", "PGW", "Strongest post-generation method; weakest under flipping and rotation."),
    ("bronze", "\U0001F949", "VINE", "PGW", "Sensitive to cropping \u2014 a 10% crop drops TPR@0.1%FPR to 0.01."),
]

FINDINGS = [
    "In-generation methods win overall: mapping the watermark into the latent distribution makes it more "
    "evenly spread through the image than a post-hoc perturbation can achieve.",
    "Geometric and regeneration attacks are the strongest categories \u2014 most current methods remain "
    "insufficiently robust against them.",
    "GaussianShading and VINE are notably weak under geometric attacks; TrustMark ranks behind StegaStamp "
    "under rotation, flipping and regeneration.",
    "Among post-generation methods, TrustMark and InvisMark achieve the highest visual quality, while "
    "RivaGAN and DctDwtSvd introduce visible colour shifts.",
]


def landing_page() -> str:
    cards = "".join(
        f'<a class="mod reveal" href="pages/api-document.html#cat-{c["id"]}" '
        f'style="--c:{bd.CATEGORY_COLORS.get(c["id"], "#2563eb")}">'
        f'<span class="c">&rarr;</span><code>{html.escape(c["title"])}</code><p>{c["desc"]}</p></a>'
        for c in bd.MAJOR_CATEGORIES
    )
    feats = "".join(
        f'<div class="feat reveal"><div class="ic">{icon}</div><h3>{title}</h3><p>{body}</p></div>'
        for icon, title, body in FEATURES
    )
    podium = "".join(
        f'<div class="pcard {cls} reveal"><div class="medal">{medal}</div>'
        f'<h4>{html.escape(name)}</h4><div class="ptag">{html.escape(tag)}</div>'
        f"<p>{html.escape(note)}</p></div>"
        for cls, medal, name, tag, note in PODIUM
    )
    findings = "".join(f"<li>{f}</li>" for f in FINDINGS)
    body = (
        '<div class="bg"><div class="glow1"></div><div class="glow2"></div><div class="glow3"></div>'
        '<div class="grid"></div></div><div class="wrap">'
        '<header class="lnav">'
        f'<a class="brand" href="index.html">{LOGO_IMG}<span>WatermarkLab</span></a>'
        "<nav>"
        '<a href="pages/api-document.html">API Docs</a>'
        '<a href="pages/api-document.html#introduction">Getting Started</a>'
        '<a href="pages/license.html">License</a>'
        f'<a href="{REPO}">GitHub</a>'
        '<a class="hot" href="pages/api-document.html">Get Started &rarr;</a>'
        "</nav></header>"

        '<section class="hero">'
        '<div class="stage"><div class="halo"></div>'
        '<canvas id="logoCanvas" width="400" height="475" aria-label="WatermarkLab logo particle animation"></canvas>'
        "</div>"
        "<div>"
        '<div class="eyebrow"><i></i>Comprehensive &middot; Fair &middot; Open &middot; Extensible</div>'
        '<h1 class="title">Benchmark blind robust<br>image watermarking.</h1>'
        '<p class="lede">One evaluation pipeline for image watermarking: embed, attack, extract, score '
        "and plot \u2014 for <b>post-generation and in-generation</b> methods alike. Eleven models, "
        "44 attack configurations and 34 differentiable attackers ship with it.</p>"
        '<div class="cta">'
        '<a class="btn pri" href="pages/api-document.html">Get Started &rarr;</a>'
        "</div>"
        '<div class="install"><span class="p">$</span><code>pip install watermarklab</code></div>'
        "</div></section>"

        '<section class="band"><h2 class="sec">Everything a robustness study needs</h2>'
        '<p class="secsub">From a single call to a full benchmark report \u2014 without wiring the parts together yourself.</p>'
        f'<div class="feats">{feats}</div></section>'

        '<section class="band"><h2 class="sec">The framework at a glance</h2>'
        '<p class="secsub">Symbols and signatures are generated from the source tree by static AST '
        "analysis.</p>"
        '<div class="stats">'
        '<div class="stat reveal"><b>8</b><span>modules</span></div>'
        '<div class="stat reveal"><b>11</b><span>watermark models</span></div>'
        '<div class="stat reveal"><b>44</b><span>attack configurations</span></div>'
        '<div class="stat reveal"><b>34</b><span>differentiable attackers</span></div>'
        '<div class="stat reveal"><b>5</b><span>datasets</span></div>'
        '<div class="stat reveal"><b>10</b><span>metrics</span></div>'
        "</div></section>"

        '<section class="band"><h2 class="sec">What the benchmark finds</h2>'
        '<p class="secsub">Ranked by cumulative RQ-AUC across the attack sweep. The strongest '
        "post-generation method is StegaStamp; in-generation methods lead overall.</p>"
        f'<div class="podium">{podium}</div><ul class="findings">{findings}</ul>'
        "</section>"

        '<section class="band"><h2 class="sec">Core modules</h2>'
        '<p class="secsub">Eight modules \u2014 jump straight into any part of the API reference.</p>'
        f'<div class="mods">{cards}</div></section>'

        '<div class="final reveal"><h2>Start benchmarking in three lines</h2>'
        "<p>Instantiate a model, wrap the default attackers, and call <code>wl.evaluate()</code>. "
        "The API reference has the full signatures for every class and method.</p>"
        '<div class="cta" style="justify-content:center">'
        '<a class="btn pri" href="pages/api-document.html">Get Started &rarr;</a>'
        '<a class="btn gho" href="pages/api-document.html#eval-watermark">Evaluate your watermark</a>'
        "</div></div>"

        '<footer class="lfoot"><div>WatermarkLab ' + VERSION + ' &middot; MIT License with Additional Terms</div>'
        '<nav><a href="pages/api-document.html">API Docs</a>'
        '<a href="pages/api-document.html#introduction">Getting Started</a>'
        f'<a href="{REPO}">GitHub</a>'
        '<a href="https://pypi.org/project/watermarklab/">PyPI</a>'
        '<a href="pages/license.html">License</a></nav></footer>'
        "</div>"
    )
    js = "var LOGO_DATA_URI = '" + LOGO_URI + "';\n" + PARTICLES_JS
    return page_shell(
        "WatermarkLab \u2014 Robust Image Watermarking Toolkit",
        LANDING_CSS,
        body,
        js,
        "WatermarkLab is a toolkit for robust image watermarking benchmarking and development: evaluation pipelines, 40+ attacks, watermark models and metrics.",
    )


LOGO_URI = ""
LOGO_IMG = ""


def read_content(name: str) -> str:
    path = Path(__file__).with_name("content") / name
    try:
        return path.read_text(encoding="utf-8").strip("\n")
    except OSError:
        return f"# content/{name} not found"


def docs_css() -> str:
    return bd.CSS + NAV_CSS + DOC_FX_CSS + TOKEN_CSS


def doc_page(title: str, active: str, content: str, desc: str = "") -> str:
    body = (
        nav_html(active, True)
        + '<main class="prose">'
        + content
        + "</main>"
        + footer_html(True)
    )
    return page_shell(title + " \u2014 WatermarkLab", docs_css(), body, DD_JS, desc)


def reference_sections(dump: dict) -> tuple[str, str]:
    """Sidebar nav + body for the reference, grouped into the major categories."""
    return bd.render_reference(dump)


API_OVERVIEW = (
    "<p>WatermarkLab provides a comprehensive set of modules and functions for the development, "
    "evaluation and comparison of robust image watermarking techniques. This reference is organised "
    "into the framework's seven core modules \u2014 <code>watermarks</code>, <code>attackers</code>, "
    "<code>metrics</code>, <code>tools</code>, <code>datasets</code>, <code>laboratories</code> and "
    "<code>draw</code> \u2014 with the base interfaces you extend listed alongside the evaluation "
    "platform.</p>"
)


def section_quickstart() -> str:
    """The four worked examples that open the API page."""
    return (
        '<h2 class="anchor-offset" id="quick-start">Quick start</h2>'
        '<p class="lead">Four complete recipes cover almost everything the library is used for: evaluating '
        "a watermark you wrote, evaluating an attack you wrote, and benchmarking the built-in "
        "post-generation and in-generation watermark families. All four end in the same "
        "<code>wl.evaluate()</code> call.</p>"
        + section_eval_watermark()
        + section_eval_attacker()
        + '<h3 class="anchor-offset" id="quickstart-pgw">3. Benchmarking PGWs</h3>'
        "<p>The built-in post-generation family, each run against the default sweep of 40+ attacks with "
        "calibrated intensity factors:</p>"
        + code_box(read_content("quickstart_pgw.txt"), "python \u2014 post-generation watermarking")
        + '<h3 class="anchor-offset" id="quickstart-igw">4. Benchmarking IGWs</h3>'
        "<p>The in-generation family. These models embed during diffusion sampling, so the dataloader yields "
        "prompts instead of images and <code>wl.evaluate()</code> routes the run to the IGW pipeline "
        "automatically:</p>"
        + code_box(read_content("quickstart_igw.txt"), "python \u2014 in-generation watermarking")
    )


def section_sidebar_onpage() -> str:
    if merged():
        links = [("Guides &amp; quick start", "api-document.html"), ("API Reference Overview", "#api-overview")]
        links += [
            (c["icon"] + "&nbsp; " + html.escape(c["title"]), "#cat-" + c["id"])
            for c in bd.MAJOR_CATEGORIES
        ]
        items = "".join(f'<a class="nav-sym" href="{href}">{label}</a>' for label, href in links)
        return f'<h4>On this page</h4><div class="nav-module nav-module-static">{items}</div>'

    links = [
        ("Quick start", "#quick-start"),
        ("1. Evaluate your watermark", "#eval-watermark"),
        ("2. Evaluate your attacker", "#eval-attacker"),
        ("3. Benchmarking PGWs", "#quickstart-pgw"),
        ("4. Benchmarking IGWs", "#quickstart-igw"),
        ("Introduction", "#introduction"),
        ("Installation", "#installation"),
        ("Core Concepts", "#core-concepts"),
        ("Visualize results", "#visualize"),
        ("API Reference Overview", "#api-overview"),
    ]
    items = "".join(
        f'<a class="nav-sym" href="{href}">{html.escape(label)}</a>' for label, href in links
    )
    return f'<h4>On this page</h4><div class="nav-module nav-module-static">{items}</div>'


def category_cards() -> str:
    out = []
    for cat in bd.MAJOR_CATEGORIES:
        n = len(cat["groups"])
        colour = bd.CATEGORY_COLORS.get(cat["id"], "#2563eb")
        out.append(
            f'<a class="catcard" href="#cat-{cat["id"]}" data-rv style="--c:{colour}">'
            f'<div class="cico">{cat["icon"]}</div>'
            f'<h4>{html.escape(cat["title"])}</h4>'
            f'<p>{cat["desc"]}</p>'
            f'<span class="cn">{n} area{"s" if n != 1 else ""}</span>'
            f'<span class="arrow" style="color:{colour}">&rarr;</span></a>'
        )
    return "".join(out)


def category_chips() -> str:
    links = "".join(
        f'<a href="#cat-{c["id"]}" style="--c:{bd.CATEGORY_COLORS.get(c["id"], "#2563eb")}">'
        f'{c["icon"]}&nbsp; {html.escape(c["title"])}</a>'
        for c in bd.MAJOR_CATEGORIES
    )
    return f'<div class="catchips">{links}</div>'


def api_page(dump: dict) -> str:
    dump = bd.filter_modules(dump)
    sidebar_nav, reference = reference_sections(dump)

    module_count = len(dump["modules"])
    class_count = sum(len(m.get("classes", [])) for m in dump["modules"])
    fn_count = sum(len(m.get("functions", [])) for m in dump["modules"])

    cards = category_cards()

    quick = section_quickstart()

    body = (
        nav_html("api", True, menu=False)
        + POLISH_BODY
        + '<div class="layout api-shell">'
        '<aside class="sidebar">'
        '<div class="searchwrap">'
        '<input id="q" type="search" placeholder="Search classes, methods\u2026  ( / )" autocomplete="off">'
        f'<div class="searchhint"><span id="hint">{module_count} modules</span><span>Esc to clear</span></div>'
        "</div>"
        '<nav class="nav" id="nav">'
        + section_sidebar_onpage()
        + "<h4>API reference</h4>"
        + f"{sidebar_nav}</nav>"
        "</aside>"
        '<main class="main"><div class="content">'
        '<div class="hero" style="padding:30px 0 18px;background:none;border-bottom:1px solid var(--border)">'
        "<h1 style=\"margin:0 0 8px;font-size:30px\">API Reference</h1>"
        '<p style="margin:0;color:var(--muted);max-width:820px">'
        f"{class_count} classes and {fn_count} functions across {module_count} modules, generated by static "
        "AST analysis of the source tree. Private helpers and non-exported internals are omitted."
        + (
            ' Step-by-step guides and runnable quick starts live under '
            '<a href="api-document.html">Guides &amp; quick start</a>.'
            if merged()
            else ""
        )
        + "</p></div>"
        + category_chips()
        + ("" if merged() else quick + section_guide())
        + '<h2 class="anchor-offset" id="api-overview" style="margin-top:40px">API Reference Overview</h2>'
        + f'<p class="group-desc">{API_OVERVIEW}</p>'
        + f'<div class="catgrid">{cards}</div>'
        + reference
        + '<div class="empty" id="empty">No symbol matches that search.</div>'
        '<p style="color:var(--muted);font-size:12.5px;margin-top:40px">'
        "Generated by static AST analysis of the source tree \u2014 every signature, default value and "
        "description is reproduced verbatim from the code's own annotations and docstrings."
        "</p>"
        "</div></main></div>"
        + footer_html(True)
    )
    return page_shell(
        "API Reference \u2014 WatermarkLab",
        docs_css(),
        body,
        bd.JS + DD_JS + DOCS_FX_JS + POLISH_JS,
        "Complete API reference for WatermarkLab: evaluation frameworks, watermark models, attacks, metrics, datasets and visualization utilities.",
    )


def section_guide() -> str:
    content = (
        '<h2 class="anchor-offset" id="introduction">Introduction</h2>'
        '<p class="lead">WatermarkLab is a framework for systematic benchmarking and development of '
        "<em>blind robust image watermarking</em>. It supports Post-Generation Watermarking (PGW) and "
        "In-Generation Watermarking (IGW), zero-bit and multi-bit payloads, and robust reversible methods "
        "that must also recover the original cover losslessly \u2014 all behind one unified evaluation "
        "pipeline.</p>"
        "<h3>Key features</h3><ul>"
        "<li>Unified evaluation pipeline for both PGW and IGW models</li>"
        "<li>Extensive collection of image attacks for robustness testing</li>"
        "<li>Comprehensive set of evaluation metrics</li>"
        "<li>Modular design for easy extension</li>"
        "<li>Structured result reporting with visualizations</li>"
        "</ul>"
        '<div class="statgrid" style="margin-top:22px">'
        '<div class="stat"><b>8</b><span>modules</span></div>'
        '<div class="stat"><b>11</b><span>watermark models</span></div>'
        '<div class="stat"><b>44</b><span>attack configurations</span></div>'
        '<div class="stat"><b>34</b><span>differentiable attackers</span></div>'
        "</div>"

        '<h2 class="anchor-offset" id="installation">Installation</h2>'
        "<p>Install WatermarkLab from PyPI:</p>"
        + code_box("pip install watermarklab", "bash")
        + "<h3>Download resources</h3>"
        "<p>Pre-trained weights and the base diffusion models used by the IGW benchmarks are hosted on "
        "Hugging Face:</p>"
        + code_box(
            "huggingface-cli download chenoly/watermarklab\n"
            "huggingface-cli download stabilityai/stable-diffusion-2-1-base\n"
            "huggingface-cli download stabilityai/stable-diffusion-2-1",
            "bash",
        )
        + "<h3>Requirements</h3>"
        '<p>Python &ge; 3.9. The package pulls in a fairly heavy scientific and generative stack:</p>'
        '<div class="cardgrid">'
        '<div class="modcard"><h4><code>core</code></h4><p>numpy, pillow, opencv-python, PyWavelets, '
        "scikit-learn, psutil, py-cpuinfo, colorama, pyfiglet, pycryptodome</p></div>"
        '<div class="modcard"><h4><code>metrics</code></h4><p>clean-fid, lpips, matplotlib, seaborn</p></div>'
        '<div class="modcard"><h4><code>models</code></h4><p>torch, onnxruntime-gpu, diffusers, transformers, '
        "accelerate, peft, compressai, kornia, nvidia-ml-py</p></div>"
        "</div>"
        '<div class="callout"><strong>GPU expected</strong>FID computation defaults to <code>cuda</code> '
        "(<code>fid_device=\"cuda\"</code>), and several IGW models run diffusion sampling. Pass "
        "<code>fid_device=\"cpu\"</code> only for small smoke tests.</div>"

        '<h2 class="anchor-offset" id="core-concepts">Core Concepts</h2>'
        "<h3>Watermark model types</h3>"
        '<div class="cardgrid">'
        '<div class="modcard"><h4>PGW &mdash; Post-Generation Watermarking</h4>'
        "<p>The watermark is embedded into a pre-existing image after it has been generated. The evaluation "
        "dataloader therefore yields <em>images</em> plus the secret bit sequence.</p></div>"
        '<div class="modcard"><h4>IGW &mdash; In-Generation Watermarking</h4>'
        "<p>The watermark is embedded during the image generation process itself, for example while sampling "
        "a diffusion model. The dataloader yields <em>text prompts</em> instead of images.</p></div>"
        "</div>"
        "<h3>Evaluation pipeline</h3>"
        "<p>The library provides a standardized evaluation process consisting of:</p>"
        "<ol>"
        "<li>Embedding the watermark into cover images or prompts</li>"
        "<li>Applying various attacks (noise, compression, geometric transformations)</li>"
        "<li>Extracting the watermark from the attacked images</li>"
        "<li>Computing evaluation metrics</li>"
        "<li>Generating comprehensive result reports</li>"
        "</ol>"
        '<div class="callout"><strong>Where the results go</strong>'
        "<code>wl.evaluate(save_path, ...)</code> writes one structured JSON report per model under "
        "<code>save_path/&lt;modelname&gt;/</code>, with timing, visual-quality scores, per-attack "
        "robustness and Base64-encoded sample images. Those JSON files are the input to every plotting "
        "function in <code>wl.draw</code>.</div>"

        '<h2 class="anchor-offset" id="visualize">How to visualize results</h2>'
        "<p>Every plotting helper reads the saved result JSON files and writes figures to a directory:</p>"
        + code_box(read_content("visualize.txt"), "python")
        + '<p style="margin-top:26px"><a href="#quick-start">Back to the quick start examples &uarr;</a></p>'
    )
    return content


def section_eval_watermark() -> str:
    content = (
        '<h3 class="anchor-offset" id="eval-watermark">1. Evaluate your watermark model</h3>'
        '<p class="lead">Subclass <code>BaseWatermarkModel</code>, implement <code>embed</code>, '
        "<code>extract</code> and <code>recover</code>, then hand the instance to <code>wl.evaluate()</code> "
        "together with a dataset and the default attacker set.</p>"
        + code_box(read_content("eval_watermark.txt"), "python")
        + "<h3>What the three methods must return</h3>"
        '<div class="cardgrid">'
        '<div class="modcard"><h4><code>embed(cover_list, secrets)</code></h4>'
        "<p>Receives the cover images (for PGW) or prompts (for IGW) and the secret bit sequences. "
        "Returns a <code>Result</code> carrying the watermarked data and the embedded bits.</p></div>"
        '<div class="modcard"><h4><code>extract(stego_list)</code></h4>'
        "<p>Receives watermarked (and possibly attacked) images and returns a <code>Result</code> with the "
        "recovered bit sequences, which are compared against the ground-truth secret.</p></div>"
        '<div class="modcard"><h4><code>recover(stego_list)</code></h4>'
        "<p>Optional. Only meaningful for reversible watermarking; raise "
        "<code>NotImplementedError</code> if your method cannot restore the cover.</p></div>"
        "</div>"
        '<div class="callout"><strong>Payload and image size</strong>'
        "Your constructor sets <code>bits_len</code> and <code>img_size</code>, and the dataset must match "
        "them (<code>MS_COCO_2017_VAL_IMAGES(im_size=..., bit_len=...)</code>). Most reference models "
        "constrain the payload &mdash; for example rivaGAN and DctDwtSvd require exactly 32 bits.</div>"
        + '<p><a href="#eval-attacker">Next: evaluate your own attacker &rarr;</a></p>'
    )
    return content


def section_eval_attacker() -> str:
    content = (
        '<h3 class="anchor-offset" id="eval-attacker">2. Evaluate your attacker</h3>'
        '<p class="lead">Subclass <code>BaseTestAttackModel</code>, implement <code>attack</code>, wrap it in '
        "<code>AttackerWithFactors</code> and pass it to <code>AttackersWithFactorsModel</code> so the "
        "evaluation sweeps it across the intensity factors you choose.</p>"
        + code_box(read_content("eval_attacker.txt"), "python")
        + "<h3>The three configuration objects</h3>"
        '<div class="cardgrid">'
        '<div class="modcard"><h4><code>BaseTestAttackModel</code></h4>'
        "<p>Your attack. <code>attack(stego_img, cover_img, factor)</code> receives uint8 image arrays and the "
        "current factor, and returns the attacked images.</p></div>"
        '<div class="modcard"><h4><code>AttackerWithFactors</code></h4>'
        "<p>Binds an attacker instance to a display <code>attackername</code>, the list of "
        "<code>factors</code> to sweep, and a LaTeX <code>factorsymbol</code> used in plots.</p></div>"
        '<div class="modcard"><h4><code>AttackersWithFactorsModel</code></h4>'
        "<p>The collection handed to <code>wl.evaluate()</code>. Pass "
        "<code>default_attackers=[your_config]</code> to benchmark against only your attack, or omit it to "
        "use the built-in 40+ sweep.</p></div>"
        "</div>"
        '<div class="callout"><strong>Which way does the factor point?</strong>'
        "Set <code>factor_inversely_related=True</code> when a larger factor means a <em>weaker</em> attack "
        "&mdash; the classic example is JPEG or VAE compression quality, where a higher quality value means "
        "less distortion. This flag is what keeps the ranking plots oriented correctly.</div>"
        + '<p><a href="#api-overview">Jump to the full API reference &rarr;</a></p>'
    )
    return content


def license_page(license_text: str) -> str:
    escaped = html.escape(license_text)
    content = (
        '<p class="breadcrumb">Legal / License</p>'
        "<h1>License</h1>"
        '<p class="lead">WatermarkLab is released under the <strong>MIT License with Additional Terms</strong>. '
        "The additional terms add a patent grant, a no-trademark clause, an ethical-use clause covering the "
        "watermark-removal (attack) functionality, third-party model/dataset restrictions, export compliance "
        "and a DCO requirement for contributions.</p>"
        '<div class="callout"><strong>Read clause 3 before using the attackers</strong>'
        "The attack implementations exist for research and defensive robustness testing. The licence "
        "prohibits using them to remove watermarks from content you are not authorised to modify, to "
        "facilitate piracy or content theft, to bypass provenance or authentication systems in production, "
        "or to create deceptive media.</div>"
        f'<pre style="max-height:none;white-space:pre-wrap">{escaped}</pre>'
    )
    return doc_page("License", "license", content, "WatermarkLab is released under the MIT License with Additional Terms.")


def main() -> None:
    global LOGO_URI, LOGO_IMG, MODE

    dump_path = Path(sys.argv[1])
    logo_path = Path(sys.argv[2])
    out_root = Path(sys.argv[3])
    license_path = Path(sys.argv[4]) if len(sys.argv) > 4 else None
    if len(sys.argv) > 5 and sys.argv[5] == "merged":
        MODE = "merged"

    raw = logo_path.read_bytes()
    LOGO_URI = "data:image/svg+xml;base64," + base64.b64encode(raw).decode("ascii")
    LOGO_IMG = f'<img src="{LOGO_URI}" alt="WatermarkLab logo">'

    dump = json.loads(dump_path.read_text(encoding="utf-8"))
    pages_dir = out_root / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    if merged():
        # Additive mode: only add the two new pages to the existing site and leave
        # every other file alone.
        new_pages = {
            pages_dir / "api-reference.html": api_page(dump),
            }
        for path, content in new_pages.items():
            content = content.replace('href="license.html"', 'href="api-document.html#license"')
            path.write_text(content, encoding="utf-8")
            print(f"wrote {path}  ({len(content):,} chars)")
        return

    license_text = ""
    if license_path and license_path.is_file():
        license_text = license_path.read_text(encoding="utf-8")

    outputs = {
        out_root / "index.html": landing_page(),
        pages_dir / "api-document.html": api_page(dump),
        pages_dir / "license.html": license_page(license_text),
    }
    for path, content in outputs.items():
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path}  ({len(content):,} chars)")

    for name in ("getting-started.html", "evaluate-watermark.html", "evaluate-attacker.html", "api.html"):
        gone = pages_dir / name
        if gone.is_file():
            gone.unlink()
            print(f"removed {gone.name} (content merged into api-document.html)")


if __name__ == "__main__":
    main()
