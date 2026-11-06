"""Agent 4: turn raw text (search suggestions, headlines, posts) into specific products and de-duplicate them.

Works on lower-case autocomplete text as well as headlines:
  1. PRODUCT_LINES  - known product lines that are products by themselves ("airpods pro", "ninja creami", "stanley quencher")
  2. brand + product type (+ model)  - "anker power bank 20000mah", "Xiaomi Redmi Watch 5 smartwatch"
  3. product type only - kept ONLY when it carries an explicit unmet-demand signal ("where to buy pickleball paddle in nigeria")
"""
import re
from .evidence import norm, similarity

LEXICON = {
 "Electronics": ["earbuds","earphones","headphones","headset","smartwatch","smart watch","fitness band","bluetooth speaker","soundbar","action camera","projector",
                 "mini projector","e-reader","vr headset","smart glasses","streaming stick","gaming console","game console","gaming controller","controller",
                 "mirrorless camera","instant camera","portable speaker","speaker","camera","dashcam","walkie talkie","starlink","satellite internet kit",
                 "tv box","android tv box","turntable","karaoke machine","microphone","lavalier microphone","wireless microphone"],
 "Computers & Accessories": ["laptop","macbook","mechanical keyboard","keyboard","gaming mouse","mouse","monitor","gaming monitor","webcam","ssd","nvme ssd",
                 "external hard drive","hard drive","flash drive","docking station","usb hub","usb c hub","laptop stand","graphics tablet","drawing tablet","tablet",
                 "ipad","router","wifi router","mesh wifi","mifi","pocket wifi","printer","ink tank printer","gaming chair","graphics card","gpu","ups"],
 "Mobile Accessories": ["phone case","wireless charger","magsafe charger","charger","fast charger","charging cable","phone stand","phone holder","screen protector",
                 "phone cooler","gimbal","selfie stick","ring light","power bank","magsafe power bank","car charger","phone"],
 "Smart Home": ["smart plug","smart bulb","smart lock","video doorbell","robot vacuum","robot mop","air purifier","smart camera","security camera","cctv camera",
                "smart thermostat","smart speaker","led strip","solar generator","portable power station","inverter","solar panel","solar light","smart switch"],
 "Home Improvement": ["laser level","stud finder","cordless drill","ceiling fan","rechargeable fan","standing fan","water purifier","water filter","door lock",
                "laser measure","water heater","generator","voltage stabilizer","dehumidifier","shower head","filtered shower head"],
 "Kitchen Appliances & Accessories": ["air fryer","coffee maker","espresso machine","coffee machine","milk frother","blender","portable blender","juicer",
                "electric kettle","rice cooker","food processor","sous vide","knife set","cast iron skillet","water bottle","tumbler","lunch box","pressure cooker",
                "waffle maker","ice maker","popcorn maker","ice cream maker","stand mixer","hand mixer","bread maker","toaster oven","microwave","slow cooker",
                "food dehydrator","pizza oven","electric grill","non stick pan","cookware set","vacuum sealer","yogurt maker","soda maker","water dispenser"],
 "Beauty": ["serum","sunscreen","face mask","sheet mask","lip balm","lip gloss","lip oil","lip mask","makeup brush","foundation","concealer","mascara","eyeliner",
            "hair dryer","hair straightener","hair curler","curling iron","hair dryer brush","air styler","hot air brush","facial roller","gua sha","led face mask",
            "perfume","fragrance","body mist","moisturizer","cleanser","toner","essence","eye cream","retinol","snail mucin","niacinamide","body lotion","body butter",
            "hair oil","shampoo","conditioner","hair mask","wig","lace front wig","hair extensions","nail polish","gel nail kit","press on nails","eyelash serum",
            "setting spray","primer","bronzer","blush","contour stick","tinted moisturizer","sunscreen stick","skin tint","deodorant","body wash"],
 "Personal Care": ["electric toothbrush","electric shaver","trimmer","beard trimmer","hair clipper","massage gun","water flosser","epilator","ipl hair removal",
            "foot spa","neck massager","massager","eye massager","scalp massager","blood pressure monitor","pulse oximeter","thermometer","heating pad","tens unit",
            "posture corrector","menstrual cup","breast pump","nebulizer"],
 "Fashion": ["sneakers","running shoes","shoes","slides","hoodie","jacket","puffer jacket","sandals","boots","backpack","tote bag","jersey","football boots",
             "leggings","sports bra","abaya","clogs","tracksuit"],
 "Fashion Accessories": ["sunglasses","handbag","crossbody bag","belt bag","wallet","belt","scarf","jewelry","necklace","bracelet","watch","cap","beanie","phone strap"],
 "Toys": ["lego set","lego","building blocks","rc car","plush toy","plushie","action figure","board game","puzzle","fidget toy","trading cards","doll","blind box",
          "kids tablet","ride on car","scooter","balance bike","stuffed animal","play kitchen","magnetic tiles"],
 "Hobbies": ["telescope","ukulele","guitar","electric guitar","keyboard piano","digital piano","3d printer","resin printer","sewing machine","embroidery machine",
             "camera lens","record player","vinyl record","drone","fpv drone","airbrush kit","cricut","cutting machine","label maker","metal detector"],
 "Sports": ["cricket bat","badminton racket","football","basketball","yoga mat","skipping rope","jump rope","pickleball paddle","padel racket","tennis racket",
            "cycling helmet","bicycle","electric bike","e-bike","electric scooter","skateboard","golf club","golf balls","boxing gloves","punching bag","swim goggles",
            "camping chair","fishing rod"],
 "Fitness": ["dumbbell","adjustable dumbbell","resistance band","treadmill","walking pad","under desk treadmill","smart scale","fitness tracker","foam roller",
             "kettlebell","protein shaker","weight bench","pull up bar","exercise bike","rowing machine","weighted vest","ab roller","creatine","protein powder",
             "pre workout","whey protein","massage chair","smart ring"],
 "Automotive": ["car vacuum","dash cam","tyre inflator","tire inflator","jump starter","car phone mount","seat cover","car organizer","obd scanner","car play adapter",
                "carplay adapter","android auto adapter","car seat cushion","car polisher","pressure washer","car cover","led headlights"],
 "Pet Products": ["pet feeder","automatic feeder","cat litter box","self cleaning litter box","dog harness","pet fountain","pet grooming brush","dog toy","cat tree",
                  "dog bed","pet camera","gps tracker","pet hair remover","dog food","cat food"],
 "Office Products": ["standing desk","office chair","ergonomic chair","desk organizer","label printer","notebook","fountain pen","whiteboard","desk lamp","monitor arm",
                     "paper shredder","laminator","planner","calculator","scientific calculator"],
 "Tools": ["tool kit","socket set","multimeter","soldering iron","cordless screwdriver","electric screwdriver","impact driver","torque wrench","heat gun","angle grinder",
           "circular saw","jigsaw","rotary tool","glue gun","welding machine","air compressor","chainsaw","leaf blower"],
 "Gardening": ["garden hose","planter","grow light","pruning shears","lawn mower","robot lawn mower","sprinkler","hydroponic kit","indoor garden","seed starter"],
 "Outdoor Products": ["camping tent","tent","sleeping bag","hiking backpack","camping stove","headlamp","portable hammock","hammock","cooler box","cooler","trekking pole",
                      "solar charger","water filter straw","rooftop tent","camping lantern","flashlight"],
 "Travel Accessories": ["travel adapter","luggage","suitcase","carry on","packing cubes","neck pillow","passport holder","luggage scale","travel organizer","airtag",
                        "luggage tracker","travel pillow"],
 "Lifestyle Products": ["scented candle","diffuser","wall art","led lamp","sunset lamp","throw blanket","humidifier","weighted blanket","sleep mask","white noise machine",
                        "vape pen","shisha","hookah","prayer mat","digital quran","photo printer","bean bag"],
 "Gifting": ["gift box","photo frame","digital photo frame","gift hamper","gift set"],
 "Specialized Consumer Products": ["baby monitor","stroller","car seat","baby carrier","bottle warmer","sterilizer","baby formula","diapers","hearing aid","breast pump",
                                   "baby bouncer","high chair","playpen","wheelchair","rollator","glucometer","cgm"],
}
CATEGORIES = list(LEXICON)
NOUN2CAT = {n: c for c, ns in LEXICON.items() for n in ns}
MAX_NOUN_WORDS = max(len(n.split()) for n in NOUN2CAT)

