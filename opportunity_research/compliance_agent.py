"""Agent 7: import / regulatory SCREENING (never legal clearance).

Rules = country rules from country_configs/<country>.json  +  GLOBAL_RULES below (product classes that are regulated in most
countries: radio/telecom type approval, drones, e-cigarettes, medical devices, cosmetics registration, supplements, lithium batteries...).
Statuses: PROHIBITED / RESTRICTED / CONDITIONAL / NO RESTRICTION FLAGGED.
'NO RESTRICTION FLAGGED' means no screening rule matched - a customs broker must still confirm HS code and duty."""
import re
from . import search
from .evidence import now_date, domain_of

SEVERITY = {"PROHIBITED": 4, "RESTRICTED": 3, "CONDITIONAL": 2, "GENERALLY PERMITTED": 1, "NO RESTRICTION FLAGGED": 1, "UNVERIFIED": 0}

REGULATORS = {   # name of the national body most often involved (screening hint only)
    "NG": {"telecom": "NCC (Nigerian Communications Commission)", "health": "NAFDAC", "standards": "SON (SONCAP)", "aviation": "NCAA", "customs": "Nigeria Customs Service"},
    "KE": {"telecom": "Communications Authority of Kenya", "health": "Pharmacy and Poisons Board / KEBS", "standards": "KEBS (PVoC)", "aviation": "KCAA", "customs": "KRA Customs"},
    "GH": {"telecom": "National Communications Authority", "health": "Food and Drugs Authority (FDA Ghana)", "standards": "Ghana Standards Authority", "aviation": "GCAA", "customs": "GRA Customs"},
    "ZA": {"telecom": "ICASA", "health": "SAHPRA", "standards": "NRCS / SABS", "aviation": "SACAA", "customs": "SARS Customs"},
    "EG": {"telecom": "NTRA", "health": "Egyptian Drug Authority", "standards": "GOEIC", "aviation": "ECAA", "customs": "Egyptian Customs Authority"},
    "MA": {"telecom": "ANRT", "health": "DMP / ONSSA", "standards": "IMANOR", "aviation": "DGAC", "customs": "ADII"},
    "UG": {"telecom": "UCC", "health": "NDA Uganda", "standards": "UNBS", "aviation": "UCAA", "customs": "URA"},
    "TZ": {"telecom": "TCRA", "health": "TMDA", "standards": "TBS", "aviation": "TCAA", "customs": "TRA"},
    "AE": {"telecom": "TDRA", "health": "MOHAP", "standards": "MoIAT (ECAS)", "aviation": "GCAA", "customs": "Dubai/UAE Customs"},
    "SA": {"telecom": "CST", "health": "SFDA", "standards": "SASO (SABER)", "aviation": "GACA", "customs": "ZATCA"},
    "KW": {"telecom": "CITRA", "health": "MOH Kuwait", "standards": "PAI", "aviation": "DGCA", "customs": "Kuwait Customs"},
    "PK": {"telecom": "PTA", "health": "DRAP", "standards": "PSQCA", "aviation": "PCAA", "customs": "Pakistan Customs (FBR)"},
    "IN": {"telecom": "WPC / DoT", "health": "CDSCO", "standards": "BIS", "aviation": "DGCA", "customs": "CBIC"},
}

def _reg(cc, k):
    return REGULATORS.get(cc.upper(), {}).get(k, {"telecom": "national telecom regulator", "health": "national health-products regulator",
                                                    "standards": "national standards bureau", "aviation": "civil aviation authority", "customs": "national customs"}[k])

