"""Agent 2: LOCAL demand validation + measured history for one candidate in one country.

Evidence collected (all measured, nothing invented):
  * Google Autocomplete in the country for the product -> is it actually searched there, with what intent
    (price / where-to-buy / city / currency / import-from-abroad). Observed phrases are kept as campaign keywords.
  * Google News country edition, dated, relevance-filtered -> mention series over the selected period (trend class)
  * optional pytrends interest (free, unofficial, fails gracefully)
Demand is a PUBLIC-INTEREST PROXY, not sales volume."""
import math, time
from datetime import date, timedelta
from . import search, geo
from .evidence import now_date, norm

_PYT = {"fails": 0, "n": 0}

def bucket_days(period):
    return {15: 3, 30: 5, 45: 7, 60: 10, 90: 15}.get(period, max(3, round(period / 6)))

def slope(y):
    n = len(y)
    if n < 2: return 0.0, (y[0] if y else 0.0), 0.0
    xm, ym = (n - 1) / 2, sum(y) / n
    sxx = sum((i - xm) ** 2 for i in range(n)); sxy = sum((i - xm) * (v - ym) for i, v in enumerate(y))
    b = sxy / sxx; a = ym - b * xm
    ss_tot = sum((v - ym) ** 2 for v in y); ss_res = sum((v - (a + b * i)) ** 2 for i, v in enumerate(y))
    return b, a, (1 - ss_res / ss_tot) if ss_tot else 0.0

def classify(counts):
    total, nz, n = sum(counts), sum(1 for c in counts if c), len(counts)
    if total < 3 or nz < 2:
        return "Insufficient data"
    half = n // 2
    if sum(counts[:half]) == 0 and sum(counts[half:]) >= 2:
        return "Emerging product demand"
    prev = counts[:-1]; mean_prev = sum(prev) / len(prev)
    if counts[-1] >= 3 and counts[-1] >= 3 * max(mean_prev, 0.5):
        return "Sudden popularity"
    b, _, _ = slope(counts); mean = total / n
    if b / max(mean, 0.5) > 0.15: return "Increasing demand"
    if b / max(mean, 0.5) < -0.15: return "Declining interest"
    return "Stable interest"

def _pytrends(cfg, name, period, s):
    if not s.get("enable_pytrends") or _PYT["fails"] >= 2 or _PYT["n"] >= s["pytrends_max_queries"]:
        return None
    _PYT["n"] += 1
    try:
        from pytrends.request import TrendReq   # optional, unofficial, free
        time.sleep(2)
        t = TrendReq(hl="en-US", tz=0, timeout=(5, 15)); t.build_payload([name], timeframe="today 3-m", geo=cfg.get("trends_geo") or cfg["code"])
        df = t.interest_over_time()
        if df is None or df.empty: return None
        cutoff = date.today() - timedelta(days=period)
        return [(i.date().isoformat(), float(v)) for i, v in df[name].items() if i.date() >= cutoff]
    except Exception:
        _PYT["fails"] += 1
        return None

def core_name(cand):
    """Short searchable name: the name people search with (found during validation), else brand + model (+ type)."""
    if cand.get("search_name"):
        return cand["search_name"]
    n = cand["name"]
    if cand.get("brand") and cand.get("model") and len(n.split()) > 5:
        n = f"{cand['brand']} {cand['model']} {cand['noun']}"
    return n.replace("  ", " ").strip()

GENERIC = {"with", "for", "and", "the", "new", "pro", "max", "plus", "mini", "ultra", "set", "pack", "kit", "edition", "version", "black", "white", "blue",
           "pink", "green", "red", "grey", "gray", "silver", "gold", "inch", "large", "small", "medium"}

def search_names(cand):
    """Short names people actually type: product line ('ninja creami'), line + model ('iphone 17'), brand + type."""
    from .product_identification import PRODUCT_LINES
    brand = norm(cand.get("brand") or "")
    name = norm(cand["name"]); ntoks = name.split()
    out = []
    for line in sorted(PRODUCT_LINES, key=len, reverse=True):
        if PRODUCT_LINES[line][0] and norm(PRODUCT_LINES[line][0]) == brand and all(t in ntoks or any(x.startswith(t) for x in ntoks) for t in norm(line).split()):
            out.append(norm(line)); break
    if len(ntoks) <= 5:
        out.insert(0, name)
    noun = norm(cand.get("noun", ""))
    words = [w for w in ntoks if w not in brand.split() and w not in noun.split()]
    alpha = [w for w in words if w.isalpha() and w not in GENERIC and len(w) > 2]
    model = [w for w in words if any(c.isdigit() for c in w)]
    if alpha:
        out.append(f"{brand} {alpha[0]}".strip())
        if model: out.append(f"{alpha[0]} {model[0]}"); out.append(f"{brand} {alpha[0]} {model[0]}".strip())
    elif model and brand:
        out.append(f"{brand} {model[0]}")
    if brand and noun and noun in name:
        out.append(f"{brand} {noun}")
    return list(dict.fromkeys(o.strip() for o in out if len(o.split()) >= 2))[:4]

