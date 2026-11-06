"""Agent 10: weighted opportunity score + separate evidence-confidence score. Missing evidence scores 0 (never positive)."""
WEIGHTS = {"demand": 35, "growth": 10, "local_gap": 30, "ubuy_gap": 5, "sourcing": 10, "profit": 5, "compliance": 5}
GROWTH = {"Sudden popularity": 90, "Increasing demand": 80, "Emerging product demand": 75, "Actively searched (no dated history)": 55, "Seasonal interest": 55,
          "Stable interest": 45, "Declining interest": 10, "Insufficient data": 0}
LOCAL = {"FULL_GAP": 100, "PARTIAL_GAP": 65, "LIKELY_GAP": 55, "NO_GAP": 0, "UNVERIFIED": 0}
UBUY = {"AVAILABLE": 100, "OTHER_COUNTRY_ONLY": 90, "NOT_FOUND": 70, "LISTED_UNAVAILABLE": 60, "UNVERIFIED": 50}   # readiness to sell, not a gate
LEGAL = {"NO RESTRICTION FLAGGED": 100, "GENERALLY PERMITTED": 100, "CONDITIONAL": 55, "RESTRICTED": 10, "PROHIBITED": 0, "UNVERIFIED": 30}

def score(cand):
    h, d, fc = cand.get("history", {}), cand.get("demand", {}), cand.get("forecast", {})
    g = GROWTH.get(h.get("trend_class"), 0)
    yoy = (cand.get("growth") or {}).get("yoy_pct")
    if yoy is not None:                              # measured year-over-year growth outranks the short-window trend class
        g = max(g, 100 if yoy >= 200 else max(0, min(100, 50 + yoy / 4)))
    if str(fc.get("direction", "")).startswith("Rising"): g = min(100, g + 10)
    if str(fc.get("direction", "")).startswith("Falling"): g = max(0, g - 15)
    m = cand.get("economics", {}).get("margin_pct")
    pr = 0 if m is None else (100 if m >= 40 else 80 if m >= 25 else 60 if m >= 15 else 35 if m >= 5 else 15 if m > 0 else 0)
    sup = cand.get("sourcing", {})
    so = 0 if not sup.get("route_found") else (100 if any(x.get("kind") == "source store" for x in sup.get("suppliers", [])) else 60)
    mk, ub, lg = cand.get("marketplace", {}), cand.get("ubuy", {}), cand.get("compliance", {})
    comp = {"demand": d.get("score", 0), "growth": g, "local_gap": LOCAL.get(mk.get("gap"), 0), "ubuy_gap": UBUY.get(ub.get("gap"), 0),
            "sourcing": so, "profit": pr, "compliance": LEGAL.get(lg.get("status"), 0)}
    total = round(sum(comp[k] * w / 100 for k, w in WEIGHTS.items()), 1)
    rows = mk.get("results", [])
    direct = sum(1 for r in rows if r.get("status") != "UNVERIFIED" and not r.get("index_only"))
    idx = sum(1 for r in rows if r.get("index_only"))
    mk_cov = ((direct + 0.5 * idx) / len(rows)) if rows else (0.5 if mk.get("local_web", {}).get("status") == "CHECKED" else 0)
    cc = {"local search evidence": (30, min(1, d.get("local_search_matches", 0) / 3)),
          "trend / news data": (10, min(1, (sum(1 for c in h.get("counts", []) if c) + d.get("sources", 0)) / 5)),
          "marketplace coverage": (30, mk_cov),
          "ubuy verification": (5, 0 if ub.get("gap") in (None, "UNVERIFIED") else 1),
          "legal screening": (10, 1 if lg.get("status") else 0),
          "sourcing evidence": (10, 1 if any(x.get("price") for x in sup.get("suppliers", [])) else (0.7 if sup.get("route_found") else 0)),
          "economics": (5, 1 if cand.get("economics", {}).get("profit") is not None else 0)}
    conf = round(sum(w * v for w, v in cc.values()), 1)
    return {"components": comp, "weights": WEIGHTS, "total": total, "confidence": conf,
            "confidence_label": "High" if conf >= 70 else "Medium" if conf >= 45 else "Low", "confidence_parts": {k: round(v[1], 2) for k, v in cc.items()}}
