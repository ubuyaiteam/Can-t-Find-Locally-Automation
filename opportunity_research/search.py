"""Search adapters. All free and key-less by default, all LOCALISED to the destination country:

  google_suggest()    Google Autocomplete (gl/hl)       -> what people in the country actually type   [demand radar core]
  google_news()       Google News RSS country edition   -> dated local mentions (history + discovery)
  google_trends_rss() Google Trends daily trending RSS  -> what is spiking in the country today
  reddit()            Reddit public JSON                -> "where can I buy X in <country>" posts
  web()               web search chain for site:/index checks:
                      existing_search_fn hook -> optional paid API (Serper / SerpAPI / Brave, only if a key is set)
                      -> Bing HTML -> DuckDuckGo HTML -> Mojeek
  (Bing RSS 'web' was REMOVED: it ignores the query and returned dictionary pages.)

Every call is counted in STATS so a blocked / empty source is visible instead of silently looking like "no demand".
Nothing here bypasses CAPTCHAs, logins or robots rules."""
import importlib, json, re, threading
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus, urlparse, parse_qs, unquote
from bs4 import BeautifulSoup
from .evidence import domain_of
from . import geo

STATS = {}
_LOCK = threading.Lock()
_DEAD = {}            # provider -> consecutive hard failures (skip provider for the rest of the run after 4)

def reset_stats():
    with _LOCK:
        STATS.clear(); _DEAD.clear()

def _track(source, r, items):
    with _LOCK:
        s = STATS.setdefault(source, {"calls": 0, "not_ok": 0, "empty": 0, "items": 0, "last_error": ""})
        s["calls"] += 1
        if r is not None and not r.ok:
            s["not_ok"] += 1
            s["last_error"] = f"{r.status}" + (f" HTTP {r.http}" if getattr(r, "http", None) else "")
        elif not items:
            s["empty"] += 1
        s["items"] += len(items)
    return items

def _dead(p):
    return _DEAD.get(p, 0) >= 4

def _mark(p, ok):
    with _LOCK:
        _DEAD[p] = 0 if ok else _DEAD.get(p, 0) + 1

def _date(s):
    try:
        return parsedate_to_datetime(s).date().isoformat()
    except Exception:
        return None

# ------------------------------------------------------------------ RSS
def parse_rss(text):
    items = []
    try:
        root = ET.fromstring(text)
    except Exception:
        return items
    for it in root.iter("item"):
        g = lambda t: (it.findtext(t) or "").strip()
        url = g("link")
        src = ""
        for el in it:
            if el.tag.split("}")[-1] == "source":
                src = domain_of(el.get("url", "")) or (el.text or "").strip()
        title = g("title")
        if src and " - " in title:              # Google News appends " - Publisher"
            title = title.rsplit(" - ", 1)[0]
        items.append({"title": title, "url": url, "snippet": re.sub(r"<[^>]+>", " ", g("description"))[:400],
                      "date": _date(g("pubDate")), "source": src or domain_of(url)})
    return items

# ------------------------------------------------------------------ Google Autocomplete
def google_suggest(f, query, cc, hl=None):
    """Returns the suggestion strings Google shows to users in country `cc` for `query`."""
    hl = hl or geo.language(cc)
    url = f"https://suggestqueries.google.com/complete/search?client=firefox&hl={hl}&gl={cc.lower()}&q={quote_plus(query)}"
    r = f.get(url)
    out = []
    if r.ok:
        try:
            data = json.loads(r.text)
            out = [s for s in (data[1] if isinstance(data, list) and len(data) > 1 else []) if isinstance(s, str)]
        except ValueError:
            out = []
    return _track("google_autocomplete", r, out)

# ------------------------------------------------------------------ Google News
def google_news(f, query, cc, days=90, country_name=None, n=60):
    hl, gl, ceid, localized = geo.news_edition(cc)
    q = query if localized or not country_name else f"{query} {country_name}"
    url = f"https://news.google.com/rss/search?q={quote_plus(q + (f' when:{int(days)}d' if days else ''))}&hl={hl}&gl={gl}&ceid={ceid}"
    r = f.get(url)
    items = parse_rss(r.text)[:n] if r.ok else []
    for it in items:
        it["localized_edition"] = localized
    return _track("google_news", r, items)

