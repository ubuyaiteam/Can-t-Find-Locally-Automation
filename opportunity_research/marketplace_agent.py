"""Agent 5: local supply check - is the product actually purchasable from local stores?

Per configured marketplace:
  1. direct search page (optionally rendered with Playwright for JavaScript sites)
  2. if blocked / JavaScript-only / unreadable -> search-index check `site:<domain> "<product>"` (one combined query per product)
Plus a universal local-web check: `"<product>" price <country>` -> local shops/sellers on the country's web (ccTLD or known shop).

Statuses per source: AVAILABLE / OUT OF STOCK / DELIVERY UNAVAILABLE / NO MATCHING LISTING FOUND / UNVERIFIED.
Blocked or unreadable sources are UNVERIFIED - never counted as absence."""
import re
from urllib.parse import quote_plus
from . import search
from .evidence import extract_listings, page_usable, best_match, availability_from_context, now_date, norm, domain_of, match_product, parse_price
from .historical_analysis import core_name

CCTLD_EXCEPT = {"GB": "uk"}

def queries_for(c):
    qs = [core_name(c), c["name"]]
    if c.get("brand") and c.get("model"): qs.append(f"{c['brand']} {c['model']}")
    qs += c.get("alt_names", [])[:1]
    return list(dict.fromkeys(q.strip() for q in qs if q.strip()))

def url_for(tpl, q):
    return tpl.replace("{q_hyphen}", norm(q).replace(" ", "-")).replace("{q_plus}", quote_plus(q)).replace("{q}", quote_plus(q))

def _row(mp):
    return {"marketplace": mp["name"], "domain": mp.get("domain", ""), "kind": mp.get("kind", "marketplace"), "status": "UNVERIFIED", "url": None, "price": None,
            "matched_title": None, "queries": [], "reason": "", "method": None, "checked_at": now_date()}

def check_direct(f, s, mp, cand, qs):
    r = _row(mp)
    if not mp.get("search_url"):
        r["reason"] = "No direct search URL; checked through search index"
        return r
    usable = 0; want = min(2, len(qs))
    for q in qs[:2]:
        url = url_for(mp["search_url"], q); r["url"] = url; r["queries"].append(q)
        res = f.get(url, render=bool(mp.get("render")) and s.get("use_playwright", False))
        if not res.ok:
            r["reason"] = f"Direct page {res.status}" + (f" (HTTP {res.http})" if res.http else "")
            return r
        ls = extract_listings(res.text, url)
        m, sc = best_match(cand, ls)
        if m:
            r.update(status=availability_from_context(m["context"]), url=m["url"], matched_title=m["title"], price=(m["price"] or {}).get("raw"), method="direct",
                     reason=f"Matching listing on site search (match {sc:.0f}%)" + ("" if m["price"] else "; price not visible"))
            return r
        if not page_usable(res.text, ls):
            r["reason"] = "Direct page is JavaScript-rendered/unreadable"
            return r
        usable += 1
    if usable >= want:
        r.update(status="NO MATCHING LISTING FOUND", method="direct", reason=f"{usable} site searches returned readable results with no matching listing")
    return r

def index_check(f, s, cfg, rows, mps, cand):
    """One combined site: query for every marketplace that the direct check could not verify."""
    todo = [(r, mp) for r, mp in zip(rows, mps) if r["status"] == "UNVERIFIED" and mp.get("domain")]
    if not todo:
        return
    core = core_name(cand)
    sites = " OR ".join(f"site:{mp['domain']}" for _, mp in todo[:6])
    items, prov = search.web(f, s, f'"{core}" ({sites})', cfg["code"], 20)
    if prov is None:
        for r, _ in todo:
            r["reason"] = (r["reason"] + "; " if r["reason"] else "") + "search index unreachable -> unverified"
        return
    for r, mp in todo[:6]:
        dom = mp["domain"].lower()
        hits = [it for it in items if domain_of(it["url"]).endswith(dom) and match_product(cand, it["title"] + " " + it.get("snippet", ""), 80)]
        r["method"] = f"search index ({prov})"
        r["queries"].append(f'"{core}" site:{dom}')
        if hits:
            h = hits[0]; txt = (h["title"] + " " + h.get("snippet", "")).lower()
            st = "OUT OF STOCK" if any(x in txt for x in ("out of stock", "sold out", "unavailable")) else "AVAILABLE"
            p = parse_price(h.get("snippet", "") + " " + h["title"])
            r.update(status=st, url=h["url"], matched_title=h["title"][:160], price=p["raw"] if p else None,
                     reason=f"Indexed listing found via {prov} (index can lag; verify the page)")
        else:
            r.update(status="NO MATCHING LISTING FOUND", reason=f"No indexed listing on {dom} ({prov}); {r['reason'] or 'direct page not readable'}".strip("; "),
                     url=r["url"] or f"https://{dom}")
            r["index_only"] = True

