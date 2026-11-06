"""Geography knowledge used by the demand radar: regions, languages, cities, currency words,
Google News editions and localized search-intent templates.

Everything here is used to make searches LOCAL to the destination country (gl / hl / ceid), and to
recognise local-intent phrases ("price in Lagos", "naira", "where to buy ... in Kenya")."""

# ---------------------------------------------------------------- regions
REGIONS = {
    "AFRICA": {"name": "Africa", "countries": [
        "DZ", "AO", "BJ", "BW", "BF", "BI", "CV", "CM", "CF", "TD", "KM", "CG", "CD", "CI", "DJ", "EG", "GQ", "ER", "SZ", "ET", "GA", "GM",
        "GH", "GN", "GW", "KE", "LS", "LR", "LY", "MG", "MW", "ML", "MR", "MU", "MA", "MZ", "NA", "NE", "NG", "RW", "ST", "SN", "SC", "SL",
        "SO", "ZA", "SS", "SD", "TZ", "TG", "TN", "UG", "ZM", "ZW"],
        "priority": ["NG", "KE", "ZA", "GH", "EG", "MA", "UG", "TZ", "ET", "RW", "CI", "SN", "ZM", "ZW", "MZ", "DZ", "TN", "BW", "NA", "MU", "CM", "AO"]},
    "WEST_AFRICA": {"name": "West Africa", "countries": ["NG", "GH", "CI", "SN", "BJ", "TG", "BF", "ML", "NE", "GN", "SL", "LR", "GM", "GW", "CV", "MR"],
                    "priority": ["NG", "GH", "CI", "SN", "BJ", "TG"]},
    "EAST_AFRICA": {"name": "East Africa", "countries": ["KE", "UG", "TZ", "RW", "ET", "BI", "SO", "DJ", "ER", "SS", "SC", "MU", "MG"],
                    "priority": ["KE", "UG", "TZ", "RW", "ET", "MU"]},
    "SOUTHERN_AFRICA": {"name": "Southern Africa", "countries": ["ZA", "BW", "NA", "ZM", "ZW", "MZ", "MW", "LS", "SZ", "AO"],
                        "priority": ["ZA", "ZM", "ZW", "BW", "NA", "MZ", "AO"]},
    "NORTH_AFRICA": {"name": "North Africa", "countries": ["EG", "MA", "DZ", "TN", "LY", "SD"], "priority": ["EG", "MA", "DZ", "TN"]},
    "GCC": {"name": "GCC / Gulf", "countries": ["AE", "SA", "KW", "QA", "BH", "OM"], "priority": ["AE", "SA", "KW", "QA", "BH", "OM"]},
    "MIDDLE_EAST": {"name": "Middle East", "countries": ["AE", "SA", "KW", "QA", "BH", "OM", "JO", "LB", "IQ", "IL", "TR", "YE", "SY", "IR", "PS"],
                    "priority": ["AE", "SA", "KW", "QA", "BH", "OM", "JO", "LB", "IQ", "TR"]},
    "SOUTH_ASIA": {"name": "South Asia", "countries": ["IN", "PK", "BD", "LK", "NP", "BT", "MV", "AF"], "priority": ["IN", "PK", "BD", "LK", "NP", "MV"]},
    "SOUTHEAST_ASIA": {"name": "Southeast Asia", "countries": ["SG", "MY", "ID", "TH", "VN", "PH", "KH", "LA", "MM", "BN", "TL"],
                       "priority": ["MY", "ID", "TH", "VN", "PH", "SG", "KH", "BN"]},
    "EAST_ASIA": {"name": "East Asia", "countries": ["JP", "KR", "CN", "HK", "TW", "MN"], "priority": ["JP", "KR", "HK", "TW", "MN"]},
    "CENTRAL_ASIA": {"name": "Central Asia & Caucasus", "countries": ["KZ", "UZ", "KG", "TJ", "TM", "AZ", "GE", "AM"], "priority": ["KZ", "UZ", "AZ", "GE", "AM", "KG"]},
    "EUROPE": {"name": "Europe", "countries": ["GB", "IE", "FR", "DE", "IT", "ES", "PT", "NL", "BE", "LU", "AT", "CH", "SE", "NO", "DK", "FI", "IS", "PL",
                                              "CZ", "SK", "HU", "RO", "BG", "GR", "HR", "SI", "RS", "BA", "ME", "MK", "AL", "EE", "LV", "LT", "CY", "MT", "UA", "MD", "BY"],
               "priority": ["GB", "DE", "FR", "IT", "ES", "NL", "PL", "SE", "IE", "GR", "PT", "RO", "CZ", "HU", "CY", "IS"]},
    "NORTH_AMERICA": {"name": "North America", "countries": ["US", "CA", "MX"], "priority": ["US", "CA", "MX"]},
    "LATAM": {"name": "Latin America & Caribbean", "countries": ["MX", "BR", "AR", "CO", "CL", "PE", "EC", "UY", "PY", "BO", "VE", "CR", "PA", "GT", "HN", "SV",
                                                                 "NI", "DO", "JM", "TT", "BS", "BB", "HT", "CU", "GY", "SR", "BZ"],
              "priority": ["MX", "BR", "CO", "CL", "PE", "AR", "EC", "CR", "PA", "DO", "JM", "TT", "UY"]},
    "OCEANIA": {"name": "Oceania", "countries": ["AU", "NZ", "FJ", "PG", "WS", "TO", "VU", "SB"], "priority": ["AU", "NZ", "FJ", "PG"]},
}

