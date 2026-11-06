# Ubuy "Can't find it locally" Demand Radar — v2

Finds products that people in a destination **country or region** actively search for, that **local stores don't stock (or barely stock)**,
that are **not yet orderable on the Ubuy storefront**, and that have a **sourcing route** — then suggests the **SKU and a search campaign**
built from the real local search phrases. Free-first: no API keys needed (optional search-API keys make supply checks more reliable).

## What changed in v2 (why v1 returned wrong results)
| v1 problem | v2 fix |
|---|---|
| Bing "web RSS" ignored the query — the Nigeria run got Merriam-Webster / Cambridge Dictionary pages as "results" | Removed. Demand now comes from **Google Autocomplete (gl/hl per country)**, **Google News country editions**, **Google Trends daily RSS**, **Reddit country subs**. site: checks use Bing HTML → DuckDuckGo → Mojeek (or Serper/SerpAPI/Brave if you add a key) |
| Google Trends silently skipped for every country except India (`setdefault` bug) | Fixed in `country_registry.load_config` |
| Extraction needed Capitalised Brand + Model headlines (274 items → 1 product) | New extractor reads lower-case search queries, 200+ known product lines (Ninja Creami, Stanley Quencher, Dyson Airwrap…), unknown brands with model numbers |
| Only India had marketplaces → every other country "unverified" | Built-in directory for ~70 countries (`market_directory.py`) + **search-index fallback** when a marketplace blocks bots (Jumia is behind Cloudflare) + local-web seller check for any country |
| No regions | **Africa, West/East/Southern/North Africa, GCC, Middle East, South Asia, SE Asia, LatAm, Europe…** — one run per selected country, products ranked by how many countries they're an opportunity in |
| Legal gate needed a positive rule match → 0 qualified in all 9 runs | Global screening rules (radio/telecom, drones, e-cigs, medical, cosmetics, supplements, lithium batteries, electrical) with country regulator names; "no restriction flagged" no longer blocks |
| Price parser knew only ₹ $ € £ AED SAR KWD | ₦ KSh GH₵ R E£ DH FCFA RM ₱ … prefix and suffix formats |
| "May become trending" not supported | **Emerging** bucket: trending in US/UK (or weak local signal) + open local supply gap |
| — | SKU + campaign suggestions (exact/phrase keywords from observed local searches, negatives, headlines, landing page) |
| — | **Source health page** (`/opportunity/health`) and `python diagnose.py NG KE ZA` |

## v2.8 – Accuracy fixes from the Madagascar run
* Small markets (no big local search population, e.g. Madagascar in French): Google suggestions are mostly from the big market of the
  same language (France). There, a suggestion counts as LOCAL demand only if it names the country, a city (Tana, Toamasina…) or the currency (Ariary);
  suggestions naming foreign retailers (fnac, darty, walmart, argos…) or other countries in French/Spanish/Portuguese (maroc, réunion, españa…) are ignored.
* 'amazon' (brand of Kindle/Echo) is no longer an "import / can't find it" signal.
* 'Likely gap' needs ≥3 product suggestions; empty spot-check text fixed.
* Best-seller listings that are accessories (cases, covers, "compatible with …") are not the product -> no more phone case as the iPhone source link.
* Books / posters / hockey results ("Stanley Cup Playoffs") never match a product; 'stanley cup winners' is not tumbler demand.
* Ad keywords: competitor store terms (amazon, fnac, jumia…) are moved to an optional "competitor terms" list; occasion / reconditionné / usado / avis / test are negatives.

## v2.7 – Faster (same results) + "How to promote" plan
* **~2.5× faster** in a simulated run (same opportunities): 12 parallel agents (was 4), 3 parallel browser tabs for Ubuy,
  adaptive per-site pacing (speeds up while a site answers normally, backs off and RETRIES on 429 instead of giving up),
  sites that hard-block 3× in a row are skipped for the run (their answer would be 'unverified' anyway),
  Ubuy / import / sourcing / growth checks start as soon as a product shows a local gap (pipelined across websites),
  fewer redundant search-suggestion probes, best-seller pages fetched in parallel, stage timings in the log.
  A test checks that the fast mode gives exactly the same verdicts as the slow sequential mode.
