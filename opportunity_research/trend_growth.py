"""Agent 13: year-over-year growth for every opportunity / emerging product, with the source of each figure.

1. Google Trends search interest (country, else worldwide) - last N weeks vs the SAME weeks one year earlier,
   from the public Google Trends 'explore' data (via the free `pytrends` library; Google rate-limits it, so results are
   cached for a week, requests are spaced out, and a blocked call is reported as 'not available' - never guessed).
   Like Google Trends itself: if interest a year ago was 0 and is now > 0 the figure is 'Breakout'.
2. Google News mentions in the country edition - this period vs the same period last year (always available).
Every figure carries its source URL so the team can open and check it."""
import json, math, threading, time
from datetime import date, timedelta
from urllib.parse import quote, quote_plus
from . import search, geo
from .evidence import norm

_STATE = {"fails": 0, "last": 0.0, "n": 0}
BREAKOUT = 99999.0          # Google-Trends style 'Breakout' (was 0 a year ago); a finite number keeps the JSON valid
_LOCK = threading.Lock()

def trends_url(kw, geo_code=None, years=5):
    return f"https://trends.google.com/trends/explore?date=today%20{years}-y" + (f"&geo={geo_code}" if geo_code else "") + f"&q={quote(kw)}"

def fmt_pct(p):
    if p is None: return "n/a"
    if p >= BREAKOUT: return "Breakout"
    return f"{'+' if p >= 0 else ''}{p:,.0f}%"

def _yoy(points, weeks):
    """points: [(date, value)] weekly. Compare the last `weeks` with the same weeks 52 weeks earlier."""
    if len(points) < 52 + weeks:
        return None, None, None
    vals = [v for _, v in points]
    now = vals[-weeks:]; before = vals[-(52 + weeks):-52]
    a, b = sum(now) / len(now), sum(before) / len(before)
    if b == 0:
        return (BREAKOUT if a > 0 else None), a, b
    return (a / b - 1) * 100, a, b

def _fetch_trends(kw, geo_code, s):
    from pytrends.request import TrendReq      # free, unofficial client of the public Google Trends explore endpoints
    t = TrendReq(hl="en-US", tz=0, timeout=(10, 25))
    t.build_payload([kw], timeframe="today 5-y", geo=geo_code or "")
    df = t.interest_over_time()
    if df is None or df.empty or kw not in df:
        return []
    return [(i.date().isoformat(), float(v)) for i, v in df[kw].items()]

def google_trends_yoy(db, s, kw, cc, weeks):
    """-> dict with yoy_pct, label, scope, url, status. Cached per keyword+geo for 7 days."""
    out = {"metric": "Google Trends search interest", "keyword": kw, "status": "not available", "yoy_pct": None, "label": "n/a"}
    if not s.get("enable_google_trends_yoy", True):
        out["status"] = "disabled"; return out
    try:
        import pytrends  # noqa: F401
    except Exception:
        out["status"] = "pytrends not installed (run update.bat)"; return out
    for geo_code, scope in ((cc, "country"), ("", "worldwide")):
        key = f"pytrends://{geo_code or 'WW'}/{kw}"
        row = db.cache_get(key, 24 * 7)
        pts = None
        if row:
            pts = json.loads(row["body"])
        else:
            with _LOCK:
                if _STATE["fails"] >= int(s.get("trends_max_failures", 4)) or _STATE["n"] >= int(s.get("trends_max_queries", 120)):
                    out["status"] = "Google Trends rate limit reached for this run"; return out
                wait = float(s.get("trends_delay_seconds", 6)) - (time.time() - _STATE["last"])
                if wait > 0: time.sleep(wait)
                _STATE["n"] += 1
                try:
                    pts = _fetch_trends(kw, geo_code, s)
                    _STATE["fails"] = 0
                except Exception as e:
                    _STATE["fails"] += 1
                    out["status"] = "Google Trends blocked the request (429/rate limit)" if "429" in str(e) else f"Google Trends error: {str(e)[:60]}"
                    _STATE["last"] = time.time()
                    return out
                _STATE["last"] = time.time()
            db.cache_put(key, 200, json.dumps(pts))
        if not pts or not any(v for _, v in pts):
            continue                                   # no country data -> try worldwide
        pct, a, b = _yoy(pts, weeks)
        if pct is None and a is None:
            continue
        peak = max(pts, key=lambda x: x[1])
        return {**out, "status": "ok", "scope": scope, "geo": geo_code or "Worldwide", "yoy_pct": pct, "label": fmt_pct(pct),
                "this_period_avg": round(a, 1), "last_year_avg": round(b, 1), "weeks": weeks, "peak": {"week": peak[0], "value": peak[1]},
                "series_tail": [v for _, v in pts[-60:]], "url": trends_url(kw, geo_code)}
    out["status"] = "no Google Trends data (too few searches)"
    out["url"] = trends_url(kw, cc)
    return out