def region_options():
    return [{"code": "R-" + k, "name": v["name"], "n": len(v["countries"]), "priority": v["priority"]} for k, v in REGIONS.items()]

def resolve_region(code):
    """'R-AFRICA' -> region dict, else None."""
    if code and code.upper().startswith("R-"):
        return REGIONS.get(code.upper()[2:])
    return None

# ---------------------------------------------------------------- language
FR = {"FR", "BE", "LU", "MC", "CI", "SN", "CM", "BJ", "TG", "BF", "ML", "NE", "GN", "GA", "CG", "CD", "CF", "TD", "MG", "DJ", "KM", "BI", "HT", "MA", "DZ", "TN"}
AR = {"AE", "SA", "KW", "QA", "BH", "OM", "JO", "LB", "IQ", "EG", "LY", "SD", "YE", "SY", "PS", "MR"}
ES = {"ES", "MX", "AR", "CO", "CL", "PE", "EC", "UY", "PY", "BO", "VE", "CR", "PA", "GT", "HN", "SV", "NI", "DO", "CU", "GQ"}
PT = {"BR", "PT", "AO", "MZ", "CV", "GW", "ST", "TL"}
OTHER_LANG = {"BA": "bs", "ME": "sr", "MK": "mk", "AL": "sq", "XK": "sq", "DE": "de", "AT": "de", "CH": "de", "IT": "it", "NL": "nl", "PL": "pl", "SE": "sv", "NO": "no", "DK": "da", "FI": "fi", "CZ": "cs", "SK": "sk",
              "HU": "hu", "RO": "ro", "BG": "bg", "GR": "el", "HR": "hr", "SI": "sl", "RS": "sr", "TR": "tr", "RU": "ru", "UA": "uk", "JP": "ja", "KR": "ko",
              "CN": "zh-CN", "TW": "zh-TW", "HK": "zh-HK", "TH": "th", "VN": "vi", "ID": "id", "IL": "he", "IR": "fa", "KZ": "ru", "UZ": "uz", "AZ": "az",
              "GE": "ka", "AM": "hy", "LT": "lt", "LV": "lv", "EE": "et", "IS": "is", "BY": "ru", "MD": "ro", "MN": "mn", "KG": "ru", "TJ": "ru", "TM": "ru"}

def language(cc):
    cc = cc.upper()
    if cc in FR: return "fr"
    if cc in AR: return "ar"
    if cc in ES: return "es"
    if cc in PT: return "pt"
    return OTHER_LANG.get(cc, "en")

