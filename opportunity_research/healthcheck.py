"""Source health check: probes every data source used for one country and reports what works on THIS machine/network.
Run from the dashboard (Source health page) or `python diagnose.py NG`."""
import time
from . import search, geo
from .country_registry import load_config
from .marketplace_agent import url_for
from .evidence import extract_listings, page_usable

SAMPLE = {"default": "airpods pro", "AE": "airpods pro", "SA": "airpods pro"}

def run(f, s, code, sample=None):
    cfg = load_config(code); cc = cfg["code"]; q = sample or SAMPLE.get(cc, SAMPLE["default"])
    rows = []

    def rec(name, kind, fn, note_ok):
        t = time.time()
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, f"error: {str(e)[:120]}"
        rows.append({"source": name, "kind": kind, "ok": ok, "detail": detail if not ok else (note_ok + (f" - {detail}" if detail else "")),
                     "seconds": round(time.time() - t, 1)})

    def ac():
        r = search.google_suggest(f, f"{q} price in {cfg['name'].lower()}", cc)
        r2 = r or search.google_suggest(f, q, cc)
        return bool(r2), (", ".join(r2[:4]) if r2 else "no suggestions (blocked or no data)")
    rec("Google Autocomplete (localised)", "demand", ac, "working")

    def news():
        r = search.google_news(f, q, cc, 90, cfg["name"])
        return bool(r), f"{len(r)} articles, edition {geo.news_edition(cc)[2]}" if r else "no articles / blocked"
    rec("Google News (country edition)", "demand", news, "working")

    def tr():
        r = search.google_trends_rss(f, cfg.get("trends_geo") or cc)
        return bool(r), f"{len(r)} trending searches today" if r else "empty / blocked"
    rec("Google Trends daily RSS", "demand", tr, "working")

    def red():
        if not search.REDDIT_SUBS.get(cc): return True, "no subreddit configured (skipped)"
        r = search.reddit(f, cc, "where to buy")
        st = search.STATS.get("reddit", {})
        return bool(r) or not st.get("not_ok"), f"{len(r)} posts"
    rec("Reddit (country subreddit)", "demand", red, "working")

    for name, fn in search.PROVIDERS:
        def prov(fn=fn):
            r, out = fn(f, f'"{q}" price', cc, 10)
            return r.ok, f"{len(out)} results" if r.ok else f"{r.status} {r.http or ''}"
        rec(f"Web search: {name}", "site: checks", prov, "working")

    for mp in cfg.get("marketplaces", []):
        def m(mp=mp):
            if not mp.get("search_url"):
                return True, "no direct URL - search-index only"
            url = url_for(mp["search_url"], q)
            res = f.get(url, render=bool(mp.get("render")) and s.get("use_playwright", False), cache=False)
            if not res.ok:
                return False, f"direct page {res.status} {res.http or ''} - will fall back to search index"
            ls = extract_listings(res.text, url)
            return page_usable(res.text, ls), (f"{len(ls)} links, {sum(1 for l in ls if l['price'])} with prices" if page_usable(res.text, ls)
                                               else "page loads but no readable product grid (JavaScript) - enable Playwright or rely on search index")
        rec(f"Marketplace: {mp['name']}", "local supply", m, "readable")

    def ub():
        from . import ubuy_agent
        from .net import RENDERER
        cat = ubuy_agent._load_catalog(s, cc)
        if cat["n"]:
            return True, f"catalogue feed: {cat['n']} products loaded from {cat['path']}"
        dom = cfg.get("ubuy_domain") or ubuy_agent.discover_domain(f, cc)
        if not dom:
            return False, "no Ubuy storefront found for this country"
        if not RENDERER.available():
            return False, f"{dom}: install Playwright (run update.bat) - Ubuy search results are rendered with JavaScript"
        r = ubuy_agent.storefront_check(f, s, dom, {"name": "Apple AirPods Pro", "brand": "Apple", "model": "", "noun": "earbuds", "alt_names": []})
        if r.get("gap") in ("AVAILABLE", "NOT_FOUND"):
            return True, f"{dom}: product cards readable ({r.get('cards_seen', '?')} cards) - {r.get('reason', '')[:80]}"
        return False, f"{dom}: search page not readable ({(r.get('checks') or [{}])[-1].get('fetch', '?')})"
    rec(f"Ubuy storefront / catalogue ({cfg.get('ubuy_domain') or 'auto-detect'})", "ubuy", ub, "working")

    def us():
        res = f.get(f"https://www.amazon.com/s?k={q.replace(' ', '+')}", cache=False)
        if not res.ok: return False, f"{res.status} {res.http or ''} - sourcing check will fall back to search index"
        n = sum(1 for l in extract_listings(res.text, "https://www.amazon.com") if "/dp/" in l["url"])
        return n > 0, f"{n} product links" if n else "page loads but no product links"
    rec("Amazon US search (sourcing route)", "sourcing", us, "readable")
    def usbs():
        res = f.get("https://www.amazon.com/gp/movers-and-shakers/electronics", cache=False)
        return res.ok, "readable" if res.ok else f"{res.status} {res.http or ''} - global universe will rely on known product lines only"
    rec("Amazon US movers & shakers (global universe)", "demand", usbs, "working")

    ok = sum(1 for r in rows if r["ok"])
    verdict = ("Good: demand + supply checks will work" if any(r["ok"] for r in rows if r["kind"] == "demand") and any(r["ok"] for r in rows if r["kind"] == "local supply")
               else "Degraded: core demand sources failed - check internet / proxy / VPN" if not any(r["ok"] for r in rows if r["kind"] == "demand")
               else "Partial: demand works but supply checks cannot be verified - add a search API key or enable Playwright")
    return {"country": cfg["name"], "code": cc, "sample": q, "ok": ok, "total": len(rows), "verdict": verdict, "rows": rows}