def news_yoy(f, cfg, kw, days):
    """Dated Google News mentions (country edition): last `days` vs the same days one year earlier."""
    today = date.today(); a1 = today - timedelta(days=days); b0 = a1 - timedelta(days=365); b1 = today - timedelta(days=365)
    def count(start, end):
        q = f'"{kw}" after:{start.isoformat()} before:{end.isoformat()}'
        items = search.google_news(f, q, cfg["code"], None, cfg["name"], n=100)
        toks = norm(kw).split()
        n = sum(1 for it in items if all(t in norm(it.get("title", "") + " " + it.get("snippet", "")) for t in toks))
        hl, gl, ceid, _ = geo.news_edition(cfg["code"])
        return n, f"https://news.google.com/search?q={quote_plus(q)}&hl={hl}&gl={gl}&ceid={ceid}"
    now_n, now_url = count(a1, today)
    prev_n, prev_url = count(b0, b1)
    pct = (BREAKOUT if now_n else None) if prev_n == 0 else (now_n / prev_n - 1) * 100
    return {"metric": "Google News mentions", "this_period": now_n, "last_year": prev_n, "yoy_pct": pct, "label": fmt_pct(pct) if pct is not None else "n/a",
            "days": days, "url": now_url, "url_last_year": prev_url, "status": "ok" if (now_n or prev_n) else "no mentions in either period"}

def analyse(f, db, s, cfg, cand, period_days):
    from .historical_analysis import core_name
    kw = (cand.get("search_name") or core_name(cand)).lower()[:90]
    weeks = max(4, min(26, round(period_days / 7)))
    g = google_trends_yoy(db, s, kw, cfg["code"], weeks)
    n = news_yoy(f, cfg, kw, max(30, period_days))
    best = g if g.get("status") == "ok" else (n if n.get("status") == "ok" else None)
    headline = (f"{g['label']} YoY · Google Trends ({g['geo']})" if g.get("status") == "ok" else
                f"{n['label']} YoY · Google News mentions ({n['this_period']} vs {n['last_year']})" if n.get("status") == "ok" else "No year-over-year data")
    return {"keyword": kw, "google_trends": g, "news": n, "headline": headline, "yoy_pct": (best or {}).get("yoy_pct"), "source": (best or {}).get("metric")}

def references(cand, cfg):
    """Every source behind a product, grouped, with links - shown at the end of each product."""
    refs, seen = [], set()
    def add(kind, title, url=None, note=""):
        k = (url or "") + "|" + title[:60]
        if k in seen:
            return
        seen.add(k); refs.append({"type": kind, "title": title[:160], "url": url, "note": (note or "")[:160]})
    gr = cand.get("growth") or {}
    if (gr.get("google_trends") or {}).get("url"):
        g = gr["google_trends"]
        add("Search trend", f"Google Trends – '{gr.get('keyword')}' ({g.get('geo', cfg['code'])}, 5 years)", g["url"],
            f"YoY {g.get('label')}: avg {g.get('this_period_avg')} vs {g.get('last_year_avg')} a year ago" if g.get("status") == "ok" else g.get("status", ""))
    if (gr.get("news") or {}).get("url"):
        n = gr["news"]
        add("News trend", f"Google News – {n['this_period']} mentions last {n['days']} days", n["url"], f"vs {n['last_year']} in the same period last year")
        add("News trend", "Google News – same period last year", n.get("url_last_year"))
    for p in (cand.get("history", {}).get("search_phrases") or [])[:6]:
        add("Local search demand", f"Google search suggestion in {cfg['name']}: '{p['phrase']}'",
            f"https://www.google.com/search?q={quote_plus(p['phrase'])}&gl={cfg['code'].lower()}", p.get("intent", ""))
    for sg in (cand.get("signals") or [])[:40]:
        if sg.get("kind") in ("amazon_list", "amazon_us", "bestseller"):
            add("Sells abroad", f"{sg.get('query') or sg.get('source')}: {sg.get('title', '')}", sg.get("url")); break
    for sg in (cand.get("signals") or []):
        if sg.get("kind") in ("google_trends_rss", "global_trend", "reddit", "news") and sg.get("url"):
            add({"google_trends_rss": "Trending now", "global_trend": "Trending abroad", "reddit": "Community", "news": "News"}[sg["kind"]],
                sg.get("title", ""), sg["url"], sg.get("date") or "")
            if len([r for r in refs if r["type"] in ("Trending now", "Trending abroad", "Community", "News")]) >= 4: break
    for e in (cand.get("history", {}).get("evidence") or [])[:3]:
        add("News", f"{e.get('date')} {e.get('title')}", e.get("url"), e.get("source", ""))
    mk = cand.get("marketplace") or {}
    for r in mk.get("results", []):
        add("Local supply check", f"{r['marketplace']}: {r['status']}", r.get("url"), r.get("reason", ""))
    if mk.get("verify_link"):
        add("Local supply check", "Spot-check local availability (Google)", mk["verify_link"])
    ub = cand.get("ubuy") or {}
    if ub.get("url") or ub.get("search_url"):
        add("Ubuy", f"Ubuy: {ub.get('status', '')}", ub.get("url") or ub.get("search_url"), ub.get("reason", ""))
    for x in (cand.get("sourcing") or {}).get("suppliers", [])[:2]:
        add("Sourcing", f"{x.get('supplier')}: {x.get('title', '')}", x.get("url"), x.get("source", ""))
    lg = cand.get("compliance") or {}
    for u in lg.get("official_sources", [])[:2]:
        add("Import rules", "Official source", u)
    return refs
