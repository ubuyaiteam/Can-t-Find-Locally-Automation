"""Flask integration: register `opportunity_bp` on any Flask app (new or existing)."""
import io, json, os
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, send_file, abort, Response
from . import orchestrator, report_agent
from .country_registry import list_countries, coverage, region_coverage
from . import geo, healthcheck
from .settings import BASE

opportunity_bp = Blueprint("opportunity", __name__, url_prefix="/opportunity",
                           template_folder=os.path.join(BASE, "templates"))
_ORCH = {}
PERIODS = [15, 30, 45, 60, 90]

def orch():
    if "o" not in _ORCH:
        _ORCH["o"] = orchestrator.make()
        _ORCH["o"].db.mark_interrupted()
        try: _ORCH["o"].db.prune_cache(_ORCH["o"].s.get("cache_keep_days", 7))      # keeps the database from growing without limit
        except Exception: pass      # runs that were alive when the server stopped can be resumed
    return _ORCH["o"]

def _buckets(rid):
    db = orch().db
    return {b: db.get_results(rid, b) for b in report_agent.BUCKETS}

def _cov(code):
    return region_coverage(code) if geo.resolve_region(code) else coverage(code)

@opportunity_bp.route("/")
def index():
    from .product_identification import CATEGORIES
    runs = orch().db.list_runs()
    for r in runs: r["counters"] = json.loads(r.pop("counters_json") or "{}")
    return render_template("opportunity/index.html", countries=list_countries(), regions=geo.region_options(), periods=PERIODS, categories=CATEGORIES,
                           runs=runs, track=orch().db.forecast_track_record(), region_max=orch().s.get("region_max_countries", 6))

@opportunity_bp.route("/api/country/<code>")
def api_country(code):
    try: return jsonify(_cov(code))
    except KeyError: abort(404)

@opportunity_bp.route("/health")
def health_page():
    return render_template("opportunity/health.html", countries=list_countries())

@opportunity_bp.route("/api/health/<code>")
def api_health(code):
    from .net import Fetcher, RunContext
    o = orch()
    try:
        return jsonify(healthcheck.run(Fetcher(o.db, o.s, RunContext()), o.s, code, request.args.get("q") or None))
    except KeyError:
        abort(404)

@opportunity_bp.route("/start", methods=["POST"])
def start():
    code = request.form.get("country", "NG"); period = int(request.form.get("period", 30))
    if period not in PERIODS: period = 30
    reg = geo.resolve_region(code); picked = None
    if reg:
        n = max(1, min(len(reg["countries"]), int(request.form.get("region_n") or orch().s.get("region_max_countries", 6))))
        picked = [c for c in request.form.getlist("region_countries") if c in reg["countries"]] or reg["priority"][:n]
    opts = {"target": max(1, min(100, int(request.form.get("target") or 20))),
            "rounds": {"quick": 1, "standard": 4, "deep": 8}.get(request.form.get("depth", "standard"), 4),
            "skip_known": request.form.get("skip_known", "1") == "1"}
    rid = orch().start(code, period, request.form.get("category", "ALL") or "ALL", min(100, int(request.form.get("max_results", 100))), region_countries=picked, opts=opts)
    return redirect(url_for("opportunity.run_page", rid=rid))

@opportunity_bp.route("/run/<int:rid>")
def run_page(rid):
    run = orch().db.get_run(rid) or abort(404)
    kids = orch().db.children(rid)
    for k in kids: k["counters"] = json.loads(k.pop("counters_json") or "{}")
    parent = orch().db.get_run(run["parent_id"]) if run.get("parent_id") else None
    from .net import RENDERER
    return render_template("opportunity/run.html", run=run, cov=_cov(run["country_code"]), children=kids, parent=parent, browser_ok=RENDERER.available(),
                           is_region=bool(geo.resolve_region(run["country_code"])))

@opportunity_bp.route("/api/run/<int:rid>")
def api_run(rid):
    db = orch().db; run = db.get_run(rid) or abort(404)
    after = int(request.args.get("after", 0))
    return jsonify({"id": rid, "status": run["status"], "stage": run["stage"], "progress": run["progress"], "error": run["error"],
                    "counters": json.loads(run["counters_json"] or "{}"), "health": json.loads(run["health_json"] or "{}"), "logs": db.get_logs(rid, after),
                    "alive": orch().is_active(rid)})

@opportunity_bp.route("/api/run/<int:rid>/results")
def api_results(rid):
    return jsonify(_buckets(rid))

@opportunity_bp.route("/run/<int:rid>/cancel", methods=["POST"])
def cancel(rid):
    orch().cancel(rid); return jsonify({"ok": True})

@opportunity_bp.route("/run/<int:rid>/resume", methods=["POST"])
def resume(rid):
    run = orch().db.get_run(rid) or abort(404)
    if run["status"] in ("cancelled", "interrupted", "failed"):
        st = json.loads(run["state_json"] or "{}")
        orch().start(run["country_code"], run["period_days"], run["category"], run["max_results"], resume_id=rid, region_countries=st.get("countries"))
    return jsonify({"ok": True})

@opportunity_bp.route("/run/<int:rid>/download/<fmt>")
def download(rid, fmt):
    db = orch().db; run = db.get_run(rid) or abort(404)
    b = _buckets(rid); name = f"ubuy_opportunities_{run['country_code']}_{run['period_days']}d_run{rid}"
    if fmt == "xlsx":
        buf = io.BytesIO(); report_agent.export_xlsx(buf, run, b, health=json.loads(run["health_json"] or "{}")); buf.seek(0)
        return send_file(buf, as_attachment=True, download_name=name + ".xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    kind = request.args.get("kind", "qualified")
    if fmt == "csv" and kind in b:
        return Response(report_agent.export_csv(b[kind]), mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename={name}_{kind}.csv"})
    abort(404)