BING_MKT = {"NG": "en-NG", "KE": "en-KE", "ZA": "en-ZA", "GH": "en-GH", "IN": "en-IN", "GB": "en-GB", "AU": "en-AU", "CA": "en-CA", "AE": "en-AE",
            "SA": "ar-SA", "EG": "ar-EG", "PK": "en-PK", "MY": "en-MY", "PH": "en-PH", "SG": "en-SG", "NZ": "en-NZ", "IE": "en-IE"}

def news(f, query, cc, days=90, country_name=None, n=60):
    """Google News first; Bing News RSS fallback (Bing *news* RSS does honour the query)."""
    items = google_news(f, query, cc, days, country_name, n)
    if items:
        return items
    mkt = BING_MKT.get(cc.upper(), "en-US")
    q = query if mkt != "en-US" or not country_name else f"{query} {country_name}"
    r = f.get(f"https://www.bing.com/news/search?q={quote_plus(q)}&format=rss&setmkt={mkt}")
    return _track("bing_news", r, parse_rss(r.text)[:n] if r.ok else [])

# ------------------------------------------------------------------ Google Trends daily RSS
def google_trends_rss(f, geo_code):
    r = f.get(f"https://trends.google.com/trending/rss?geo={geo_code}")
    out = []
    if not r.ok:
        return _track("google_trends_rss", r, out)
    try:
        root = ET.fromstring(r.text)
    except Exception:
        return _track("google_trends_rss", r, out)
    for it in root.iter("item"):
        d = {"title": (it.findtext("title") or "").strip(), "traffic": "", "news": [], "date": _date(it.findtext("pubDate") or "")}
        cur = None
        for el in it.iter():
            tag = el.tag.split("}")[-1]
            if tag == "approx_traffic":
                d["traffic"] = (el.text or "").strip()
            elif tag == "news_item_title":
                cur = {"title": (el.text or "").strip(), "url": ""}; d["news"].append(cur)
            elif tag == "news_item_url" and cur is not None:
                cur["url"] = (el.text or "").strip()
        out.append(d)
    return _track("google_trends_rss", r, out)

# ------------------------------------------------------------------ Reddit
REDDIT_SUBS = {"NG": "Nigeria", "KE": "Kenya", "GH": "ghana", "ZA": "southafrica", "EG": "Egypt", "MA": "Morocco", "UG": "Uganda", "TZ": "tanzania",
               "ET": "Ethiopia", "AE": "dubai", "SA": "saudiarabia", "KW": "Kuwait", "QA": "qatar", "BH": "Bahrain", "OM": "Oman", "PK": "pakistan",
               "BD": "bangladesh", "LK": "srilanka", "NP": "Nepal", "IN": "india", "MY": "malaysia", "PH": "Philippines", "ID": "indonesia",
               "TR": "Turkey", "JO": "jordan", "LB": "lebanon", "IQ": "Iraq", "RW": "Rwanda", "ZM": "zambia", "ZW": "Zimbabwe", "MU": "mauritius",
               "BR": "brasil", "MX": "mexico", "CO": "Colombia", "AR": "argentina", "CL": "chile", "PE": "PERU", "AU": "australia", "NZ": "newzealand",
               "GB": "AskUK", "IE": "ireland", "CY": "cyprus", "IS": "Iceland", "UZ": "uzbekistan", "KZ": "Kazakhstan"}

def reddit(f, cc, query, n=25):
    sub = REDDIT_SUBS.get(cc.upper())
    if not sub or _dead("reddit"):
        return []
    r = f.get(f"https://www.reddit.com/r/{sub}/search.json?q={quote_plus(query)}&restrict_sr=1&sort=new&t=year&limit={n}")
    out = []
    if r.ok:
        try:
            for ch in json.loads(r.text).get("data", {}).get("children", []):
                d = ch.get("data", {})
                ts = d.get("created_utc")
                out.append({"title": d.get("title", ""), "url": "https://www.reddit.com" + d.get("permalink", ""), "snippet": (d.get("selftext") or "")[:400],
                            "date": datetime.fromtimestamp(ts, timezone.utc).date().isoformat() if ts else None, "source": "reddit.com/r/" + sub})
        except (ValueError, AttributeError):
            pass
    if not r.ok:
        with _LOCK: _DEAD["reddit"] = 99            # blocked (403): stop asking for the rest of the run
    return _track("reddit", r, out)