* **How to promote** section on every opportunity (and an Excel column): priority, message/angle from the evidence,
  Google Search ad groups built from the REAL local searches (where-to-buy / price / city), Shopping/PMax feed title +
  custom labels, SEO page/FAQ actions, Instagram/TikTok, YouTube, community answers, WhatsApp/email where relevant,
  launch timing with the country's upcoming sales events (Black/White Friday, Diwali, Ramadan/Eid, 11.11 …), a 3-step test plan and KPIs.

## v2.6 – Year-over-year growth + references
* Every opportunity / emerging product shows **how much it is up vs last year**, e.g. "▲ +2,400% YoY · Google Trends (IN)":
  Google Trends search interest (country, else worldwide) for the last N weeks vs the same weeks a year earlier ("Breakout" when it
  was 0 a year ago), plus Google News mentions this period vs last year. Each figure links to the Google Trends / Google News page it came from.
  Google Trends is accessed with the free `pytrends` library (installed by run.bat); Google rate-limits it, so requests are spaced out
  (`trends_delay_seconds`) and cached 7 days - when blocked the card says so instead of guessing, and the News figure is used.
* Measured YoY growth feeds the Growth part of the opportunity score.
* **References** section at the end of every product (and an Excel column): Google Trends, Google News (this year / last year),
  the local Google searches, the abroad best-seller list, trending/news/community posts, every local-store check, the Ubuy page,
  the sourcing listing and official import sources.

## v2.5 – Deep research: target 20+ opportunities, different answers each run
* **Target opportunities** (default 20) + **Research depth** (Quick 1 round / Standard 4 / Deep 8) on the start page. After the normal
  pass the run keeps going in rounds, each exploring NEW source pages, until the target, the round limit, 150 min or the request budget is reached.
* **Bigger research universe (~210 source pages):** Amazon US Best Sellers, Movers & Shakers, New Releases, Most Wished For, Most Gifted
  (25 categories, incl. page 2) and Amazon UK Best Sellers / Movers / New Releases (12 categories), plus the 220+ product lines, US/UK trends,
  local Google demand. The pool is shuffled per run, so every run starts from a different slice.
* **Variety:** products confirmed as sold locally in the last 14 days are skipped (`remember_sold_locally_days`), so each run spends its
  effort on products not yet checked. Choose "Re-check everything" to disable.
* Products outside the built-in category list are kept (e.g. "Dr Teal's Pure Epsom Salt", "LEGO Icons Wildflower Bouquet").
* A product found on an Amazon US/UK list uses that listing as its sourcing route (no extra search).
* The page cache is pruned to 7 days at start-up (`cache_keep_days`) so the database stops growing.

## v2.4 (after run #18 India)
* Model names written together are understood ("Galaxy Z **Fold7**", "S25", "PlayStation®5" = PS5) — run #18 wrongly listed the Z Fold 7 as missing.
* Amazon India prints the brand on a separate card line; the brand is now taken from the card.
* Variant words must agree (Pro / Max / Ultra / Mini / Plus / Slim / Digital…): "PS5 Pro" ≠ "PS5 Digital", "iPhone 16 Pro" ≠ "iPhone 16 Pro Max".
* "Fold 7" and "Flip 7" are never merged; "apple iphone 16 vs 17 vs 18" no longer becomes a product.
* Bigger funnel (320 validated, 240 supply-checked).

## v2.3 (after run #17 Pakistan)
* **Local search suggestions as supply evidence** when stores block bots (Daraz/PriceOye robots, OLX 403) and free search engines
  return nothing: "airpods pro daraz" / "... price in pakistan daraz" ⇒ sold locally; only "where to buy / import / ubuy" ⇒ **LIKELY_GAP**
  (shown with low/medium confidence + spot-check link; counts as an opportunity).
* Empty answers from free search engines are no longer treated as "not listed".
* 70 funnel slots reserved for products trending abroad (Amazon US / US-UK trends); bigger funnel (450 candidates, 220 validated, 160 supply-checked).
* Every product carries a **Ubuy link** (product page when found in a card, otherwise the Ubuy search) — clickable pill + Excel column.
* `run.bat` installs Playwright/Chromium automatically when missing; the run page warns when the Ubuy card check is off.

