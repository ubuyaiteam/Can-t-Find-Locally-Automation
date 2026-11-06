"""Built-in directory of local marketplaces + Ubuy storefronts per country.

* `search_url` uses {q} (url-encoded), {q_plus} or {q_hyphen}.
* `kind`: "marketplace" (formal e-commerce), "retailer" (single chain), "classifieds" (Jiji/OLX style: second-hand / grey supply).
* Every marketplace is ALSO checked through the search index (`site:domain "product"`) when the direct page is blocked
  (Cloudflare / JavaScript), so blocked sites no longer make a country unverifiable.
* A country_configs/<name>.json file with the same "code" overrides / extends anything here.
* Patterns are best-effort: run the Source health check page (or `python diagnose.py NG`) on your machine after installing
  and correct any pattern that fails. Ubuy domains are marked `ubuy_verified: False` until the health check confirms them.
"""

def M(name, domain, url, kind="marketplace", render=False):
    return {"name": name, "domain": domain, "search_url": url, "kind": kind, "render": render}

def jumia(tld, label):
    return M(f"Jumia {label}", f"jumia.{tld}", f"https://www.jumia.{tld}/catalog/?q={{q}}", render=True)

def jiji(tld, label):
    return M(f"Jiji {label}", f"jiji.{tld}", f"https://jiji.{tld}/search?query={{q}}", "classifieds", render=True)

def amazon(tld, label):
    return M(f"Amazon {label}", f"amazon.{tld}", f"https://www.amazon.{tld}/s?k={{q}}")

def noon(path, label):
    return M(f"Noon {label}", "noon.com", f"https://www.noon.com/{path}/search/?q={{q}}", render=True)

def daraz(tld, label):
    return M(f"Daraz {label}", f"daraz.{tld}", f"https://www.daraz.{tld}/catalog/?q={{q}}", render=True)

def meli(tld, label, host="mercadolibre"):
    return M(f"Mercado {'Livre' if host == 'mercadolivre' else 'Libre'} {label}", f"{host}.{tld}", f"https://listado.{host}.{tld}/{{q_hyphen}}")

def lazada(tld, label):
    return M(f"Lazada {label}", f"lazada.{tld}", f"https://www.lazada.{tld}/catalog/?q={{q}}", render=True)

def shopee(tld, label):
    return M(f"Shopee {label}", f"shopee.{tld}", f"https://shopee.{tld}/search?keyword={{q}}", render=True)

def ebay(tld, label):
    return M(f"eBay {label}", f"ebay.{tld}", f"https://www.ebay.{tld}/sch/i.html?_nkw={{q}}")

