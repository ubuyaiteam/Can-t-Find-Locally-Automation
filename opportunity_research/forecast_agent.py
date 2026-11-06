"""Agent 3: transparent statistical forecast (linear trend over measured buckets). Estimate, not a guarantee."""
from datetime import date
from .historical_analysis import slope, bucket_days
INSUFFICIENT = "Insufficient data for reliable forecast."

def forecast(cfg, cand, horizon):
    h = cand["history"]; counts = h["counts"]; total, nz, n = sum(counts), sum(1 for c in counts if c), len(counts)
    month = date.today().month
    months = {(month + i) % 12 + 1 for i in range(0, horizon // 30 + 2)}
    seasonal = [x["label"] for x in cfg.get("seasonal_hints", []) if months & set(x["months"]) and (not x.get("categories") or cand["category"] in x["categories"])]
    risks = ["Forecast is a statistical extrapolation of dated local news mentions, not a prediction of sales.",
             "Local search suggestions prove that people search for the product, not how many units they buy."]
    if h.get("google_trends_mean") is None:
        risks.append("No Google Trends series was available for this product.")
    if total < 5 or nz < 3:
        return {"direction": INSUFFICIENT, "confidence": None, "confidence_label": "n/a", "baseline": None, "seasonal": seasonal,
                "evidence": f"{total} mentions across {nz} of {n} periods", "risks": risks, "measured": False, "horizon_days": horizon}
    b, a, r2 = slope(counts); m = max(1, round(horizon / h["bucket_days"]))
    pred = max(0.0, sum(a + b * (n + i) for i in range(m)) / m); base = sum(counts[-3:]) / min(3, n)
    chg = (pred - base) / max(base, 0.5)
    d = "Rising" if chg > 0.2 else ("Falling" if chg < -0.2 else "Flat / stable")
    conf = min(1.0, total / 12) * 0.5 + max(0, r2) * 0.3 + min(1.0, nz / n) * 0.2
    lab = "High" if conf >= 0.7 else ("Medium" if conf >= 0.4 else "Low")
    if seasonal: risks.append("Seasonal effects may amplify or distort the trend: " + "; ".join(seasonal))
    return {"direction": f"{d} (est. {chg*100:+.0f}% vs recent level)", "confidence": round(conf, 2), "confidence_label": lab, "baseline": round(base, 2),
            "predicted_level": round(pred, 2), "seasonal": seasonal, "evidence": f"Linear fit over {n} periods, {total} mentions, R²={r2:.2f}",
            "risks": risks, "measured": False, "horizon_days": horizon}