SHOP_URL = re.compile(r"/(p|product|products|proizvod|proizvodi|artikal|artikl|item|dp|shop|catalog|katalog|urun|produkt|produit|producto|produto|sku)[/\-_]|[-_/]\d{4,}|\.html?$", re.I)
NEWS_HOSTS = ("news", "vijesti", "klix", "blog", "forum", "wiki", "youtube", "facebook", "instagram", "tiktok", "reddit", "gov", "edu")
GENERIC_TLDS = {"US", "IO"}

def local_web(f, s, cfg, cand):
    """UNIVERSAL local-market check for ANY country: product pages of shops on the country's own web domain (site:.ba, site:.ng ...).
    Works for countries that have no marketplace in the directory. Only trusted when the search provider honoured site:/quotes."""
    cc = cfg["code"].upper()
    if cc in GENERIC_TLDS:
        return {"status": "SKIPPED", "sellers": [], "provider": None, "reason": f"{cc} shops mostly use .com - marketplace checks only"}
    tld = CCTLD_EXCEPT.get(cc, cc.lower())
    core = core_name(cand)
    items, prov = search.web(f, s, f'{core} site:.{tld}', cc, 25)
    if prov is None:
        return {"status": "UNVERIFIED", "sellers": [], "provider": None, "tld": tld, "query": f'"{core}" site:.{tld}'}
    sellers, mentions = [], 0
    for it in items:
        d = domain_of(it["url"])
        if not (d == tld or d.endswith("." + tld)):
            continue
        text = it["title"] + " " + it.get("snippet", "")
        if not match_product(cand, text, 80):
            continue
        mentions += 1
        p = parse_price(text)
        shop_like = bool(p) or bool(SHOP_URL.search(it["url"])) or any(w in text.lower() for w in ("add to cart", "u korpu", "dodaj u", "in stock", "na stanju", "buy now", "kupi", "cijena", "cena", "price"))
        if shop_like and not any(h in d for h in NEWS_HOSTS):
            sellers.append({"domain": d, "url": it["url"], "title": it["title"][:140], "price": p["raw"] if p else None})
    uniq = list({x["domain"]: x for x in sellers}.values())
    return {"status": "CHECKED", "sellers": uniq[:8], "provider": prov, "tld": tld, "mentions": mentions, "query": f'"{core}" site:.{tld}'}

STORE_WORDS_EXTRA = {"PK": ["hafeez centre", "hall road", "saddar"], "IN": ["croma", "reliance digital"], "NG": ["computer village", "slot"],
                     "KE": ["luthuli"], "AE": ["sharaf dg", "carrefour"], "SA": ["jarir", "extra"]}

def _store_words(cfg, allm):
    words = []
    for m in allm:
        d = (m.get("domain") or "").lower()
        if not d or "." not in d:
            continue
        w = d.split(".")[0].replace("www", "")
        if len(w) >= 3 and w not in words:
            words.append(w)
    return words + [w for w in STORE_WORDS_EXTRA.get(cfg["code"].upper(), []) if w not in words]