# Product lines that are specific products on their own: phrase -> (brand, noun, category)
PRODUCT_LINES = {
    "airpods pro": ("Apple", "earbuds", "Electronics"), "airpods max": ("Apple", "headphones", "Electronics"), "airpods": ("Apple", "earbuds", "Electronics"),
    "apple watch ultra": ("Apple", "smartwatch", "Electronics"), "apple watch": ("Apple", "smartwatch", "Electronics"), "airtag": ("Apple", "airtag", "Travel Accessories"),
    "ipad pro": ("Apple", "tablet", "Computers & Accessories"), "ipad air": ("Apple", "tablet", "Computers & Accessories"), "macbook air": ("Apple", "laptop", "Computers & Accessories"),
    "macbook pro": ("Apple", "laptop", "Computers & Accessories"), "mac mini": ("Apple", "laptop", "Computers & Accessories"), "apple pencil": ("Apple", "graphics tablet", "Computers & Accessories"),
    "iphone": ("Apple", "smartphone", "Electronics"), "galaxy z fold": ("Samsung", "smartphone", "Electronics"), "galaxy z flip": ("Samsung", "smartphone", "Electronics"),
    "galaxy s": ("Samsung", "smartphone", "Electronics"), "galaxy a": ("Samsung", "smartphone", "Electronics"), "pixel": ("Google", "smartphone", "Electronics"),
    "redmi note": ("Xiaomi", "smartphone", "Electronics"), "redmi watch": ("Xiaomi", "smartwatch", "Electronics"), "redmi buds": ("Xiaomi", "earbuds", "Electronics"),
    "oraimo freepods": ("Oraimo", "earbuds", "Electronics"), "oraimo watch": ("Oraimo", "smartwatch", "Electronics"), "nothing phone": ("Nothing", "smartphone", "Electronics"),
    "galaxy watch": ("Samsung", "smartwatch", "Electronics"), "galaxy buds": ("Samsung", "earbuds", "Electronics"), "galaxy tab": ("Samsung", "tablet", "Computers & Accessories"),
    "galaxy ring": ("Samsung", "smart ring", "Fitness"), "oura ring": ("Oura", "smart ring", "Fitness"), "whoop": ("Whoop", "fitness tracker", "Fitness"),
    "pixel buds": ("Google", "earbuds", "Electronics"), "pixel watch": ("Google", "smartwatch", "Electronics"), "nest hub": ("Google", "smart speaker", "Smart Home"),
    "echo dot": ("Amazon", "smart speaker", "Smart Home"), "fire tv stick": ("Amazon", "streaming stick", "Electronics"), "kindle paperwhite": ("Amazon", "e-reader", "Electronics"),
    "kindle": ("Amazon", "e-reader", "Electronics"), "ring doorbell": ("Ring", "video doorbell", "Smart Home"), "blink camera": ("Blink", "security camera", "Smart Home"),
    "playstation 5": ("Sony", "gaming console", "Electronics"), "ps5 pro": ("Sony", "gaming console", "Electronics"), "ps5": ("Sony", "gaming console", "Electronics"),
    "playstation portal": ("Sony", "gaming console", "Electronics"), "dualsense": ("Sony", "gaming controller", "Electronics"),
    "nintendo switch 2": ("Nintendo", "gaming console", "Electronics"), "nintendo switch": ("Nintendo", "gaming console", "Electronics"),
    "xbox series x": ("Microsoft", "gaming console", "Electronics"), "xbox series s": ("Microsoft", "gaming console", "Electronics"), "steam deck": ("Valve", "gaming console", "Electronics"),
    "rog ally": ("Asus", "gaming console", "Electronics"), "legion go": ("Lenovo", "gaming console", "Electronics"), "meta quest 3": ("Meta", "vr headset", "Electronics"),
    "meta quest": ("Meta", "vr headset", "Electronics"), "ray-ban meta": ("Meta", "smart glasses", "Electronics"), "ray ban meta": ("Meta", "smart glasses", "Electronics"),
    "gopro hero": ("GoPro", "action camera", "Electronics"), "osmo pocket": ("DJI", "gimbal", "Mobile Accessories"), "dji osmo": ("DJI", "action camera", "Electronics"),
    "dji mini": ("DJI", "drone", "Hobbies"), "dji neo": ("DJI", "drone", "Hobbies"), "dji mic": ("DJI", "wireless microphone", "Electronics"), "insta360": ("Insta360", "action camera", "Electronics"),
    "instax mini": ("Fujifilm", "instant camera", "Electronics"), "jbl flip": ("JBL", "bluetooth speaker", "Electronics"), "jbl charge": ("JBL", "bluetooth speaker", "Electronics"),
    "jbl go": ("JBL", "bluetooth speaker", "Electronics"), "jbl partybox": ("JBL", "bluetooth speaker", "Electronics"), "bose quietcomfort": ("Bose", "headphones", "Electronics"),
    "sony wh-1000xm5": ("Sony", "headphones", "Electronics"), "sony wh-1000xm6": ("Sony", "headphones", "Electronics"), "beats studio": ("Beats", "headphones", "Electronics"),
    "beats solo": ("Beats", "headphones", "Electronics"), "beats fit pro": ("Beats", "earbuds", "Electronics"), "marshall emberton": ("Marshall", "bluetooth speaker", "Electronics"),
    "starlink mini": ("Starlink", "starlink", "Electronics"), "starlink kit": ("Starlink", "starlink", "Electronics"),
    "ninja creami": ("Ninja", "ice cream maker", "Kitchen Appliances & Accessories"), "ninja slushi": ("Ninja", "ice maker", "Kitchen Appliances & Accessories"),
    "ninja foodi": ("Ninja", "air fryer", "Kitchen Appliances & Accessories"), "ninja air fryer": ("Ninja", "air fryer", "Kitchen Appliances & Accessories"),
    "cosori air fryer": ("Cosori", "air fryer", "Kitchen Appliances & Accessories"), "instant pot": ("Instant", "pressure cooker", "Kitchen Appliances & Accessories"),
    "nespresso vertuo": ("Nespresso", "coffee machine", "Kitchen Appliances & Accessories"), "nespresso": ("Nespresso", "coffee machine", "Kitchen Appliances & Accessories"),
    "breville barista": ("Breville", "espresso machine", "Kitchen Appliances & Accessories"), "kitchenaid": ("KitchenAid", "stand mixer", "Kitchen Appliances & Accessories"),
    "vitamix": ("Vitamix", "blender", "Kitchen Appliances & Accessories"), "nutribullet": ("NutriBullet", "blender", "Kitchen Appliances & Accessories"),
    "blendjet": ("BlendJet", "portable blender", "Kitchen Appliances & Accessories"), "sodastream": ("SodaStream", "soda maker", "Kitchen Appliances & Accessories"),
    "stanley quencher": ("Stanley", "tumbler", "Kitchen Appliances & Accessories"), "stanley cup": ("Stanley", "tumbler", "Kitchen Appliances & Accessories"),
    "stanley tumbler": ("Stanley", "tumbler", "Kitchen Appliances & Accessories"), "owala freesip": ("Owala", "water bottle", "Kitchen Appliances & Accessories"),
    "owala": ("Owala", "water bottle", "Kitchen Appliances & Accessories"), "hydro flask": ("Hydro Flask", "water bottle", "Kitchen Appliances & Accessories"),
    "yeti rambler": ("YETI", "tumbler", "Kitchen Appliances & Accessories"), "yeti cooler": ("YETI", "cooler", "Outdoor Products"), "le creuset": ("Le Creuset", "cookware set", "Kitchen Appliances & Accessories"),
    "caraway cookware": ("Caraway", "cookware set", "Kitchen Appliances & Accessories"), "hexclad": ("HexClad", "non stick pan", "Kitchen Appliances & Accessories"),
    "ooni pizza oven": ("Ooni", "pizza oven", "Kitchen Appliances & Accessories"), "ooni": ("Ooni", "pizza oven", "Kitchen Appliances & Accessories"),
    "dyson airwrap": ("Dyson", "air styler", "Beauty"), "dyson supersonic": ("Dyson", "hair dryer", "Beauty"), "dyson airstrait": ("Dyson", "hair straightener", "Beauty"),
    "dyson v15": ("Dyson", "cordless vacuum", "Smart Home"), "dyson v12": ("Dyson", "cordless vacuum", "Smart Home"), "shark flexstyle": ("Shark", "air styler", "Beauty"),
    "revlon one step": ("Revlon", "hair dryer brush", "Beauty"), "ghd": ("ghd", "hair straightener", "Beauty"), "theragun": ("Therabody", "massage gun", "Personal Care"),
    "hypervolt": ("Hyperice", "massage gun", "Personal Care"), "oral-b io": ("Oral-B", "electric toothbrush", "Personal Care"), "waterpik": ("Waterpik", "water flosser", "Personal Care"),
    "philips oneblade": ("Philips", "trimmer", "Personal Care"), "braun ipl": ("Braun", "ipl hair removal", "Personal Care"), "ulike": ("Ulike", "ipl hair removal", "Personal Care"),
    "foreo luna": ("Foreo", "cleanser", "Beauty"), "currentbody": ("CurrentBody", "led face mask", "Beauty"),
    "cosrx snail mucin": ("COSRX", "snail mucin", "Beauty"), "cosrx": ("COSRX", "serum", "Beauty"), "the ordinary niacinamide": ("The Ordinary", "niacinamide", "Beauty"),
    "the ordinary": ("The Ordinary", "serum", "Beauty"), "cerave": ("CeraVe", "moisturizer", "Beauty"), "la roche-posay": ("La Roche-Posay", "sunscreen", "Beauty"),
    "la roche posay": ("La Roche-Posay", "sunscreen", "Beauty"), "beauty of joseon": ("Beauty of Joseon", "sunscreen", "Beauty"), "anua": ("Anua", "toner", "Beauty"),
    "skin1004": ("SKIN1004", "sunscreen", "Beauty"), "medicube": ("Medicube", "serum", "Beauty"), "laneige lip": ("Laneige", "lip mask", "Beauty"),
    "olaplex": ("Olaplex", "hair mask", "Beauty"), "mielle rosemary": ("Mielle", "hair oil", "Beauty"), "mielle": ("Mielle", "hair oil", "Beauty"),
    "sol de janeiro": ("Sol de Janeiro", "body mist", "Beauty"), "rare beauty": ("Rare Beauty", "blush", "Beauty"), "fenty beauty": ("Fenty Beauty", "foundation", "Beauty"),
    "charlotte tilbury": ("Charlotte Tilbury", "setting spray", "Beauty"), "glow recipe": ("Glow Recipe", "toner", "Beauty"), "drunk elephant": ("Drunk Elephant", "serum", "Beauty"),
    "summer fridays": ("Summer Fridays", "lip balm", "Beauty"), "dior lip glow oil": ("Dior", "lip oil", "Beauty"), "bath and body works": ("Bath & Body Works", "body mist", "Beauty"),
    "victoria secret mist": ("Victoria's Secret", "body mist", "Beauty"), "native deodorant": ("Native", "deodorant", "Beauty"),
    "lattafa": ("Lattafa", "perfume", "Beauty"), "armaf club de nuit": ("Armaf", "perfume", "Beauty"),
    "lego technic": ("LEGO", "lego set", "Toys"), "lego star wars": ("LEGO", "lego set", "Toys"), "lego icons": ("LEGO", "lego set", "Toys"), "labubu": ("Pop Mart", "blind box", "Toys"),
    "pop mart": ("Pop Mart", "blind box", "Toys"), "squishmallow": ("Squishmallows", "plush toy", "Toys"), "pokemon cards": ("Pokémon", "trading cards", "Toys"),
    "tonies": ("Tonies", "kids tablet", "Toys"), "yoto player": ("Yoto", "kids tablet", "Toys"), "magna-tiles": ("Magna-Tiles", "magnetic tiles", "Toys"),
    "crocs": ("Crocs", "clogs", "Fashion"), "on cloud": ("On", "running shoes", "Fashion"), "hoka": ("Hoka", "running shoes", "Fashion"), "new balance 9060": ("New Balance", "sneakers", "Fashion"),
    "new balance 530": ("New Balance", "sneakers", "Fashion"), "adidas samba": ("Adidas", "sneakers", "Fashion"), "nike dunk": ("Nike", "sneakers", "Fashion"),
    "air jordan": ("Nike", "sneakers", "Fashion"), "asics gel": ("ASICS", "running shoes", "Fashion"), "ugg": ("UGG", "boots", "Fashion"), "stanley adventure": ("Stanley", "tumbler", "Kitchen Appliances & Accessories"),
    "lululemon belt bag": ("lululemon", "belt bag", "Fashion Accessories"), "lululemon": ("lululemon", "leggings", "Fashion"), "skims": ("SKIMS", "leggings", "Fashion"),
    "jellycat": ("Jellycat", "plush toy", "Toys"), "bambu lab": ("Bambu Lab", "3d printer", "Hobbies"), "creality": ("Creality", "3d printer", "Hobbies"),
    "cricut": ("Cricut", "cutting machine", "Hobbies"), "brother sewing": ("Brother", "sewing machine", "Hobbies"),
    "ecoflow": ("EcoFlow", "portable power station", "Smart Home"), "jackery": ("Jackery", "portable power station", "Smart Home"), "bluetti": ("Bluetti", "portable power station", "Smart Home"),
    "anker solix": ("Anker", "portable power station", "Smart Home"), "roborock": ("Roborock", "robot vacuum", "Smart Home"), "roomba": ("iRobot", "robot vacuum", "Smart Home"),
    "eufy robovac": ("eufy", "robot vacuum", "Smart Home"), "levoit": ("Levoit", "air purifier", "Smart Home"), "philips hue": ("Philips Hue", "smart bulb", "Smart Home"),
    "tp-link deco": ("TP-Link", "mesh wifi", "Computers & Accessories"), "garmin forerunner": ("Garmin", "smartwatch", "Electronics"), "garmin fenix": ("Garmin", "smartwatch", "Electronics"),
    "garmin venu": ("Garmin", "smartwatch", "Electronics"), "fitbit charge": ("Fitbit", "fitness tracker", "Fitness"), "amazfit": ("Amazfit", "smartwatch", "Electronics"),
    "walking pad": ("", "walking pad", "Fitness"), "bowflex selecttech": ("Bowflex", "adjustable dumbbell", "Fitness"), "optimum nutrition": ("Optimum Nutrition", "whey protein", "Fitness"),
    "creatine monohydrate": ("", "creatine", "Fitness"), "hydrogen water bottle": ("", "water bottle", "Kitchen Appliances & Accessories"),
    "carplay ai box": ("", "carplay adapter", "Automotive"), "70mai": ("70mai", "dash cam", "Automotive"), "viofo": ("Viofo", "dash cam", "Automotive"),
    "noco boost": ("NOCO", "jump starter", "Automotive"), "litter robot": ("Whisker", "self cleaning litter box", "Pet Products"), "petlibro": ("Petlibro", "automatic feeder", "Pet Products"),
    "furbo": ("Furbo", "pet camera", "Pet Products"), "nanit": ("Nanit", "baby monitor", "Specialized Consumer Products"), "owlet": ("Owlet", "baby monitor", "Specialized Consumer Products"),
    "uppababy": ("UPPAbaby", "stroller", "Specialized Consumer Products"), "doona": ("Doona", "car seat", "Specialized Consumer Products"), "freestyle libre": ("Abbott", "cgm", "Specialized Consumer Products"),
    "samsonite": ("Samsonite", "luggage", "Travel Accessories"), "away luggage": ("Away", "luggage", "Travel Accessories"), "tile tracker": ("Tile", "luggage tracker", "Travel Accessories"),
}
for _ph, (_b, _n, _c) in PRODUCT_LINES.items():
    NOUN2CAT.setdefault(_n, _c)
