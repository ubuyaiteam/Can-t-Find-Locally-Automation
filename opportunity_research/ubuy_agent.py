"""Agent 6: Ubuy destination-storefront status. INFORMATIONAL - it decides the recommended action, it never rejects:
   in the Ubuy catalogue  -> "ready to sell: launch the campaign now"
   not in the catalogue   -> "add / enable the SKU, then launch"

Sources, in order:
 1. Your own catalogue export / Google Merchant Center feed for that store (most accurate, no web requests):
    put  data/ubuy_catalog/<CC>.csv | .tsv | .txt | .xml   (e.g. data/ubuy_catalog/IN.tsv) - needs a 'title' column
    (and optionally 'link', 'price', 'availability'), or set settings["ubuy_catalog_files"] = {"IN": "path/to/feed.xml"}.
 2. Optional: the public storefront search page (settings["ubuy_check_search_page"] = true). Ubuy's robots.txt disallows
    /search for bots, so this is OFF by default; as the site owner you may enable it (and add the host to robots_exempt_hosts).
    Ubuy renders results with JavaScript, so it also needs "use_playwright": true.
 3. Search index (site:ubuy...) - only when a provider honours the site: operator."""
import csv, glob, os, threading
import xml.etree.ElementTree as ET
from . import search
from .evidence import extract_listings, best_match, now_date, availability_from_context, domain_of, match_product, parse_price, norm
from .marketplace_agent import queries_for, url_for
from .historical_analysis import core_name
from .settings import BASE

_CAT = {}
_LOCK = threading.Lock()

def _load_catalog(s, cc):
    with _LOCK:
        if cc in _CAT:
            return _CAT[cc]
        path = (s.get("ubuy_catalog_files") or {}).get(cc)
        if not path:
            hits = [p for ext in ("csv", "tsv", "txt", "xml") for p in glob.glob(os.path.join(BASE, "data", "ubuy_catalog", f"{cc}*.{ext}"))
                    + glob.glob(os.path.join(BASE, "data", "ubuy_catalog", f"{cc.lower()}*.{ext}"))]
            path = hits[0] if hits else None
        elif not os.path.isabs(path):
            path = os.path.join(BASE, path)
        items = []
        if path and os.path.exists(path):
            try:
                if path.lower().endswith(".xml"):
                    for it in ET.parse(path).getroot().iter():
                        if it.tag.split("}")[-1] not in ("item", "entry"):
                            continue
                        g = {c.tag.split("}")[-1]: (c.text or "").strip() for c in it}
                        if g.get("title"):
                            items.append({"title": g["title"], "url": g.get("link", ""), "price": g.get("price", ""), "availability": g.get("availability", "")})
                else:
                    with open(path, encoding="utf-8-sig", errors="ignore") as fh:
                        head = fh.readline(); fh.seek(0)
                        rd = csv.DictReader(fh, delimiter="\t" if head.count("\t") > head.count(",") else ",")
                        for row in rd:
                            row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
                            t = row.get("title") or row.get("name") or row.get("product_name")
                            if t:
                                items.append({"title": t, "url": row.get("link") or row.get("url", ""), "price": row.get("price", ""),
                                              "availability": row.get("availability", "")})
            except Exception:
                items = []
        idx = {}
        for it in items:
            for tok in set(norm(it["title"]).split()[:3]):
                idx.setdefault(tok, []).append(it)
        _CAT[cc] = {"path": path, "n": len(items), "idx": idx}
        return _CAT[cc]

def _catalog_lookup(cat, cand):
    brand = norm(cand.get("brand") or "").split()
    keys = brand[:1] or norm(cand["name"]).split()[:1]
    pool = []
    for k in keys:
        pool += cat["idx"].get(k, [])
    best, bs = None, 0
    for it in pool:
        sc = match_product(cand, it["title"], 85)
        if sc > bs:
            best, bs = it, sc
    return best

_DOMAINS = {}
SKIP_LINKS = ("shop-import-products", "/brand/", "/category/", "/store/")

def discover_domain(f, cc):
    """Find the Ubuy storefront of a country that is not in market_directory.py (ubuy.<tld>, ubuy.com.<tld>, ubuy.co.<tld>)."""
    if cc in _DOMAINS:
        return _DOMAINS[cc]
    tld = {"GB": "uk"}.get(cc, cc.lower())
    found = None
    for d in (f"www.ubuy.{tld}", f"www.ubuy.com.{tld}", f"www.ubuy.co.{tld}", "www.ubuy.com"):   # ubuy.com = global store (ships worldwide)
        r = f.get(f"https://{d}/")
        if r.ok and "ubuy" in (r.text or "")[:200000].lower():
            found = d; break
    _DOMAINS[cc] = found
    return found