def search_supply(f, cfg, cand, allm):
    """Availability evidence from Google Autocomplete in the country (works even when every store blocks bots)."""
    from .historical_analysis import search_names, _mentions
    from .trend_discovery import foreign
    from . import geo
    cc = cfg["code"]
    stores = _store_words(cfg, allm)
    names = search_names(cand) or [core_name(cand).lower()]
    nm = min(names, key=len)                      # the short name shoppers type: "airpods pro", "ninja creami"
    probes = [f"{nm} {st}" for st in stores[:2]] + [f"{nm} price in {cfg['name'].lower()}", f"{nm} {cfg['name'].lower()}"]
    listed, unmet, n = {}, [], 0
    unmet_pat = geo.UNMET_PATTERNS["en"] + geo.UNMET_PATTERNS.get(geo.language(cc), [])
    ok = False
    for q in probes:
        sugs = search.google_suggest(f, q, cc)
        ok = ok or bool(sugs)
        for sg in sugs:
            low = sg.lower()
            if foreign(sg, cc) or not any(_mentions(sg, cand, x) for x in names) or any(f" {st} " in f" {low} " for st in geo.FOREIGN_STORES):
                continue
            n += 1
            for st in stores:
                if f" {st}" in f" {low}":
                    listed.setdefault(st, []).append(sg)
            if any(p in low for p in unmet_pat):
                unmet.append(sg)
    return {"checked": n > 0 or ok, "n_suggestions": n, "listed_on": listed, "unmet": unmet[:5], "stores": stores, "probes": probes}

# Specialist stores: absence there proves nothing for other categories (Myntra has no 3D printers).
SPECIALIST = {
    "myntra.com": {"Fashion", "Fashion Accessories", "Beauty", "Personal Care", "Sports", "Fitness"}, "ajio.com": {"Fashion", "Fashion Accessories"},
    "nykaa.com": {"Beauty", "Personal Care"}, "meesho.com": {"Fashion", "Fashion Accessories", "Beauty", "Lifestyle Products", "Kitchen Appliances & Accessories", "Toys"},
    "croma.com": {"Electronics", "Computers & Accessories", "Mobile Accessories", "Smart Home", "Kitchen Appliances & Accessories", "Personal Care"},
    "reliancedigital.in": {"Electronics", "Computers & Accessories", "Mobile Accessories", "Smart Home", "Kitchen Appliances & Accessories", "Personal Care"},
    "vijaysales.com": {"Electronics", "Computers & Accessories", "Mobile Accessories", "Smart Home", "Kitchen Appliances & Accessories", "Personal Care"},
    "jiomart.com": {"Electronics", "Kitchen Appliances & Accessories", "Beauty", "Personal Care", "Fashion", "Toys", "Lifestyle Products"},
    "xcite.com": {"Electronics", "Computers & Accessories", "Mobile Accessories", "Smart Home", "Kitchen Appliances & Accessories", "Personal Care"},
    "sharafdg.com": {"Electronics", "Computers & Accessories", "Mobile Accessories", "Smart Home", "Kitchen Appliances & Accessories", "Personal Care"},
    "jarir.com": {"Electronics", "Computers & Accessories", "Mobile Accessories", "Office Products", "Toys"},
    "extra.com": {"Electronics", "Computers & Accessories", "Mobile Accessories", "Smart Home", "Kitchen Appliances & Accessories", "Personal Care"},
    "priceoye.pk": {"Electronics", "Mobile Accessories", "Computers & Accessories"}, "startech.com.bd": {"Electronics", "Computers & Accessories", "Mobile Accessories"},
    "compughana.com": {"Electronics", "Computers & Accessories", "Mobile Accessories"}, "electroplanet.ma": {"Electronics", "Computers & Accessories", "Kitchen Appliances & Accessories"},
    "mytek.tn": {"Electronics", "Computers & Accessories", "Mobile Accessories"}, "ksp.co.il": {"Electronics", "Computers & Accessories", "Mobile Accessories"},
}
MAJOR = ("amazon.", "flipkart.com", "jumia.", "noon.com", "takealot.com", "daraz.", "mercadolibre.", "mercadolivre.", "lazada.", "shopee.", "tokopedia.com",
         "trendyol.com", "hepsiburada.com", "konga.com", "kilimall.", "allegro.pl", "bol.com", "ebay.", "walmart.com", "kaspi.kz", "uzum.uz", "coupang.com",
         "snapdeal.com", "trademe.co.nz", "otto.de", "cdiscount.com", "ekupi.", "emag.", "alza.", "ananas.rs", "mimovrste.com", "digitec.ch", "worten.pt",
         "rozetka.com.ua", "prom.ua", "komplett.no", "verkkokauppa.com", "mall.cz",
         # price-comparison sites list offers of many local shops: very strong availability evidence
         "heureka.", "arukereso.hu", "pricerunner.", "prisjakt.", "geizhals.", "kuantokusta.pt", "hintaopas.fi", "skroutz.", "zap.co.il")

