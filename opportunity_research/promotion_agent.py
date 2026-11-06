"""Agent 14: how to promote each opportunity - built from the evidence the run collected (no invented numbers):
the real local search phrases (+ their intent), the type of supply gap, year-over-year growth, category, Ubuy status,
and the country's shopping calendar."""
from datetime import date
from urllib.parse import quote_plus
from .historical_analysis import core_name
from .evidence import norm

VISUAL = {"Beauty", "Fashion", "Fashion Accessories", "Toys", "Lifestyle Products", "Kitchen Appliances & Accessories", "Personal Care", "Fitness",
          "Gifting", "Hobbies", "Outdoor Products"}
DEMO = {"Electronics", "Computers & Accessories", "Mobile Accessories", "Smart Home", "Tools", "Automotive", "Hobbies", "Kitchen Appliances & Accessories"}
MUSLIM_MAJORITY = {"AE", "SA", "KW", "QA", "BH", "OM", "JO", "IQ", "EG", "MA", "DZ", "TN", "LY", "SD", "PK", "BD", "ID", "MY", "TR", "NG", "SN", "ML", "NE",
                   "BN", "AZ", "UZ", "KZ", "KG", "TJ", "TM", "AF", "YE", "MV", "SO", "DJ", "MR", "GM", "GN", "SL"}
WHATSAPP_COMMERCE = {"IN", "PK", "BD", "NG", "KE", "GH", "ZA", "AE", "SA", "KW", "QA", "BH", "OM", "EG", "MA", "BR", "MX", "CO", "AR", "ID", "MY", "TR", "LK", "NP"}

# (month, day, label, countries or None=global, categories or None=all).  Moving festivals = approximate dates, confirm locally.
EVENTS = [
    (11, 11, "11.11 Singles' Day sales", {"MY", "SG", "ID", "TH", "VN", "PH", "PK", "BD", "LK", "NP", "CN"}, None),
    (11, 27, "Black Friday / White Friday", None, None), (11, 30, "Cyber Monday", None, {"Electronics", "Computers & Accessories", "Mobile Accessories", "Smart Home"}),
    (12, 12, "12.12 sales", {"MY", "SG", "ID", "TH", "VN", "PH", "PK", "BD"}, None), (12, 20, "Christmas / year-end gifting", None, None),
    (1, 1, "New Year sales", None, None), (2, 14, "Valentine's Day", None, {"Beauty", "Fashion Accessories", "Gifting", "Lifestyle Products", "Electronics"}),
    (2, 8, "Ramadan starts (approx. 2027)", MUSLIM_MAJORITY, None), (3, 10, "Eid al-Fitr (approx. 2027)", MUSLIM_MAJORITY, None),
    (5, 16, "Eid al-Adha (approx. 2027)", MUSLIM_MAJORITY, None), (3, 22, "Holi", {"IN", "NP"}, {"Beauty", "Gifting", "Toys"}),
    (7, 15, "Prime Day / mid-year sales", None, None), (8, 1, "Back to school", None, {"Computers & Accessories", "Office Products", "Electronics", "Fashion"}),
    (10, 29, "Diwali (approx. 2027)", {"IN", "NP", "LK", "MU", "FJ", "SG", "MY", "AE", "GB"}, None), (11, 8, "Diwali (2026)", {"IN", "NP", "LK", "MU", "FJ"}, None),
    (5, 10, "Mother's Day (May, most countries)", None, {"Beauty", "Gifting", "Lifestyle Products", "Personal Care", "Kitchen Appliances & Accessories"}),
    (6, 21, "Father's Day (June, most countries)", None, {"Electronics", "Tools", "Personal Care", "Fashion Accessories", "Gifting"}),
]

def upcoming(cc, category, days=100, today=None):
    today = today or date.today()
    out = []
    for m, d, label, ccs, cats in EVENTS:
        if ccs and cc not in ccs: continue
        if cats and category not in cats: continue
        for y in (today.year, today.year + 1):
            try: dt = date(y, m, d)
            except ValueError: continue
            delta = (dt - today).days
            if 0 <= delta <= days:
                out.append({"date": dt.isoformat(), "event": label, "in_days": delta}); break
    return sorted(out, key=lambda x: x["in_days"])[:4]