# Countries where English is widely used for online shopping searches even if another language dominates
ENGLISH_ALSO = AR | {"BA", "RS", "HR", "SI", "ME", "MK", "AL", "RO", "BG", "CZ", "SK", "HU", "PL", "UA", "IT", "AT", "CH", "BE", "PT", "ES", "FR", "MA", "DZ", "TN", "IL", "MY", "ID", "TH", "VN", "TR", "NL", "SE", "NO", "DK", "FI", "DE", "PL", "GR", "CY", "MT", "IS", "KZ", "UZ",
                     "AZ", "GE", "AM", "JP", "KR", "HK", "TW", "CI", "SN", "CM", "RW", "BI", "MZ", "AO", "LB", "JO"}

# Google News editions known to exist (hl-gl:ceid). Others fall back to the US English edition + country name.
NEWS_EDITIONS = {
    "en": {"US", "GB", "AU", "CA", "IN", "IE", "NZ", "ZA", "NG", "KE", "GH", "UG", "TZ", "ZW", "ET", "NA", "BW", "PK", "BD", "SG", "MY", "PH", "IL", "LB"},
    "fr": {"FR", "BE", "CH", "CA", "MA", "SN", "CI", "CM"},
    "ar": {"AE", "SA", "EG", "LB"},
    "es": {"ES", "MX", "AR", "CO", "CL", "PE", "VE", "CU", "US"},
    "pt": {"BR", "PT"},
}
NEWS_EDITIONS_OTHER = {"DE": "de", "AT": "de", "IT": "it", "NL": "nl", "PL": "pl", "SE": "sv", "NO": "no", "CZ": "cs", "HU": "hu", "RO": "ro", "GR": "el",
                       "TR": "tr", "RU": "ru", "UA": "uk", "JP": "ja", "KR": "ko", "TW": "zh-Hant", "HK": "zh-Hant", "CN": "zh-Hans", "TH": "th", "VN": "vi",
                       "ID": "id", "LT": "lt", "LV": "lv", "SK": "sk", "SI": "sl", "RS": "sr", "BG": "bg"}

def news_edition(cc):
    """-> (hl, gl, ceid, localized: bool)"""
    cc = cc.upper()
    for lang in ("en", language(cc)):
        if cc in NEWS_EDITIONS.get(lang, set()):
            return (f"{lang}-{cc}" if lang in ("en", "es", "pt", "fr") else lang), cc, f"{cc}:{lang}", True
    if cc in NEWS_EDITIONS_OTHER:
        l = NEWS_EDITIONS_OTHER[cc]
        return l, cc, f"{cc}:{l}", True
    return "en-US", "US", "US:en", False