DIRECTORY = {
    # ------------------------------------------------------------- Africa
    "NG": {"ubuy": "www.ubuy.com.ng", "marketplaces": [jumia("com.ng", "Nigeria"), M("Konga", "konga.com", "https://www.konga.com/search?search={q}", render=True),
           jiji("ng", "Nigeria"), M("Slot", "slot.ng", "https://slot.ng/catalogsearch/result/?q={q}", "retailer")]},
    "KE": {"ubuy": "www.ubuy.co.ke", "marketplaces": [jumia("co.ke", "Kenya"), M("Kilimall", "kilimall.co.ke", "https://www.kilimall.co.ke/search?q={q}", render=True),
           jiji("co.ke", "Kenya"), M("Carrefour Kenya", "carrefour.ke", "https://www.carrefour.ke/mafken/en/search?keyword={q}", "retailer", True)]},
    "GH": {"ubuy": "www.ubuy.com.gh", "marketplaces": [jumia("com.gh", "Ghana"), jiji("com.gh", "Ghana"), M("Melcom", "melcom.com", "https://www.melcom.com/search?q={q}", "retailer"),
           M("CompuGhana", "compughana.com", "https://compughana.com/catalogsearch/result/?q={q}", "retailer")]},
    "ZA": {"ubuy": "www.ubuy.za.com", "marketplaces": [M("Takealot", "takealot.com", "https://www.takealot.com/all?qsearch={q}", render=True), amazon("co.za", "South Africa"),
           M("Makro", "makro.co.za", "https://www.makro.co.za/search/?text={q}", "retailer", True), M("Bob Shop", "bobshop.co.za", "https://www.bobshop.co.za/search?q={q}"),
           M("Incredible", "incredible.co.za", "https://www.incredible.co.za/catalogsearch/result/?q={q}", "retailer")]},
    "EG": {"ubuy": "www.ubuy.com.eg", "marketplaces": [amazon("eg", "Egypt"), noon("egypt-en", "Egypt"), jumia("com.eg", "Egypt"),
           M("B.TECH", "btech.com", "https://btech.com/en/catalogsearch/result/?q={q}", "retailer")]},
    "MA": {"ubuy": "www.ubuy.ma", "marketplaces": [jumia("ma", "Morocco"), M("Avito", "avito.ma", "https://www.avito.ma/fr/maroc/{q_hyphen}", "classifieds"),
           M("Electroplanet", "electroplanet.ma", "https://www.electroplanet.ma/recherche?q={q}", "retailer")]},
    "UG": {"ubuy": "www.ubuy.co.ug", "marketplaces": [jumia("ug", "Uganda"), jiji("ug", "Uganda")]},
    "TZ": {"ubuy": "www.ubuy.co.tz", "marketplaces": [jiji("co.tz", "Tanzania"), M("Kilimall TZ", "kilimall.co.tz", "https://www.kilimall.co.tz/search?q={q}", render=True)]},
    "ET": {"ubuy": None, "marketplaces": [jiji("com.et", "Ethiopia")]},
    "RW": {"ubuy": None, "marketplaces": [M("Kasha / Jumia RW (via search index)", "rw", "", "marketplace")]},
    "CI": {"ubuy": None, "marketplaces": [jumia("ci", "Côte d'Ivoire"), M("Coin Afrique CI", "coinafrique.com", "https://ci.coinafrique.com/search?keyword={q}", "classifieds")]},
    "SN": {"ubuy": None, "marketplaces": [jumia("sn", "Senegal"), M("Expat-Dakar", "expat-dakar.com", "https://www.expat-dakar.com/annonces?txt={q}", "classifieds")]},
    "DZ": {"ubuy": None, "marketplaces": [jumia("dz", "Algeria"), M("Ouedkniss", "ouedkniss.com", "https://www.ouedkniss.com/s/1?keywords={q}", "classifieds", True)]},
    "TN": {"ubuy": None, "marketplaces": [jumia("com.tn", "Tunisia"), M("Mytek", "mytek.tn", "https://www.mytek.tn/catalogsearch/result/?q={q}", "retailer"),
           M("Tayara", "tayara.tn", "https://www.tayara.tn/ads/k/{q}/", "classifieds")]},
    "ZM": {"ubuy": None, "marketplaces": [M("Jiji Zambia / ZEdeals (via search index)", "zm", "", "marketplace")]},
    "ZW": {"ubuy": None, "marketplaces": [M("Classifieds ZW (via search index)", "co.zw", "", "classifieds")]},
    "MZ": {"ubuy": "www.ubuy.co.mz", "marketplaces": [M("Mozambique shops (via search index)", "co.mz", "", "marketplace")]},
    "BW": {"ubuy": None, "marketplaces": [M("Botswana shops (via search index)", "co.bw", "", "marketplace")]},
    "NA": {"ubuy": None, "marketplaces": [M("Namibia shops (via search index)", "com.na", "", "marketplace")]},
    "MU": {"ubuy": None, "marketplaces": [M("Galaxy", "galaxy.mu", "https://galaxy.mu/search?q={q}", "retailer"), M("Courts Mammouth", "courtsmammouth.mu", "https://courtsmammouth.mu/catalogsearch/result/?q={q}", "retailer")]},
    "CM": {"ubuy": None, "marketplaces": [M("Coin Afrique CM", "coinafrique.com", "https://cm.coinafrique.com/search?keyword={q}", "classifieds"), jumia("cm", "Cameroon")]},
    # ------------------------------------------------------------- Middle East
    "AE": {"ubuy": "www.ubuy.ae", "marketplaces": [amazon("ae", "UAE"), noon("uae-en", "UAE"), M("Sharaf DG", "uae.sharafdg.com", "https://uae.sharafdg.com/?q={q}&post_type=product", "retailer", True),
           M("Carrefour UAE", "carrefouruae.com", "https://www.carrefouruae.com/mafuae/en/search?keyword={q}", "retailer", True), M("Dubizzle", "dubizzle.com", "https://uae.dubizzle.com/search/?keyword={q}", "classifieds", True)]},
    "SA": {"ubuy": "www.ubuy.com.sa", "marketplaces": [amazon("sa", "Saudi Arabia"), noon("saudi-en", "Saudi"), M("Jarir", "jarir.com", "https://www.jarir.com/sa-en/catalogsearch/result?search={q}", "retailer", True),
           M("Extra", "extra.com", "https://www.extra.com/en-sa/search/?text={q}", "retailer", True)]},
    "KW": {"ubuy": "www.ubuy.com.kw", "marketplaces": [M("Xcite", "xcite.com", "https://www.xcite.com/search?q={q}", "retailer", True), amazon("ae", "UAE (ships to KW)"),
           M("Blink", "blink.com.kw", "https://www.blink.com.kw/search?q={q}", "retailer", True), noon("kuwait-en", "Kuwait")]},
    "QA": {"ubuy": "www.ubuy.qa", "marketplaces": [M("Lulu Qatar", "luluhypermarket.com", "https://www.luluhypermarket.com/en-qa/search?q={q}", "retailer", True),
           M("Jumbo", "jumbo.qa", "https://www.jumbo.qa/catalogsearch/result/?q={q}", "retailer"), noon("qatar-en", "Qatar")]},
    "BH": {"ubuy": "www.ubuy.com.bh", "marketplaces": [M("Sharaf DG Bahrain", "bahrain.sharafdg.com", "https://bahrain.sharafdg.com/?q={q}&post_type=product", "retailer", True),
           noon("bahrain-en", "Bahrain")]},
    "OM": {"ubuy": "www.ubuy.om", "marketplaces": [M("Sharaf DG Oman", "oman.sharafdg.com", "https://oman.sharafdg.com/?q={q}&post_type=product", "retailer", True),
           noon("oman-en", "Oman")]},
    "JO": {"ubuy": None, "marketplaces": [M("OpenSooq Jordan", "jo.opensooq.com", "https://jo.opensooq.com/en/find?term={q}", "classifieds", True)]},
    "IQ": {"ubuy": None, "marketplaces": [M("Miswag", "miswag.com", "https://miswag.com/search?q={q}", render=True)]},
    "LB": {"ubuy": None, "marketplaces": [M("Lebanon shops (via search index)", "com.lb", "", "marketplace")]},
    "TR": {"ubuy": "www.ubuy.com.tr", "marketplaces": [M("Trendyol", "trendyol.com", "https://www.trendyol.com/sr?q={q}", render=True),
           M("Hepsiburada", "hepsiburada.com", "https://www.hepsiburada.com/ara?q={q}", render=True), amazon("com.tr", "Türkiye"), M("n11", "n11.com", "https://www.n11.com/arama?q={q}")]},
    "IL": {"ubuy": None, "marketplaces": [M("KSP", "ksp.co.il", "https://ksp.co.il/web/search/?search={q}", "retailer", True), M("Zap", "zap.co.il", "https://www.zap.co.il/search.aspx?keyword={q}")]},
    # ------------------------------------------------------------- South Asia
    "PK": {"ubuy": "www.ubuy.com.pk", "marketplaces": [daraz("pk", "Pakistan"), M("PriceOye", "priceoye.pk", "https://priceoye.pk/search?q={q}", "retailer"),
           M("OLX Pakistan", "olx.com.pk", "https://www.olx.com.pk/items/q-{q_hyphen}", "classifieds", True)]},
    "BD": {"ubuy": None, "marketplaces": [daraz("com.bd", "Bangladesh"), M("Star Tech", "startech.com.bd", "https://www.startech.com.bd/product/search?search={q}", "retailer"),
           M("Bikroy", "bikroy.com", "https://bikroy.com/en/ads?query={q}", "classifieds")]},
    "LK": {"ubuy": "www.ubuy.lk", "marketplaces": [daraz("lk", "Sri Lanka"), M("ikman", "ikman.lk", "https://ikman.lk/en/ads?query={q}", "classifieds")]},
    "NP": {"ubuy": None, "marketplaces": [daraz("com.np", "Nepal"), M("Hamrobazar", "hamrobazaar.com", "https://hamrobazaar.com/search?q={q}", "classifieds", True)]},
    "MV": {"ubuy": None, "marketplaces": [M("Maldives shops (via search index)", "mv", "", "marketplace")]},
    # ------------------------------------------------------------- Asia
    "MY": {"ubuy": None, "marketplaces": [lazada("com.my", "Malaysia"), shopee("com.my", "Malaysia"), M("Mudah", "mudah.my", "https://www.mudah.my/malaysia/for-sale?q={q}", "classifieds", True)]},
    "ID": {"ubuy": None, "marketplaces": [M("Tokopedia", "tokopedia.com", "https://www.tokopedia.com/search?q={q}", render=True), shopee("co.id", "Indonesia"), lazada("co.id", "Indonesia")]},
    "TH": {"ubuy": None, "marketplaces": [lazada("co.th", "Thailand"), shopee("co.th", "Thailand")]},
    "VN": {"ubuy": None, "marketplaces": [shopee("vn", "Vietnam"), lazada("vn", "Vietnam"), M("Tiki", "tiki.vn", "https://tiki.vn/search?q={q}", render=True)]},
    "PH": {"ubuy": None, "marketplaces": [lazada("com.ph", "Philippines"), shopee("ph", "Philippines")]},
    "SG": {"ubuy": None, "marketplaces": [amazon("sg", "Singapore"), lazada("sg", "Singapore"), shopee("sg", "Singapore")]},
    "KH": {"ubuy": None, "marketplaces": [M("Khmer24", "khmer24.com", "https://www.khmer24.com/en/search?q={q}", "classifieds")]},
    "JP": {"ubuy": None, "marketplaces": [amazon("co.jp", "Japan"), M("Rakuten", "rakuten.co.jp", "https://search.rakuten.co.jp/search/mall/{q}/")]},
    "KR": {"ubuy": None, "marketplaces": [M("Coupang", "coupang.com", "https://www.coupang.com/np/search?q={q}", render=True)]},
    "HK": {"ubuy": None, "marketplaces": [M("HKTVmall", "hktvmall.com", "https://www.hktvmall.com/hktv/en/search_a?keyword={q}", render=True)]},
    "KZ": {"ubuy": None, "marketplaces": [M("Kaspi", "kaspi.kz", "https://kaspi.kz/shop/search/?text={q}", render=True)]},
    "UZ": {"ubuy": "www.ubuy.uz", "marketplaces": [M("Uzum", "uzum.uz", "https://uzum.uz/ru/search?query={q}", render=True)]},
    # ------------------------------------------------------------- Europe / Americas / Oceania
    "GB": {"ubuy": None, "marketplaces": [amazon("co.uk", "UK"), M("Argos", "argos.co.uk", "https://www.argos.co.uk/search/{q_hyphen}/", "retailer"), ebay("co.uk", "UK")]},
    "DE": {"ubuy": None, "marketplaces": [amazon("de", "Germany"), M("Otto", "otto.de", "https://www.otto.de/suche/{q}/"), ebay("de", "Germany")]},
    "FR": {"ubuy": None, "marketplaces": [amazon("fr", "France"), M("Cdiscount", "cdiscount.com", "https://www.cdiscount.com/search/10/{q_plus}.html"), M("Fnac", "fnac.com", "https://www.fnac.com/SearchResult/ResultList.aspx?Search={q}", "retailer")]},
    "IT": {"ubuy": None, "marketplaces": [amazon("it", "Italy"), ebay("it", "Italy")]},
    "ES": {"ubuy": None, "marketplaces": [amazon("es", "Spain"), M("PcComponentes", "pccomponentes.com", "https://www.pccomponentes.com/search/?query={q}", "retailer", True)]},
    "NL": {"ubuy": None, "marketplaces": [amazon("nl", "Netherlands"), M("bol.com", "bol.com", "https://www.bol.com/nl/nl/s/?searchtext={q}")]},
    "PL": {"ubuy": None, "marketplaces": [amazon("pl", "Poland"), M("Allegro", "allegro.pl", "https://allegro.pl/listing?string={q}", render=True)]},
    "SE": {"ubuy": None, "marketplaces": [amazon("se", "Sweden"), M("Prisjakt", "prisjakt.nu", "https://www.prisjakt.nu/search?search={q}", render=True)]},
    "IE": {"ubuy": None, "marketplaces": [amazon("co.uk", "UK (ships to IE)"), M("Harvey Norman IE", "harveynorman.ie", "https://www.harveynorman.ie/catalogsearch/result/?q={q}", "retailer")]},
    "GR": {"ubuy": None, "marketplaces": [M("Skroutz", "skroutz.gr", "https://www.skroutz.gr/search?keyphrase={q}", render=True)]},
    "CY": {"ubuy": None, "marketplaces": [M("Skroutz CY", "skroutz.cy", "https://www.skroutz.cy/search?keyphrase={q}", render=True), M("Bazaraki", "bazaraki.com", "https://www.bazaraki.com/ads/?q={q}", "classifieds")]},
    "IS": {"ubuy": "www.ubuy.is", "marketplaces": [M("Elko", "elko.is", "https://elko.is/leit?q={q}", "retailer", True)]},
    "US": {"ubuy": None, "marketplaces": [amazon("com", "US"), M("Walmart", "walmart.com", "https://www.walmart.com/search?q={q}", render=True), ebay("com", "US")]},
    "CA": {"ubuy": None, "marketplaces": [amazon("ca", "Canada"), M("Best Buy CA", "bestbuy.ca", "https://www.bestbuy.ca/en-ca/search?search={q}", "retailer", True)]},
    "MX": {"ubuy": None, "marketplaces": [meli("com.mx", "México"), amazon("com.mx", "México")]},
    "BR": {"ubuy": None, "marketplaces": [meli("com.br", "Brasil", "mercadolivre"), amazon("com.br", "Brasil")]},
    "AR": {"ubuy": None, "marketplaces": [meli("com.ar", "Argentina")]},
    "CO": {"ubuy": None, "marketplaces": [meli("com.co", "Colombia"), M("Falabella CO", "falabella.com.co", "https://www.falabella.com.co/falabella-co/search?Ntt={q}", "retailer", True)]},
    "CL": {"ubuy": None, "marketplaces": [meli("cl", "Chile"), M("Falabella CL", "falabella.com", "https://www.falabella.com/falabella-cl/search?Ntt={q}", "retailer", True)]},
    "PE": {"ubuy": None, "marketplaces": [meli("com.pe", "Perú"), M("Falabella PE", "falabella.com.pe", "https://www.falabella.com.pe/falabella-pe/search?Ntt={q}", "retailer", True)]},
    "EC": {"ubuy": None, "marketplaces": [meli("com.ec", "Ecuador")]},
    "UY": {"ubuy": None, "marketplaces": [meli("com.uy", "Uruguay")]},
    "CR": {"ubuy": None, "marketplaces": [meli("co.cr", "Costa Rica")]},
    "PA": {"ubuy": None, "marketplaces": [meli("com.pa", "Panamá")]},
    "DO": {"ubuy": None, "marketplaces": [meli("com.do", "Rep. Dominicana")]},
    "AU": {"ubuy": None, "marketplaces": [amazon("com.au", "Australia"), ebay("com.au", "Australia"), M("JB Hi-Fi", "jbhifi.com.au", "https://www.jbhifi.com.au/search?query={q}", "retailer", True)]},
    "NZ": {"ubuy": None, "marketplaces": [M("Trade Me", "trademe.co.nz", "https://www.trademe.co.nz/a/search?search_string={q}", "marketplace", True),
           M("Mighty Ape", "mightyape.co.nz", "https://www.mightyape.co.nz/search?q={q}", "retailer", True)]},
    # ------------------------------------------------------------- more of Europe (v2.2)
    "BA": {"ubuy": None, "marketplaces": [M("eKupi BA", "ekupi.ba", "https://www.ekupi.ba/bs/search?q={q}"), M("Domod", "domod.ba", "https://domod.ba/pretraga?q={q}", "retailer"),
           M("Tehnomag", "tehnomag.ba", "https://www.tehnomag.ba/pretraga?q={q}", "retailer"), M("OLX.ba", "olx.ba", "https://olx.ba/pretraga?trazilica={q}", "classifieds", True)]},
    "RS": {"ubuy": None, "marketplaces": [M("Ananas", "ananas.rs", "https://ananas.rs/pretraga?query={q}", render=True), M("Gigatron", "gigatron.rs", "https://gigatron.rs/pretraga?pojam={q}", "retailer", True),
           M("Tehnomanija", "tehnomanija.rs", "https://www.tehnomanija.rs/search?text={q}", "retailer", True), M("KupujemProdajem", "kupujemprodajem.com", "https://www.kupujemprodajem.com/pretraga?keywords={q}", "classifieds", True)]},
    "HR": {"ubuy": None, "marketplaces": [M("eKupi HR", "ekupi.hr", "https://www.ekupi.hr/hr/search?q={q}"), M("Links", "links.hr", "https://www.links.hr/hr/search?q={q}", "retailer"),
           M("Njuškalo", "njuskalo.hr", "https://www.njuskalo.hr/search/?keywords={q}", "classifieds", True)]},
    "SI": {"ubuy": None, "marketplaces": [M("Mimovrste", "mimovrste.com", "https://www.mimovrste.com/iskanje?s={q}"), M("Big Bang", "bigbang.si", "https://www.bigbang.si/iskanje/?q={q}", "retailer", True),
           M("Bolha", "bolha.com", "https://www.bolha.com/?ctl=search_ads&keywords={q}", "classifieds")]},
    "ME": {"ubuy": None, "marketplaces": [M("Tehnomax", "tehnomax.me", "https://www.tehnomax.me/pretraga?q={q}", "retailer")]},
    "MK": {"ubuy": None, "marketplaces": [M("Setec", "setec.mk", "https://setec.mk/index.php?route=product/search&search={q}", "retailer"), M("Pazar3", "pazar3.mk", "https://www.pazar3.mk/oglasi?Keyword={q}", "classifieds")]},
    "AL": {"ubuy": None, "marketplaces": [M("Neptun AL", "neptun.al", "https://www.neptun.al/search?q={q}", "retailer", True)]},
    "BG": {"ubuy": None, "marketplaces": [M("eMAG BG", "emag.bg", "https://www.emag.bg/search/{q}"), M("Technopolis", "technopolis.bg", "https://www.technopolis.bg/bg/search/?query={q}", "retailer", True),
           M("OLX BG", "olx.bg", "https://www.olx.bg/ads/q-{q_hyphen}/", "classifieds")]},
    "RO": {"ubuy": None, "marketplaces": [M("eMAG RO", "emag.ro", "https://www.emag.ro/search/{q}"), M("Altex", "altex.ro", "https://altex.ro/cauta/?q={q}", "retailer", True),
           M("OLX RO", "olx.ro", "https://www.olx.ro/oferte/q-{q_hyphen}/", "classifieds")]},
    "HU": {"ubuy": None, "marketplaces": [M("eMAG HU", "emag.hu", "https://www.emag.hu/search/{q}"), M("Árukereső", "arukereso.hu", "https://www.arukereso.hu/CategorySearch.php?st={q}")]},
    "CZ": {"ubuy": None, "marketplaces": [M("Alza", "alza.cz", "https://www.alza.cz/search.htm?exps={q}", render=True), M("Heureka", "heureka.cz", "https://www.heureka.cz/?h%5Bfraze%5D={q}"),
           M("Mall.cz", "mall.cz", "https://www.mall.cz/hledej?s={q}")]},
    "SK": {"ubuy": None, "marketplaces": [M("Alza SK", "alza.sk", "https://www.alza.sk/search.htm?exps={q}", render=True), M("Heureka SK", "heureka.sk", "https://www.heureka.sk/?h%5Bfraze%5D={q}")]},
    "AT": {"ubuy": None, "marketplaces": [amazon("de", "DE (serves AT)"), M("Geizhals", "geizhals.at", "https://geizhals.at/?fs={q}")]},
    "CH": {"ubuy": None, "marketplaces": [M("Digitec Galaxus", "digitec.ch", "https://www.digitec.ch/en/search?q={q}", render=True), M("Brack", "brack.ch", "https://www.brack.ch/search?query={q}", "retailer", True)]},
    "BE": {"ubuy": None, "marketplaces": [M("bol.com BE", "bol.com", "https://www.bol.com/be/nl/s/?searchtext={q}"), amazon("com.be", "Belgium")]},
    "PT": {"ubuy": None, "marketplaces": [M("Worten", "worten.pt", "https://www.worten.pt/search?query={q}", "retailer", True), M("KuantoKusta", "kuantokusta.pt", "https://www.kuantokusta.pt/search?q={q}")]},
    "DK": {"ubuy": None, "marketplaces": [M("Pricerunner DK", "pricerunner.dk", "https://www.pricerunner.dk/search?q={q}", render=True), M("Elgiganten", "elgiganten.dk", "https://www.elgiganten.dk/search?q={q}", "retailer", True)]},
    "NO": {"ubuy": None, "marketplaces": [M("Komplett", "komplett.no", "https://www.komplett.no/search?q={q}", "retailer"), M("Prisjakt NO", "prisjakt.no", "https://www.prisjakt.no/search?search={q}", render=True)]},
    "FI": {"ubuy": None, "marketplaces": [M("Verkkokauppa", "verkkokauppa.com", "https://www.verkkokauppa.com/fi/search?query={q}", "retailer", True), M("Hintaopas", "hintaopas.fi", "https://hintaopas.fi/search?search={q}", render=True)]},
    "UA": {"ubuy": None, "marketplaces": [M("Rozetka", "rozetka.com.ua", "https://rozetka.com.ua/search/?text={q}", render=True), M("Prom.ua", "prom.ua", "https://prom.ua/search?search_term={q}")]},
    "GE": {"ubuy": None, "marketplaces": [M("MyMarket", "mymarket.ge", "https://www.mymarket.ge/en/search/?q={q}", render=True)]},
    "AZ": {"ubuy": None, "marketplaces": [M("Umico", "umico.az", "https://umico.az/search?query={q}", render=True)]},
    "AM": {"ubuy": None, "marketplaces": [M("Menu/Zigzag (via search index)", "am", "", "marketplace")]},
}

# Source stores Ubuy buys from (used to confirm a sourcing route exists)
SOURCE_STORES = [{"name": "Amazon US", "domain": "amazon.com"}, {"name": "Walmart US", "domain": "walmart.com"}, {"name": "eBay US", "domain": "ebay.com"},
                 {"name": "Amazon UK", "domain": "amazon.co.uk"}, {"name": "Amazon DE", "domain": "amazon.de"}, {"name": "Amazon JP", "domain": "amazon.co.jp"}]

def for_country(cc):
    d = DIRECTORY.get(cc.upper())
    if not d:
        return {}
    mps = [dict(m) for m in d["marketplaces"]]
    out = {"marketplaces": mps}
    if d.get("ubuy"):
        out.update(ubuy_domain=d["ubuy"], ubuy_search_url=f"https://{d['ubuy']}/search/?q={{q}}", ubuy_verified=False)
    return out

UBUY_REFERENCE = ["www.ubuy.co.in", "www.ubuy.ae", "www.ubuy.com.kw"]
