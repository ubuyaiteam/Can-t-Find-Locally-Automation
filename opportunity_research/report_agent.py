"""Agent 11: qualification gate, ranking, flat report rows, XLSX/CSV export."""
import csv, io
from .evidence import now_date

FIELDS = ["Rank", "Product name", "Brand / model", "Category", "Why it is an opportunity", "Local search demand (observed phrases)", "Historical demand findings",
          "Future trend forecast", "Demand score", "Marketplace verification results", "Local market availability status", "Ubuy destination availability",
          "Legal and import status", "Sourcing route", "Estimated purchase cost", "Estimated landed cost", "Potential selling price", "Estimated profit and margin",
          "YoY growth", "Google Trends YoY", "News mentions YoY", "Opportunity score", "Confidence level", "Ubuy link", "Suggested SKU", "Campaign keywords", "Ad headlines", "Landing page", "Promotion plan", "Risks", "Recommended action",
          "Source URLs", "References", "Verification dates", "Bucket", "Reasons"]
BUCKETS = ("qualified", "emerging", "watchlist", "rejected")

def classify(cand, s):
    """Final gate. qualified = proven local demand + verified local gap + not orderable on Ubuy + no legal block + sourcing route.
    emerging  = early / international trend with an open local gap but not yet strong local search demand ("may become trending")."""
    if cand["status"] == "rejected": return "rejected", cand["reasons"]
    d, mk, ub, lg, sp = (cand.get(k, {}) for k in ("demand", "marketplace", "ubuy", "compliance", "sourcing"))
    if cand["status"] == "emerging": return "emerging", cand["reasons"]
    if cand["status"] == "watch": return "watchlist", cand["reasons"]
    why = []
    if not d.get("local_evidence"): why.append("Local demand not established")
    if mk.get("gap") not in ("FULL_GAP", "PARTIAL_GAP", "LIKELY_GAP"): why.append(f"Local supply gap not verified ({mk.get('gap', 'unchecked')})")
    if lg.get("status") in ("PROHIBITED", "RESTRICTED"): why.append(f"Legal status {lg.get('status')}: compliance review first")
    if not sp.get("route_found") and not sp.get("unverified") and ub.get("gap") != "AVAILABLE": why.append("No sourcing route found (not on Amazon US / source stores)")
    if s.get("strict_qualification", False) and not cand.get("economics", {}).get("assessable"): why.append("Commercial viability not assessable")
    return ("qualified", []) if not why else ("watchlist", why)

def action(bucket, c):
    lg = c.get("compliance", {}).get("status")
    if bucket == "qualified":
        g = c.get("ubuy", {}).get("gap")
        if g == "AVAILABLE": a = "Ready to sell: already in the Ubuy catalogue - launch the suggested search campaign now"
        elif g == "OTHER_COUNTRY_ONLY": a = "Quick win: SKU exists on another Ubuy store - enable it for this country, then launch the campaign"
        elif g == "NOT_FOUND": a = "Add the SKU (source listing below) to the Ubuy store, then launch the suggested campaign"
        else: a = "Confirm the SKU is in the Ubuy catalogue, then launch the suggested campaign"
        if lg == "CONDITIONAL": a += "; confirm the flagged certification/registration with the customs broker first"
        return a + "."
    if bucket == "emerging":
        return "Monitor: early/international trend with an open local gap. Pre-list the SKU and re-run in 2-4 weeks; launch ads once local searches appear."
    if bucket == "rejected": return "No action - rejected."
    r = " ".join(c.get("reasons", []))
    if "Legal" in r or "compliance" in r.lower(): return "Compliance review by import expert before any commercial work."
    if "unverified" in r.lower() or "UNVERIFIED" in r: return "Verify local marketplaces manually (or enable Playwright / a search API key) and re-run."
    return "Manual review: collect the missing evidence listed in reasons."

def _promo_text(pr):
    if not pr: return ""
    lines = [f"Priority: {pr['priority']} | Message: {pr['message']}", f"Timing: {pr['timing']}"]
    for ch in pr["channels"]:
        lines.append(f"- {ch['channel']}: " + "; ".join(ch["do"]))
    if pr.get("price_note"): lines.append(pr["price_note"])
    return "\n".join(lines)