_LINES_SORTED = sorted(PRODUCT_LINES, key=lambda s: -len(s))
_LINE_RE = re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(p) for p in _LINES_SORTED) + r")(?![a-z])")

SYN = {"earbuds": ["wireless earphones", "tws earbuds"], "power bank": ["portable charger"], "smartwatch": ["smart watch"], "smart watch": ["smartwatch"],
       "air fryer": ["oil free fryer"], "massage gun": ["percussion massager"], "headphones": ["wireless headphones"], "vape pen": ["vaporizer pen"],
       "robot vacuum": ["robotic vacuum cleaner"], "dash cam": ["dashboard camera"], "air purifier": ["air cleaner"], "yoga mat": ["exercise mat"],
       "tumbler": ["insulated cup"], "portable power station": ["solar generator"], "walking pad": ["under desk treadmill"]}
USE_CASE = {"Electronics": "Personal entertainment / communication", "Computers & Accessories": "Work, study and gaming setups", "Mobile Accessories": "Everyday phone use and charging",
            "Smart Home": "Home automation, power and security", "Home Improvement": "DIY and home upgrades", "Kitchen Appliances & Accessories": "Home cooking and food prep",
            "Beauty": "Skincare / makeup / hair routines", "Personal Care": "Grooming and wellness", "Fashion": "Everyday wear", "Fashion Accessories": "Style accessories",
            "Toys": "Children's play and collectibles", "Hobbies": "Leisure and creative hobbies", "Sports": "Sports practice and play", "Fitness": "Home / gym workouts",
            "Automotive": "Car care and driving convenience", "Pet Products": "Pet care", "Office Products": "Home-office and stationery", "Tools": "Repair and workshop tasks",
            "Gardening": "Home gardening", "Outdoor Products": "Camping, hiking and outdoor leisure", "Travel Accessories": "Travel convenience",
            "Lifestyle Products": "Home ambience and lifestyle", "Gifting": "Gift giving", "Specialized Consumer Products": "Baby, health and specialised needs"}

