"""Master Orchestrator: staged research funnel with checkpoints, resume, cancel, request budget and progress logs.
Supports single-country runs and REGION runs (e.g. Africa): a region run executes one child run per country and
aggregates the products that are opportunities in one or more countries."""
import json, threading, traceback
from concurrent.futures import ThreadPoolExecutor
import time
from . import universe, trend_growth, promotion_agent
from . import (trend_discovery, product_identification, historical_analysis, forecast_agent, marketplace_agent, ubuy_agent,
               compliance_agent, sourcing_agent, profit_agent, scoring_agent, report_agent, campaign_agent, geo, settings as settings_mod)
from .country_registry import load_config, COUNTRIES
from .database import DB
from .net import Fetcher, RunContext, Cancelled

STAGES = ["discovery", "identification", "history", "marketplace", "ubuy", "compliance", "sourcing", "report"]
STAGE_LABEL = {"discovery": "1. Scanning local demand signals", "identification": "2. Identifying specific products", "history": "3. Validating local search demand",
               "marketplace": "4. Local supply check", "ubuy": "5. Ubuy storefront check", "compliance": "6. Import screening",
               "sourcing": "7. Sourcing route", "report": "8. Scoring, SKUs and campaigns"}
BUCKET_RANK = {"qualified": 0, "emerging": 1, "watchlist": 2, "rejected": 3}

