"""Offline tests with MOCKED website responses (no network). Run:  python -m unittest discover -s tests -v"""
import io, json, os, re, sys, tempfile, unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from urllib.parse import urlparse, parse_qs, unquote_plus
from xml.sax.saxutils import escape
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from opportunity_research import orchestrator, product_identification as pid, report_agent, search, healthcheck, geo
from opportunity_research.net import Fetcher, RunContext
from opportunity_research.country_registry import load_config, coverage, region_coverage
from opportunity_research.database import DB
from opportunity_research import settings as S

# products that people in the mocked countries search for
PRODUCTS = {
    "ninja creami": {"local": True},           # wanted, not sold locally, not on Ubuy  -> opportunity
    "zento pro 2 yoga mat": {"local": True},  # wanted, not sold locally              -> opportunity
    "boatix rockerz 450 headphones": {"local": True, "sold": True},       # sold on 2 local marketplaces -> rejected
    "lumio glow 3 air purifier": {"local": True, "ubuy": True},           # already on Ubuy -> rejected
    "nexa glide 9 massage gun": {"local": True, "blocked": True},         # every supply source blocked -> watchlist
    "vapor king x5 vape pen": {"local": True},                            # India: prohibited
}
GLOBAL = "Glowbit Halo 2 smart ring"                                     # trending in the US only -> emerging
STATE = {"hook": None, "n": 0, "universe": False}
NOW = datetime.now(timezone.utc)

def rss(items):
    body = "".join(f"<item><title>{escape(t)}</title><link>{escape(u)}</link><description></description><pubDate>{format_datetime(dt)}</pubDate></item>" for t, u, dt in items)
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>{body}</channel></rss>'

def cards(extra=None, prefix="/dp/"):
    items = ([extra] if extra else []) + [(f"Generic Steel Bottle {i} Insulated 1 Litre", f"{prefix}{i}", "₦4,990") for i in range(4)]
    return "<html><body>" + "".join(f'<div class="c"><a href="{u}">{t}</a><span>{p}</span></div>' for t, u, p in items) + "</body></html>"

def bing(results):
    lis = "".join(f'<li class="b_algo"><h2><a href="{escape(u)}">{escape(t)}</a></h2><div class="b_caption"><p>{escape(sn)}</p></div></li>' for t, u, sn in results)
    return f'<html><body><ol id="b_results">{lis}</ol></body></html>'

def ddg(results):
    rs = "".join(f'<div class="result"><a class="result__a" href="{escape(u)}">{escape(t)}</a><a class="result__snippet">{escape(sn)}</a></div>' for t, u, sn in results)
    return f'<html><body><div class="results">{rs or "<div class=no-results>No results.</div>"}</div></body></html>'

def which(text):
    t = text.lower()
    for p in PRODUCTS:
        core = p.split()[:2]
        if all(w in t for w in core):
            return p
    return None