def _groups(phrases):
    g = {"price": [], "where_to_buy": [], "local": [], "product": []}
    for p in phrases:
        k = {"price": "price", "unmet": "where_to_buy", "local": "local"}.get(p.get("intent"), "product")
        g[k].append(p["phrase"].lower())
    return {k: list(dict.fromkeys(v))[:8] for k, v in g.items() if v}

def plan(cfg, cand):
    cc, country = cfg["code"].upper(), cfg["name"]
    core = cand["name"] if len(cand["name"].split()) <= 6 else core_name(cand).title()      # display name, proper case
    cat = cand.get("category", "")
    mk, ub, gr, d, sc = (cand.get(k) or {} for k in ("marketplace", "ubuy", "growth", "demand", "scores"))
    phrases = [p for p in ((cand.get("history") or {}).get("search_phrases") or []) if not str(p.get("intent", "")).startswith("generic")]
    yoy = gr.get("yoy_pct")
    gap = mk.get("gap")

    # ---- why it will sell (the angle) - every claim comes from the run's evidence
    angles = []
    if gap == "FULL_GAP": angles.append(("Not sold by local stores", f"{mk.get('reason', '')}"))
    if gap == "PARTIAL_GAP": angles.append(("Hard to get locally (out of stock / grey market)", mk.get("reason", "")))
    if gap == "LIKELY_GAP": angles.append(("People ask where to buy it", mk.get("reason", "")))
    if d.get("unmet_signals"): angles.append(("Shoppers are actively looking for a seller", f"{d['unmet_signals']} 'where to buy / import' searches"))
    if yoy is not None and yoy >= 50: angles.append(("Trending", gr.get("headline", "")))
    message = ("Finally available in " + country + " – original " + core + ", delivered to your door" if gap in ("FULL_GAP", "LIKELY_GAP") else
               "Original " + core + " in stock – no grey-market risk" if gap == "PARTIAL_GAP" else "Original " + core + " delivered to " + country)
    if yoy is not None and yoy >= 200:
        message += " – the trending pick"

    # ---- priority
    total = sc.get("total") or 0
    prio = "High" if total >= 75 and (yoy or 0) >= 0 else "Medium" if total >= 60 else "Test"
    if yoy is not None and yoy < -30: prio = "Test" if prio != "Test" else prio

    groups = _groups(phrases)
    landing = ub.get("url") or ub.get("search_url")
    steps = []
    # 1 Google Search
    adg = []
    if groups.get("where_to_buy"): adg.append(f"'Where to buy' ad group (strongest intent): " + ", ".join(f"[{p}]" for p in groups["where_to_buy"][:4]))
    if groups.get("price"): adg.append("'Price' ad group: " + ", ".join(f"[{p}]" for p in groups["price"][:4]))
    if groups.get("local"): adg.append("'City / country' ad group: " + ", ".join(f"[{p}]" for p in groups["local"][:4]))
    if groups.get("product"): adg.append("Product-name ad group (phrase match): " + ", ".join(f'"{p}"' for p in groups["product"][:4]))
    steps.append({"channel": "Google Search Ads", "why": f"{len(phrases)} real searches for this product were observed in {country}",
                  "do": adg or [f'Phrase match "{core.lower()}", "{core.lower()} price", "buy {core.lower()}"'],
                  "tip": f"Ad copy angle: {message}. Land on {'the Ubuy product page' if ub.get('url') else 'the Ubuy search page'}; add negatives: used, repair, fake, replica, manual."})
    # 2 Shopping / PMax via GMC
    steps.append({"channel": "Google Shopping / Performance Max (Merchant Center feed)",
                  "why": "Buyers searching a specific product compare price and seller on Shopping",
                  "do": [f"Feed title: '{core}" + (f" {cand['model'].upper()}" if cand.get("model") and norm(cand["model"]) not in norm(core) else "") + f" | Original, ships to {country}'",
                         f"custom_label_0 = opportunity_{cc.lower()}, custom_label_1 = {(gap or 'gap').lower()}, custom_label_2 = {'trending' if (yoy or 0) >= 100 else 'steady'}",
                         "product_highlight: authenticity, delivery time to " + country + ", duties shown at checkout",
                         "Own campaign / asset group for these labels so the opportunity budget is not mixed with the catalogue"],
                  "tip": "Use the observed search phrases as PMax search themes."})
    # 3 SEO
    seo = [f"Optimise the Ubuy page for '{(groups.get('price') or [core.lower() + ' price in ' + country.lower()])[0]}' (title, H1, price + delivery time to {country})"]
    if groups.get("where_to_buy"): seo.append(f"FAQ block answering '{groups['where_to_buy'][0]}' (availability, delivery days, duties, warranty) + FAQ schema")
    if any(" vs " in p["phrase"].lower() for p in phrases): seo.append("Comparison article for the 'vs' searches people make (" + next(p["phrase"] for p in phrases if " vs " in p["phrase"].lower()) + ")")
    seo.append(f"Internal links from the {cat} category and brand page on the {country} store")
    steps.append({"channel": "SEO (organic)", "why": "The same searches will keep coming; organic captures them without ad cost", "do": seo, "tip": ""})
    # 4 Social / creators
    if cat in VISUAL or (yoy or 0) >= 100:
        steps.append({"channel": "Instagram / TikTok / Facebook", "why": "Visual, trend-driven category" + (f" and {gr.get('headline')}" if yoy and yoy >= 100 else ""),
                      "do": [f"Short videos (unboxing / before-after / 'finally in {country}')", f"2–3 micro-creators in {country} with a Ubuy discount code to track sales",
                             "Retarget Ubuy product-page visitors with a carousel ad"], "tip": ""})
    if cat in DEMO:
        steps.append({"channel": "YouTube (Shorts + in-stream)", "why": "Buyers watch demos/reviews before buying this type of product",
                      "do": [f"Target the review/unboxing videos for '{core.lower()}'", f"15–30 s demo ending with 'available in {country} on Ubuy'"], "tip": ""})
    if any(sg.get("kind") == "reddit" for sg in cand.get("signals", [])):
        steps.append({"channel": "Community answers", "why": "People asked where to buy it in the country's community forum",
                      "do": ["Answer those threads helpfully with a disclosed Ubuy link (see References)"], "tip": "Disclose that you represent Ubuy."})
    if cc in WHATSAPP_COMMERCE:
        steps.append({"channel": "WhatsApp / email / push", "why": "Messaging is a main shopping channel in " + country,
                      "do": [f"'Now available in {country}' broadcast to {cat} buyers", "Back-in-stock / price-drop alerts for this SKU"], "tip": ""})

    ev = upcoming(cc, cat)
    timing = ("Launch now - search interest is rising year over year" if (yoy or 0) >= 50 else "Launch now with a test budget")
    if ev:
        timing += "; then push for " + ", ".join(f"{e['event']} ({e['date']}, in {e['in_days']} days)" for e in ev[:3])
    price_note = None
    if ub.get("price") and mk.get("reference_price"):
        price_note = f"Ubuy price {ub['price']} vs local listing {mk['reference_price']} - lead with price if Ubuy is lower, with authenticity/warranty if not"
    return {"priority": prio, "message": message, "angles": angles, "channels": steps, "timing": timing, "events": ev, "price_note": price_note,
            "landing_page": landing,
            "test_plan": ["Week 1-2: Search exact/phrase on the observed phrases + Shopping/PMax with the custom labels",
                          "Keep what converts (track by custom_label_0 and the creator codes); pause phrases with clicks but no sales",
                          "Week 3+: scale winners; add social/video for products with rising YoY growth"],
            "kpis": ["Conversion rate of the observed-phrase ad groups", "ROAS by custom_label_0", "Organic clicks for the price / where-to-buy queries"]}