class Orchestrator:
    def __init__(self, db, s, fetcher_cls=Fetcher):
        self.db, self.s, self.fetcher_cls = db, s, fetcher_cls
        self.contexts = {}

    # ---------------------------------------------------------------- job control
    def start(self, code, period, category="ALL", max_results=100, resume_id=None, region_countries=None, opts=None):
        max_results = max(1, min(int(max_results), self.s["max_results_cap"]))
        opts = opts or {}
        reg = geo.resolve_region(code)
        if reg:
            ccs = region_countries or reg["priority"][: int(self.s.get("region_max_countries", 6))]
            ccs = [c for c in ccs if c in COUNTRIES]
            rid = resume_id or self.db.create_run(code.upper(), f"{reg['name']} ({len(ccs)} countries)", int(period), category or "ALL", max_results)
            if not resume_id:
                self.db.update_run(rid, state_json=json.dumps({"region": True, "countries": ccs, "children": {}, "opts": opts}))
            ctx = RunContext(self.db, rid); self.contexts[rid] = ctx
            threading.Thread(target=self.run_region, args=(rid,), daemon=True).start()
            return rid
        cfg = load_config(code)
        rid = resume_id or self.db.create_run(cfg["code"], cfg["name"], int(period), category or "ALL", max_results)
        if not resume_id:
            self.db.update_run(rid, state_json=json.dumps({"opts": opts}))
        ctx = RunContext(self.db, rid); self.contexts[rid] = ctx
        threading.Thread(target=self.run, args=(rid,), daemon=True).start()
        return rid

    def cancel(self, rid):
        if rid in self.contexts: self.contexts[rid].cancel.set()
        run = self.db.get_run(rid) or {}
        st = json.loads(run.get("state_json") or "{}")
        for child in (st.get("children") or {}).values():
            if child in self.contexts: self.contexts[child].cancel.set()

    def is_active(self, rid):
        return rid in self.contexts and not self.contexts[rid].cancel.is_set() and (self.db.get_run(rid) or {}).get("status") == "running"

    # ---------------------------------------------------------------- region run
    def run_region(self, rid):
        ctx = self.contexts.get(rid) or RunContext(self.db, rid)
        run = self.db.get_run(rid); st = json.loads(run["state_json"] or "{}")
        ccs = st.get("countries", []); children = st.setdefault("children", {})
        self.db.update_run(rid, status="running", error=None)
        ctx.log("Region Orchestrator", f"Region run over {len(ccs)} countries: {', '.join(COUNTRIES[c]['name'] for c in ccs)}")
        try:
            for i, cc in enumerate(ccs):
                ctx.check()
                child = children.get(cc)
                crun = self.db.get_run(child) if child else None
                if crun and crun["status"] == "completed":
                    continue
                if not child:
                    cfg = load_config(cc)
                    child = self.db.create_run(cfg["code"], cfg["name"], run["period_days"], run["category"], run["max_results"], parent_id=rid)
                    self.db.update_run(child, state_json=json.dumps({"opts": st.get("opts", {})}))
                    children[cc] = child
                    self.db.update_run(rid, state_json=json.dumps(st))
                self.db.update_run(rid, stage=f"Country {i + 1}/{len(ccs)}: {COUNTRIES[cc]['name']}", progress=round(100 * i / max(1, len(ccs)), 1))
                ctx.log("Region Orchestrator", f"--- {COUNTRIES[cc]['name']} (child run #{child}) ---")
                cctx = RunContext(self.db, child); cctx.cancel = ctx.cancel; self.contexts[child] = cctx
                self.run(child, cctx)
                c = self.db.get_run(child)
                cnt = json.loads(c["counters_json"] or "{}")
                ctx.log("Region Orchestrator", f"{COUNTRIES[cc]['name']}: {c['status']} - {cnt.get('qualified', 0)} opportunities, {cnt.get('emerging', 0)} emerging")
                if c["status"] == "cancelled":
                    raise Cancelled()
            self.aggregate_region(rid)
            self.db.update_run(rid, status="completed", stage="Completed", progress=100)
        except Cancelled:
            self.db.update_run(rid, status="cancelled", stage="Cancelled (can be resumed)")
            ctx.log("Region Orchestrator", "Region run cancelled - completed countries are kept", "warn")
        except Exception as e:
            self.db.update_run(rid, status="failed", error=str(e)[:300])
            ctx.log("Region Orchestrator", f"Region run failed: {e}\n{traceback.format_exc()[-300:]}", "error")

    def aggregate_region(self, rid):
        run = self.db.get_run(rid); st = json.loads(run["state_json"] or "{}")
        agg = {}
        req = 0
        for cc, child in st.get("children", {}).items():
            c = self.db.get_run(child) or {}
            req += json.loads(c.get("counters_json") or "{}").get("requests_used", 0)
            for row in self.db.get_results(child):
                if row["bucket"] == "rejected" and not row.get("signals"):
                    continue
                k = row["key"]
                a = agg.setdefault(k, {**row, "region_breakdown": [], "bucket": "rejected", "score": 0})
                a["region_breakdown"].append({"country": COUNTRIES[cc]["name"], "code": cc, "child_run": child, "bucket": row["bucket"],
                                              "score": (row.get("scores") or {}).get("total", 0), "gap": (row.get("marketplace") or {}).get("gap"),
                                              "ubuy": (row.get("ubuy") or {}).get("status"), "demand": (row.get("demand") or {}).get("score"),
                                              "phrases": [p["phrase"] for p in ((row.get("history") or {}).get("search_phrases") or [])[:3]]})
                if BUCKET_RANK[row["bucket"]] < BUCKET_RANK[a["bucket"]] or (row["bucket"] == a["bucket"] and (row.get("scores") or {}).get("total", 0) > a["score"]):
                    keep = a["region_breakdown"]
                    a.update({**row, "region_breakdown": keep}); a["score"] = (row.get("scores") or {}).get("total", 0)
        rows = list(agg.values())
        for r in rows:
            r["region_countries_qualified"] = sum(1 for b in r["region_breakdown"] if b["bucket"] == "qualified")
            r["region_countries_emerging"] = sum(1 for b in r["region_breakdown"] if b["bucket"] == "emerging")
            r["reasons"] = r.get("reasons") or []
            if r["bucket"] in ("qualified", "emerging"):
                r["reasons"] = []
        for b in ("qualified", "emerging"):
            ranked = sorted([r for r in rows if r["bucket"] == b], key=lambda r: (-r["region_countries_qualified"], -r["region_countries_emerging"], -r["score"]))
            for i, r in enumerate(ranked, 1): r["rank"] = i
        for r in rows:
            r.setdefault("rank", 0); r["confidence"] = (r.get("scores") or {}).get("confidence", 0)
        self.db.save_results(rid, rows)
        counters = {"candidates": len(rows), "after_dedupe": len(rows), "qualified": sum(1 for r in rows if r["bucket"] == "qualified"),
                    "emerging": sum(1 for r in rows if r["bucket"] == "emerging"),
                    "marketplace_gaps": sum(1 for r in rows if (r.get("marketplace") or {}).get("gap") in ("FULL_GAP", "PARTIAL_GAP")),
                    "ubuy_gaps": sum(1 for r in rows if (r.get("ubuy") or {}).get("gap") in ("NOT_FOUND", "OTHER_COUNTRY_ONLY", "LISTED_UNAVAILABLE")),
                    "compliance_review": sum(1 for r in rows if (r.get("compliance") or {}).get("status") in ("RESTRICTED", "CONDITIONAL")),
                    "requests_used": req, "countries": len(st.get("children", {}))}
        self.db.update_run(rid, counters_json=json.dumps(counters))
        self.db.log(rid, "Region Orchestrator", f"Aggregated: {counters['qualified']} products are opportunities in at least one country, {counters['emerging']} emerging")

    # ---------------------------------------------------------------- single-country run
    def run(self, rid, ctx=None):
        ctx = ctx or self.contexts.get(rid) or RunContext(self.db, rid)
        run = self.db.get_run(rid); cfg = load_config(run["country_code"])
        f = self.fetcher_cls(self.db, self.s, ctx)
        st = json.loads(run["state_json"] or "{}") or {}
        st.setdefault("done", []); st.setdefault("cands", []); st.setdefault("dropped", []); st.setdefault("coverage", {})
        st.setdefault("opts", {}); st.setdefault("round", 1); st.setdefault("t0", time.time()); st.setdefault("rounds_log", [])
        self.db.update_run(rid, status="running", error=None)
        ctx.log("Orchestrator", f"Run {rid} started: {cfg['name']}, {run['period_days']} days, category {run['category']}" + (" (resumed)" if st["done"] else ""))
        try:
            for i, stage in enumerate(STAGES):
                if stage in st["done"]: continue
                ctx.check()
                self.db.update_run(rid, stage=STAGE_LABEL[stage], progress=round(100 * i / len(STAGES), 1))
                ctx.log("Orchestrator", f"Stage: {STAGE_LABEL[stage]}")
                t_stage = time.time()
                getattr(self, "st_" + stage)(rid, run, cfg, f, ctx, st)
                st["done"].append(stage); self._save(rid, st, f)
                ctx.log("Orchestrator", f"{STAGE_LABEL[stage]} finished in {int(time.time() - t_stage) // 60}m {int(time.time() - t_stage) % 60}s "
                        f"({f.n_requests} web requests so far)")
            self.deep_research(rid, run, cfg, f, ctx, st)
            self.db.update_run(rid, status="completed", stage="Completed", progress=100)
            ctx.log("Orchestrator", f"Completed. Network requests used: {f.n_requests}")
        except Cancelled:
            self._save(rid, st, f); self.db.update_run(rid, status="cancelled", stage="Cancelled (can be resumed)")
            ctx.log("Orchestrator", "Run cancelled by user - checkpoint saved", "warn")
        except Exception as e:
            self._save(rid, st, f); self.db.update_run(rid, status="failed", error=str(e)[:300])
            ctx.log("Orchestrator", f"Run failed: {e}\n{traceback.format_exc()[-300:]}", "error")
        return st

    # ---------------------------------------------------------------- deep research
    def deep_research(self, rid, run, cfg, f, ctx, st):
        """Keep researching new slices of the 'sells abroad' universe until the target number of opportunities is reached."""
        o = st.get("opts", {})
        target = int(o.get("target") or self.s.get("target_opportunities", 20))
        rounds = int(o.get("rounds") or self.s.get("max_research_rounds", 6))
        minutes = float(self.s.get("max_research_minutes", 150))
        budget = self.s["max_requests_per_run"]
        A = "Deep research"
        while True:
            q = sum(1 for c in st["cands"] if c.get("bucket") == "qualified")
            why = (f"target of {target} opportunities reached" if q >= target else f"round limit ({rounds}) reached" if st["round"] >= rounds else
                   f"time limit ({minutes:.0f} min) reached" if time.time() - st["t0"] > minutes * 60 else
                   "request budget nearly used" if f.n_requests > budget * 0.85 else None)
            if why:
                ctx.log(A, f"Stopping: {why}. {q} opportunities, {sum(1 for c in st['cands'] if c.get('bucket') == 'emerging')} emerging.")
                return
            ctx.check()
            st["round"] += 1; rn = st["round"]
            pages, total = universe.slice_for(rid, rn, int(self.s.get("universe_pages_per_round", 24)), run["category"])
            if not pages:
                ctx.log(A, f"Research universe exhausted ({total} source pages explored)."); return
            self.db.update_run(rid, stage=f"Deep research round {rn}/{rounds}: {q}/{target} opportunities so far", progress=min(99, round(100 * q / max(1, target), 1)))
            ctx.log(A, f"Round {rn}: {q}/{target} opportunities so far - exploring {len(pages)} new source pages: "
                    + ", ".join(sorted({p['src'] for p in pages}))[:300])
            raw, ok = universe.harvest(f, pages, ctx, time.strftime("%Y-%m-%d"))
            new, dropped = product_identification.identify(raw, self.s["candidate_pool_max"])
            have = {c["key"] for c in st["cands"]}
            known = self.db.recent_verdicts(cfg["code"], int(self.s.get("remember_sold_locally_days", 14)))
            fresh = [c for c in new if c["key"] not in have and c["key"] not in known]
            for c in fresh: c["round"] = rn
            st["cands"] += fresh
            ctx.log(A, f"Round {rn}: {ok}/{len(pages)} pages readable -> {len(new)} products, {len(fresh)} new "
                    f"({sum(1 for c in new if c['key'] in known)} skipped: confirmed sold locally in the last {self.s.get('remember_sold_locally_days', 14)} days)")
            st["rounds_log"].append({"round": rn, "pages": len(pages), "readable": ok, "new": len(fresh)})
            if fresh:
                for stage in ("history", "marketplace", "ubuy", "compliance", "sourcing", "report"):
                    getattr(self, "st_" + stage)(rid, run, cfg, f, ctx, st)
            self._save(rid, st, f)

    def _save(self, rid, st, f):
        c = st["cands"]
        counters = {"candidates": len(c) + len(st["dropped"]), "after_dedupe": len(c),
                    "qualified": sum(1 for x in c if x.get("bucket") == "qualified"), "emerging": sum(1 for x in c if x.get("bucket") == "emerging"),
                    "round": st.get("round", 1),
                    "marketplace_gaps": sum(1 for x in c if x.get("marketplace", {}).get("gap") in ("FULL_GAP", "PARTIAL_GAP", "LIKELY_GAP")),
                    "ubuy_gaps": sum(1 for x in c if x.get("ubuy", {}).get("gap") in ("NOT_FOUND", "OTHER_COUNTRY_ONLY", "LISTED_UNAVAILABLE")),
                    "compliance_review": sum(1 for x in c if x.get("compliance", {}).get("status") in ("RESTRICTED", "CONDITIONAL")),
                    "requests_used": f.n_requests}
        self.db.update_run(rid, state_json=json.dumps(st, default=str), counters_json=json.dumps(counters), health_json=json.dumps(f.health))

    def _par(self, items, fn, ctx, st=None, rid=None, f=None, every=10):
        done = 0
        with ThreadPoolExecutor(self.s["workers"]) as ex:
            futs = [ex.submit(fn, c) for c in items]
            for fu in futs:
                try: fu.result()
                except Cancelled: raise
                except Exception as e: ctx.log("Orchestrator", f"Item error: {e}", "warn")
                done += 1
                if st is not None and done % every == 0: self._save(rid, st, f)

    @staticmethod
    def _reject(c, why): c["status"], c["reasons"] = "rejected", [why]
    @staticmethod
    def _watch(c, why): c["status"], c["reasons"] = "watch", [why]
    @staticmethod
    def _live(st): return [c for c in st["cands"] if c["status"] == "active"]

    # ---------------------------------------------------------------- stages
    def st_discovery(self, rid, run, cfg, f, ctx, st):
        st["raw"], st["coverage"] = trend_discovery.discover(f, self.s, cfg, run["period_days"], run["category"], ctx, run_id=rid)

    def st_identification(self, rid, run, cfg, f, ctx, st):
        st["cands"], st["dropped"] = product_identification.identify(st.pop("raw", []), self.s["candidate_pool_max"])
        if st.get("opts", {}).get("skip_known", True):
            known = self.db.recent_verdicts(cfg["code"], int(self.s.get("remember_sold_locally_days", 14)))
            skip = [c for c in st["cands"] if c["key"] in known]
            st["cands"] = [c for c in st["cands"] if c["key"] not in known]
            if skip:
                ctx.log("Agent 4 Product Identification", f"{len(skip)} products skipped - confirmed as sold locally in an earlier run (last "
                        f"{self.s.get('remember_sold_locally_days', 14)} days); this run explores other products instead")
        ctx.log("Agent 4 Product Identification", f"{len(st['cands'])} specific products kept; {len(st['dropped'])} vague/duplicate/weak dropped. "
                + "Top: " + ", ".join(c["name"] for c in st["cands"][:12]))

    def st_history(self, rid, run, cfg, f, ctx, st):
        act = [c for c in self._live(st) if not c["done"].get("history")]
        # reserve slots for products selling abroad (Amazon US / global trends): the main source of new Ubuy opportunities
        intl = [c for c in act if all(x.get("scope") == "international" for x in c["signals"])]
        local = [c for c in act if c not in intl]
        n_int = min(len(intl), int(self.s.get("international_shortlist", 70)))
        short = local[: self.s["demand_shortlist"] - n_int] + intl[:n_int]
        keep = {id(c) for c in short}
        for c in act:
            if id(c) not in keep: self._reject(c, "Not shortlisted for demand validation (funnel limit)")
        def job(c):
            if c["done"].get("history"): return
            series = historical_analysis.analyse(f, self.s, cfg, c, run["period_days"], ctx)
            c["forecast"] = forecast_agent.forecast(cfg, c, run["period_days"])
            self.db.add_observations(rid, cfg["code"], c["key"], c["name"], "local_news_mentions", series, "google news (country edition)")
            self.db.add_observations(rid, cfg["code"], c["key"], c["name"], "local_search_suggestions",
                                     [(c["history"]["series_end"], c["history"]["series_end"], float(c["demand"]["local_search_matches"]))], "google autocomplete")
            level = sum(c["history"]["counts"][-3:]) / max(1, min(3, len(c["history"]["counts"])))
            self.db.review_forecasts(cfg["code"], c["key"], level)
            if c["forecast"].get("baseline") is not None:
                self.db.add_forecast(rid, cfg["code"], c["key"], run["period_days"], c["forecast"]["direction"], c["forecast"]["baseline"])
            c["done"]["history"] = True
        self._par(short, job, ctx, st, rid, f)
        n_em = 0
        for c in short:
            if "demand" not in c or c.get("_classified"): continue
            c["_classified"] = True
            d = c["demand"]
            if d["only_international"] and not d["searched_locally"]:
                c["track"] = "emerging"; n_em += 1          # keep: may become trending - still check the local gap
            elif d["score"] < self.s["min_demand_score"] and not d["local_evidence"]:
                self._reject(c, f"Weak local demand evidence (score {d['score']}, no local searches found)")
            elif not d["local_evidence"]:
                c["track"] = "emerging"; n_em += 1
        ctx.log("Agent 2/3 Demand & Forecast", f"{sum(1 for c in self._live(st) if c.get('track') != 'emerging')} products with proven local demand, "
                f"{n_em} early/international signals kept as emerging candidates")

    def st_marketplace(self, rid, run, cfg, f, ctx, st):
        # unmet-demand + imported/global products first; ultra-mainstream items are still checked but cost only 1 request (early stop)
        act = sorted([c for c in self._live(st) if "demand" in c and not c["done"].get("marketplace")], key=lambda c: (c.get("track") == "emerging", -(c["demand"]["score"] + 10 * min(3, c["demand"].get("unmet_signals", 0))
                                                                                    + (15 if any(x["kind"] in ("amazon_us", "amazon_list") for x in c["signals"]) else 0))))
        lim = self.s["marketplace_check_limit"]
        for c in act[lim:]: self._reject(c, "Not shortlisted for local supply check (funnel limit)")
        def job(c):
            if c["done"].get("marketplace"): return
            c["marketplace"] = marketplace_agent.verify(f, self.s, cfg, c, ctx); c["done"]["marketplace"] = True
            if c["marketplace"]["gap"] in ("NO_GAP", "FULL_GAP", "PARTIAL_GAP"):
                self.db.put_verdict(cfg["code"], c["key"], c["name"], c["marketplace"]["gap"], c["marketplace"]["reason"])
            for r in c["marketplace"]["results"]: self.db.add_evidence(rid, c["key"], "marketplace", r["marketplace"], r["url"], r["status"], r["reason"])
            if self.s.get("pipeline_checks", True) and c["marketplace"]["gap"] in ("FULL_GAP", "PARTIAL_GAP", "LIKELY_GAP"):
                self._deep_checks(rid, run, cfg, f, ctx, c)      # pipelined: Ubuy / import / sourcing / growth start right away
        self._par(act[:lim], job, ctx, st, rid, f)
        for c in self._live(st):
            if "marketplace" not in c: continue
            g = c["marketplace"]["gap"]
            if g == "NO_GAP": self._reject(c, "Already sold locally: " + c["marketplace"]["reason"])
            elif g == "UNVERIFIED" and c.get("track") != "emerging": self._watch(c, "Local availability unverified: " + c["marketplace"]["reason"])
        ctx.log("Agent 5 Local supply", f"{sum(1 for c in self._live(st) if c.get('marketplace', {}).get('gap') in ('FULL_GAP', 'PARTIAL_GAP', 'LIKELY_GAP'))} products show a local supply gap")

    def _deep_checks(self, rid, run, cfg, f, ctx, c):
        """Same checks the later stages run, started as soon as a product shows a local gap, so different websites
        (Ubuy, Amazon US, Google Trends, Google News) are worked on in parallel. Results are identical - only earlier."""
        if not c["done"].get("ubuy"):
            c["ubuy"] = ubuy_agent.verify(f, self.s, cfg, c, ctx); c["done"]["ubuy"] = True
            self.db.add_evidence(rid, c["key"], "ubuy", cfg.get("ubuy_domain") or "-", c["ubuy"].get("url"), c["ubuy"]["status"], c["ubuy"]["reason"])
        if not c["done"].get("compliance"):
            c["compliance"] = compliance_agent.screen(f, self.s, cfg, c, ctx); c["done"]["compliance"] = True
        if c["compliance"].get("status") not in ("RESTRICTED", "PROHIBITED") and not c["done"].get("sourcing"):
            c["sourcing"] = sourcing_agent.find(f, self.s, cfg, c, ctx); c["economics"] = profit_agent.analyse(cfg, c); c["done"]["sourcing"] = True
            for x in c["sourcing"]["suppliers"]: self.db.add_evidence(rid, c["key"], "sourcing", x["supplier_site"], x["url"], x["kind"], x["supplier"])
        if "growth" not in c and c["compliance"].get("status") != "PROHIBITED":
            c["growth"] = trend_growth.analyse(f, self.db, self.s, cfg, c, run["period_days"])

    def _open(self, st):
        """active + watchlist (not rejected): later checks also run for watchlist items so their cards are complete."""
        live = [c for c in st["cands"] if c["status"] == "active"]
        watch = sorted([c for c in st["cands"] if c["status"] == "watch" and "demand" in c], key=lambda c: -c["demand"]["score"])
        return live + watch[: int(self.s.get("watchlist_deep_checks", 40))]

    def st_ubuy(self, rid, run, cfg, f, ctx, st):
        act = self._open(st)
        def job(c):
            if c["done"].get("ubuy"): return
            c["ubuy"] = ubuy_agent.verify(f, self.s, cfg, c, ctx); c["done"]["ubuy"] = True
            self.db.add_evidence(rid, c["key"], "ubuy", cfg.get("ubuy_domain") or "-", c["ubuy"].get("url"), c["ubuy"]["status"], c["ubuy"]["reason"])
        self._par(act, job, ctx, st, rid, f)
        act = [c for c in act if "ubuy" in c]
        n_in = sum(1 for c in act if c["ubuy"]["gap"] == "AVAILABLE")
        ctx.log("Agent 6 Ubuy", f"{n_in} already in the Ubuy catalogue (ready to campaign), "
                f"{sum(1 for c in act if c['ubuy']['gap'] == 'NOT_FOUND')} not in catalogue (add SKU), "
                f"{sum(1 for c in act if c['ubuy']['gap'] == 'UNVERIFIED')} not checked (no catalogue feed)")

    def st_compliance(self, rid, run, cfg, f, ctx, st):
        todo = [c for c in self._open(st) if not c["done"].get("compliance")]
        act = todo[: self.s["deep_check_limit"]]
        for c in todo[self.s["deep_check_limit"]:]:
            if c["status"] == "active": self._watch(c, "Beyond deep-check limit; re-run to continue")
        def job(c):
            if c["done"].get("compliance"): return
            c["compliance"] = compliance_agent.screen(f, self.s, cfg, c, ctx); c["done"]["compliance"] = True
        self._par(act, job, ctx, st, rid, f)
        act = [c for c in st["cands"] if c["status"] != "rejected" and c.get("compliance")]     # incl. products checked early (pipelined)
        for c in act:
            if c["compliance"].get("status") == "PROHIBITED": self._reject(c, "Import prohibited: " + c["compliance"]["reason"])
        ctx.log("Agent 7 Compliance", f"{sum(1 for c in act if c['status'] == 'rejected')} prohibited; "
                f"{sum(1 for c in act if c.get('compliance', {}).get('status') in ('RESTRICTED', 'CONDITIONAL'))} need a certificate/permit check")

    def st_sourcing(self, rid, run, cfg, f, ctx, st):
        act = [c for c in self._open(st) if c.get("compliance") and c["compliance"].get("status") != "RESTRICTED"]
        def job(c):
            if c["done"].get("sourcing"): return
            c["sourcing"] = sourcing_agent.find(f, self.s, cfg, c, ctx); c["economics"] = profit_agent.analyse(cfg, c); c["done"]["sourcing"] = True
            for x in c["sourcing"]["suppliers"]: self.db.add_evidence(rid, c["key"], "sourcing", x["supplier_site"], x["url"], x["kind"], x["supplier"])
        self._par(act, job, ctx, st, rid, f)

    def st_report(self, rid, run, cfg, f, ctx, st):
        for c in st["cands"]:
            if c["status"] == "active" and c.get("track") == "emerging":
                c["status"] = "emerging"
                c["reasons"] = ["Early signal: " + ("trending internationally, not yet searched locally" if c["demand"].get("only_international") else "weak local demand so far")
                                + f"; local supply: {c.get('marketplace', {}).get('gap', 'n/a')}"]
            if c["status"] != "rejected" and "history" in c:
                if "economics" not in c: c["economics"] = profit_agent.analyse(cfg, c) if "sourcing" in c else {"missing": ["Not reached"], "assessable": False}
                c["scores"] = scoring_agent.score(c)
        report_agent.build(st["cands"], self.s, run["max_results"])
        # year-over-year growth (Google Trends + Google News) for opportunities / emerging, then re-score with it
        todo = [c for c in st["cands"] if c["bucket"] in ("qualified", "emerging") and "growth" not in c][: int(self.s.get("growth_checks_per_round", 60))]
        if todo:
            def gjob(c):
                c["growth"] = trend_growth.analyse(f, self.db, self.s, cfg, c, run["period_days"])
            self._par(todo, gjob, ctx)
            ok = sum(1 for c in todo if (c.get("growth") or {}).get("google_trends", {}).get("status") == "ok")
            ctx.log("Agent 13 Growth", f"Year-over-year growth for {len(todo)} products: {ok} from Google Trends, "
                    f"{sum(1 for c in todo if c.get('growth', {}).get('source') == 'Google News mentions')} from Google News mentions"
                    + ("" if ok else f" (Google Trends: {(todo[0].get('growth') or {}).get('google_trends', {}).get('status')})"))
            for c in st["cands"]:
                if c["status"] != "rejected" and "history" in c:
                    c["scores"] = scoring_agent.score(c)
            report_agent.build(st["cands"], self.s, run["max_results"])
        for c in st["cands"]:
            if c["bucket"] in ("qualified", "emerging"):
                c["campaign"] = campaign_agent.suggest(cfg, c)
                c["references"] = trend_growth.references(c, cfg)
                c["promotion"] = promotion_agent.plan(cfg, c)
        dropped = [{"key": "dropped-%d" % i, "name": d["name"], "brand": "", "model": "", "category": "-", "signals": [], "status": "rejected", "reasons": [d["reason"]],
                    "bucket": "rejected", "rank": 0, "scores": {"total": 0, "confidence": 0, "confidence_label": "n/a"}, "action": "No action - rejected."}
                   for i, d in enumerate(st["dropped"][:200])]
        rows = report_agent.to_rows(st["cands"] + dropped)
        self.db.save_results(rid, rows)
        ctx.log("Agent 11 Report", ", ".join(f"{sum(1 for r in rows if r['bucket'] == b)} {b}" for b in report_agent.BUCKETS))

def make(overrides=None, fetcher_cls=Fetcher):
    s = settings_mod.load(overrides)
    return Orchestrator(DB(s["db_path"]), s, fetcher_cls)
