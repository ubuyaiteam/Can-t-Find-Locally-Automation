"""Country registry (ISO list ~195 countries/territories) + per-country research configuration."""
import glob, json, os
from .settings import BASE

_RAW = """AF|Afghanistan|AFN;AL|Albania|ALL;DZ|Algeria|DZD;AD|Andorra|EUR;AO|Angola|AOA;AG|Antigua and Barbuda|XCD;AR|Argentina|ARS;AM|Armenia|AMD;AU|Australia|AUD;AT|Austria|EUR;AZ|Azerbaijan|AZN;BS|Bahamas|BSD;BH|Bahrain|BHD;BD|Bangladesh|BDT;BB|Barbados|BBD;BY|Belarus|BYN;BE|Belgium|EUR;BZ|Belize|BZD;BJ|Benin|XOF;BT|Bhutan|BTN;BO|Bolivia|BOB;BA|Bosnia and Herzegovina|BAM;BW|Botswana|BWP;BR|Brazil|BRL;BN|Brunei|BND;BG|Bulgaria|EUR;BF|Burkina Faso|XOF;BI|Burundi|BIF;CV|Cabo Verde|CVE;KH|Cambodia|KHR;CM|Cameroon|XAF;CA|Canada|CAD;CF|Central African Republic|XAF;TD|Chad|XAF;CL|Chile|CLP;CN|China|CNY;CO|Colombia|COP;KM|Comoros|KMF;CG|Congo|XAF;CD|DR Congo|CDF;CR|Costa Rica|CRC;CI|Côte d'Ivoire|XOF;HR|Croatia|EUR;CU|Cuba|CUP;CY|Cyprus|EUR;CZ|Czechia|CZK;DK|Denmark|DKK;DJ|Djibouti|DJF;DM|Dominica|XCD;DO|Dominican Republic|DOP;EC|Ecuador|USD;EG|Egypt|EGP;SV|El Salvador|USD;GQ|Equatorial Guinea|XAF;ER|Eritrea|ERN;EE|Estonia|EUR;SZ|Eswatini|SZL;ET|Ethiopia|ETB;FJ|Fiji|FJD;FI|Finland|EUR;FR|France|EUR;GA|Gabon|XAF;GM|Gambia|GMD;GE|Georgia|GEL;DE|Germany|EUR;GH|Ghana|GHS;GR|Greece|EUR;GD|Grenada|XCD;GT|Guatemala|GTQ;GN|Guinea|GNF;GW|Guinea-Bissau|XOF;GY|Guyana|GYD;HT|Haiti|HTG;HN|Honduras|HNL;HK|Hong Kong|HKD;HU|Hungary|HUF;IS|Iceland|ISK;IN|India|INR;ID|Indonesia|IDR;IR|Iran|IRR;IQ|Iraq|IQD;IE|Ireland|EUR;IL|Israel|ILS;IT|Italy|EUR;JM|Jamaica|JMD;JP|Japan|JPY;JO|Jordan|JOD;KZ|Kazakhstan|KZT;KE|Kenya|KES;KI|Kiribati|AUD;XK|Kosovo|EUR;KW|Kuwait|KWD;KG|Kyrgyzstan|KGS;LA|Laos|LAK;LV|Latvia|EUR;LB|Lebanon|LBP;LS|Lesotho|LSL;LR|Liberia|LRD;LY|Libya|LYD;LI|Liechtenstein|CHF;LT|Lithuania|EUR;LU|Luxembourg|EUR;MG|Madagascar|MGA;MW|Malawi|MWK;MY|Malaysia|MYR;MV|Maldives|MVR;ML|Mali|XOF;MT|Malta|EUR;MH|Marshall Islands|USD;MR|Mauritania|MRU;MU|Mauritius|MUR;MX|Mexico|MXN;FM|Micronesia|USD;MD|Moldova|MDL;MC|Monaco|EUR;MN|Mongolia|MNT;ME|Montenegro|EUR;MA|Morocco|MAD;MZ|Mozambique|MZN;MM|Myanmar|MMK;NA|Namibia|NAD;NR|Nauru|AUD;NP|Nepal|NPR;NL|Netherlands|EUR;NZ|New Zealand|NZD;NI|Nicaragua|NIO;NE|Niger|XOF;NG|Nigeria|NGN;KP|North Korea|KPW;MK|North Macedonia|MKD;NO|Norway|NOK;OM|Oman|OMR;PK|Pakistan|PKR;PW|Palau|USD;PS|Palestine|ILS;PA|Panama|PAB;PG|Papua New Guinea|PGK;PY|Paraguay|PYG;PE|Peru|PEN;PH|Philippines|PHP;PL|Poland|PLN;PT|Portugal|EUR;QA|Qatar|QAR;RO|Romania|RON;RU|Russia|RUB;RW|Rwanda|RWF;KN|Saint Kitts and Nevis|XCD;LC|Saint Lucia|XCD;VC|Saint Vincent and the Grenadines|XCD;WS|Samoa|WST;SM|San Marino|EUR;ST|Sao Tome and Principe|STN;SA|Saudi Arabia|SAR;SN|Senegal|XOF;RS|Serbia|RSD;SC|Seychelles|SCR;SL|Sierra Leone|SLE;SG|Singapore|SGD;SK|Slovakia|EUR;SI|Slovenia|EUR;SB|Solomon Islands|SBD;SO|Somalia|SOS;ZA|South Africa|ZAR;KR|South Korea|KRW;SS|South Sudan|SSP;ES|Spain|EUR;LK|Sri Lanka|LKR;SD|Sudan|SDG;SR|Suriname|SRD;SE|Sweden|SEK;CH|Switzerland|CHF;SY|Syria|SYP;TW|Taiwan|TWD;TJ|Tajikistan|TJS;TZ|Tanzania|TZS;TH|Thailand|THB;TL|Timor-Leste|USD;TG|Togo|XOF;TO|Tonga|TOP;TT|Trinidad and Tobago|TTD;TN|Tunisia|TND;TR|Türkiye|TRY;TM|Turkmenistan|TMT;TV|Tuvalu|AUD;UG|Uganda|UGX;UA|Ukraine|UAH;AE|United Arab Emirates|AED;GB|United Kingdom|GBP;US|United States|USD;UY|Uruguay|UYU;UZ|Uzbekistan|UZS;VU|Vanuatu|VUV;VA|Vatican City|EUR;VE|Venezuela|VES;VN|Vietnam|VND;YE|Yemen|YER;ZM|Zambia|ZMW;ZW|Zimbabwe|ZWG"""
COUNTRIES = {}
for _row in _RAW.split(";"):
    c, n, cur = _row.split("|")
    COUNTRIES[c] = {"code": c, "name": n, "currency": cur}