## v2.2 (after runs #12 India and #14 Bosnia)
* **Ubuy is checked exactly like a shopper sees it:** the engine opens `https://<ubuy store>/search/?q=<product>` in a headless browser
  (results are JavaScript-rendered), reads the product cards and marks the product **"On Ubuy storefront"** when its name is in a card
  (accessory cards such as "… user guide", "case for …" are ignored; card price and product link are recorded). Robots.txt is not applied to
  `ubuy.*` hosts because it is your own storefront (`"ubuy_ignore_robots"`). Countries without a known store are auto-detected
  (`ubuy.<tld>`, `ubuy.com.<tld>`, `ubuy.co.<tld>`, else the global `ubuy.com`). **Run update.bat once** to install the browser.
* **Every country gets a local-market check:** besides the marketplace directory (now ~100 countries, incl. Bosnia: eKupi, Domod, Tehnomag, OLX.ba;
  Serbia, Croatia, Slovenia, Balkans, eMAG/Alza/Heureka countries, Nordics, Ukraine…), the engine searches for shop pages on the country's own web
  domain (`<product> site:.ba`) through DuckDuckGo (validated; Bing is only a fallback). Product pages with a price/cart = local seller.
* Gap confidence (high / medium) and a one-click **"Spot-check local availability"** link on every product.
* Ubuy / import / sourcing checks now also run for the top watchlist items (no more "n/a" pills).
* Prices: KM, Kč, lei, Ft, лв, ₴, RSD, ден…; every card's price is taken from its own card.

## v2.1 fixes (after the first live India run, #11)
* **Search engines that ignore `site:`/quotes are detected and not trusted** (live: Bing returned apple.com/Wikipedia for every
  `site:flipkart.com` query, which v2.0 read as "not listed"). Untrustworthy index answers now mean UNVERIFIED, never "missing".
* **One in-stock listing on a local marketplace = available locally (NO_GAP).** The check runs major marketplaces first and stops at the first
  in-stock listing. LOW supply (PARTIAL_GAP) now only means out-of-stock / classifieds-only / a few small sellers.