# ------------------------------------------------------------------ web search chain (for site:/index checks)
def _bing_html(f, query, cc, n):
    r = f.get(f"https://www.bing.com/search?q={quote_plus(query)}&cc={cc.lower()}&setlang=en&count={max(10, n)}")
    out = []
    if r.ok:
        soup = BeautifulSoup(r.text, "html.parser")
        for li in soup.select("li.b_algo")[:n]:
            a = li.select_one("h2 a")
            if not a or not a.get("href", "").startswith("http"):
                continue
            sn = li.select_one(".b_caption p") or li.select_one("p")
            out.append({"title": a.get_text(" ", strip=True), "url": a["href"], "snippet": sn.get_text(" ", strip=True) if sn else "", "date": None,
                        "source": domain_of(a["href"])})
        if not out and "b_results" not in r.text:      # not a results page at all (consent/anti-bot page) -> treat as failure
            r.status = "unreadable"
    return r, out

DDG_REGION = {"US": "us-en", "GB": "uk-en", "IN": "in-en", "ZA": "za-en", "AU": "au-en", "CA": "ca-en", "NZ": "nz-en", "IE": "ie-en", "SG": "sg-en",
              "MY": "my-en", "PH": "ph-en", "PK": "pk-en", "ID": "id-en", "AE": "xa-en", "SA": "xa-en", "KW": "xa-en", "QA": "xa-en", "BH": "xa-en",
              "OM": "xa-en", "EG": "xa-en", "DE": "de-de", "FR": "fr-fr", "ES": "es-es", "IT": "it-it", "NL": "nl-nl", "PL": "pl-pl", "SE": "se-sv",
              "TR": "tr-tr", "BR": "br-pt", "MX": "mx-es", "AR": "ar-es", "CO": "co-es", "CL": "cl-es", "PE": "pe-es", "JP": "jp-jp", "KR": "kr-kr"}

def _ddg(f, query, cc, n):
    kl = DDG_REGION.get(cc.upper(), "wt-wt")
    r = f.get(f"https://html.duckduckgo.com/html/?q={quote_plus(query)}&kl={kl}")
    out = []
    if r.ok:
        for a in BeautifulSoup(r.text, "html.parser").select("a.result__a")[:n]:
            href = a.get("href", "")
            if "uddg=" in href:
                href = unquote(parse_qs(urlparse(href).query).get("uddg", [href])[0])
            sn = a.find_parent(class_="result")
            snippet = sn.select_one(".result__snippet").get_text(" ", strip=True) if sn and sn.select_one(".result__snippet") else ""
            out.append({"title": a.get_text(" ", strip=True), "url": href, "snippet": snippet, "date": None, "source": domain_of(href)})
        if not out and "no-results" not in r.text and "result" not in r.text:
            r.status = "unreadable"
    return r, out

def _mojeek(f, query, cc, n):
    r = f.get(f"https://www.mojeek.com/search?q={quote_plus(query)}")
    out = []
    if r.ok:
        for li in BeautifulSoup(r.text, "html.parser").select("ul.results-standard li")[:n]:
            a = li.select_one("a.ob") or li.select_one("h2 a")
            if not a: continue
            sn = li.select_one("p.s")
            out.append({"title": a.get_text(" ", strip=True), "url": a.get("href", ""), "snippet": sn.get_text(" ", strip=True) if sn else "",
                        "date": None, "source": domain_of(a.get("href", ""))})
        if not out and "results" not in r.text:
            r.status = "unreadable"
    return r, out

