"""Agent 1: "Can't find it locally" demand radar - candidate discovery for ONE destination country.

Sources (each fails independently, every one localised to the country):
  A. Google Autocomplete (gl=<country>, hl=<language>) probed with local buying-intent templates per product type:
       "<type> price in <country>", "where to buy <type> in <country>", "buy <type> <city>", ...
     -> the suggestions are REAL searches made in that country and usually name the exact brand/model people want.
  B. Open "unmet demand" probes: "where to buy a…z in <country>", "how to order … to <country>"
  C. Google Trends daily trending RSS for the country
  D. Google News country edition: launches / "now available in" / "not available in" / category price news
  E. Reddit country subreddit: "where can I buy", "anyone know where to get", "ship to"
  F. Global early-trend universe (US/UK trending + configured bestseller pages) -> marked scope=international, they must
     later prove LOCAL search demand or they end up in the "Emerging" bucket ("may become trending").
"""
import datetime, re, string
from concurrent.futures import ThreadPoolExecutor
from . import search, geo
from .evidence import domain_of, extract_listings, norm
from .product_identification import LEXICON, CATEGORIES, PRODUCT_LINES, extract_from_text
from .country_registry import COUNTRIES

AMAZON_US_SLUGS = {"electronics": "Electronics", "kitchen": "Kitchen Appliances & Accessories", "beauty": "Beauty", "hpc": "Personal Care",
                   "toys-and-games": "Toys", "sporting-goods": "Sports", "pet-supplies": "Pet Products", "office-products": "Office Products",
                   "automotive": "Automotive", "hi": "Tools", "lawn-garden": "Gardening", "baby-products": "Specialized Consumer Products",
                   "fashion": "Fashion", "home-garden": "Lifestyle Products", "videogames": "Electronics", "pc": "Computers & Accessories",
                   "wireless": "Mobile Accessories", "arts-crafts": "Hobbies"}
_OTHER = {}

def foreign(text, cc):
    """True if a search suggestion is about ANOTHER country ('where to buy 3d printer in philippines')."""
    if cc not in _OTHER:
        names = {v["name"].lower() for k, v in COUNTRIES.items() if k != cc}
        names |= {"maroc", "algérie", "algerie", "tunisie", "sénégal", "senegal", "côte d'ivoire", "cote d'ivoire", "cameroun", "france", "belgique", "suisse",
                  "réunion", "reunion", "maurice", "québec", "quebec", "gabon", "congo", "mali", "niger", "tchad", "bénin", "benin", "togo", "guinée", "haïti",
                  "españa", "espana", "méxico", "brasil", "argentina", "colombia", "chile", "perú", "portugal", "angola", "moçambique", "allemagne", "italie",
                  "espagne", "royaume-uni", "etats-unis", "états-unis", "dom tom", "martinique", "guadeloupe", "guyane", "mayotte",
                  "usa", "uk", "dubai", "uae", "america", "canada", "australia", "philippines", "pakistan", "bangladesh", "nigeria", "kenya", "india", "china",
                  "singapore", "malaysia", "south africa", "saudi", "qatar", "kuwait", "germany", "japan", "korea", "ghana", "egypt", "sri lanka", "nepal"}
        names -= {COUNTRIES[cc]["name"].lower()} | ({"uae", "dubai"} if cc == "AE" else set()) | ({"usa", "america"} if cc == "US" else set()) | \
                 ({"uk"} if cc == "GB" else set()) | ({"saudi"} if cc == "SA" else set())
        _OTHER[cc] = re.compile(r"\b(" + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r")\b")
    return bool(_OTHER[cc].search(text.lower()))