def flat(c):
    h, fc, mk, ub, lg, sp, ec, d, cp = (c.get(k, {}) or {} for k in ("history", "forecast", "marketplace", "ubuy", "compliance", "sourcing", "economics", "demand", "campaign"))
    sup = "; ".join(f"{x['supplier'][:40]} ({x['country']}) {x['url']} price={x['price'] or 'n/a'}" for x in sp.get("suppliers", [])[:3]) or sp.get("reason", "Verify manually")
    lw = mk.get("local_web", {}) or {}
    urls = [e["url"] for e in h.get("evidence", [])[:3]] + [r["url"] for r in mk.get("results", []) if r.get("url")][:5] + \
           [x["url"] for x in lw.get("sellers", [])[:3]] + ([ub["url"]] if ub.get("url") else []) + lg.get("official_sources", [])[:2] + \
           [x["url"] for x in lg.get("official_hits", [])] + [x["url"] for x in sp.get("suppliers", [])[:2]]
    mkres = "; ".join(f"{r['marketplace']}: {r['status']}" + (f" [{r['method']}]" if r.get("method") else "") for r in mk.get("results", [])) or "n/a"
    if lw.get("status") == "CHECKED": mkres += f"; local web sellers: {len(lw.get('sellers', []))}"
    pm = f"{ec['profit']} ({ec['margin_pct']}%)" if ec.get("profit") is not None else ec.get("status", "Supplier quotation required")
    sc = c.get("scores", {})
    phrases = [p["phrase"] for p in h.get("search_phrases", [])[:8]]
    comp = d.get("components", {})
    why = []
    if d.get("local_search_matches"): why.append(f"{d['local_search_matches']} local search suggestions ({d.get('local_intent_matches', 0)} with price/where-to-buy intent)")
    if d.get("unmet_signals"): why.append(f"{d['unmet_signals']} 'can't find it' signals")
    if mk.get("gap") in ("FULL_GAP", "PARTIAL_GAP"): why.append(mk.get("reason", ""))
    if d.get("only_international"): why.append("trending abroad, not yet searched locally")
    why.append(f"trend: {h.get('trend_class', 'n/a')}")
    return {"Rank": c.get("rank", ""), "Product name": c["name"], "Brand / model": f"{c.get('brand','')} {c.get('model','')}".strip(), "Category": c["category"],
            "Why it is an opportunity": "; ".join(x for x in why if x),
            "Local search demand (observed phrases)": " | ".join(phrases) or "none observed",
            "Historical demand findings": f"{h.get('trend_class','n/a')}; {h.get('mentions',0)} dated local mentions in last {h.get('period_days','?')} days; buckets={h.get('counts')}",
            "Future trend forecast": f"{fc.get('direction','n/a')} | confidence {fc.get('confidence_label','n/a')} | {fc.get('evidence','')}",
            "Demand score": f"{d.get('score', '')} " + (str({k: v for k, v in comp.items() if v}) if comp else ""),
            "Marketplace verification results": f"{mkres} (verified {mk.get('verified',0)}/{mk.get('checked',0)})",
            "Local market availability status": f"{mk.get('gap','not checked')} - {mk.get('reason','')}", "Ubuy destination availability": f"{ub.get('status','not checked')} - {ub.get('reason','')}",
            "Legal and import status": f"{lg.get('status','not checked')} | HS hint: {lg.get('hs_hint') or 'n/a (broker to confirm)'} | {lg.get('reason','')}",
            "Sourcing route": sup, "Estimated purchase cost": (ec.get("purchase_cost") or {}).get("listed") or "Supplier quotation required",
            "Estimated landed cost": ec.get("landed_cost") if ec.get("landed_cost") is not None else "Not computable: " + ", ".join(ec.get("missing", [])[:3]),
            "Potential selling price": (ec.get("selling_price") or {}).get("raw") or "Not established", "Estimated profit and margin": pm,
            "YoY growth": (c.get("growth") or {}).get("headline", "not measured"),
            "Google Trends YoY": (lambda g: f"{g.get('label')} ({g.get('geo')}: avg {g.get('this_period_avg')} vs {g.get('last_year_avg')}) {g.get('url')}" if g.get("status") == "ok"
                                  else f"{g.get('status', 'not measured')} {g.get('url') or ''}".strip())((c.get("growth") or {}).get("google_trends") or {}),
            "News mentions YoY": (lambda n: f"{n.get('label')} ({n.get('this_period')} vs {n.get('last_year')} mentions) {n.get('url')}" if n else "not measured")((c.get("growth") or {}).get("news")),
            "References": "\n".join(f"[{r['type']}] {r['title']}" + (f" – {r['url']}" if r.get("url") else "") for r in (c.get("references") or [])),
            "Opportunity score": sc.get("total", ""), "Ubuy link": ub.get("url") or ub.get("search_url") or "", "Confidence level": f"{sc.get('confidence_label','')} ({sc.get('confidence','')})",
            "Suggested SKU": f"{(cp.get('sku') or {}).get('title', '')} | source: {(cp.get('sku') or {}).get('source_listing') or (cp.get('sku') or {}).get('source_search', '')}" if cp else "",
            "Campaign keywords": " ".join(cp.get("keywords_exact", [])[:8] + cp.get("keywords_phrase", [])[:3]) if cp else "",
            "Ad headlines": " | ".join(cp.get("headlines", [])[:4]) if cp else "", "Landing page": cp.get("landing_page") or "" if cp else "",
            "Promotion plan": _promo_text(c.get("promotion")),
            "Risks": " | ".join(fc.get("risks", [])[:3]), "Recommended action": c.get("action", ""), "Source URLs": "\n".join(dict.fromkeys(u for u in urls if u)),
            "Verification dates": f"market {mk.get('checked_at','-')}; ubuy {ub.get('checked_at','-')}; legal {lg.get('checked_at','-')}; source {sp.get('checked_at','-')}",
            "Bucket": c.get("bucket", ""), "Reasons": "; ".join(c.get("reasons", []))}

