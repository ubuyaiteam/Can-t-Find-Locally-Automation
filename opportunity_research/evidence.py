"""Shared text utilities: normalisation, product matching, listing extraction, evidence helpers."""
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
try:
    from rapidfuzz import fuzz
except Exception:   # graceful fallback
    fuzz = None
import difflib

NO_RESULT_PHRASES = ("no results found", "did not match any", "no products found", "0 results", "we couldn't find",
                     "we could not find", "no results for", "no matching products", "nothing found", "sorry, no results",
                     "didn't match any", "did not find any")
UNAVAILABLE = ("out of stock", "currently unavailable", "sold out", "notify me", "temporarily unavailable")
NO_DELIVERY = ("cannot be delivered", "not deliverable", "does not ship to", "unable to deliver", "doesn't ship to", "not available in your")
_CUR = (r"US\s?\$|C\$|A\$|NZ\$|MX\$|R\$|HK\$|S\$|N\$|GH₵|GH¢|KSh|Ksh|KES|TSh|TZS|USh|UGX|₦|NGN|GHS|ZAR|ZMW|RWF|ETB|EGP|E£|MAD|DH|Dhs?|DZD|TND|"
        r"AED|SAR|QAR|KWD|KD|BHD|BD|OMR|JOD|₹|Rs\.?|INR|PKR|LKR|NPR|BDT|৳|RM|MYR|Rp|IDR|฿|THB|₱|PHP|₫|VND|£|GBP|€|EUR|₺|TL|TRY|zł|PLN|kr|SEK|NOK|DKK|"
        r"CFA|FCFA|XOF|XAF|MUR|BWP|ZWG|MZN|AOA|CHF|¥|JPY|₩|KRW|KM|BAM|Kč|CZK|lei|RON|лв|BGN|Ft|HUF|₴|грн|UAH|RSD|дин|MKD|ден|USD|\$|R(?=\s?\d)")
_NUM = r"\d{1,3}(?:[ ,.\u00a0]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?"
PRICE_RE = re.compile(r"(" + _CUR + r")\s?(" + _NUM + r")(?!\d)")
PRICE_SUFFIX_RE = re.compile(r"(?<![\w.,])(" + _NUM + r")\s?(" + _CUR + r")(?![A-Za-z])")

def _num(raw):
    t = raw.replace(" ", "").replace("\u00a0", "")
    if re.search(r"\.\d{3}(\D|$)", t) and "," not in t:      # 1.299 (European thousands)
        t = t.replace(".", "")
    elif re.search(r",\d{2}$", t) and t.count(",") == 1 and "." in t:   # 1.299,00
        t = t.replace(".", "").replace(",", ".")
    else:
        t = t.replace(",", "")
    return float(t)

def now_date():
    from .database import _utcnow
    return _utcnow().strftime("%Y-%m-%d")

def norm(s):
    return re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower().replace("-", " ")).strip()

def tokens(s):
    return [t for t in norm(s).split() if t]

def similarity(a, b):
    a, b = norm(a), norm(b)
    if fuzz:
        return fuzz.token_sort_ratio(a, b)
    return 100 * difflib.SequenceMatcher(None, a, b).ratio()

def parse_price(text):
    text = text or ""
    for rx, ci, vi in ((PRICE_RE, 1, 2), (PRICE_SUFFIX_RE, 2, 1)):
        m = rx.search(text)
        if m:
            try:
                v = _num(m.group(vi))
            except ValueError:
                continue
            if v <= 0:
                continue
            return {"raw": m.group(0).strip(), "currency": m.group(ci).replace(" ", ""), "value": v}
    return None

ACCESSORY = {"case", "cases", "cover", "covers", "protector", "protectors", "skin", "skins", "strap", "straps", "compatible", "replacement", "holder",
             "mount", "sticker", "stickers", "decal", "tempered", "pouch", "carrying", "sleeve", "propeller", "propellers", "refill", "refills", "parts",
             "accessories", "accessory", "guard", "film", "protection", "keychain", "playoffs", "hockey", "nhl", "paperback", "hardcover",
             "poster", "dvd", "blu", "novel", "calendar", "costume", "charm", "charms", "lanyard", "dock", "stand", "bag", "manual", "guide", "book", "ebook"}