STOP = set("""the a an and or for with of in on at to from by new best top trending latest popular cheap cheapest buy price prices review reviews cost
vs is are how why what where which who this that these your you our launch launched launches sale deal deals offer offers original fake authentic
january february march april may june july august september october november december monday tuesday wednesday thursday friday saturday sunday
amazon jumia konga jiji flipkart takealot noon daraz google youtube reddit tiktok instagram facebook news gadgets guide list year week hands-on unboxing
wireless bluetooth smart portable electric digital cordless rechargeable premium gaming mechanical foldable usb led hd 4k magnetic compact automatic
mini home kitchen outdoor indoor travel kids baby men women mens womens ladies set pack pair combo free shipping official genuine near me online store shop
used second hand fairly refurbished uk us usa china dubai nigeria kenya ghana africa india pakistan egypt""".split())
MODIFIERS = {"pro", "max", "plus", "ultra", "mini", "lite", "se", "air", "neo", "go", "fe", "s", "x"}
KNOWN_BRANDS = {b.lower() for b in """Apple Samsung Xiaomi Redmi Poco Sony Bose JBL Anker Soundcore Ugreen Baseus Logitech Razer Dyson Philips Nike Adidas Puma Garmin GoPro DJI Lego
Hasbro Mattel Ninja Instant Oral-B Braun Fitbit Huawei Honor Oppo Vivo Realme OnePlus Nothing Infinix Tecno Itel boAt Noise Oraimo Dell HP Lenovo Asus Acer MSI Canon Nikon
Fujifilm Insta360 Govee Ecovacs Roborock Eufy Ring Nest Tapo TP-Link Kindle Theragun Hyperice Stanley Yeti Hydro Owala Cosrx Anua Olaplex Cerave Medicube Laneige
Amazfit Haylou Kospet Beats Marshall Sennheiser Skullcandy Jabra Shokz Tribit Sonos Hisense TCL LG Panasonic Sharp Toshiba Kenwood Tefal Moulinex Russell Hobbs
Breville Delonghi De'Longhi Nespresso Keurig Cuisinart KitchenAid Cosori Instant Vitamix NutriBullet Ninja Shark Bissell Levoit Honeywell Xiaomi Mi Roku Chromecast
Steam Nintendo Xbox PlayStation Meta Oculus Valve Corsair HyperX SteelSeries Keychron Elgato Rode Hollyland Boya Zhiyun Godox Neewer EcoFlow Jackery Bluetti Itel
Anker Romoss Xiaomi Ugreen Orico Sandisk Samsung Kingston Seagate WD Crucial 70mai Viofo Noco Petlibro Furbo Nanit Owlet Graco Chicco Medela Omron Withings Oura
Crocs Hoka Asics Brooks Saucony Salomon Converse Vans Reebok Fila Skechers Timberland UGG Lululemon Gymshark Skims Coach Kate Spade Michael Kors Pandora Casio
Fossil Seiko Citizen Lattafa Armaf Rasasi Afnan Maison Dior Chanel Gucci Fenty Maybelline Loreal L'Oreal Nivea Neutrogena Garnier Revlon Ghd Remington Wahl Andis
Babyliss Conair Foreo Bambu Creality Elegoo Anycubic Cricut Brother Singer Bowflex Peloton Xiaomi Huawei""".replace("\n", " ").split()}
_PRICE_RE = re.compile(r"\b(price|prices|cost|how much|prix|precio|preço|preco|سعر)\b")