def global_rules(cc):
    return [
        {"id": "g-ecig", "pattern": r"\b(vape|vaping|e-?cig|e-?cigarette|heated tobacco|hookah pen|disposable vape|shisha)\b", "status": "RESTRICTED",
         "regime": "Tobacco / e-cigarette controls (banned or licensed in many countries)", "authority": _reg(cc, "health"), "hs_hint": "8543 / 2404"},
        {"id": "g-drone", "pattern": r"\b(drone|fpv|quadcopter|dji mini|dji neo|dji air|dji avata)\b", "status": "RESTRICTED",
         "regime": "Drone import/operation permit", "authority": _reg(cc, "aviation"), "hs_hint": "8806"},
        {"id": "g-radio", "pattern": r"\b(walkie|two-way radio|starlink|satellite|router|mifi|pocket wifi|signal booster|cb radio|gps tracker)\b", "status": "CONDITIONAL",
         "regime": "Radio / telecom equipment type approval", "authority": _reg(cc, "telecom"), "hs_hint": "8517 / 8526"},
        {"id": "g-medical", "pattern": r"\b(blood pressure monitor|pulse oximeter|glucometer|cgm|freestyle libre|hearing aid|nebulizer|thermometer|tens unit|breast pump|wheelchair)\b",
         "status": "CONDITIONAL", "regime": "Medical device registration", "authority": _reg(cc, "health"), "hs_hint": "9018 / 9019 / 9021 / 9025"},
        {"id": "g-supp", "pattern": r"\b(creatine|whey|protein powder|pre workout|supplement|vitamin|collagen|baby formula|melatonin)\b", "status": "CONDITIONAL",
         "regime": "Food supplement / food import registration", "authority": _reg(cc, "health"), "hs_hint": "2106 / 1901"},
        {"id": "g-cosm", "pattern": r"\b(serum|sunscreen|moisturizer|cleanser|toner|retinol|niacinamide|snail mucin|foundation|mascara|perfume|body mist|lotion|hair oil|shampoo|lip|cosmetic)\b",
         "status": "CONDITIONAL", "regime": "Cosmetics product notification / registration", "authority": _reg(cc, "health"), "hs_hint": "3304 / 3303 / 3305"},
        {"id": "g-battery", "pattern": r"\b(power bank|portable power station|solar generator|ecoflow|jackery|bluetti|jump starter|lithium|e-?bike|electric scooter|hoverboard)\b",
         "status": "CONDITIONAL", "regime": "Lithium-battery dangerous-goods shipping rules (UN38.3, air-freight limits)", "authority": "Carrier / IATA DGR + " + _reg(cc, "standards"),
         "hs_hint": "8507 / 8711"},
        {"id": "g-weapons", "pattern": r"\b(knife|taser|stun gun|pepper spray|crossbow|airsoft|bb gun|night vision|tactical)\b", "status": "RESTRICTED",
         "regime": "Weapons / dual-use controls", "authority": _reg(cc, "customs"), "hs_hint": "9304 / 8211"},
        {"id": "g-cbd", "pattern": r"\b(cbd|cannabis|hemp oil|thc|kratom|delta-8)\b", "status": "PROHIBITED", "regime": "Narcotics / controlled substances",
         "authority": _reg(cc, "health"), "hs_hint": "1302"},
        {"id": "g-elec", "pattern": r"\b(air fryer|kettle|blender|hair dryer|straightener|air styler|microwave|heater|inverter|generator|stabilizer|charger)\b",
         "status": "CONDITIONAL", "regime": "Electrical product conformity (plug type / voltage / certificate of conformity)", "authority": _reg(cc, "standards"), "hs_hint": "8516 / 8509 / 8504"},
    ]

def screen(f, s, cfg, cand, ctx=None):
    text = " ".join([cand["name"], cand["noun"], cand["category"]] + cand.get("alt_names", []))
    country_rules = cfg.get("regulatory_rules", [])
    rules = country_rules + [g for g in global_rules(cfg["code"]) if not any(r["id"].split("-", 1)[-1] == g["id"][2:] for r in country_rules)]
    matched = [r for r in rules if re.search(r["pattern"], text, re.I)]
    out = {"checked_at": now_date(), "rules": [], "requirements": [], "official_sources": [], "official_hits": [], "hs_hint": None,
           "hs_status": "HS code not established - customs-broker confirmation required",
           "duty_info": f"Duty/taxes must be confirmed against the official tariff of {cfg['name']} for the final HS code.", "expert_review": True}
    if not matched:
        out.update(status="NO RESTRICTION FLAGGED", reason="No screening rule matched. Standard import: confirm HS code and duty with a customs broker.")
    else:
        status = max((r["status"] for r in matched), key=lambda x: SEVERITY[x])
        out["status"] = status
        out["rules"] = [{"id": r["id"], "regime": r["regime"], "authority": r["authority"], "status": r["status"], "note": r.get("note", "")} for r in matched]
        out["requirements"] = list(dict.fromkeys(r["regime"] + " (" + r["authority"] + ")" for r in matched if r["status"] != "GENERALLY PERMITTED"))
        hs = [r["hs_hint"] for r in matched if r.get("hs_hint")]
        out["hs_hint"] = hs[0] if hs else None
        out["official_sources"] = list(dict.fromkeys(u for r in matched for u in r.get("source_urls", [])))
        out["reason"] = "; ".join(f"{r['regime']} -> {r['status']}" for r in matched)
    if cfg.get("official_domains") and out["status"] != "PROHIBITED" and s.get("enable_official_search", True):
        sites = " OR ".join("site:" + d for d in cfg["official_domains"][:6])
        try:
            items, _ = search.web(f, s, f"{cand['name']} import ({sites})", cfg["code"], 10)
            for h in items:
                if any(domain_of(h["url"]).endswith(d) for d in cfg["official_domains"]):
                    out["official_hits"].append({"title": h["title"][:120], "url": h["url"]})
        except Exception:
            pass
        out["official_hits"] = out["official_hits"][:3]
    return out
