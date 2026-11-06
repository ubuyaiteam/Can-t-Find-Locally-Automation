import json, os
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULTS = {
    "db_path": "data/opportunity.db",
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 UbuyOpportunityResearch/2.0",
    "request_timeout": 15,
    "min_delay_per_domain": 1.5,      # seconds between requests to the same host
    "max_requests_per_run": 9000,     # hard budget of NETWORK requests per run (cache hits are free)
    "cache_ttl_hours": 24,
    "workers": 12,                    # parallel agents (each website still has its own adaptive pace)
    "render_workers": 3,              # parallel headless-browser tabs (Ubuy product cards, JS marketplaces)
    "adaptive_throttle": True,        # speed up while a site answers normally, back off on 429
    "retries": 2,
    "respect_robots": True,
    # Feed/search endpoints that are meant to be consumed programmatically (RSS) or are the
    # already-existing search implementation of this project. Everything else obeys robots.txt.
    # Feed / API-style endpoints (RSS, autocomplete JSON) and the search pages used for site: checks. Remove a host to make it obey robots.txt.
    "robots_exempt_hosts": ["www.bing.com", "html.duckduckgo.com", "lite.duckduckgo.com", "trends.google.com", "suggestqueries.google.com",
                            "news.google.com", "www.mojeek.com", "www.reddit.com"],
    "host_delays": {"suggestqueries.google.com": 0.4, "news.google.com": 0.8, "www.reddit.com": 2.5, "html.duckduckgo.com": 2.0, "www.bing.com": 1.5,
                    "www.amazon.in": 1.0, "www.amazon.com": 1.0, "www.amazon.co.uk": 1.0},
    # fastest pace allowed per site (adaptive pacing never goes below this)
    "host_min_delays": {"suggestqueries.google.com": 0.15, "news.google.com": 0.4, "www.amazon.in": 0.6, "www.amazon.com": 0.6, "www.amazon.co.uk": 0.6,
                        "html.duckduckgo.com": 1.5, "www.reddit.com": 2.0, "trends.google.com": 1.0},
    "default_min_delay": 0.7,
    "use_playwright": True,            # render JavaScript pages (Ubuy search cards, JS marketplaces); falls back to plain HTTP if not installed          # optional: render JavaScript marketplaces (pip install playwright)
    "candidate_pool_max": 450,
    "demand_shortlist": 320,
    "marketplace_check_limit": 240,   # cheap: the check stops at the first in-stock local listing
    "deep_check_limit": 60,
    "min_demand_score": 20,
    "min_verified_marketplaces": 2,   # capped by the number of marketplaces configured for the country
    "strict_qualification": False,    # True = also require a supplier price or reference selling price
    "autocomplete_types_per_category": 5,
    "max_autocomplete_probes": 260,
    "enable_reddit": True,
    "include_global_trends": True,    # US/UK trends as the "may become trending" universe
    "global_trend_geos": ["US", "GB"],
    "enable_index_fallback": True,    # site: search when a marketplace blocks bots / needs JavaScript
    "enable_local_web_check": True,
    "enable_official_search": True,
    "region_max_countries": 6,
    # ---- deep research (v2.5): keep exploring new source pages until the target is met
    "target_opportunities": 20,
    "max_research_rounds": 6,         # round 1 = normal run; each extra round explores new Amazon US/UK best-seller/new-release/wished-for pages
    "max_research_minutes": 150,
    "universe_pages_per_round": 24,
    "remember_sold_locally_days": 14, # products confirmed as sold locally are skipped in later runs (variety + speed)
    "cache_keep_days": 7,
    "international_shortlist": 70,    # funnel slots reserved for products trending abroad (Amazon US / US-UK trends)
    "enable_search_supply_signal": True,  # use local search suggestions ("<product> daraz") as availability evidence when stores block bots
    "max_product_line_probes": 220,   # known global product lines tested against local searches
    "include_amazon_us_universe": True,   # Amazon US best sellers / movers & shakers as the 'sold abroad' universe
    "ubuy_catalog_files": {},         # {"IN": "data/ubuy_catalog/IN.tsv"}; or just drop <CC>.csv/.tsv/.xml into data/ubuy_catalog/
    "ubuy_check_search_page": True,   # open the Ubuy search page in a headless browser and read the product cards (needs Playwright)
    "ubuy_ignore_robots": True,
    "watchlist_deep_checks": 60,      # also run Ubuy / import / sourcing checks for the top watchlist items       # Ubuy is your own storefront: its robots.txt (/search disallowed) is not applied to ubuy.* hosts        # region runs: number of priority countries researched
    "serper_api_key": None, "serpapi_key": None, "brave_api_key": None,   # OPTIONAL paid search APIs (more reliable site: checks)
    "enable_pytrends": False,         # optional unofficial Google Trends series (pip install pytrends); often rate-limited          # optional unofficial free Google Trends access; fails gracefully
    "pytrends_max_queries": 25,
    "existing_search_fn": None,       # e.g. "engine:web_search" -> fn(query, n) -> [{title,url,snippet}]
    "max_results_cap": 100,
}

def load(overrides=None):
    s = dict(DEFAULTS)
    p = os.path.join(BASE, "opportunity_settings.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as fh:
            s.update(json.load(fh))
    if overrides:
        s.update(overrides)
    if not os.path.isabs(s["db_path"]):
        s["db_path"] = os.path.join(BASE, s["db_path"])
    return s