PRIORITY_TYPES = {   # product types probed first per category (most cross-border-relevant)
    "Electronics": ["earbuds", "smartwatch", "headphones", "bluetooth speaker", "gaming console", "projector", "action camera", "starlink", "smartphone"],
    "Computers & Accessories": ["laptop", "tablet", "monitor", "mechanical keyboard", "router", "ssd", "printer"],
    "Mobile Accessories": ["power bank", "charger", "phone case", "wireless charger", "ring light", "gimbal"],
    "Smart Home": ["portable power station", "solar generator", "robot vacuum", "air purifier", "security camera", "inverter", "smart lock"],
    "Home Improvement": ["rechargeable fan", "water purifier", "generator", "shower head", "water heater"],
    "Kitchen Appliances & Accessories": ["air fryer", "blender", "coffee machine", "tumbler", "water bottle", "ice cream maker", "stand mixer", "pressure cooker"],
    "Beauty": ["serum", "sunscreen", "hair dryer brush", "air styler", "perfume", "body mist", "wig", "lip oil", "hair oil", "moisturizer"],
    "Personal Care": ["electric toothbrush", "trimmer", "massage gun", "water flosser", "ipl hair removal", "blood pressure monitor"],
    "Fashion": ["sneakers", "running shoes", "clogs", "jersey", "leggings"],
    "Fashion Accessories": ["handbag", "sunglasses", "watch", "belt bag"],
    "Toys": ["lego set", "blind box", "rc car", "doll", "plush toy", "trading cards"],
    "Hobbies": ["drone", "3d printer", "sewing machine", "guitar", "digital piano", "cutting machine"],
    "Sports": ["pickleball paddle", "padel racket", "electric scooter", "football boots", "bicycle", "boxing gloves"],
    "Fitness": ["walking pad", "treadmill", "adjustable dumbbell", "creatine", "whey protein", "smart ring", "exercise bike"],
    "Automotive": ["dash cam", "carplay adapter", "tire inflator", "jump starter", "obd scanner"],
    "Pet Products": ["automatic feeder", "self cleaning litter box", "pet camera", "dog harness", "pet fountain"],
    "Office Products": ["standing desk", "ergonomic chair", "monitor arm", "label maker"],
    "Tools": ["cordless drill", "tool kit", "multimeter", "angle grinder", "air compressor"],
    "Gardening": ["grow light", "hydroponic kit", "lawn mower"],
    "Outdoor Products": ["camping tent", "camping chair", "cooler", "solar charger", "headlamp"],
    "Travel Accessories": ["luggage", "airtag", "packing cubes", "travel adapter"],
    "Lifestyle Products": ["humidifier", "diffuser", "weighted blanket", "sunset lamp", "digital quran"],
    "Gifting": ["gift set", "digital photo frame"],
    "Specialized Consumer Products": ["baby monitor", "stroller", "breast pump", "car seat", "glucometer"],
}
NEWS_QUERIES = ["launch price", "now available in", "not available in", "coming to", "officially launched in", "where to buy", "price and availability"]
REDDIT_QUERIES = ["where can I buy", "where to buy", "anyone know where", "ship to", "import from amazon"]

def _intent(text, mk):
    t = text.lower()
    lang = mk["lang"]
    if any(p in t for p in geo.UNMET_PATTERNS.get(lang, []) + geo.UNMET_PATTERNS["en"]):
        return "unmet"
    if any(w in t.split() or w in t for w in geo.PRICE_WORDS.get(lang, []) + geo.PRICE_WORDS["en"]):
        return "price"
    if any(c in t for c in mk["cities"]) or mk["country"] in t or any(c and c in t.split() for c in mk["currency"]):
        return "local"
    if any(w in t.split() for w in geo.BUY_WORDS.get(lang, []) + geo.BUY_WORDS["en"]):
        return "buy"
    return "search"