CONFIG_DIR = os.path.join(BASE, "country_configs")
DEFAULT_CFG = {"ubuy_domain": None, "ubuy_search_url": None, "ubuy_reference_domains": [], "marketplaces": [],
               "category_marketplaces": [], "bestseller_pages": [], "official_sources": [], "official_domains": [],
               "regulatory_rules": [], "seasonal_hints": [], "economics": {}, "news_market": "en-US", "trends_geo": None}

def load_config(code):
    from . import market_directory
    code = code.upper()
    base = COUNTRIES.get(code)
    if not base:
        raise KeyError(code)
    cfg = json.loads(json.dumps(DEFAULT_CFG)); cfg.update(base); cfg["configured"] = False
    d = market_directory.for_country(code)
    if d:
        cfg.update(d); cfg["directory"] = True
    for p in glob.glob(os.path.join(CONFIG_DIR, "*.json")):
        try:
            with open(p, encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception:
            continue
        if str(d.get("code", "")).upper() == code:
            cfg.update(d); cfg["configured"] = True
    # BUGFIX v2: DEFAULT_CFG has trends_geo=None, so setdefault() never fired and Google Trends was skipped for every
    # country except India.
    cfg["trends_geo"] = cfg.get("trends_geo") or code
    return cfg

def coverage(code):
    """Research-coverage indicator: which verification layers have real sources configured."""
    cfg = load_config(code)
    from . import geo
    layers = {"Local search demand (Google, localised)": True, "Local marketplaces": bool(cfg["marketplaces"]),
              "Ubuy storefront": bool(cfg["ubuy_search_url"]), "Import screening rules": True,
              "Country-specific legal rules": bool(cfg["regulatory_rules"])}
    n = sum(layers.values())
    level = "Full" if n == 5 else ("Good" if layers["Local marketplaces"] and layers["Ubuy storefront"] else ("Partial" if layers["Local marketplaces"] else "Basic"))
    notes = []
    if not layers["Local marketplaces"]: notes.append("no marketplace directory: supply is checked through local web search only (lower confidence)")
    if not glob.glob(os.path.join(BASE, "data", "ubuy_catalog", f"{code.upper()}*")) and not glob.glob(os.path.join(BASE, "data", "ubuy_catalog", f"{code.lower()}*")):
        notes.append(f"tip: add data/ubuy_catalog/{code.upper()}.tsv (Merchant Center feed) so results show which products are already in the Ubuy catalogue")
    return {"code": cfg["code"], "name": cfg["name"], "currency": cfg["currency"], "level": level, "layers": layers,
            "language": geo.language(cfg["code"]), "news_edition": geo.news_edition(cfg["code"])[2],
            "marketplaces": [m["name"] for m in cfg["marketplaces"]], "ubuy_domain": cfg.get("ubuy_domain"),
            "note": "; ".join(notes)}

def list_countries():
    out = []
    for c in sorted(COUNTRIES.values(), key=lambda x: x["name"]):
        cv = coverage(c["code"])
        out.append({"code": c["code"], "name": c["name"], "currency": c["currency"], "coverage": cv["level"]})
    return out

def region_coverage(code):
    from . import geo
    reg = geo.resolve_region(code)
    if not reg:
        raise KeyError(code)
    return {"code": code.upper(), "name": reg["name"], "level": "Region", "countries": [{"code": c, "name": COUNTRIES[c]["name"], "coverage": coverage(c)["level"]}
            for c in reg["countries"] if c in COUNTRIES], "priority": reg["priority"], "layers": {}, "note": ""}