# ---------------------------------------------------------------- local-intent vocabulary
CITIES = {
    "NG": ["lagos", "abuja", "port harcourt", "ibadan", "kano"], "KE": ["nairobi", "mombasa", "kisumu"], "GH": ["accra", "kumasi"],
    "ZA": ["johannesburg", "cape town", "durban", "pretoria"], "EG": ["cairo", "alexandria"], "MA": ["casablanca", "rabat", "marrakech"],
    "UG": ["kampala"], "TZ": ["dar es salaam", "arusha"], "ET": ["addis ababa"], "RW": ["kigali"], "CI": ["abidjan"], "SN": ["dakar"],
    "ZM": ["lusaka"], "ZW": ["harare"], "MZ": ["maputo"], "DZ": ["algiers", "alger"], "TN": ["tunis"], "BW": ["gaborone"], "NA": ["windhoek"],
    "CM": ["douala", "yaounde"], "AO": ["luanda"], "MU": ["port louis"],
    "AE": ["dubai", "abu dhabi", "sharjah"], "SA": ["riyadh", "jeddah", "dammam"], "KW": ["kuwait city"], "QA": ["doha"], "BH": ["manama"],
    "OM": ["muscat"], "JO": ["amman"], "LB": ["beirut"], "IQ": ["baghdad", "erbil"], "TR": ["istanbul", "ankara"], "IL": ["tel aviv"],
    "IN": ["mumbai", "delhi", "bangalore", "hyderabad", "chennai"], "PK": ["karachi", "lahore", "islamabad"], "BD": ["dhaka", "chittagong"],
    "LK": ["colombo"], "NP": ["kathmandu"], "MV": ["male"],
    "MY": ["kuala lumpur", "penang"], "ID": ["jakarta", "surabaya"], "TH": ["bangkok"], "VN": ["ho chi minh", "hanoi"], "PH": ["manila", "cebu"],
    "SG": ["singapore"], "KH": ["phnom penh"], "BN": ["bandar seri begawan"],
    "GB": ["london", "manchester"], "DE": ["berlin", "munich"], "FR": ["paris", "lyon"], "IT": ["milan", "rome"], "ES": ["madrid", "barcelona"],
    "NL": ["amsterdam"], "PL": ["warsaw"], "SE": ["stockholm"], "IE": ["dublin"], "GR": ["athens"], "PT": ["lisbon"], "RO": ["bucharest"],
    "CZ": ["prague"], "HU": ["budapest"], "CY": ["nicosia", "limassol"], "IS": ["reykjavik"],
    "US": ["new york", "los angeles"], "CA": ["toronto", "vancouver"], "MX": ["cdmx", "monterrey", "guadalajara"], "BR": ["sao paulo", "rio"],
    "AR": ["buenos aires"], "CO": ["bogota", "medellin"], "CL": ["santiago"], "PE": ["lima"], "EC": ["quito", "guayaquil"], "CR": ["san jose"],
    "PA": ["panama"], "DO": ["santo domingo"], "JM": ["kingston"], "TT": ["port of spain"], "UY": ["montevideo"],
    "AU": ["sydney", "melbourne", "brisbane"], "NZ": ["auckland", "wellington"], "FJ": ["suva"], "PG": ["port moresby"],
    "BA": ["sarajevo", "banja luka", "tuzla", "mostar"], "RS": ["beograd", "belgrade", "novi sad"], "HR": ["zagreb", "split"], "SI": ["ljubljana"],
    "ME": ["podgorica"], "MK": ["skopje"], "AL": ["tirana"], "BG": ["sofia"], "SK": ["bratislava"], "AT": ["wien", "vienna"], "CH": ["zurich", "geneva"],
    "BE": ["brussels", "antwerp"], "DK": ["copenhagen"], "NO": ["oslo"], "FI": ["helsinki"], "UA": ["kyiv", "kiev"],
    "MG": ["antananarivo", "tana", "toamasina", "tamatave", "mahajanga", "majunga", "fianarantsoa", "antsirabe", "toliara", "diego", "mada"],
    "KZ": ["almaty", "astana"], "UZ": ["tashkent"], "AZ": ["baku"], "GE": ["tbilisi"], "AM": ["yerevan"], "JP": ["tokyo"], "KR": ["seoul"], "HK": ["hong kong"], "TW": ["taipei"],
}
CURRENCY_WORDS = {
    "NGN": ["naira", "ngn", "₦"], "KES": ["ksh", "kes", "shilling", "shillings"], "GHS": ["cedi", "cedis", "ghs", "gh₵"], "ZAR": ["rand", "zar"],
    "EGP": ["egp", "egyptian pound", "جنيه"], "MAD": ["dirham", "dh", "mad"], "UGX": ["ugx", "shillings"], "TZS": ["tzs", "tsh"], "ETB": ["birr", "etb"],
    "RWF": ["rwf", "frw"], "XOF": ["fcfa", "cfa", "xof"], "XAF": ["fcfa", "cfa", "xaf"], "ZMW": ["kwacha", "zmw"], "ZWG": ["usd", "zig"], "MZN": ["meticais", "mzn"],
    "DZD": ["dzd", "dinar", "da"], "TND": ["dinar", "tnd", "dt"], "BWP": ["pula", "bwp"], "NAD": ["nad", "n$"], "AOA": ["kwanza", "aoa"], "MUR": ["rs", "mur"],
    "AED": ["aed", "dirham", "درهم"], "SAR": ["sar", "riyal", "ريال"], "KWD": ["kwd", "kd", "dinar"], "QAR": ["qar", "riyal"], "BHD": ["bhd", "bd", "dinar"],
    "OMR": ["omr", "rial"], "JOD": ["jod", "jd", "dinar"], "INR": ["rs", "inr", "rupees", "₹"], "PKR": ["pkr", "rs", "rupees"], "BDT": ["taka", "bdt", "৳"],
    "LKR": ["lkr", "rs"], "NPR": ["npr", "rs"], "MYR": ["rm", "ringgit"], "IDR": ["rp", "rupiah"], "THB": ["baht", "฿"], "VND": ["vnd", "dong", "đ"],
    "PHP": ["php", "peso", "₱"], "GBP": ["£", "gbp"], "EUR": ["€", "eur", "euro"], "USD": ["$", "usd"], "CAD": ["cad"], "AUD": ["aud"], "NZD": ["nzd"],
    "BAM": ["km", "bam"], "RSD": ["rsd", "din", "dinara"], "HUF": ["ft", "huf"], "CZK": ["kč", "czk"], "RON": ["lei", "ron"], "BGN": ["лв", "bgn"],
    "UAH": ["грн", "₴", "uah"], "MKD": ["ден", "mkd"], "PLN": ["zł", "pln"], "CHF": ["chf"], "DKK": ["kr", "dkk"], "NOK": ["kr", "nok"], "SEK": ["kr", "sek"],
    "MGA": ["ariary", "mga"],
    "MXN": ["mxn", "pesos"], "BRL": ["r$", "reais"], "COP": ["cop", "pesos"], "CLP": ["clp", "pesos"], "PEN": ["soles", "s/"], "TRY": ["tl", "lira"],
}