def _mentions(text, cand, name=None):
    t = " " + norm(text) + " "
    toks = [x for x in norm(name or core_name(cand)).split() if x not in ("the", "and", "with")]
    if not toks:
        return False
    req = [x for x in toks if any(c.isdigit() for c in x)]
    if any(f" {r} " not in t for r in req):
        return False
    rest = [x for x in toks if x not in req]
    return sum(1 for r in rest if f" {r} " in t) >= max(1, math.ceil(len(rest) * 0.75)) if rest else True

AMBIGUOUS = {"stanley cup": {"winners", "winner", "playoffs", "playoff", "hockey", "nhl", "final", "finals", "trophy", "champions", "champion", "odds", "schedule"},
             "apple watch": {"face", "faces", "wallpaper"}, "lego": {"movie", "game", "film"}, "pokemon": {"game", "episode", "anime", "movie"}}

def off_topic(text, cand):
    """'stanley cup winners' is about hockey, not the tumbler."""
    low = " " + norm(text) + " "; name = norm(cand.get("search_name") or cand["name"])
    for k, bad in AMBIGUOUS.items():
        if k in name or k in low:
            if any(f" {b} " in low for b in bad if b not in name):
                return True
    return False

def search_demand(f, cfg, cand):
    """Google Autocomplete validation in the destination country (suggestions about OTHER countries are ignored)."""
    from .trend_discovery import foreign
    cc, country = cfg["code"], cfg["name"]
    mk = geo.local_markers(cc, country)
    names = search_names(cand) or [core_name(cand).lower()]
    # main name + buying-intent probes first; extra name variants only when the main name was not conclusive (saves ~1/3 of requests)
    probes = [(names[0], names[0]), (f"{names[0]} price", names[0])]
    probes += [(t.format(p=names[0]), names[0]) for t in geo.intent_templates(cc, country)[:2]]
    variants = [(nm, nm) for nm in names[1:3]]
    seen, phrases, best_name = set(), [], None
    for q, nm in dict.fromkeys(probes + variants):
        if (q, nm) in variants and len(phrases) >= 5:
            continue
        for sg in search.google_suggest(f, q, cc):
            k = norm(sg)
            if k in seen or foreign(sg, cc) or not _mentions(sg, cand, nm) or off_topic(sg, cand):
                continue
            if any(f" {st} " in f" {k} " for st in geo.FOREIGN_STORES):
                continue                                  # 'ps5 pro fnac' = a French shopper, not a local one
            seen.add(k); best_name = best_name or nm
            low = sg.lower()
            intent = ("unmet" if any(p in low for p in geo.UNMET_PATTERNS.get(mk["lang"], []) + geo.UNMET_PATTERNS["en"]) else
                      "price" if any(w in low for w in geo.PRICE_WORDS.get(mk["lang"], []) + geo.PRICE_WORDS["en"]) else
                      "local" if (mk["country"] in low or any(c in low for c in mk["cities"]) or any(c and c in low.split() for c in mk["currency"])) else "search")
            phrases.append({"phrase": sg, "intent": intent, "probe": q})
    for p in phrases:
        low = " " + p["phrase"].lower() + " "
        p["local_marker"] = (f" {mk['country']} " in low or any(f" {c} " in low for c in mk["cities"]) or any(c and f" {c} " in low for c in mk["currency"]))
    if geo.needs_local_marker(cc):
        # small market: Google mixes in suggestions from the big market of the same language -> only explicitly local phrases count
        local_only = [p for p in phrases if p["local_marker"]]
        n_market = len(phrases)
        phrases = local_only + [dict(p, intent="generic (" + geo.language(cc) + "-speaking market)") for p in phrases if not p["local_marker"]]
        n = len(local_only)
        n_local = n
        n_unmet = sum(1 for p in local_only if p["intent"] == "unmet")
        return {"phrases": phrases[:40], "matches": n, "local_intent": n_local, "unmet_intent": n_unmet, "search_name": best_name,
                "searched_locally": n >= 1, "language_market_matches": n_market,
                "note": f"{n_market} suggestions in the {geo.language(cc)}-speaking market, {n} explicitly about {country}"}
    n = len(phrases)
    n_local = sum(1 for p in phrases if p["intent"] in ("price", "local", "unmet"))
    n_unmet = sum(1 for p in phrases if p["intent"] == "unmet")
    return {"phrases": phrases[:40], "matches": n, "local_intent": n_local, "unmet_intent": n_unmet, "search_name": best_name,
            "searched_locally": n >= 1 and (n_local >= 1 or n >= 3)}