_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-\+\.'/]*")

def _tok(text):
    return _TOKEN_RE.findall(text or "")

def _is_year(t):
    return t.isdigit() and len(t) == 4 and t.startswith("20")

_UNIT_RE = re.compile(r"\d+(gb|tb|mah|w|ml|l|kg|inch|in|mm|cm|pcs|pieces|k|x|oz|v|hz|ft|m)|\d{5,}")

def _modelish(t):
    tl = t.lower().strip(".")
    if tl in MODIFIERS:
        return True
    return (any(c.isdigit() for c in tl) and len(tl) <= 14 and not _is_year(tl) and tl not in STOP and not _UNIT_RE.fullmatch(tl))

def _pretty(name, brand):
    words = []
    for w in name.split():
        if w.isupper() and len(w) > 1: words.append(w)
        elif any(c.isdigit() for c in w) and len(w) <= 4: words.append(w.upper())
        elif w.islower(): words.append(w.capitalize())
        else: words.append(w)
    out = " ".join(words)
    if brand and out.lower().startswith(brand.lower()):
        out = brand + out[len(brand):]
    elif brand and brand.lower() not in out.lower():
        out = f"{brand} {out}"
    return out

def extract_from_text(text, lowercase_source=False):
    """-> [{name, brand, model, noun, category, specific, kind}]
    Each token can belong to only one product mention (no double counting of overlapping matches)."""
    text = text or ""
    spans = [(m.start(), m.end(), m.group(0)) for m in _TOKEN_RE.finditer(text)]
    toks = [x[2] for x in spans]; low = [t.lower().strip(".'") for t in toks]
    taken = [False] * len(toks)
    out = []
    low_text = text.lower()

    def tok_index(pos):
        for idx, (a, b, _) in enumerate(spans):
            if a <= pos < b or a >= pos:
                return idx
        return len(spans)

    # 1) known product lines (longest first, glued model digits allowed: "galaxy s25")
    for m in _LINE_RE.finditer(low_text):
        phrase = m.group(1); brand, noun, cat = PRODUCT_LINES[phrase]
        i0 = tok_index(m.start()); i1 = tok_index(m.end() - 1) + 1
        if any(taken[i0:i1]):
            continue
        glued = ""
        last = spans[i1 - 1]
        if last[1] > m.end():                      # phrase ends inside a token: "iphone16" / "galaxy s25"
            glued = low_text[m.end():last[1]]
        suf, k = [], i1
        while k < len(toks) and len(suf) < 3 and _modelish(toks[k]) and low[k] not in STOP:
            if low[k].isdigit() and (any(x.isdigit() for x in suf) or glued):
                break
            suf.append(low[k]); k += 1
        for x in range(i0, k): taken[x] = True
        model = (glued + " " + " ".join(suf)).strip()
        name = _pretty(phrase + glued + (" " + " ".join(suf) if suf else ""), brand)
        out.append({"name": name, "brand": brand, "model": model, "noun": noun, "category": cat, "specific": bool(brand) or bool(model), "kind": "line"})

    # 2) brand / model + product type
    i = 0
    while i < len(toks):
        hit = None
        for n in range(MAX_NOUN_WORDS, 0, -1):
            ph = " ".join(low[i:i + n])
            if len(low[i:i + n]) == n and ph in NOUN2CAT and not any(taken[i:i + n]):
                hit = (n, ph); break
        if not hit:
            i += 1; continue
        n, noun = hit
        pre, j = [], i
        while j > 0 and len(pre) < 4 and not taken[j - 1]:
            t, tl = toks[j - 1], low[j - 1]
            has_model = any(any(c.isdigit() for c in x) for x in pre)
            ok = (tl in KNOWN_BRANDS or _modelish(t) or (not lowercase_source and t[:1].isupper() and len(t) > 1)
                  or (lowercase_source and has_model and t.isalpha() and len(t) > 2 and len(pre) < 3))   # "zento pro 2 yoga mat"
            if tl in STOP or _is_year(tl) or not ok:
                break
            pre.insert(0, t); j -= 1
        brand = next((p for p in pre if p.lower() in KNOWN_BRANDS), "")
        if not brand:
            # lower-case queries: "oraimo freepods 4 earbuds" -> brand within 4 tokens before the noun
            bi = next((x for x in range(i - 1, max(-1, i - 5), -1) if low[x] in KNOWN_BRANDS and not taken[x]), None)
            if bi is not None and not any(taken[x] or (low[x] in STOP) for x in range(bi, i)):
                brand = toks[bi]; j = bi
                pre = [t for t in toks[bi:i] if not _UNIT_RE.fullmatch(t.lower())]
            elif pre and not any(c.isdigit() for c in pre[0]) and pre[0].lower() not in MODIFIERS and (not lowercase_source or any(any(c.isdigit() for c in x) for x in pre)):
                brand = pre[0]
        suf, k = [], i + n
        while k < len(toks) and len(suf) < 2 and not taken[k] and _modelish(toks[k]) and low[k] not in STOP:
            if low[k].isdigit() and any(x.isdigit() for x in suf + pre):
                break
            suf.append(toks[k]); k += 1
        for x in range(j, k): taken[x] = True
        model = " ".join(t for t in pre + suf if t != brand and (any(c.isdigit() for c in t) or t.lower() in MODIFIERS))
        brand_disp = brand.upper() if brand.lower() in ("jbl", "hp", "lg", "tcl", "dji", "msi", "ugg", "wd") else (brand.title() if brand.islower() else brand)
        name = _pretty(" ".join(pre + toks[i:i + n] + suf), brand_disp)
        specific = bool(brand) or bool(model)
        out.append({"name": name, "brand": brand_disp, "model": model.strip(), "noun": noun, "category": NOUN2CAT[noun],
                    "specific": specific, "kind": "branded" if specific else "type"})
        i = k
    if any(o["specific"] for o in out):
        out = [o for o in out if o["specific"]]
    for o in out:
        o["name"] = re.sub(r"\bIphone\b", "iPhone", re.sub(r"\bIpad\b", "iPad", re.sub(r"\bAirpods\b", "AirPods", o["name"])))
    return out