def route(url):
    STATE["n"] += 1
    if STATE["hook"]: STATE["hook"](STATE["n"])
    u = urlparse(url); qs = parse_qs(u.query); q = unquote_plus((qs.get("q") or qs.get("k") or qs.get("search") or qs.get("query") or [""])[0])
    host = u.netloc
    if "amazon.com" in host and "/gp/" in u.path and STATE.get("universe"):
        seed = abs(hash(url)) % 100000
        items = [(f"Zorvex{seed}x{i} Glow Lamp, Sunset Projection", f"/Zorvex-Glow/dp/B{seed}{i:03d}", "$24.99") for i in range(2)]
        return 200, "<html><body>" + "".join(f'<div class="c"><a href="{u}">{t}</a><span>{p}</span></div>' for t, u, p in items) + "</body></html>"
    if "suggestqueries" in host and "zorvex" in q.lower():
        b = re.search(r"zorvex\w+", q.lower()).group(0)
        return 200, json.dumps([q, [f"{b} glow lamp price in nigeria", f"where to buy {b} glow lamp in lagos"]])
    if "suggestqueries" in host:
        gl = qs.get("gl", [""])[0]
        p = which(q)
        if p:
            if "vapor" in p and gl != "in":
                return 200, json.dumps([q, []])
            return 200, json.dumps([q, [f"{p} price in nigeria", f"where to buy {p} in lagos", f"{p} lagos"]])
        if "price in" in q or "where to buy" in q:
            return 200, json.dumps([q, [f"{p} price in nigeria" for p in list(PRODUCTS)[:5]] + ["vapor king x5 vape pen price in india"]])
        return 200, json.dumps([q, []])
    if "news.google.com" in host:
        p = which(q)
        if p and '"' in q:
            return 200, rss([(f"{p.title()} is the gadget everyone in Lagos wants", f"https://news{i % 4}.example.ng/{i}-{p.replace(' ', '-')}", NOW - timedelta(days=d))
                             for i, d in enumerate([1, 2, 3, 5, 8, 12, 20, 26])])
        if "viral product" in q:
            return 200, rss([(f"{GLOBAL} sells out across the US", "https://us.example.com/ring", NOW - timedelta(days=2))])
        return 200, rss([])
    if "trends.google.com" in host:
        if "geo=US" in url:
            return 200, '<?xml version="1.0"?><rss xmlns:ht="https://trends.google.com/trending/rss"><channel><item><title>glowbit halo 2 smart ring</title>' \
                        f'<pubDate>{format_datetime(NOW)}</pubDate><ht:approx_traffic>50K+</ht:approx_traffic></item></channel></rss>'
        return 200, '<?xml version="1.0"?><rss><channel></channel></rss>'
    if "reddit.com" in host:
        return 200, json.dumps({"data": {"children": [{"data": {"title": "Where can I buy a Ninja Creami in Lagos?", "permalink": "/r/Nigeria/comments/x/creami/",
                                                                "selftext": "", "created_utc": NOW.timestamp() - 86400}}]}})
    if "bing.com" in host and "/news/" in u.path:
        return 200, rss([])
    if "duckduckgo" in host:
        code, body = route(url.replace("https://html.duckduckgo.com/html/", "https://www.bing.com/search"))
        if code != 200:
            return code, body
        import re as _re
        res = _re.findall(r'<li class="b_algo"><h2><a href="([^"]+)">([^<]*)</a></h2><div class="b_caption"><p>([^<]*)</p>', body)
        from html import unescape
        return 200, ddg([(unescape(t), unescape(u), unescape(sn)) for u, t, sn in res])
    if "bing.com" in host or "mojeek" in host:
        p = which(q); lq = q.lower()
        if p and PRODUCTS[p].get("blocked"):
            return 403, "Access Denied"
        if "glowbit" in lq and "site:amazon.com" not in lq:
            return (200, bing([])) if "bing" in host else (403, "")
        if "site:amazon.com" in lq:
            name = p or ("glowbit halo 2 smart ring" if "glowbit" in lq else "")
            return 200, bing([(f"{name.title()} - Amazon.com", f"https://www.amazon.com/dp/B0{abs(hash(name)) % 99999}", "$129.99 Free delivery")] if name else [])
        if p and PRODUCTS[p].get("sold") and "site:" in lq:
            return 200, bing([(f"{p.title()} | Jumia Nigeria", "https://www.jumia.com.ng/boatix-rockerz-450.html", "₦25,000 Add to cart")])
        if p and PRODUCTS[p].get("ubuy") and "ubuy" in lq:
            return 200, bing([(f"{p.title()}", "https://www.ubuy.com.ng/en/product/123-lumio-glow-3-air-purifier", "₦99,000")])
        if "import" in lq:
            return 200, bing([("Import policy notification", "https://www.cbic.gov.in/resources/notification-1", "")])
        return 200, bing([])
    full = unquote_plus(url).lower()
    p = which(full.replace("-", " ").replace("+", " "))
    if "ubuy" in host:
        if p and PRODUCTS[p].get("ubuy"):
            return 200, cards(("Lumio Glow 3 Air Purifier HEPA", "/product/123-lumio-glow-3-air-purifier", "₦99,000"), "/product/x")
        return 200, cards(None, "/product/")
    if p and PRODUCTS[p].get("blocked"):
        return 403, "Access Denied"
    if "amazon.com" in host and "/s" in u.path and p:
        return 200, cards((p.title() + " - Original", f"/dp/B0{abs(hash(p)) % 99999}", "$129.99"))
    if "jumia" in host:
        return 200, "<html><title>Just a moment...</title><body>Verify you are human</body></html>"     # Cloudflare-style page
    if p and PRODUCTS[p].get("sold") and ("konga" in host or "slot.ng" in host or "amazon.in" in host or "flipkart" in host):
        return 200, cards(("Boatix Rockerz 450 Bluetooth Wireless Headphones", "/dp/B0X", "₦25,000"))
    return 200, cards()