def build(cands, s, max_results):
    """Assign buckets, rank qualified, return list ready for DB."""
    for c in cands:
        b, why = classify(c, s); c["bucket"], c["reasons"] = b, why
        if "scores" not in c: c["scores"] = {"total": 0, "confidence": 0, "confidence_label": "n/a"}
        c["action"] = action(b, c)
    q = sorted([c for c in cands if c["bucket"] == "qualified"], key=lambda c: (-c["scores"]["total"], -c["scores"]["confidence"]))
    for i, c in enumerate(q, 1):
        if i > max_results:
            c["bucket"], c["reasons"] = "watchlist", [f"Qualified but beyond requested maximum of {max_results}"]; c["rank"] = 0
        else: c["rank"] = i
    em = sorted([c for c in cands if c["bucket"] == "emerging"], key=lambda c: (-c["scores"]["total"], -c["scores"]["confidence"]))
    for i, c in enumerate(em, 1): c["rank"] = i
    for c in cands: c.setdefault("rank", 0)
    return cands

def to_rows(cands):
    return [{"key": c["key"], "bucket": c["bucket"], "rank": c.get("rank", 0), "score": c["scores"]["total"], "confidence": c["scores"]["confidence"], **c} for c in cands]

def export_csv(cands):
    buf = io.StringIO(); w = csv.DictWriter(buf, fieldnames=FIELDS); w.writeheader()
    for c in cands: w.writerow(flat(c))
    return ("\ufeff" + buf.getvalue()).encode("utf-8")

def export_xlsx(path_or_buf, run, buckets, coverage=None, health=None):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    wb = Workbook(); wb.remove(wb.active)
    for name, rows in (("Opportunities", buckets.get("qualified", [])), ("Emerging", buckets.get("emerging", [])), ("Watchlist", buckets.get("watchlist", [])),
                       ("Rejected", buckets.get("rejected", []))):
        ws = wb.create_sheet(name); ws.append(FIELDS)
        for c in ws[1]: c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="0F4C5C"); c.alignment = Alignment(wrap_text=True, vertical="top")
        for r in rows:
            ws.append([("" if v is None else v) for v in flat(r).values()])
        for i in range(1, len(FIELDS) + 1):
            ws.column_dimensions[ws.cell(1, i).column_letter].width = 12 if i in (1, 9, 19) else 40
        for row in ws.iter_rows(min_row=2):
            for c in row: c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.freeze_panes = "C2"
    ws = wb.create_sheet("Run info")
    for k, v in [("Country / region", run["country_name"]), ("Period (days)", run["period_days"]), ("Category", run["category"]), ("Run created (UTC)", run["created_at"]), ("Exported", now_date()),
                 ("Note", "Demand figures are public-interest proxies, not sales. Legal status is rule-based screening - not legal advice or clearance.")]:
        ws.append([k, v])
    for h, v in (health or {}).items(): ws.append([f"Source health: {h}", str(v)])
    wb.save(path_or_buf)