def collect_news(f, cfg, cand, start, today, period, want=8):
    core = core_name(cand)
    qs = list(dict.fromkeys([f'"{core}"', f'{core} {cfg["name"]}']))
    seen, kept, raw, tried = set(), [], 0, []
    for q in qs:
        tried.append(q)
        items = search.news(f, q, cfg["code"], max(period, 7), cfg["name"])
        raw += len(items)
        for it in items:
            if it["url"] in seen or not it.get("date"):
                continue
            seen.add(it["url"])
            d = date.fromisoformat(it["date"])
            if start <= d <= today and _mentions(it.get("title", "") + " " + it.get("snippet", ""), cand):
                kept.append(it)
        if len(kept) >= want:
            break
    return kept, raw, tried

def analyse(f, s, cfg, cand, period, ctx):
    today = date.today(); start = today - timedelta(days=period)
    bd = bucket_days(period); nb = math.ceil(period / bd)
    sd = search_demand(f, cfg, cand)
    if sd.get("search_name"):
        cand["search_name"] = sd["search_name"]
    in_period, raw_n, tried = collect_news(f, cfg, cand, start, today, period)
    counts = [0] * nb; series = []
    for it in in_period:
        idx = min(nb - 1, (date.fromisoformat(it["date"]) - start).days // bd)
        counts[idx] += 1
    for i, c in enumerate(counts):
        series.append(((start + timedelta(days=i * bd)).isoformat(), (start + timedelta(days=min(period, (i + 1) * bd))).isoformat(), float(c)))
    pt = _pytrends(cfg, core_name(cand), period, s)
    trends_mean = round(sum(v for _, v in pt) / len(pt), 1) if pt else None
    sig = cand["signals"]
    local_sig = [x for x in sig if x.get("scope") == "local"]
    intl_sig = [x for x in sig if x.get("scope") == "international"]
    discovery_unmet = sum(1 for x in local_sig if x.get("intent") == "unmet")
    trend_hit = any(x["kind"] == "google_trends_rss" for x in local_sig)
    reddit_hit = any(x["kind"] == "reddit" for x in local_sig)
    domains = {it["source"] for it in in_period} | {x["source"] for x in local_sig if x["kind"] not in ("autocomplete",)}
    mentions = len(in_period)

    comp = {
        "search_presence": min(35, 9 * sd["matches"] + 3 * sum(1 for x in local_sig if x["kind"] == "autocomplete")),
        "local_buying_intent": min(20, 7 * sd["local_intent"]),
        "unmet_demand": min(15, 7.5 * (sd["unmet_intent"] + discovery_unmet + (1 if reddit_hit else 0))),
        "news_and_sources": min(15, 2.5 * mentions + 2 * len(domains)),
        "trend_spike": 10 if trend_hit else (min(10, trends_mean / 10) if trends_mean else 0),
        "global_momentum": min(5, 2.5 * len({x["source"] for x in intl_sig})),
    }
    demand = sum(comp.values())
    local_ok = sd["searched_locally"] or trend_hit or reddit_hit or mentions >= 2 or bool(trends_mean)
    only_international = not local_sig and bool(intl_sig)
    trend_class = classify(counts)
    if trend_class == "Insufficient data" and sd["matches"] >= 3:
        trend_class = "Actively searched (no dated history)"
    hist = {"period_days": period, "bucket_days": bd, "counts": counts, "series_start": start.isoformat(), "series_end": today.isoformat(),
            "trend_class": trend_class, "mentions": mentions, "distinct_sources": len(domains), "google_trends_mean": trends_mean,
            "measured": True, "metric": "Dated local news mentions per bucket + local search suggestions (public-interest proxies, NOT sales)",
            "queries_tried": tried, "items_fetched": raw_n, "items_relevant_in_period": mentions,
            "evidence": [{"title": it["title"][:140], "url": it["url"], "date": it["date"], "source": it["source"]} for it in in_period[:8]],
            "search_phrases": sd["phrases"], "checked_at": now_date()}
    cand["history"] = hist
    cand["demand"] = {"score": round(min(100, demand), 1), "components": {k: round(v, 1) for k, v in comp.items()},
                      "local_evidence": bool(local_ok), "searched_locally": sd["searched_locally"], "local_search_matches": sd["matches"],
                      "local_intent_matches": sd["local_intent"], "unmet_signals": sd["unmet_intent"] + discovery_unmet + (1 if reddit_hit else 0),
                      "only_international": only_international, "sources": len(domains),
                      "formula": "search presence(35)+local buying intent(20)+unmet-demand phrases(15)+news & sources(15)+trend spike(10)+global momentum(5)"}
    return series