* **Specialist stores only count for their categories** (Myntra/AJIO/Nykaa/Croma/... prove nothing about other categories).
* **Accessories are not the product** ("case for Google Pixel 11", "carrying case for DJI Neo", other brands' banner ads), sizes/pack counts are not
  model numbers, plural/singular and type synonyms are handled ("Nike football" = "Nike … soccer ball"), PS5 = PlayStation 5.
* **Different models are never merged** (iPhone 16 Pro ≠ iPhone 17 Pro); brand-less items ("Football", "3D Printer", "Phone 2 Pro") are dropped.
* **Suggestions about other countries are ignored** ("where to buy 3d printer in philippines" during an India run).
* **Global "sold abroad" universe:** 220+ known product lines and Amazon US best sellers / movers & shakers are tested against LOCAL searches,
  using the short name people type ("Ninja NC301 CREAMi Ice Cream Maker" is searched as "ninja creami").
* **Sourcing route = direct Amazon US search** (not a search engine).
* **Ubuy is informational, not a gate:** in the Ubuy catalogue → "ready to sell, launch campaign"; not in it → "add SKU". Ubuy's robots.txt blocks
  /search for bots and results load through a protected API, so the exact check uses **your catalogue / Merchant Center feed**:
  drop `data/ubuy_catalog/IN.tsv` (or .csv/.xml) — see `data/ubuy_catalog/README.txt`.

## Result buckets
* **Opportunities** – proven local search demand + verified local supply gap (not sold, or only out-of-stock/grey supply) + not prohibited/restricted + sourcing route. The Ubuy status sets the action (launch campaign vs add SKU).
* **Emerging / may become trending** – trending abroad or early local signal, with an open local gap. Pre-list and re-run in 2–4 weeks.
* **Watchlist** – evidence couldn't be verified (blocked sources) or needs compliance review.
* **Rejected** – already sold locally, already on Ubuy, prohibited, or weak demand (with reasons).

## First thing after updating
Run the health check for your key markets **on the machine that runs the engine**:
```
python diagnose.py NG KE GH ZA AE
```
It shows which sources answer from your network, whether each marketplace page is readable, and whether the Ubuy domain/search URL
in `opportunity_research/market_directory.py` is right (Ubuy domains other than India are marked unconfirmed until this passes — correct them there if needed).
If marketplaces are JavaScript/Cloudflare-protected, rely on the automatic search-index fallback, set `"use_playwright": true`, or
add `"serper_api_key"` (or `serpapi_key` / `brave_api_key`) in `opportunity_settings.json` for the most reliable site: checks.
A country run takes roughly 15–30 minutes (polite rate limits); a region run = that × number of countries selected.

---
## v1 documentation (still applies where not superseded above)


A free-first, zero-training, evidence-driven research app (Flask + SQLite + plain Python agents).
**No paid APIs, no API keys, no AI inference, no training data.** It discovers trending products for a destination
country, checks local marketplaces and the Ubuy storefront, screens import rules, finds public suppliers, scores
opportunities, and stores every observation so it builds its own history over time.

> **Read this first – what this package is and is not**
> * I could not see your existing project (`C:\Users\U138\Desktop\ubuy-engine`). This is a **self-contained module**
>   (`opportunity_research/`) that runs on its own *or* plugs into your existing Flask app with 2 lines. It does **not**
>   modify your `app.py`, `engine.py`, `campaign_*.py`, `ubuy_checker.py` or `jobstore.py`, so your campaign/event research is untouched.
> * It has its own SQLite file (`data/opportunity.db`) and job tables. It can reuse your existing search function (see below).
> * It was tested with **mocked website responses** (11 automated tests, all passing). Live behaviour against real marketplaces
>   was **not** verified in my environment (no access to those sites). Marketplace HTML changes often: expect some sites to come back
>   **UNVERIFIED** until you adjust their `search_url` in `country_configs/india.json`. That is by design – blocked or unreadable
>   sites are never counted as proof that a product is missing.
> * Legal screening is a **rule-based screening aid, not legal advice or clearance**. Nothing is auto-approved because a search found no ban.

## Quick start (Windows)
See **INSTALL.md** for details. Short version:
```
install.bat
run.bat
```
Open http://127.0.0.1:5000/opportunity/ → pick country (India), period, category → **Start research**.

## How the pipeline works (staged funnel)
| Stage | Agent(s) | What happens |
|---|---|---|
| 1 | Trend Discovery | Google Trends public RSS, Bing News/Web RSS (DuckDuckGo HTML fallback), configured bestseller pages → raw product mentions |
| 2 | Product Identification | Brand/model/category extraction, vague + duplicate removal (RapidFuzz) |
| 3 | Historical + Forecast | Dated news mentions bucketed over the selected period (measured); optional `pytrends`; linear-trend forecast or *"Insufficient data for reliable forecast."* |
| 4 | Marketplace verification | Searches each configured marketplace (exact, brand+model, alternates). Statuses: AVAILABLE / OUT OF STOCK / DELIVERY UNAVAILABLE / NO MATCHING LISTING FOUND / UNVERIFIED |
| 5 | Ubuy verification | Searches the destination Ubuy storefront; products already orderable there are excluded |
| 6 | Compliance | Country rule set + official-domain search evidence → PROHIBITED / RESTRICTED / CONDITIONAL / GENERALLY PERMITTED / UNVERIFIED |
| 7 | Sourcing + economics | Public supplier pages/snippets; landed cost & profit only from evidence + your configured assumptions |
| 8 | Scoring + report | 25/15/20/15/15/10 weighted score, separate evidence-confidence score, mandatory legal gate |

**Buckets:** *Qualified* (every rule passed) · *Watchlist / manual review* (uncertain or conditional) · *Rejected* (with reasons).
If fewer than 100 qualify you get fewer than 100 – nothing is padded.

### Qualification rules (all required)
credible local demand · verified local supply gap (≥3 verified marketplaces) · not orderable on Ubuy destination ·
legal status GENERALLY PERMITTED · a sourcing route exists · commercial viability assessable (supplier price **or** reference selling price).
Set `"strict_qualification": false` in `opportunity_settings.json` to relax the last rule.

## Honest limits you should know
* **Demand = public-interest proxy** (dated news mentions, optional Google Trends). It is not sales volume. Nothing is invented.
* **Profit/landed cost** need real inputs. By default every assumption in `country_configs/india.json → economics` is `null`,
  so you will see *"Supplier quotation required"*. Fill in FX rate, shipping, duty %, tax %, expenses to enable the maths.
* **Customs duty / HS code** are never guessed: only an HS *hint* is shown, always flagged for expert confirmation.
* **JavaScript-heavy marketplaces** (Myntra, Meesho, AJIO, Nykaa, …) usually return UNVERIFIED with plain HTTP. Optional fix:
  `pip install playwright`, `python -m playwright install chromium`, set `"use_playwright": true` (slower; still never bypasses CAPTCHAs).
* **robots.txt** is respected for marketplaces, Ubuy, suppliers and official sites. Only the RSS/search endpoints in
  `robots_exempt_hosts` (Bing RSS, DuckDuckGo HTML, Google Trends RSS) skip the check, as they are the project's existing search path. Edit that list if you prefer stricter behaviour.
* The regulatory rules, marketplace search URLs and Ubuy reference domains in `india.json` are **best-effort starting points from my general knowledge** – verify them against the official sites before relying on them.
* Only **India** has a detailed configuration. The 195-entry country list is selectable, but other countries show **Minimal coverage**:
  marketplace/Ubuy/legal checks are Unverified, so their products land on the watchlist. Add `country_configs/<name>.json` (copy `india.json`) with real, verified sources to upgrade a country. No marketplaces or government sites were invented for other countries.
* A first full run makes many polite requests (1.5 s per host). Expect **tens of minutes**; later runs are faster thanks to the 24 h cache. Budget: `max_requests_per_run` (default 1500).

## Plug into your existing Flask app
```python
# in your existing app.py, after `app = Flask(__name__)`
from opportunity_research.blueprint import opportunity_bp
app.register_blueprint(opportunity_bp)          # dashboard at /opportunity/
```
Copy the `opportunity_research/`, `country_configs/` and `templates/opportunity/` folders into your project, merge `requirements.txt`.
To reuse your own search function, put in `opportunity_settings.json`:
`{"existing_search_fn": "engine:your_search_function"}` (signature `fn(query, n) -> [{"title","url","snippet"}]`).

## Dashboard
Country search + coverage indicator · 15/30/45/60/90-day period · category (ALL default) · max 100 · live progress ·
agent activity log · source-health panel · counters (candidates, qualified, marketplace gaps, Ubuy gaps, compliance review, requests) ·
expandable product cards with clickable evidence URLs · Excel (Qualified/Watchlist/Rejected/Run info) · CSV per tab · history list ·
**Cancel** and **Resume** (checkpoints are saved after every stage and every 10 items).

## Self-building history
Every run stores trend observations, forecasts, availability findings, evidence URLs and verification dates in SQLite. On later runs,
forecasts whose horizon has elapsed are compared with newly observed levels and marked *supported / not supported*
(shown on the home page). Optional ML can be added later on top of this real data.

## Files
```
app.py                       standalone launcher
opportunity_research/        orchestrator + agents (trend_discovery, historical_analysis, forecast_agent, product_identification,
                             marketplace_agent, ubuy_agent, compliance_agent, sourcing_agent, profit_agent, scoring_agent,
                             report_agent), net.py (polite HTTP), search.py, evidence.py, database.py, country_registry.py, blueprint.py
country_configs/india.json   India marketplaces, Ubuy, official sources, 19 screening rules, seasonal hints, economics assumptions
templates/opportunity/       dashboard
tests/test_pipeline.py       offline tests with mocked websites
```
## Tests
`python -m unittest discover -s tests -v` → 11 tests: discovery, duplicate removal, marketplace found / not found / blocked,
Ubuy available / not found, prohibited, uncertain legal, supplier unavailable, interrupt + resume, Excel, CSV, empty results, Flask start.
#   C a n - t - F i n d - L o c a l l y - A u t o m a t i o n  
 