def relevant(mp, cand):
    dom = (mp.get("domain") or "").lower()
    cats = mp.get("categories")
    if cats:
        return cand["category"] in cats
    for d, cs in SPECIALIST.items():
        if dom.endswith(d):
            return cand["category"] in cs
    return True

def is_major(mp):
    return any(m in (mp.get("domain") or "").lower() for m in MAJOR)

def verify(f, s, cfg, cand, ctx=None):
    """Order: major marketplaces first. Stops as soon as one in-stock local listing is found (= product IS available locally)."""
    allm = list(cfg.get("marketplaces", [])) + [m for m in cfg.get("category_marketplaces", []) if cand["category"] in m.get("categories", [])]
    mps = [m for m in allm if relevant(m, cand)]
    skipped = [m["name"] for m in allm if m not in mps]
    mps.sort(key=lambda m: (not is_major(m), m.get("kind") == "classifieds"))
    qs = queries_for(cand)
    rows = []
    for mp in mps:
        r = check_direct(f, s, mp, cand, qs); r["major"] = is_major(mp)
        rows.append(r)
        if r["status"] == "AVAILABLE" and r["kind"] != "classifieds":
            break                                      # available locally -> no need to keep checking
    found = any(r["status"] == "AVAILABLE" and r["kind"] != "classifieds" for r in rows)
    if not found and s.get("enable_index_fallback", True):
        index_check(f, s, cfg, rows, mps[:len(rows)], cand)
    found = any(r["status"] == "AVAILABLE" and r["kind"] != "classifieds" for r in rows)
    lw = local_web(f, s, cfg, cand) if (s.get("enable_local_web_check", True) and not found) else {"status": "SKIPPED", "sellers": []}
    formal = [r for r in rows if r["kind"] != "classifieds"]
    avail = sum(1 for r in formal if r["status"] == "AVAILABLE")
    oos = sum(1 for r in formal if r["status"] in ("OUT OF STOCK", "DELIVERY UNAVAILABLE"))
    avail_cls = sum(1 for r in rows if r["kind"] == "classifieds" and r["status"] == "AVAILABLE")
    absent_direct = [r for r in formal if r["status"] == "NO MATCHING LISTING FOUND" and r.get("method") == "direct"]
    absent_index = [r for r in formal if r["status"] == "NO MATCHING LISTING FOUND" and r.get("index_only")]
    major_absent_direct = [r for r in absent_direct if r.get("major")]
    verified = sum(1 for r in rows if r["status"] != "UNVERIFIED") + (1 if lw.get("status") == "CHECKED" else 0)
    n_sellers = len(lw.get("sellers", []))
    lw_ok = lw.get("status") == "CHECKED"
    need = max(1, min(int(s.get("min_verified_marketplaces", 2)), len(formal) or 1))
    confidence = "high"
    if avail:
        r0 = next(r for r in formal if r["status"] == "AVAILABLE")
        gap, why = "NO_GAP", f"In stock locally on {r0['marketplace']}" + (f" ({r0['price']})" if r0.get("price") else "") + f" [{r0.get('method') or 'direct'}]: {(r0.get('matched_title') or '')[:90]}"
    elif n_sellers >= 3:
        gap, why = "NO_GAP", f"Sold by {n_sellers} local web shops (.{lw.get('tld')}): " + ", ".join(x["domain"] for x in lw["sellers"][:4])
    elif oos or avail_cls or n_sellers:
        parts = []
        if oos: parts.append(f"listed but out of stock / not deliverable on {oos} marketplace(s)")
        if avail_cls: parts.append(f"only {avail_cls} classifieds listing(s) (second-hand / grey supply)")
        if n_sellers: parts.append(f"only {n_sellers} local web shop(s): " + ", ".join(x["domain"] for x in lw["sellers"][:3]))
        gap, why = "PARTIAL_GAP", "Low local supply: " + ", ".join(parts)
    elif major_absent_direct and (len(absent_direct) + len(absent_index)) >= need:
        gap = "FULL_GAP"
        why = (f"Not listed on {', '.join(r['marketplace'] for r in major_absent_direct)} (direct site search)"
               + (f" + {len(absent_direct) - len(major_absent_direct)} other store(s)" if len(absent_direct) > len(major_absent_direct) else "")
               + (f" + {len(absent_index)} via verified search index" if absent_index else "")
               + (f"; no local web shop found (.{lw.get('tld')})" if lw_ok else ""))
    elif absent_direct and lw_ok:
        gap, confidence = "FULL_GAP", "medium"
        why = f"Not listed on {', '.join(r['marketplace'] for r in absent_direct)} and no local web shop page found (.{lw.get('tld')}, via {lw.get('provider')})"
    elif lw_ok and not formal:
        gap, confidence = "FULL_GAP", "medium"
        why = (f"No local shop page found on the country's web (.{lw.get('tld')}, via {lw.get('provider')}); no marketplace directory for this country - "
               f"medium confidence, spot-check with the link")
    else:
        gap = "UNVERIFIED"
        why = (f"Could not verify the main local marketplace(s): {', '.join(r['marketplace'] + ' (' + (r['reason'] or 'unreadable') + ')' for r in formal if r['status'] == 'UNVERIFIED')[:250]}"
               if any(r["status"] == "UNVERIFIED" for r in formal) else "No marketplace directory and the local web search was not answerable (search engines blocked)")
    ss = None
    if gap == "UNVERIFIED" and s.get("enable_search_supply_signal", True):
        # Marketplaces block bots and free search engines don't answer -> use what LOCAL SHOPPERS search for:
        # "airpods pro daraz" / "... price in pakistan daraz" = sold locally; nothing but "where to buy / import / ubuy" = likely gap.
        ss = search_supply(f, cfg, cand, allm)
        if ss["listed_on"]:
            gap, confidence = "NO_GAP", "medium"
            why = "Local shoppers search it together with local stores: " + "; ".join(f"{k}: '{v[0]}'" for k, v in list(ss["listed_on"].items())[:3]) + " [search suggestions]"
        elif ss["checked"] and ss["n_suggestions"] >= 3:
            gap = "LIKELY_GAP"
            confidence = "medium" if ss["unmet"] else "low"
            why = (f"No local store appears in {ss['n_suggestions']} local search suggestions for this product"
                   + (f"; buyers ask how to get it: '{ss['unmet'][0]}'" if ss["unmet"] else "")
                   + (f" (store pages not readable - spot-check {', '.join(ss['stores'][:3])})" if ss["stores"] else
                      " (no local online store could be checked for this country - spot-check with the link)"))
    prices = [r for r in rows if r["status"] == "AVAILABLE" and r["price"]] + [x for x in lw.get("sellers", []) if x.get("price")]
    return {"results": rows, "local_web": lw, "checked": len(rows), "verified": verified, "available": avail, "available_classifieds": avail_cls,
            "absent": len(absent_direct) + len(absent_index), "local_sellers": n_sellers, "gap": gap, "reason": why, "not_relevant_stores": skipped,
            "gap_confidence": confidence, "search_supply": ss, "verify_link": f"https://www.google.com/search?q={quote_plus(core_name(cand))}+site%3A.{CCTLD_EXCEPT.get(cfg['code'].upper(), cfg['code'].lower())}",
            "reference_price": prices[0]["price"] if prices else None, "checked_at": now_date()}
