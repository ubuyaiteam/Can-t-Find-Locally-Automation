"""Agent 12: SKU + campaign suggestions, built ONLY from observed evidence (real local search phrases, observed listings)."""
from urllib.parse import quote_plus
from .historical_analysis import core_name
from .evidence import norm

NEGATIVES = ["used", "repair", "fake", "replica", "second hand", "manual", "how to use", "review", "vs", "free", "download", "wallpaper", "png",
             "meaning", "drawing", "jobs", "rent", "parts", "screen replacement", "occasion", "reconditionné", "reconditionne", "seconde main",
             "usado", "usada", "seminovo", "gebraucht", "mode d emploi", "notice", "avis", "test", "winners", "playoffs"]
COMPETITORS = {"amazon", "fnac", "ebay", "jumia", "aliexpress", "temu", "shein", "cdiscount", "darty", "boulanger", "walmart", "noon", "daraz", "desertcart",
               "flipkart", "takealot", "konga", "jiji", "olx", "mercado libre", "mercadolibre", "lazada", "shopee", "carrefour", "leclerc", "best buy"}

def _clip(t, n):
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"

def suggest(cfg, cand):
    core = core_name(cand)
    phrases = [p["phrase"] for p in (cand.get("history", {}).get("search_phrases") or []) if not str(p.get("intent", "")).startswith("generic")]
    phrases += [s.get("title") for s in cand.get("signals", []) if s.get("kind") == "autocomplete" and s.get("title")
                and (cfg["name"].lower() in s["title"].lower() or not __import__("opportunity_research.geo", fromlist=["x"]).needs_local_marker(cfg["code"]))]
    seen, kws, comp = set(), [], []
    for p in phrases:
        k = norm(p)
        if not k or k in seen or any(f" {n} " in f" {k} " for n in NEGATIVES):
            continue
        seen.add(k)
        if any(f" {c} " in f" {k} " for c in COMPETITORS):
            comp.append(p.lower()); continue          # competitor terms: optional conquest campaign, not the main ad groups
        kws.append(p.lower())
    exact = [f"[{k}]" for k in kws[:10]]
    phrase = [f'"{core.lower()}"', f'"{core.lower()} price"', f'"buy {core.lower()}"']
    if cfg.get("name"):
        phrase.append(f'"{core.lower()} {cfg["name"].lower()}"')
    ub = cfg.get("ubuy_domain")
    landing = f"https://{ub}/search/?q={quote_plus(core)}" if ub else None
    unmet = (cand.get("demand") or {}).get("unmet_signals", 0)
    mk = cand.get("marketplace", {})
    hook = "Hard to find locally? Get the original" if mk.get("gap") == "FULL_GAP" else "Original, imported & delivered"
    headlines = [_clip(f"{core}", 30), _clip(f"Buy {core} in {cfg['name']}", 30), _clip(f"{cand.get('brand') or core} – 100% Original", 30),
                 "Fast Delivery to Your Door", "Imported From USA & UK", _clip(f"{core} at Ubuy", 30)]
    descriptions = [_clip(f"{hook}. {core} shipped to {cfg['name']} with duties handled at checkout.", 90),
                    _clip(f"Shop {core} from top US stores via Ubuy. Secure payment, tracked delivery.", 90)]
    sku = {"title": core, "brand": cand.get("brand") or "", "model": cand.get("model") or "", "product_type": cand.get("noun"), "category": cand.get("category"),
           "variants_seen_in_searches": list(dict.fromkeys(p for p in kws if norm(core) in norm(p)))[:6],
           "source_search": f"https://www.amazon.com/s?k={quote_plus(core)}",
           "source_listing": next((x["url"] for x in cand.get("sourcing", {}).get("suppliers", []) if x.get("kind") == "source store"), None)}
    channels = ["Google Search (exact + phrase match on the observed local queries)"]
    if unmet:
        channels.append("Google Search 'where to buy' / 'price in' intent ad group")
    if cand.get("category") in ("Beauty", "Fashion", "Fashion Accessories", "Toys", "Lifestyle Products", "Kitchen Appliances & Accessories"):
        channels.append("Meta / TikTok creative (visual, trend-driven category)")
    channels.append("Google Merchant Center listing on the destination Ubuy storefront (Shopping / PMax)")
    return {"sku": sku, "competitor_terms": comp[:8], "keywords_exact": exact, "keywords_phrase": phrase, "negative_keywords": NEGATIVES[:12], "headlines": headlines,
            "descriptions": descriptions, "landing_page": landing, "channels": channels,
            "keyword_source": f"{len(kws)} real search suggestions observed in {cfg['name']}" if kws else "No local search phrases observed - keywords are generic"}