def _digits(text):
    from .evidence import split_glued
    return frozenset(t for t in split_glued(norm(text)).split() if any(c.isdigit() for c in t))

def _words(text, brand, noun):
    from .evidence import split_glued
    skip = set(norm(brand).split()) | set(norm(noun).split()) | MODIFIERS
    return frozenset(t for t in split_glued(norm(text)).split() if t.isalpha() and len(t) > 2 and t not in skip)

def identify(raw, cap=300):
    """raw: [{name,brand,model,noun,category,specific,signal}] -> (candidates, dropped).
    Generic product types survive only with an explicit unmet-demand signal (people asking where to buy it)."""
    dropped, groups = [], []
    for r in raw:
        if not r["specific"] or not (r.get("brand") or "").strip():
            dropped.append({"name": r["name"], "reason": "Vague: no brand (generic product types are stocked everywhere and cannot be an SKU)"}); continue
        if len(norm(r["name"]).split()) < 2:
            dropped.append({"name": r["name"], "reason": "Vague: brand only"}); continue
        key = norm(r["name"])
        digits = _digits(key)
        placed = False
        for g in groups:
            if (g["noun"] == r["noun"] and _digits(g["key"]) == digits and norm(g["brand"]) == norm(r["brand"])
                    and _words(g["key"], g["brand"], g["noun"]) == _words(key, r["brand"], r["noun"]) and (g["key"] == key or similarity(g["key"], key) >= 88)):
                g["signals"].append(r["signal"]); placed = True
                if len(r["name"]) > len(g["name"]) and len(r["name"].split()) <= 7 and r["model"]:
                    g["name"], g["model"] = r["name"], r["model"] or g["model"]
                g["aliases"].add(r["name"])
                break
        if not placed:
            groups.append({"key": key, "name": r["name"], "brand": r["brand"], "model": r["model"], "noun": r["noun"], "category": r["category"],
                           "specific": r["specific"], "signals": [r["signal"]], "aliases": {r["name"]}})
    cands = []
    for g in groups:
        alts = [a for a in g["aliases"] if a != g["name"]]
        alts += [(g["brand"] + " " + s).strip() for s in SYN.get(g["noun"], [])]
        if g["model"] and g["brand"] and not norm(g["model"]).replace(" ", "").isdigit():
            alts.append(f"{g['brand']} {g['model']}")
        variants = sorted({s["title"][:80] for s in g["signals"] if s.get("title")})[:5]
        cands.append({"key": norm(g["name"]).replace(" ", "-"), "name": g["name"], "brand": g["brand"], "model": g["model"],
                      "brand_known": (g["brand"] or "").lower() in KNOWN_BRANDS or any(g["brand"] == v[0] for v in PRODUCT_LINES.values()),
                      "noun": g["noun"], "category": g["category"], "product_type_only": not g["specific"],
                      "alt_names": list(dict.fromkeys(a for a in alts if a.strip()))[:5], "variants": variants, "use_case": USE_CASE.get(g["category"], ""),
                      "signals": g["signals"], "status": "active", "reasons": [], "done": {}})
    W = {"unmet": 5, "price": 3, "buy": 3, "local": 2, "trend": 4, "reddit": 4, "news": 1, "global": 1}
    for c in cands:
        intents = [s.get("intent", "news") for s in c["signals"]]
        c["strength"] = (sum(W.get(x, 1) for x in intents) + len({s["source"] for s in c["signals"]}) * 2
                         + (2 if c["brand_known"] else 0) - (4 if c["product_type_only"] else 0))
    cands.sort(key=lambda c: -c["strength"])
    for c in cands[cap:]:
        dropped.append({"name": c["name"], "reason": "Below candidate-pool cap (weak initial signal)"})
    return cands[:cap], dropped

