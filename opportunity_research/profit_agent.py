"""Agent 9: economics only from evidence + user-supplied assumptions in the country config ('economics')."""
import re

def _val(p):
    return p["value"] if p else None

def analyse(cfg, cand):
    eco = cfg.get("economics", {}) or {}
    local_cur = cfg.get("currency")
    sup = next((x for x in cand.get("sourcing", {}).get("suppliers", []) if x.get("price_value")), None)
    out = {"purchase_cost": None, "landed_cost": None, "selling_price": None, "profit": None, "margin_pct": None, "min_price_for_target": None,
           "missing": [], "status": "Supplier quotation required", "basis": [], "currency": local_cur}
    # purchase cost (supplier LISTED price - not a quotation)
    purchase = None
    if sup:
        cur = {"US$": "USD", "$": "USD", "£": "GBP", "€": "EUR", "₦": "NGN", "₹": "INR", "KSh": "KES", "Ksh": "KES", "GH₵": "GHS", "R": "ZAR"}.get(
            sup["price_currency"] or "", sup["price_currency"] or "")
        rate = 1.0 if cur == local_cur else (eco.get("fx_rates", {}) or {}).get(f"{cur}_{local_cur}")
        out["purchase_cost"] = {"listed": sup["price"], "source": sup["url"], "type": "supplier listed price (estimate, not a quotation)"}
        if rate: purchase = sup["price_value"] * rate; out["purchase_cost"]["local"] = round(purchase, 2)
        else: out["missing"].append(f"FX rate {cur}_{local_cur} (set economics.fx_rates)")
    else:
        out["missing"].append("Supplier price")
    # selling price: only from evidence (local listing / Ubuy reference)
    ref = cand.get("marketplace", {}).get("reference_price") or cand.get("ubuy", {}).get("price")
    sp = None
    if ref:
        from .evidence import parse_price
        pp = parse_price(ref)
        if pp:
            sp = pp["value"]; out["selling_price"] = {"value": sp, "raw": ref, "type": "observed price of a comparable/matching listing"}
    else:
        out["missing"].append("Reference selling price (no comparable listing observed)")
    ship, duty, tax = eco.get("shipping_per_item"), eco.get("duty_rate_pct"), eco.get("tax_rate_pct")
    for k, v in (("shipping_per_item", ship), ("duty_rate_pct", duty), ("tax_rate_pct", tax)):
        if v is None: out["missing"].append(f"economics.{k} (user assumption not set)")
    if purchase is not None and None not in (ship, duty, tax):
        d = purchase * duty / 100; t = (purchase + ship + d) * tax / 100
        out["landed_cost"] = round(purchase + ship + d + t + (eco.get("other_import_per_item") or 0), 2)
        out["basis"].append("Landed = purchase + shipping + duty + tax + other (rates from user config, confirm with customs broker)")
    sx, ff = eco.get("selling_expense_pct"), eco.get("fulfilment_per_item")
    if out["landed_cost"] is not None and sp is not None and sx is not None and ff is not None:
        out["profit"] = round(sp - out["landed_cost"] - sp * sx / 100 - ff, 2); out["margin_pct"] = round(out["profit"] / sp * 100, 1)
        out["status"] = "Estimated from observed prices + configured assumptions"
    elif out["landed_cost"] is not None:
        out["status"] = "Landed cost estimated; profit not computable (selling price/expenses missing)"
    elif purchase is not None or sup:
        out["status"] = "Partial - landed cost/profit not computable"
    tm = eco.get("target_margin_pct")
    if out["landed_cost"] is not None and sx is not None and ff is not None and tm is not None and (1 - sx / 100 - tm / 100) > 0:
        out["min_price_for_target"] = round((out["landed_cost"] + ff) / (1 - sx / 100 - tm / 100), 2)
    out["assessable"] = bool(sup or sp)
    return out