# Phrases inside a search suggestion that signal the buyer cannot easily get the product locally
UNMET_PATTERNS = {
    "en": ["where to buy", "where can i buy", "available in", "availability in", "ship to", "shipping to", "delivery to", "deliver to", "from amazon",
           "from usa", "from us", "from uk", "from china", "order from", "import", "imported", "buy online in", "original", "authentic", "ubuy"],
    "fr": ["où acheter", "ou acheter", "disponible à", "disponible en", "livraison à", "livraison en", "commander depuis", "importer", "importation"],
    "es": ["dónde comprar", "donde comprar", "disponible en", "envío a", "envio a", "importar"],
    "pt": ["onde comprar", "disponível em", "disponivel em", "envio para", "importar"],
    "ar": ["من وين", "اين اشتري", "أين أشتري", "متوفر في", "شحن الى"],
}
PRICE_WORDS = {"en": ["price", "prices", "cost", "how much"], "fr": ["prix"], "es": ["precio", "precios"], "pt": ["preço", "preco"], "ar": ["سعر", "اسعار", "أسعار"],
               "de": ["preis"], "it": ["prezzo"], "bs": ["cijena", "cijene"], "hr": ["cijena", "cijene"], "sr": ["cena", "cene", "cijena"],
               "mk": ["цена"], "sq": ["cmimi"], "ro": ["pret"], "cs": ["cena"], "sk": ["cena"], "hu": ["ár"], "bg": ["цена"], "uk": ["ціна"], "sl": ["cena"], "tr": ["fiyat", "fiyatı"], "pl": ["cena"], "nl": ["prijs"], "id": ["harga"], "vi": ["giá"], "th": ["ราคา"]}
BUY_WORDS = {"en": ["buy", "shop", "store", "sale", "online"], "fr": ["acheter", "boutique"], "es": ["comprar", "tienda"], "pt": ["comprar", "loja"],
             "ar": ["شراء", "متجر"], "de": ["kaufen"], "it": ["comprare"], "tr": ["satın al"], "pl": ["kupić"], "nl": ["kopen"], "id": ["beli"]}