_CUT = re.compile(r"\s[-–—|:(\[,]|,\s|\s\(|\sfor\s|\swith\s", re.I)
_GENERIC_DESC = {"insulated", "stainless", "steel", "wireless", "bluetooth", "portable", "rechargeable", "cordless", "electric", "digital", "smart",
                 "waterproof", "adjustable", "foldable", "heavy", "professional", "compatible", "multi", "multipurpose", "set", "pack", "kit", "bundle",
                 "count", "pcs", "piece", "pieces", "unisex", "mens", "womens", "men's", "women's", "kids", "large", "small", "mini", "extra"}
_DESCRIPTIVE = {"new", "the", "original", "premium", "upgraded", "2024", "2025", "2026", "best", "official", "genuine", "authentic"}

def extract_listing_title(title, category):
    """A product title from a best-seller list -> one SKU-level product. Uses the normal extractor first (known types,
    product lines); otherwise brand (first word) + the next 1-3 words up to the first separator, so products outside the
    lexicon ('Dr Teal's Epsom Salt', 'Grandma's Secret Spot Remover') are no longer lost."""
    tl = " " + title.lower() + " "
    if any(w in tl for w in (" case ", " case,", " cover ", " compatible with ", " compatible for ", " screen protector", " tempered glass", " for iphone",
                             " for samsung", " for galaxy", " for ps5", " for playstation", " for apple", " for pixel", " skin ", " stand for ", " charger for ")):
        found = [p for p in extract_from_text(title, False) if p.get("brand")]
        # keep it only if the accessory itself is the product type (e.g. a 'phone case' brand)
        found = [p for p in found if p["noun"] and any(w in p["noun"] for w in ("case", "protector", "charger", "stand", "cover"))]
        return found[:1]
    found = [p for p in extract_from_text(title, False) if p.get("brand")]
    fb = _listing_fallback(title, category)
    if found:
        f0 = found[0]
        if fb and len(fb[0]["name"]) > len(f0["name"]) and norm(fb[0]["name"]).startswith(norm(f0["name"])) and not f0["model"]:
            fb[0].update(noun=f0["noun"] if norm(f0["noun"]) in norm(fb[0]["name"]) else "", category=f0["category"], brand=f0["brand"])
            return fb                                   # 'LEGO Icons' -> 'LEGO Icons Wildflower Bouquet'
        if len(f0["name"].split()) >= 2:
            return found[:1]
    return fb or found[:1]

def _listing_fallback(title, category):
    head = _CUT.split(title, 1)[0].strip()
    words = [w for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9'&\.\-\+]*", head) if w.lower() not in _DESCRIPTIVE]
    if len(words) < 2 or not words[0][:1].isupper() or words[0].lower() in STOP or words[0].isdigit():
        return []
    brand = words[0]
    if len(words) > 2 and words[1][:1].isupper() and words[0].rstrip(".").lower() in ("dr", "mr", "mrs", "st", "the", "la", "le", "el"):   # "Dr Teal's"
        brand = f"{words[0]} {words[1]}"; rest = words[2:]
    else:
        rest = words[1:]
    keep = []
    for w in rest:
        if w.lower() in _GENERIC_DESC or _UNIT_RE.fullmatch(w.lower()):
            break                                     # stop at the first generic descriptor ('Insulated', 'Wireless', '20oz')
        keep.append(w)
    rest = keep[:3]
    if not rest:
        return []
    name = _pretty(" ".join([brand] + rest), brand)
    model = " ".join(w for w in rest if any(c.isdigit() for c in w))
    return [{"name": name, "brand": brand, "model": model, "noun": "", "category": category, "specific": True, "kind": "listing"}]