class FakeFetcher(Fetcher):
    def _raw_get(self, url, render=False, wait_for=None): return route(url)
    def _robots_txt(self, host, scheme): return 404, ""

def mk(tmp, **kw):
    s = S.load({"db_path": os.path.join(tmp, "t.db"), "min_delay_per_domain": 0, "respect_robots": False, "enable_pytrends": False, "retries": 0, "workers": 4,
                "autocomplete_types_per_category": 1, "max_autocomplete_probes": 40, "enable_google_trends_yoy": False, **kw})
    return orchestrator.Orchestrator(DB(s["db_path"]), s, FakeFetcher), s

class T(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(); STATE.update(hook=None, n=0, universe=False)

    def full_run(self, cc="NG", name="Nigeria", **kw):
        o, s = mk(self.tmp, **kw); rid = o.db.create_run(cc, name, 30, "ALL", 100); o.run(rid, RunContext(o.db, rid)); return o, rid

    def buckets(self, o, rid):
        return {k: {r["name"].lower(): r for r in o.db.get_results(rid, k)} for k in report_agent.BUCKETS}

    def find(self, b, bucket, word):
        return next((v for k, v in b[bucket].items() if word in k), None)

    def test_01_extraction_lowercase_and_lines(self):
        e = pid.extract_from_text
        self.assertEqual(e("ninja creami price in nigeria", True)[0]["name"], "Ninja Creami")
        self.assertEqual(e("iphone 16 pro max price in nigeria", True)[0]["name"], "Apple iPhone 16 Pro Max")
        r = e("where to buy oraimo freepods 4 earbuds in lagos", True)
        self.assertEqual(len(r), 1); self.assertEqual(r[0]["brand"], "Oraimo")
        self.assertEqual(e("Zento Pro 2 Yoga Mat goes viral", False)[0]["model"], "Pro 2")
        self.assertFalse(e("Best air fryer 2026", False)[0]["specific"])

    def test_02_duplicates_and_vague(self):
        raw = []
        for t, intent in [("Zento Pro 2 Yoga Mat goes viral", "news"), ("ZENTO Pro 2 yoga mat review", "news"), ("best air fryer 2026", "news"),
                          ("where to buy pickleball paddle in nigeria", "unmet")]:
            for p in pid.extract_from_text(t): p["signal"] = {"source": "x", "title": t, "intent": intent, "scope": "local", "kind": "news"}; raw.append(p)
        cands, dropped = pid.identify(raw)
        names = [c["name"].lower() for c in cands]
        self.assertEqual(sum("zento" in n for n in names), 1)
        self.assertFalse(any("pickleball" in n for n in names), "brand-less product types are never SKUs")
        self.assertTrue(any("air fryer" in d["name"].lower() for d in dropped))
        raw = []
        for t in ("apple iphone 16 pro price", "apple iphone 17 pro price", "phone 2 pro price"):
            for p in pid.extract_from_text(t, True): p["signal"] = {"source": "x", "title": t, "intent": "price", "scope": "local", "kind": "autocomplete"}; raw.append(p)
        names = [c["name"] for c in pid.identify(raw)[0]]
        self.assertIn("Apple iPhone 16 Pro", names); self.assertIn("Apple iPhone 17 Pro", names)       # different models never merged (run #11 bug)
        self.assertFalse(any(n.startswith("Phone") for n in names))

    def test_03_config_bugfix_and_directory(self):
        cfg = load_config("NG")
        self.assertEqual(cfg["trends_geo"], "NG", "Google Trends geo must be set for every country (v1 bug)")
        self.assertTrue(any("Jumia" in m["name"] for m in cfg["marketplaces"]))
        self.assertEqual(cfg["ubuy_domain"], "www.ubuy.com.ng")
        self.assertEqual(load_config("ZW")["trends_geo"], "ZW")
        self.assertIn(coverage("NG")["level"], ("Good", "Full"))
        self.assertGreater(len(region_coverage("R-AFRICA")["countries"]), 50)
        self.assertEqual(geo.news_edition("NG")[2], "NG:en"); self.assertEqual(geo.language("CI"), "fr")

    def test_04_bing_html_parser_and_garbage_detection(self):
        o, s = mk(self.tmp); f = FakeFetcher(o.db, s)
        items, prov = search.web(f, s, '"ninja creami" (site:amazon.com OR site:walmart.com)', "US")
        self.assertIn(prov, ("duckduckgo", "bing_html")); self.assertTrue(items and "amazon.com" in items[0]["url"])

    def test_05_nigeria_pipeline(self):
        o, rid = self.full_run()
        self.assertEqual(o.db.get_run(rid)["status"], "completed")
        b = self.buckets(o, rid)
        creami = self.find(b, "qualified", "creami")
        self.assertIsNotNone(creami, f"Ninja Creami must be an opportunity; buckets: { {k: list(v) for k, v in b.items() if k != 'rejected'} }")
        self.assertEqual(creami["marketplace"]["gap"], "FULL_GAP")
        jumia = next(r for r in creami["marketplace"]["results"] if "Jumia" in r["marketplace"])
        self.assertEqual(jumia["status"], "UNVERIFIED", "blocked Jumia + empty free-search answer is never counted as 'not listed'")
        self.assertGreater(creami["demand"]["local_search_matches"], 0)
        self.assertTrue(creami["sourcing"]["route_found"])
        self.assertTrue(any("lagos" in k for k in creami["campaign"]["keywords_exact"]), "campaign keywords must come from observed local searches")
        self.assertIsNotNone(self.find(b, "qualified", "zento"))
        boat = self.find(b, "rejected", "boatix"); self.assertIn("sold locally", " ".join(boat["reasons"]))
        lum = self.find(b, "qualified", "lumio"); self.assertEqual(lum["ubuy"]["gap"], "AVAILABLE")
        self.assertIn("Ready to sell", lum["action"], "already in the Ubuy catalogue = ready to campaign, not rejected")
        nexa = self.find(b, "qualified", "nexa") or self.find(b, "watchlist", "nexa")
        self.assertIsNotNone(nexa)
        self.assertNotEqual(nexa["marketplace"]["gap"], "FULL_GAP", "fully blocked sources are never a verified FULL gap")
        if nexa["marketplace"]["gap"] == "LIKELY_GAP":
            self.assertIn(nexa["marketplace"]["gap_confidence"], ("low", "medium"))
        vape = self.find(b, "qualified", "vape")
        self.assertIsNone(vape)

    def test_06_emerging_global_trend(self):
        o, rid = self.full_run()
        b = self.buckets(o, rid)
        ring = self.find(b, "emerging", "glowbit")
        self.assertIsNotNone(ring, f"US-trending product with a local gap must be 'emerging'; emerging={list(b['emerging'])}")
        self.assertTrue(ring["demand"]["only_international"])

    def test_07_india_prohibited(self):
        o, rid = self.full_run("IN", "India")
        b = self.buckets(o, rid)
        vape = self.find(b, "rejected", "vape")
        self.assertIsNotNone(vape); self.assertIn("prohibited", " ".join(vape["reasons"]).lower())

    def test_08_region_run(self):
        o, s = mk(self.tmp)
        rid = o.db.create_run("R-WEST_AFRICA", "West Africa (2 countries)", 30, "ALL", 100)
        o.db.update_run(rid, state_json=json.dumps({"region": True, "countries": ["NG", "GH"], "children": {}}))
        o.contexts[rid] = RunContext(o.db, rid)
        o.run_region(rid)
        run = o.db.get_run(rid); self.assertEqual(run["status"], "completed")
        self.assertEqual(len(o.db.children(rid)), 2)
        q = o.db.get_results(rid, "qualified")
        creami = next(r for r in q if "creami" in r["name"].lower())
        self.assertGreaterEqual(creami["region_countries_qualified"], 1)
        self.assertEqual({b["code"] for b in creami["region_breakdown"]}, {"NG", "GH"})

    def test_09_interrupt_and_resume(self):
        o, s = mk(self.tmp); rid = o.db.create_run("NG", "Nigeria", 30, "ALL", 100); ctx = RunContext(o.db, rid)
        def hook(n):
            if n == 120: ctx.cancel.set()
        STATE["hook"] = hook
        o.run(rid, ctx); self.assertEqual(o.db.get_run(rid)["status"], "cancelled")
        STATE["hook"] = None
        o.run(rid, RunContext(o.db, rid)); self.assertEqual(o.db.get_run(rid)["status"], "completed")
        self.assertTrue(o.db.get_results(rid, "qualified"))

    def test_10_exports(self):
        o, rid = self.full_run()
        run = o.db.get_run(rid); b = {k: o.db.get_results(rid, k) for k in report_agent.BUCKETS}
        buf = io.BytesIO(); report_agent.export_xlsx(buf, run, b); self.assertGreater(len(buf.getvalue()), 4000)
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(buf.getvalue())); self.assertEqual(wb.sheetnames[:2], ["Opportunities", "Emerging"])
        csv = report_agent.export_csv(b["qualified"]).decode("utf-8-sig"); self.assertIn("Campaign keywords", csv.splitlines()[0])

    def test_11_empty_results_are_honest(self):
        global route
        orig = route
        try:
            globals()["route"] = lambda url: (503, "")
            o, rid = self.full_run()
            self.assertEqual(o.db.get_run(rid)["status"], "completed")
            self.assertEqual(o.db.get_results(rid, "qualified"), [])
            logs = " ".join(l["message"] for l in o.db.get_logs(rid))
            self.assertIn("NOT evidence that there is no demand", logs)
        finally:
            globals()["route"] = orig

    def test_13_search_engine_ignoring_site_operator_is_unverified(self):
        """Run #11: Bing returned apple.com/wikipedia for every site:flipkart.com query -> must NOT count as 'not listed'."""
        from opportunity_research import marketplace_agent
        o, s = mk(self.tmp); f = FakeFetcher(o.db, s)
        orig = search.PROVIDERS
        from opportunity_research.net import Result
        junk = lambda f, q, cc, n: (Result("ok", 200, "<html/>", "x"), [{"title": "Apple", "url": "https://www.apple.com", "snippet": "Apple"}])
        search.PROVIDERS = [("junk", junk)]
        try:
            items, prov = search.web(f, s, '"Apple iPhone 17" (site:flipkart.com)', "IN")
            self.assertIsNone(prov, "a provider that ignores site: must not be trusted")
        finally:
            search.PROVIDERS = orig

    def test_14_single_local_listing_means_available(self):
        from opportunity_research import marketplace_agent
        o, s = mk(self.tmp); f = FakeFetcher(o.db, s)
        cfg = load_config("IN")
        cand = {"name": "Boatix Rockerz 450 Headphones", "brand": "Boatix", "model": "450", "noun": "headphones", "category": "Electronics", "alt_names": []}
        r = marketplace_agent.verify(f, s, cfg, cand)
        self.assertEqual(r["gap"], "NO_GAP"); self.assertEqual(r["checked"], 1, "must stop after the first in-stock local listing")
        cand2 = {"name": "Ninja Creami", "brand": "Ninja", "model": "", "noun": "ice cream maker", "category": "Kitchen Appliances & Accessories", "alt_names": []}
        r2 = marketplace_agent.verify(f, s, cfg, cand2)
        self.assertIn("Myntra", r2["not_relevant_stores"], "a fashion store proves nothing about kitchen appliances")

    def test_15_foreign_suggestions_and_catalogue(self):
        from opportunity_research.trend_discovery import foreign
        from opportunity_research import ubuy_agent
        self.assertTrue(foreign("where to buy 3d printer in philippines", "IN")); self.assertFalse(foreign("ninja creami price in india", "IN"))
        d = os.path.join(self.tmp, "cat"); os.makedirs(d)
        with open(os.path.join(d, "IN.tsv"), "w") as fh:
            fh.write("id\ttitle\tlink\tprice\n1\tNinja NC301 CREAMi Ice Cream Maker\thttps://www.ubuy.co.in/product/1-ninja\t29999 INR\n")
        o, s = mk(self.tmp, ubuy_catalog_files={"IN": os.path.join(d, "IN.tsv")}); ubuy_agent._CAT.clear()
        cfg = load_config("IN")
        hit = ubuy_agent.verify(FakeFetcher(o.db, s), s, cfg, {"name": "Ninja Creami", "brand": "Ninja", "model": "", "noun": "ice cream maker", "alt_names": []})
        miss = ubuy_agent.verify(FakeFetcher(o.db, s), s, cfg, {"name": "Owala Freesip", "brand": "Owala", "model": "", "noun": "water bottle", "alt_names": []})
        ubuy_agent._CAT.clear()
        self.assertEqual(hit["gap"], "AVAILABLE"); self.assertEqual(miss["gap"], "NOT_FOUND")

    def test_16_ubuy_product_cards(self):
        """Real Ubuy India search-page structure (rendered): product name in a card => available on Ubuy."""
        from opportunity_research import ubuy_agent
        html = open(os.path.join(os.path.dirname(__file__), "fixtures", "ubuy_in_iphone18.html"), encoding="utf-8").read()
        class F(FakeFetcher):
            def _raw_get(self, url, render=False, wait_for=None): return 200, html
        o, s = mk(self.tmp); f = F(o.db, s)
        r = ubuy_agent.storefront_check(f, s, "www.ubuy.co.in", {"name": "Apple iPhone 18 Pro Max", "brand": "Apple", "model": "18 pro max", "noun": "smartphone", "alt_names": []})
        self.assertEqual(r["gap"], "AVAILABLE"); self.assertEqual(r["price"], "INR 211539"); self.assertIn("UDII1LW6O", r["url"])
        r2 = ubuy_agent.storefront_check(f, s, "www.ubuy.co.in", {"name": "Google Pixel 11", "brand": "Google", "model": "11", "noun": "smartphone", "alt_names": []})
        self.assertEqual(r2["gap"], "NOT_FOUND", "a 'user guide' card must not count as the phone")

    def test_17_country_without_old_coverage(self):
        """Bosnia (run #14 was all UNVERIFIED): local marketplaces + local web shops (.ba) must give a verdict."""
        o, rid = self.full_run("BA", "Bosnia and Herzegovina")
        b = self.buckets(o, rid)
        creami = self.find(b, "qualified", "creami")
        self.assertIsNotNone(creami, f"buckets: { {k: list(v) for k, v in b.items() if k != 'rejected'} }")
        self.assertEqual(creami["marketplace"]["local_web"]["tld"], "ba")
        self.assertIn(creami["marketplace"]["gap"], ("FULL_GAP", "PARTIAL_GAP"))

    def test_18_search_supply_signal(self):
        """Run #17 Pakistan: Daraz/PriceOye robots, OLX 403, free search engines empty -> local search suggestions decide."""
        from opportunity_research import marketplace_agent as m
        cfg = load_config("PK")
        sug = {"airpods pro daraz": ["airpods pro daraz", "airpods pro 2 daraz price"], "ninja creami price in pakistan": ["where to buy ninja creami in pakistan"],
               "ninja creami pakistan": ["ninja creami pakistan ubuy"]}
        orig = search.google_suggest
        search.google_suggest = lambda f, q, cc, hl=None: sug.get(q, [])
        try:
            a = m.search_supply(None, cfg, {"name": "Apple AirPods Pro", "brand": "Apple", "noun": "earbuds", "alt_names": [], "model": ""}, cfg["marketplaces"])
            b = m.search_supply(None, cfg, {"name": "Ninja Creami", "brand": "Ninja", "noun": "ice cream maker", "alt_names": [], "model": ""}, cfg["marketplaces"])
        finally:
            search.google_suggest = orig
        self.assertIn("daraz", a["listed_on"]); self.assertFalse(b["listed_on"]); self.assertTrue(b["unmet"])

    def test_19_real_amazon_india_titles(self):
        """Run #18: 'Galaxy Z Fold7' (glued, brand on a separate card line) is the Fold 7; variants must agree."""
        from opportunity_research.evidence import match_product as m, best_match
        C = lambda n, b, noun: {"name": n, "brand": b, "noun": noun, "alt_names": []}
        fold = C("Samsung Galaxy Z Fold 7", "Samsung", "smartphone")
        hit, sc = best_match(fold, [{"title": "Galaxy Z Fold7 5G Mobile with Galaxy AI (Blue Shadow, 12GB RAM, 256GB Storage)", "url": "/dp/x",
                                     "context": "Samsung Galaxy Z Fold7 5G Mobile ₹1,28,999", "price": None}])
        self.assertTrue(hit)
        self.assertFalse(m(fold, "Samsung Galaxy Z Flip7 5G Smartphone"))
        self.assertFalse(m(C("Sony PS5 Pro", "Sony", "gaming console"), "Sony PlayStation®5 Digital Edition (slim) Console"))
        self.assertTrue(m(C("Sony PS5 Pro", "Sony", "gaming console"), "PlayStation®5 Pro Console"))
        self.assertFalse(m(C("Apple iPhone 16 Pro", "Apple", "smartphone"), "iPhone 16 Pro Max"))
        self.assertFalse(m(C("Sony Playstation Portal", "Sony", "gaming console"), "Spigen EZ Fit Tempered Glass for Sony PlayStation Portal Remote Player"))
        self.assertEqual([x["name"] for x in pid.extract_from_text("apple iphone 16 17 18", True)], ["Apple iPhone 16"])

    def test_20_deep_research_reaches_target(self):
        """User request: at least 20 opportunities per run -> research continues in rounds over new source pages."""
        STATE["universe"] = True
        o, s = mk(self.tmp, universe_pages_per_round=3, demand_shortlist=400, marketplace_check_limit=400, deep_check_limit=400, international_shortlist=300)
        rid = o.db.create_run("NG", "Nigeria", 30, "ALL", 100)
        o.db.update_run(rid, state_json=json.dumps({"opts": {"target": 20, "rounds": 8}}))
        o.run(rid, RunContext(o.db, rid))
        q = o.db.get_results(rid, "qualified")
        logs = " ".join(l["message"] for l in o.db.get_logs(rid))
        self.assertGreaterEqual(len(q), 20, f"only {len(q)} opportunities; log: {logs[-600:]}")
        self.assertIn("Round 2", logs)
        # second run of the same country explores different pages and skips nothing it has not confirmed as sold locally
        rid2 = o.db.create_run("NG", "Nigeria", 30, "ALL", 100)
        o.db.update_run(rid2, state_json=json.dumps({"opts": {"target": 20, "rounds": 2}}))
        o.run(rid2, RunContext(o.db, rid2))
        n1 = {r["key"] for r in q}; n2 = {r["key"] for r in o.db.get_results(rid2, "qualified")}
        self.assertTrue(n2 - n1, "a new run must surface products the previous run did not")

    def test_21_yoy_growth_and_references(self):
        """User request: show where the data comes from and how much it is up vs last year (e.g. 'Google Trends +2,400%')."""
        from opportunity_research import trend_growth
        from datetime import date as _d, timedelta as _td
        orig = trend_growth._fetch_trends
        def fake(kw, geo_code, s):
            start = _d.today() - _td(weeks=260)
            return [((start + _td(weeks=i)).isoformat(), 2.0 if i < 230 else 50.0) for i in range(261)]
        trend_growth._fetch_trends = fake
        trend_growth._STATE.update(fails=0, n=0, last=0)
        try:
            o, rid = self.full_run(enable_google_trends_yoy=True, trends_delay_seconds=0)
        finally:
            trend_growth._fetch_trends = orig
        creami = next(r for r in o.db.get_results(rid, "qualified") if "creami" in r["name"].lower())
        g = creami["growth"]["google_trends"]
        self.assertEqual(g["status"], "ok"); self.assertEqual(g["label"], "+2,400%")
        self.assertIn("trends.google.com/trends/explore", g["url"])
        self.assertIn("+2,400% YoY", creami["growth"]["headline"])
        pr = creami["promotion"]
        self.assertTrue(pr["channels"] and pr["channels"][0]["channel"] == "Google Search Ads")
        self.assertTrue(any("lagos" in x for x in pr["channels"][0]["do"]), "ad groups must use the real local searches")
        self.assertIn(pr["priority"], ("High", "Medium", "Test"))
        types = {r["type"] for r in creami["references"]}
        for t in ("Search trend", "Local search demand", "Local supply check"):
            self.assertIn(t, types)
        from flask import Flask
        from opportunity_research import blueprint
        blueprint._ORCH["o"] = o
        app = Flask(__name__); app.register_blueprint(blueprint.opportunity_bp)
        body = app.test_client().get(f"/opportunity/api/run/{rid}/results").get_data(as_text=True)
        self.assertNotIn("Infinity", body); json.loads(body)

    def test_22_speedups_do_not_change_results(self):
        """Pipelined checks + more workers must give exactly the same verdicts as the sequential stages."""
        def outcome(**kw):
            self.tmp = tempfile.mkdtemp()
            o, rid = self.full_run(**kw)
            return {(r["name"], r["bucket"], (r.get("marketplace") or {}).get("gap"), (r.get("ubuy") or {}).get("gap"), (r.get("compliance") or {}).get("status"))
                    for r in o.db.get_results(rid) if r.get("signals")}
        slow = outcome(pipeline_checks=False, workers=1, render_workers=1)
        fast = outcome(pipeline_checks=True, workers=12, render_workers=3)
        self.assertEqual(slow, fast)

    def test_23_adaptive_pacing(self):
        o, s = mk(self.tmp, min_delay_per_domain=1.5)
        f = FakeFetcher(o.db, s)
        h = "suggestqueries.google.com"
        for _ in range(40): f._adapt(h, True)
        self.assertAlmostEqual(f._delay[h], s["host_min_delays"][h])      # speeds up to the floor, never below
        f._adapt(h, False); self.assertGreater(f._delay[h], 0.3)           # backs off on 429

    def test_24_madagascar_rows_from_user(self):
        """User-reported Madagascar run: French-market suggestions, fake 'amazon' unmet signals, a phone case as source, a hockey book as Ubuy match."""
        from opportunity_research import historical_analysis as ha, campaign_agent
        from opportunity_research.evidence import match_product
        cfg = load_config("MG")
        sug = {"sony ps5 pro": ["sony ps5 pro", "sony ps5 pro 2tb", "ps5 pro fnac", "ps5 pro occasion"],
               "sony ps5 pro price": ["sony ps5 pro prix madagascar"],
               "amazon kindle paperwhite": ["amazon kindle paperwhite", "amazon kindle paperwhite signature edition", "amazon kindle paperwhite (nouvelle génération)"]}
        orig = search.google_suggest
        search.google_suggest = lambda f, q, cc, hl=None: sug.get(q, [])
        try:
            ps = ha.search_demand(None, cfg, {"name": "Sony PS5 Pro", "brand": "Sony", "noun": "gaming console", "alt_names": [], "model": "5 pro"})
            kd = ha.search_demand(None, cfg, {"name": "Amazon Kindle Paperwhite", "brand": "Amazon", "noun": "e-reader", "alt_names": [], "model": ""})
        finally:
            search.google_suggest = orig
        self.assertEqual(ps["matches"], 1, "only the suggestion that names Madagascar is local demand")
        self.assertFalse(any("fnac" in p["phrase"] for p in ps["phrases"]))
        self.assertEqual(kd["unmet_intent"], 0, "the brand word 'amazon' is not an import signal")
        self.assertFalse(kd["searched_locally"])
        self.assertEqual(pid.extract_listing_title("Temdan Compatible with iPhone 18 Pro Max Case, Military Grade Protection", "Electronics"), [])
        self.assertFalse(match_product({"name": "Stanley Cup", "brand": "Stanley", "noun": "tumbler", "alt_names": []},
                                       "The Stanley Cup Playoffs The Quest for Hockeys Biggest Prize Spectacular Sports"))
        self.assertTrue(ha.off_topic("stanley cup winners", {"name": "Stanley Cup"}))
        cp = campaign_agent.suggest(load_config("IN"), {"name": "Sony PS5 Pro", "brand": "Sony", "category": "Electronics", "signals": [],
                                                       "history": {"search_phrases": [{"phrase": "ps5 pro amazon", "intent": "search"}, {"phrase": "ps5 pro price in india", "intent": "price"}]}})
        self.assertIn("ps5 pro amazon", cp["competitor_terms"]); self.assertNotIn("[ps5 pro amazon]", cp["keywords_exact"])

    def test_12_healthcheck_and_flask(self):
        o, s = mk(self.tmp)
        r = healthcheck.run(FakeFetcher(o.db, s), s, "NG")
        self.assertTrue(any(x["source"].startswith("Google Autocomplete") and x["ok"] for x in r["rows"]))
        self.assertTrue(any("Jumia" in x["source"] and not x["ok"] for x in r["rows"]))
        from flask import Flask
        from opportunity_research import blueprint
        blueprint._ORCH["o"] = o
        app = Flask(__name__); app.register_blueprint(blueprint.opportunity_bp)
        c = app.test_client()
        page = c.get("/opportunity/").get_data(as_text=True)
        self.assertIn("Africa", page); self.assertIn("Nigeria", page)
        self.assertEqual(c.get("/opportunity/api/country/R-AFRICA").get_json()["level"], "Region")
        self.assertEqual(c.get("/opportunity/health").status_code, 200)

if __name__ == "__main__":
    unittest.main()