def _paid(f, s, query, cc, n):
    """Optional paid providers - only used when the user put a key in opportunity_settings.json."""
    if not (s.get("serper_api_key") or s.get("serpapi_key") or s.get("brave_api_key")):
        return None, None
    import requests
    try:
        if s.get("serper_api_key"):
            r = requests.post("https://google.serper.dev/search", json={"q": query, "gl": cc.lower(), "num": n},
                              headers={"X-API-KEY": s["serper_api_key"]}, timeout=s["request_timeout"])
            return [{"title": o.get("title", ""), "url": o.get("link", ""), "snippet": o.get("snippet", ""), "date": None, "source": domain_of(o.get("link", ""))}
                    for o in r.json().get("organic", [])][:n], "serper"
        if s.get("serpapi_key"):
            r = requests.get("https://serpapi.com/search.json", params={"q": query, "gl": cc.lower(), "num": n, "api_key": s["serpapi_key"]}, timeout=s["request_timeout"])
            return [{"title": o.get("title", ""), "url": o.get("link", ""), "snippet": o.get("snippet", ""), "date": None, "source": domain_of(o.get("link", ""))}
                    for o in r.json().get("organic_results", [])][:n], "serpapi"
        r = requests.get("https://api.search.brave.com/res/v1/web/search", params={"q": query, "country": cc.lower(), "count": n},
                         headers={"X-Subscription-Token": s["brave_api_key"], "Accept": "application/json"}, timeout=s["request_timeout"])
        return [{"title": o.get("title", ""), "url": o.get("url", ""), "snippet": re.sub(r"<[^>]+>", "", o.get("description", "")), "date": None,
                 "source": domain_of(o.get("url", ""))} for o in r.json().get("web", {}).get("results", [])][:n], "brave"
    except Exception:
        return None, None

PROVIDERS = [("duckduckgo", _ddg), ("bing_html", _bing_html), ("mojeek", _mojeek)]   # DDG honours site:/quotes; Bing often does not for bots

_SITE_RE = re.compile(r"site:([A-Za-z0-9.\-]+)")

def _honours_operators(query, items):
    """Free engines sometimes ignore site:/quotes for automated clients and return the same generic page
    (seen live: Bing returned apple.com/wikipedia for every site:flipkart.com query). A site: query is only
    trusted when at least one result is on a requested domain; an EMPTY result list is accepted as 'no results'."""
    if not items:
        return True
    sites = [d.lower().lstrip(".") for d in _SITE_RE.findall(query)]
    on = lambda dom, d: dom == d or dom.endswith("." + d)
    if sites and not any(any(on(domain_of(it.get("url", "")), d) for d in sites) for it in items):
        return False
    quoted = re.findall(r'"([^"]+)"', query)
    if quoted:
        toks = [t for t in re.findall(r"[a-z0-9]+", quoted[0].lower()) if len(t) > 1]
        need = max(1, int(len(toks) * 0.6 + 0.5))
        blob = [(it.get("title", "") + " " + it.get("snippet", "") + " " + it.get("url", "")).lower() for it in items]
        if toks and not any(sum(1 for t in toks if t in b) >= need for b in blob):
            return False
    return True

def web(f, settings, query, cc="US", n=10):
    """Returns (items, provider). provider is None when no provider gave a TRUSTWORTHY answer
    => callers must treat the check as UNVERIFIED (never as 'absent')."""
    hook = settings.get("existing_search_fn")
    if hook:
        try:
            mod, fn = hook.split(":")
            res = getattr(importlib.import_module(mod), fn)(query, n) or []
            out = [{"title": r.get("title", ""), "url": r.get("url") or r.get("link", ""), "snippet": r.get("snippet") or r.get("body", ""),
                    "date": None, "source": domain_of(r.get("url") or r.get("link", ""))} for r in res]
            if _honours_operators(query, out):
                return _track("existing_search_fn", None, out[:n]), "existing_search_fn"
        except Exception:
            pass
    items, prov = _paid(f, settings, query, cc, n)
    if prov:
        return _track(prov, None, items), prov
    for name, fn in PROVIDERS:
        if _dead(name):
            continue
        r, out = fn(f, query, cc, n)
        if r.ok and not _honours_operators(query, out):
            r.status = "ignored_site_operator"           # generic page instead of real results
        elif r.ok and not out:
            # live (run #17): Bing returned 0 results even for "airpods pro price" -> an empty answer from a FREE engine is not evidence
            r.status = "empty_untrusted"
        _track(name, r, out)
        if r.ok:
            _mark(name, True)
            return out, name
        if r.status != "empty_untrusted":           # an empty answer is not a provider failure
            _mark(name, False)
    return [], None