def intent_templates(cc, country_name):
    """Autocomplete probe templates. {p} = product (or prefix letter for open discovery)."""
    lang = language(cc)
    cn = country_name.lower()
    city = (CITIES.get(cc.upper()) or [cn])[0]
    en = [f"{{p}} price in {cn}", f"where to buy {{p}} in {cn}", f"{{p}} in {cn}", f"buy {{p}} {city}", f"how to order {{p}} to {cn}"]
    loc = {
        "fr": [f"prix {{p}} {cn}", f"où acheter {{p}} {city}", f"{{p}} {city}"],
        "es": [f"precio {{p}} {cn}", f"donde comprar {{p}} en {city}", f"{{p}} {city}"],
        "pt": [f"preço {{p}} {cn}", f"onde comprar {{p}} {city}", f"{{p}} {city}"],
        "ar": [f"سعر {{p}}", f"{{p}} {city}"],
        "bs": [f"{{p}} cijena", f"{{p}} {city}", f"{{p}} bih"], "hr": [f"{{p}} cijena", f"{{p}} {city}"], "sr": [f"{{p}} cena", f"{{p}} {city}"],
        "sl": [f"{{p}} cena", f"{{p}} {city}"], "ro": [f"{{p}} pret", f"{{p}} {city}"], "cs": [f"{{p}} cena", f"{{p}} {city}"], "pl": [f"{{p}} cena", f"{{p}} {city}"],
        "hu": [f"{{p}} ár", f"{{p}} {city}"], "de": [f"{{p}} preis", f"{{p}} kaufen {city}"], "it": [f"{{p}} prezzo", f"{{p}} {city}"],
        "nl": [f"{{p}} prijs", f"{{p}} kopen"], "tr": [f"{{p}} fiyat", f"{{p}} {city}"], "uk": [f"{{p}} ціна", f"{{p}} {city}"],
    }.get(lang, [])
    if lang == "en":
        return en
    return loc + (en[:3] if cc.upper() in ENGLISH_ALSO or not loc else [])

def local_markers(cc, country_name):
    cc = cc.upper()
    from .country_registry import COUNTRIES
    cur = COUNTRIES.get(cc, {}).get("currency", "")
    return {"country": country_name.lower(), "cities": CITIES.get(cc, []), "currency": CURRENCY_WORDS.get(cur, [cur.lower()] if cur else []),
            "lang": language(cc)}


# Google suggestions are country-specific only where the country has a big search population in that language.
# Elsewhere (e.g. Madagascar, French) suggestions are largely France-wide, so a suggestion only counts as LOCAL demand
# when it names the country, a city or the currency.
LOCALISED_SUGGEST = {"US", "GB", "CA", "AU", "IN", "PK", "BD", "NG", "KE", "ZA", "PH", "MY", "ID", "SG", "AE", "SA", "EG", "TR", "DE", "FR", "IT", "ES", "MX",
                     "BR", "AR", "CO", "CL", "PE", "JP", "KR", "TH", "VN", "PL", "NL", "SE", "UA", "RU", "MA", "DZ", "GH", "IE", "NZ", "PT", "BE", "CH", "AT",
                     "RO", "CZ", "HU", "GR", "IL", "IQ", "KZ", "UZ", "LK", "NP"}
# retailer names that show a suggestion belongs to ANOTHER market (France, Spain, US ...)
FOREIGN_STORES = {"fnac", "darty", "boulanger", "cdiscount", "leclerc", "auchan", "carrefour", "but", "conforama", "rakuten", "el corte ingles",
                  "mediamarkt", "media markt", "saturn", "walmart", "target", "best buy", "bestbuy", "costco", "argos", "currys", "kmart", "flipkart",
                  "lidl", "action", "kiabi", "decathlon", "micromania", "leroy merlin", "castorama", "jb hi-fi", "harvey norman"}

def needs_local_marker(cc):
    return cc.upper() not in LOCALISED_SUGGEST