EXPAND = {"playstation 5": "ps5", "playstation5": "ps5", "playstation 4": "ps4", "play station 5": "ps5", "nintendo switch 2": "switch2"}
_GENERIC_WORDS = {"pro", "max", "plus", "mini", "ultra", "lite", "new", "smart", "wireless", "portable", "electric", "with", "for", "and"}

NOUN_SYN = [{"football", "soccer ball", "soccerball"}, {"shoe", "sneaker", "trainer", "footwear"}, {"machine", "maker", "brewer"},
            {"smartwatch", "smart watch", "watch"}, {"earbud", "earphone", "bud", "headphone", "tws"}, {"tumbler", "cup", "mug", "bottle"},
            {"power bank", "powerbank", "portable charger", "battery pack"}, {"speaker", "soundbar"}, {"laptop", "notebook"}, {"tablet", "tab", "ipad"},
            {"perfume", "fragrance", "eau de parfum", "edp", "parfum"}, {"console", "playstation", "xbox"}, {"phone", "smartphone", "mobile"},
            {"air fryer", "airfryer"}, {"vacuum", "vacuum cleaner"}, {"serum", "essence", "ampoule"}, {"drone", "quadcopter"}]

VARIANTS = {"pro", "max", "plus", "ultra", "mini", "lite", "fe", "air", "slim", "digital", "edge"}

def _sing(w):
    return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w

_GLUE = re.compile(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])")

def split_glued(t):
    """'galaxy z fold7' -> 'galaxy z fold 7', 's25' -> 's 25' (applied to BOTH sides of a match)."""
    return _GLUE.sub(" ", t)

def _expand(t):
    for k, v in EXPAND.items():
        if k in t:
            t += " " + v
        elif re.search(r"\b" + re.escape(v) + r"\b", t):
            t += " " + k                             # both directions: ps5 <-> playstation 5
    return t

def match_product(cand, text, threshold=85):
    """0..100 match between a candidate and a listing title. Rejects accessories FOR the product ('case for Google Pixel 11'),
    requires the same model numbers and the brand (or a distinctive product-line word such as 'labubu', 'creami')."""
    t = split_glued(_expand(norm(text)))
    t = re.sub(r"\b(size|pack of|set of|qty|quantity)\s+\d+\b", " ", t)
    ttoks = t.split(); tset = set(ttoks)
    if not t:
        return 0
    brand0 = tokens(cand.get("brand") or "")
    if t.startswith("sponsored ad from") and brand0 and not all(b in ttoks[3:6] for b in brand0):
        return 0                                         # banner ad of ANOTHER brand ("Sponsored ad from JETech ... Pixel 11")
    cand_words = set(tokens(split_glued(norm(cand["name"]))) + tokens(cand.get("noun") or ""))
    acc = [w for w in tset & ACCESSORY if w not in cand_words]
    if acc:
        return 0
    brand = tokens(cand.get("brand") or "")
    if brand and "for" in ttoks:                        # "... compatible / for Apple iPhone 17": accessory unless the brand leads the title
        i = ttoks.index("for")
        if any(b in ttoks[i + 1:i + 4] for b in brand) and not all(b in ttoks[:i] for b in brand):
            return 0
    noun_words = set(tokens(cand.get("noun") or ""))
    distinctive = {x for x in tokens(split_glued(_expand(norm(cand["name"])))) + tokens(split_glued(norm(cand.get("search_name") or "")))
                   if not x.isdigit() and len(x) >= (3 if any(c.isdigit() for c in x) else 4) and x not in noun_words and x not in brand and x not in _GENERIC_WORDS}
    brand_ok = (not brand) or all(b in tset for b in brand) or bool(distinctive & tset)
    if not brand_ok:
        return 0
    tsing = {_sing(x) for x in tset}
    tjoined = " " + " ".join(_sing(x) for x in ttoks) + " "
    noun_alts = set()
    for w in noun_words | {norm(cand.get("noun") or "")}:
        for g in NOUN_SYN:
            if _sing(w) in g or w in g:
                noun_alts |= g
    noun_hit = bool(noun_words) and (all(_sing(w) in tsing for w in noun_words) or any(f" {_sing(a)} " in tjoined for a in noun_alts))
    best = 0
    for n in [cand["name"]] + list(cand.get("alt_names", [])) + ([cand["search_name"]] if cand.get("search_name") else []):
        ntoks = tokens(split_glued(_expand(norm(n))))
        if not ntoks:
            continue
        models = [x for x in ntoks if any(c.isdigit() for c in x)]
        if models and not all(m in tset for m in models):
            continue
        # variant words must agree: 'PS5 Pro' != 'PS5 Digital', 'iPhone 16 Pro' != 'iPhone 16 Pro Max'
        cvar = {x for x in ntoks if x in VARIANTS}
        if not cvar <= tset:
            continue
        if models:
            i = next((k for k, x in enumerate(ttoks) if x == models[-1]), None)
            if i is not None and any(x in VARIANTS and x not in cvar for x in ttoks[i + 1:i + 3]):
                continue
        core = [x for x in ntoks if x not in brand and x not in noun_words]
        nouns_in_n = [x for x in ntoks if x in noun_words]
        have = sum(1 for x in core if _sing(x) in tsing)
        if nouns_in_n:                                   # product type: exact words, plural/singular or a synonym ("soccer ball" for football)
            if not noun_hit and not (core and have == len(core) and (distinctive & tset or models)):
                continue
        cover = 100 * have / len(core) if core else 100
        best = max(best, cover)
    return best if best >= threshold else 0