def parse_cards(html, url):
    """Ubuy search-result product cards -> [{title, url, price}]"""
    out, seen = [], set()
    for l in extract_listings(html, url):
        u = l["url"]
        if "/product/" not in u or any(x in u for x in SKIP_LINKS) or len(l["title"]) < 6:
            continue
        key = u.split("?")[0]
        if key in seen:
            continue
        seen.add(key)
        out.append({"title": l["title"], "url": key, "price": l.get("price"), "context": l.get("context", "")})
    return out

def storefront_check(f, s, dom, cand):
    """Open the storefront search page in a real (headless) browser - results are JavaScript-rendered - and look for the product
    name in the product cards. Ubuy is your own storefront; robots.txt for ubuy hosts is bypassed only when
    settings['ubuy_ignore_robots'] is true (default)."""
    checks, last = [], None
    for q in queries_for(cand)[:2]:
        url = f"https://{dom}/search/?q={q.replace(' ', '+')}"
        res = f.get(url, render=True, wait_for='a[href*="/product/"]')
        checks.append({"query": q, "url": url, "fetch": res.status + ("" if res.ok else f" {res.http or ''}")})
        if not res.ok:
            return {"checks": checks}
        cards = parse_cards(res.text, url)
        hit = None; best = 0
        for c in cards:
            sc = match_product(cand, c["title"], 85)
            if sc > best:
                hit, best = c, sc
        if hit:
            return {"checks": checks, "status": "On Ubuy storefront", "gap": "AVAILABLE", "url": hit["url"],
                    "price": (hit["price"] or {}).get("raw"), "reason": f"Product card: {hit['title'][:90]}", "source": "storefront (rendered)",
                    "cards_seen": len(cards)}
        if cards:
            last = {"checks": checks, "status": "Not on Ubuy storefront", "gap": "NOT_FOUND",
                    "reason": f"{len(cards)} product cards for '{q}', none matching ({', '.join(c['title'][:40] for c in cards[:3])}…)", "source": "storefront (rendered)",
                    "cards_seen": len(cards)}
            continue
        if not RENDER_OK():
            return {"checks": checks, "status": "Not checked", "gap": "UNVERIFIED",
                    "reason": "Ubuy search results load with JavaScript - install Playwright (see INSTALL.md) for the exact Ubuy check"}
    return last or {"checks": checks}

def RENDER_OK():
    from .net import RENDERER
    return RENDERER.available()

def verify(f, s, cfg, cand, ctx=None):
    cc = cfg["code"]
    base = {"checked_at": now_date(), "storefront": cfg.get("ubuy_domain"), "checks": [], "url": None, "price": None, "informational": True}
    cat = _load_catalog(s, cc)
    if cat["n"]:
        hit = _catalog_lookup(cat, cand)
        base["checks"].append({"query": core_name(cand), "url": None, "fetch": f"catalogue file ({cat['n']} products)"})
        if hit:
            oos = "out" in (hit.get("availability") or "").lower()
            return {**base, "status": "In Ubuy catalogue" + (" (out of stock)" if oos else ""), "gap": "LISTED_UNAVAILABLE" if oos else "AVAILABLE",
                    "url": hit.get("url"), "price": hit.get("price") or None, "reason": f"Catalogue match: {hit['title'][:90]}", "source": "catalogue"}
        return {**base, "status": "Not in Ubuy catalogue", "gap": "NOT_FOUND", "reason": f"No match among {cat['n']} catalogue products", "source": "catalogue"}
    dom = cfg.get("ubuy_domain") or discover_domain(f, cc)
    if dom:
        from urllib.parse import quote_plus as _qp
        base["search_url"] = f"https://{dom}/search/?q={_qp(core_name(cand))}"      # always give the team a Ubuy link
        base["storefront"] = dom
    if dom and s.get("ubuy_check_search_page", True):
        st = storefront_check(f, s, dom, cand)
        base["checks"] += st.pop("checks", [])
        if st.get("gap"):
            return {**base, **st, "storefront": dom}
    if dom:
        dom = dom.replace("www.", "")
        items, prov = search.web(f, s, f'"{core_name(cand)}" site:{dom}', cc, 10)
        base["checks"].append({"query": f"site:{dom}", "url": None, "fetch": prov or "no trustworthy search provider"})
        if prov:
            for it in items:
                if domain_of(it["url"]).endswith(dom) and "/product/" in it["url"] and match_product(cand, it["title"], 85):
                    p = parse_price(it["title"] + " " + it.get("snippet", ""))
                    return {**base, "status": "Indexed on Ubuy storefront", "gap": "AVAILABLE", "url": it["url"], "price": p["raw"] if p else None,
                            "reason": f"Indexed product page found via {prov}", "source": "index"}
    return {**base, "status": "Not checked", "gap": "UNVERIFIED",
            "reason": "Add the store's catalogue / Merchant Center feed to data/ubuy_catalog/ for an exact Ubuy check", "source": None}
