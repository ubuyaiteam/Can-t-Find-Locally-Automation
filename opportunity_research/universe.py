"""Research universe: the pool of 'what sells abroad' source pages that deep research works through, round by round.

Sources (public pages, fetched politely, robots.txt respected):
  * Amazon US  - Best Sellers, Movers & Shakers, New Releases, Most Wished For, Most Gifted  x ~25 categories (+ page 2)
  * Amazon UK  - Best Sellers, Movers & Shakers, New Releases x ~12 categories
The pool is SHUFFLED with the run id, so every run explores a different slice first (different answers each run);
each additional round takes the next unexplored slice."""
import random
from .evidence import extract_listings
from .product_identification import extract_listing_title

US_SLUGS = {"electronics": "Electronics", "kitchen": "Kitchen Appliances & Accessories", "beauty": "Beauty", "hpc": "Personal Care",
            "toys-and-games": "Toys", "sporting-goods": "Sports", "pet-supplies": "Pet Products", "office-products": "Office Products",
            "automotive": "Automotive", "hi": "Tools", "lawn-garden": "Gardening", "baby-products": "Specialized Consumer Products",
            "fashion": "Fashion", "home-garden": "Lifestyle Products", "videogames": "Electronics", "pc": "Computers & Accessories",
            "wireless": "Mobile Accessories", "arts-crafts": "Hobbies", "musical-instruments": "Hobbies", "appliances": "Kitchen Appliances & Accessories",
            "photo": "Electronics", "industrial": "Tools", "luxury-beauty": "Beauty", "outdoor-recreation": "Outdoor Products", "smart-home": "Smart Home"}
US_LISTS = ["movers-and-shakers", "bestsellers", "new-releases", "most-wished-for", "most-gifted"]
UK_SLUGS = {"electronics": "Electronics", "kitchen": "Kitchen Appliances & Accessories", "beauty": "Beauty", "drugstore": "Personal Care",
            "toys": "Toys", "sports": "Sports", "pet-supplies": "Pet Products", "diy": "Tools", "computers": "Computers & Accessories",
            "videogames": "Electronics", "baby": "Specialized Consumer Products", "fashion": "Fashion"}
UK_LISTS = ["movers-and-shakers", "bestsellers", "new-releases"]

def pool(category=None):
    pages = []
    for slug, cat in US_SLUGS.items():
        if category and category != "ALL" and cat != category:
            continue
        for lst in US_LISTS:
            pages.append({"url": f"https://www.amazon.com/gp/{lst}/{slug}", "cat": cat, "src": f"Amazon US {lst}", "store": "amazon.com"})
            if lst in ("bestsellers", "movers-and-shakers"):
                pages.append({"url": f"https://www.amazon.com/gp/{lst}/{slug}?pg=2", "cat": cat, "src": f"Amazon US {lst} p2", "store": "amazon.com"})
    for slug, cat in UK_SLUGS.items():
        if category and category != "ALL" and cat != category:
            continue
        for lst in UK_LISTS:
            pages.append({"url": f"https://www.amazon.co.uk/gp/{lst}/{slug}", "cat": cat, "src": f"Amazon UK {lst}", "store": "amazon.co.uk"})
    return pages

def slice_for(run_id, round_no, size, category=None):
    """Deterministic per run, different between runs: shuffle with the run id, take the round's slice."""
    p = pool(category)
    random.Random(int(run_id) * 7919).shuffle(p)
    a = (round_no - 1) * size
    return p[a:a + size], len(p)

def harvest(f, pages, ctx=None, date=None):
    """Fetch the pages, return raw product mentions (scope=international)."""
    from concurrent.futures import ThreadPoolExecutor
    raw, ok = [], 0
    def get(pg):
        if ctx: ctx.check()
        return pg, f.get(pg["url"])
    with ThreadPoolExecutor(4) as ex:                  # amazon.com and amazon.co.uk pages fetched in parallel (each site keeps its own pace)
        fetched = list(ex.map(get, pages))
    for pg, r in fetched:
        if not r.ok:
            continue
        ok += 1
        seen = set()
        for l in extract_listings(r.text, pg["url"]):
            if "/dp/" not in l["url"] or len(l["title"]) < 15:
                continue
            title = " ".join(l["title"].split()[:16])
            if title in seen:
                continue
            seen.add(title)
            for p in extract_listing_title(title, pg["cat"]):
                p["signal"] = {"source": pg["store"], "kind": "amazon_list", "intent": "global", "url": l["url"].split("/ref=")[0], "title": title[:160],
                               "date": date, "scope": "international", "query": pg["src"]}
                raw.append(p)
    return raw, ok