def discover(f, s, cfg, period, category, ctx, run_id=0):
    A = "Agent 1 Demand Radar"
    ctx.log(A, f"Scanning local demand signals for {cfg['name']} (language '{geo.language(cfg['code'])}', Google News edition {geo.news_edition(cfg['code'])[2]})")
    search.reset_stats()
    cc, country = cfg["code"], cfg["name"]
    mk = geo.local_markers(cc, country)
    cats = [category] if category and category != "ALL" else CATEGORIES
    raw, coverage = [], {}

    def add(text, url, kind, intent, date=None, scope="local", title=None, lowercase=False, query=None):
        for p in extract_from_text(text, lowercase):
            p["signal"] = {"source": domain_of(url) or kind, "kind": kind, "intent": intent, "url": url, "title": (title or text)[:160],
                           "date": date, "scope": scope, "query": query}
            raw.append(p)

    # ---- A + B: Google Autocomplete probes ------------------------------------------------------------
    tpls = geo.intent_templates(cc, country)
    per_cat = max(1, int(s.get("autocomplete_types_per_category", 5)))
    probes = []
    for c in cats:
        types = (PRIORITY_TYPES.get(c) or LEXICON[c])[: per_cat if len(cats) > 1 else per_cat * 3]
        for t in types:
            for tp in tpls[: (2 if len(cats) > 1 else len(tpls))]:
                probes.append((tp.format(p=t), c))
    if not category or category == "ALL":
        lead = tpls[1].split("{p}")[0] if "{p}" in tpls[1] else "where to buy "
        probes += [(lead + ch, None) for ch in string.ascii_lowercase]
    probes = list(dict.fromkeys(probes))[: int(s.get("max_autocomplete_probes", 260))]
    ac_url = lambda q: f"https://www.google.com/search?q={q.replace(' ', '+')}&gl={cc.lower()}"

    def ac_job(pq):
        ctx.check()
        q, _ = pq
        return q, search.google_suggest(f, q, cc)
    n_sug = 0
    with ThreadPoolExecutor(s["workers"]) as ex:
        for q, sugs in ex.map(ac_job, probes):
            for sg in sugs:
                if norm(sg) == norm(q) or foreign(sg, cc):
                    continue
                n_sug += 1
                add(sg, ac_url(sg), "autocomplete", _intent(sg, mk), datetime.date.today().isoformat(), "local", sg, lowercase=True, query=q)
    coverage["Google Autocomplete"] = f"{len(probes)} local-intent probes, {n_sug} real local search suggestions"
    ctx.log(A, f"Google Autocomplete: {len(probes)} probes -> {n_sug} local search suggestions")

    # ---- A2: known global product lines tested against LOCAL searches ---------------------------------
    lines = [l for l, (b, n, c) in PRODUCT_LINES.items() if b and (not category or category == "ALL" or c == category)]
    lines = lines[: int(s.get("max_product_line_probes", 220))]
    def line_job(line):
        ctx.check()
        return line, search.google_suggest(f, line, cc)
    n_line = 0
    with ThreadPoolExecutor(s["workers"]) as ex:
        for line, sugs in ex.map(line_job, lines):
            for sg in sugs:
                if foreign(sg, cc) or line not in sg.lower():
                    continue
                n_line += 1
                add(sg, ac_url(sg), "autocomplete", _intent(sg, mk), datetime.date.today().isoformat(), "local", sg, lowercase=True, query=line)
    coverage["Global product lines searched locally"] = f"{len(lines)} product lines probed, {n_line} local suggestions"
    ctx.log(A, f"Known global product lines: {len(lines)} probed in {country} search -> {n_line} local suggestions")

    # ---- A3: 'sells abroad' universe, first slice (Amazon US/UK best sellers, movers, new releases, most wished for, gifted) ----
    n_us = 0
    if s.get("include_amazon_us_universe", True) and cc != "US":
        from . import universe
        pages, total = universe.slice_for(run_id or 1, 1, int(s.get("universe_pages_per_round", 24)), category)
        got, ok_pages = universe.harvest(f, pages, ctx, datetime.date.today().isoformat())
        raw += got; n_us = len(got)
        coverage["Sells-abroad universe (round 1)"] = f"{ok_pages}/{len(pages)} of {total} source pages, {n_us} products"
        ctx.log(A, f"Sells-abroad universe: {ok_pages}/{len(pages)} pages readable (of {total} in the pool) -> {n_us} products to test against local demand")

    # ---- C: Google Trends daily RSS -------------------------------------------------------------------
    geo_code = cfg.get("trends_geo") or cc
    try:
        items = search.google_trends_rss(f, geo_code)
        coverage["Google Trends RSS"] = len(items)
        for it in items:
            add(it["title"], f"https://trends.google.com/trending?geo={geo_code}", "google_trends_rss", "trend", it["date"], "local", it["title"], lowercase=True)
            for n in it["news"]:
                add(n["title"], n["url"] or f"https://trends.google.com/trending?geo={geo_code}", "google_trends_rss", "trend", it["date"], "local", n["title"])
    except Exception as e:
        coverage["Google Trends RSS"] = f"failed: {e}"

    # ---- D: Google News country edition ---------------------------------------------------------------
    nq = [f"{q} {country}" for q in NEWS_QUERIES]
    nq += [f"{c.split(' &')[0].lower()} price {country}" for c in cats[:24]]
    def news_job(q):
        ctx.check()
        return q, search.news(f, q, cc, max(period, 30), country)
    n_news = 0
    with ThreadPoolExecutor(s["workers"]) as ex:
        for q, res in ex.map(news_job, nq):
            n_news += len(res)
            for r in res:
                intent = "unmet" if any(p in (r["title"] + " " + q).lower() for p in ("not available", "where to buy", "coming to")) else "news"
                add(r["title"] + ". " + r.get("snippet", ""), r["url"], "news", intent, r.get("date"), "local" if r.get("localized_edition", True) else "regional", r["title"])
    coverage["Google News"] = f"{len(nq)} queries, {n_news} articles"

    # ---- E: Reddit -------------------------------------------------------------------------------------
    n_red = 0
    if s.get("enable_reddit", True):
        for q in REDDIT_QUERIES:
            try:
                for r in search.reddit(f, cc, q):
                    n_red += 1
                    add(r["title"] + ". " + r["snippet"], r["url"], "reddit", "unmet", r["date"], "local", r["title"])
            except Exception:
                pass
        coverage["Reddit"] = f"{n_red} posts" if search.REDDIT_SUBS.get(cc) else "no country subreddit configured"

    # ---- F: global early-trend universe ---------------------------------------------------------------
    if s.get("include_global_trends", True):
        for g in s.get("global_trend_geos", ["US", "GB"]):
            if g == cc:
                continue
            try:
                for it in search.google_trends_rss(f, g):
                    for n in [{"title": it["title"], "url": ""}] + it["news"]:
                        add(n["title"], n["url"] or f"https://trends.google.com/trending?geo={g}", "global_trend", "global", it["date"], "international", n["title"],
                            lowercase=not n["url"])
            except Exception:
                pass
        for q in ("viral product", "tiktok made me buy it", "sold out everywhere", "best selling gadget"):
            for r in search.google_news(f, q, "US", 30):
                add(r["title"], r["url"], "global_news", "global", r.get("date"), "international", r["title"])
    for bp in cfg.get("bestseller_pages", []):
        if category and category != "ALL" and bp.get("category") and bp["category"] != category:
            continue
        try:
            r = f.get(bp["url"])
            if not r.ok:
                coverage[bp["name"]] = f"unavailable ({r.status})"; continue
            ls = extract_listings(r.text, bp["url"])
            coverage[bp["name"]] = len(ls)
            for l in ls:
                add(l["title"], bp["url"], "bestseller", "global" if bp.get("scope") == "international" else "buy", None, bp.get("scope", "local"), l["title"])
        except Exception as e:
            coverage[bp["name"]] = f"failed: {e}"

    if category and category != "ALL":
        raw = [r for r in raw if r["category"] == category]
    health = {k: dict(v) for k, v in search.STATS.items()}
    coverage["Fetch health"] = health
    ctx.log(A, "Fetch health (calls / failed / empty / items / last error): "
            + "; ".join(f"{k}: {v['calls']}/{v['not_ok']}/{v['empty']}/{v['items']}/{v['last_error'] or '-'}" for k, v in health.items()))
    local_raw = sum(1 for r in raw if r["signal"]["scope"] == "local")
    if not raw:
        failed = [k for k, v in health.items() if v["calls"] and v["not_ok"] == v["calls"]]
        ctx.log(A, "NO PRODUCT SIGNALS. " + (f"These sources failed on every call: {', '.join(failed)} - check network/VPN or open the Source health page. " if failed else "")
                + "This is NOT evidence that there is no demand.", "warn")
    ctx.log(A, f"{len(raw)} product mentions extracted ({local_raw} local, {len(raw) - local_raw} international early-trend)")
    return raw, coverage