def extract_listings(html, base):
    soup = BeautifulSoup(html or "", "html.parser")
    out, seen = [], set()
    for a in soup.find_all("a", href=True)[:1500]:
        txt = a.get_text(" ", strip=True)
        if len(txt) < 12:
            img = a.find("img")
            txt = (img.get("alt") if img and img.get("alt") else None) or a.get("title") or a.get("aria-label") or txt
        if not txt or len(txt) < 8:
            continue
        href = urljoin(base, a["href"])
        ctx = ""
        node = a
        for _ in range(5):
            if node.parent is None:
                break
            node = node.parent
            t = node.get_text(" ", strip=True)
            if len(t) > 700:
                break
            ctx = t
            if PRICE_RE.search(t):          # smallest container that holds a price = this product's card
                break
        k = (href, txt[:50])
        if k in seen:
            continue
        seen.add(k)
        out.append({"title": txt[:200], "url": href, "context": ctx or txt, "price": parse_price(ctx or txt)})
        if len(out) >= 400:
            break
    return out

def page_usable(html, listings, min_cards=3):
    """A page is usable evidence only if it shows a recognisable product grid or an explicit no-results message."""
    low = (html or "").lower()
    if any(p in low for p in NO_RESULT_PHRASES):
        return True
    return sum(1 for l in listings if l["price"]) >= min_cards

def domain_of(url):
    return urlparse(url).netloc.lower().replace("www.", "")

def best_match(cand, listings, url_filter=None):
    best, bs = None, 0
    brand = norm(cand.get("brand") or "")
    for l in listings:
        if url_filter and not url_filter(l["url"]):
            continue
        sc = match_product(cand, l["title"])
        if not sc and brand and brand not in norm(l["title"]) and brand in norm((l.get("context") or "")[:160]):
            sc = match_product(cand, f"{cand.get('brand')} {l['title']}")      # brand printed on the card, not in the title
        if sc > bs:
            best, bs = l, sc
    return (best, bs) if best else (None, 0)

def availability_from_context(ctx):
    low = (ctx or "").lower()
    if any(p in low for p in NO_DELIVERY):
        return "DELIVERY UNAVAILABLE"
    if any(p in low for p in UNAVAILABLE):
        return "OUT OF STOCK"
    return "AVAILABLE"
