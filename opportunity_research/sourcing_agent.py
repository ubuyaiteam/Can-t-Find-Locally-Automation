"""Agent 8: sourcing route. Ubuy's model is cross-border retail, so the primary route is a live listing on a source store
(Amazon US/UK/DE/JP, Walmart, eBay); B2B suppliers (Alibaba etc.) are the secondary route.
Prices / MOQ are only recorded if literally present on public pages/snippets."""
import re
from urllib.parse import quote_plus
from . import search
from .evidence import domain_of, now_date, match_product, parse_price
from .market_directory import SOURCE_STORES
from .historical_analysis import core_name

B2B = ("alibaba.com", "made-in-china.com", "globalsources.com", "dhgate.com", "indiamart.com", "tradeindia.com", "ec21.com", "tradekey.com", "aliexpress.com")
MOQ_RE = re.compile(r"(?:MOQ|Min\.?\s*Order(?:\s*Quantity)?|Minimum Order)[:\s]*([\d,]+)\s*(pieces|pcs|units|sets|pairs|piece)?", re.I)

def _hit(r, kind, country, store=None):
    text = r["title"] + " " + r.get("snippet", "")
    price = parse_price(text); moq = MOQ_RE.search(text)
    return {"supplier": store or r["title"][:90], "supplier_site": domain_of(r["url"]), "country": country, "url": r["url"], "kind": kind,
            "price": price["raw"] if price else None, "price_value": price["value"] if price else None, "price_currency": price["currency"] if price else None,
            "moq": (moq.group(1) + " " + (moq.group(2) or "")).strip() if moq else None, "title": r["title"][:140], "source": "search snippet", "checked_at": now_date()}

def _amazon_us_direct(f, cand):
    """Direct Amazon US search page (Ubuy's main source store)."""
    from .evidence import extract_listings, best_match
    url = f"https://www.amazon.com/s?k={quote_plus(core_name(cand))}"
    r = f.get(url)
    if not r.ok:
        return None, r.status
    ls = [l for l in extract_listings(r.text, url) if "/dp/" in l["url"]]
    m, sc = best_match(cand, ls)
    if not m:
        return False, "ok"
    return {"supplier": "Amazon US", "supplier_site": "amazon.com", "country": "United States", "url": m["url"].split("/ref=")[0], "kind": "source store",
            "price": (m["price"] or {}).get("raw"), "price_value": (m["price"] or {}).get("value"), "price_currency": (m["price"] or {}).get("currency"),
            "moq": None, "title": m["title"][:140], "source": "amazon.com search page", "checked_at": now_date()}, "ok"

def find(f, s, cfg, cand, ctx=None):
    core = core_name(cand)
    hits, seen = [], set()
    # the product was FOUND on a source store's best-seller / new-release list -> that listing is the sourcing route
    for sg in cand.get("signals", []):
        if sg.get("kind") in ("amazon_list", "amazon_us") and "/dp/" in (sg.get("url") or "") and sg["url"] not in seen:
            uk = "amazon.co.uk" in sg["url"]
            seen.add(sg["url"])
            hits.append({"supplier": "Amazon UK" if uk else "Amazon US", "supplier_site": "amazon.co.uk" if uk else "amazon.com",
                         "country": "United Kingdom" if uk else "United States", "url": sg["url"], "kind": "source store", "price": None,
                         "price_value": None, "price_currency": None, "moq": None, "title": sg.get("title", "")[:140],
                         "source": f"listed on {sg.get('query', 'best-seller list')}", "checked_at": now_date()})
            break
    direct, st = (None, "skipped") if hits else _amazon_us_direct(f, cand)
    if direct:
        hits.append(direct); seen.add(direct["url"])
    sites = " OR ".join("site:" + x["domain"] for x in SOURCE_STORES[:4])
    items, prov = (search.web(f, s, f'"{core}" ({sites})', "US", 15) if not hits else ([], "amazon.com direct"))
    for r in items:
        d = domain_of(r["url"])
        st = next((x for x in SOURCE_STORES if d.endswith(x["domain"])), None)
        if not st or r["url"] in seen or not match_product(cand, r["title"] + " " + r.get("snippet", ""), 80):
            continue
        seen.add(r["url"])
        hits.append(_hit(r, "source store", {"amazon.com": "United States", "walmart.com": "United States", "ebay.com": "United States",
                                             "amazon.co.uk": "United Kingdom", "amazon.de": "Germany"}.get(st["domain"], "Abroad"), st["name"]))
    if not hits:
        b2b, _ = search.web(f, s, f'"{core}" wholesale (site:alibaba.com OR site:made-in-china.com OR site:globalsources.com)', "US", 10)
        for r in b2b:
            if r["url"] in seen or not any(b in domain_of(r["url"]) for b in B2B) or not match_product(cand, r["title"] + " " + r.get("snippet", ""), 70):
                continue
            seen.add(r["url"])
            hits.append(_hit(r, "B2B supplier", "China (B2B platform - verify supplier location)"))
    fallback = f"https://www.amazon.com/s?k={quote_plus(core)}"
    return {"suppliers": hits[:5], "route_found": bool(hits), "checked_at": now_date(), "provider": prov,
            "source_search_url": fallback,
            "reason": "" if hits else ("Search index unreachable - check source stores manually" if prov is None else
                                       "No matching listing found on source stores or B2B platforms - verify manually"),
            "unverified": prov is None and not hits and direct is None}
