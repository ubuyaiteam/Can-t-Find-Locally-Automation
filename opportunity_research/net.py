"""Polite HTTP layer: robots.txt, per-domain rate limit, SQLite cache, request budget, retry/backoff,
block detection (never bypasses CAPTCHA / anti-bot), optional Playwright rendering."""
import threading, time
from urllib.parse import urlparse
from urllib import robotparser
import requests

BLOCK_MARKERS = ("captcha", "robot check", "access denied", "unusual traffic", "enter the characters you see",
                 "are you a human", "verify you are human", "pardon our interruption", "request blocked")
_PW_LOCK = threading.Lock()

class BudgetExceeded(Exception): pass
class Cancelled(Exception): pass

class Result:
    def __init__(self, status, http=0, text="", url="", cached=False):
        self.status, self.http, self.text, self.url, self.cached = status, http, text, url, cached
    @property
    def ok(self): return self.status == "ok"

class RunContext:
    def __init__(self, db=None, run_id=None):
        self.db, self.run_id = db, run_id
        self.cancel = threading.Event()
    def check(self):
        if self.cancel.is_set():
            raise Cancelled()
    def log(self, agent, msg, level="info"):
        if self.db and self.run_id:
            try: self.db.log(self.run_id, agent, msg, level)
            except Exception: pass

class _Renderer:
    """One persistent headless Chromium in its own thread (Playwright's sync API is single-threaded).
    Renders JavaScript pages exactly as a visitor's browser would. Never solves CAPTCHAs / challenges."""
    def __init__(self):
        self._q = None; self._ok = None; self._lock = threading.Lock()

    def available(self):
        if self._ok is None:
            try:
                import playwright.sync_api  # noqa: F401
                self._ok = True
            except Exception:
                self._ok = False
        return self._ok

    def _worker(self, q, ua):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            try:
                b = p.chromium.launch(headless=True)
            except Exception as e:                    # browser binary missing: python -m playwright install chromium
                self._ok = False
                while True:
                    job = q.get(); job[3]["err"] = f"Chromium not installed ({str(e)[:80]})"; job[2].set()
            ctx = b.new_context(user_agent=ua, locale="en-US", viewport={"width": 1366, "height": 900})
            while True:
                url, wait_for, done, out = q.get()
                pg = ctx.new_page()
                try:
                    resp = pg.goto(url, timeout=out["timeout"], wait_until="domcontentloaded")
                    if wait_for:
                        try: pg.wait_for_selector(wait_for, timeout=out["timeout"])
                        except Exception: pass
                    pg.wait_for_timeout(1500)
                    out["code"], out["html"] = (resp.status if resp else 0), pg.content()
                except Exception as e:
                    out["err"] = str(e)[:150]
                finally:
                    pg.close(); done.set()

    def render(self, url, s, wait_for=None):
        import queue
        with self._lock:
            if self._q is None:
                self._q = queue.Queue()
                for _ in range(max(1, int(s.get("render_workers", 3)))):        # parallel browser workers
                    threading.Thread(target=self._worker, args=(self._q, s["user_agent"]), daemon=True).start()
        done, out = threading.Event(), {"timeout": max(20, s["request_timeout"] * 2) * 1000}
        self._q.put((url, wait_for, done, out))
        done.wait(timeout=out["timeout"] / 1000 * 3 + 10)
        if "html" not in out:
            raise RuntimeError(out.get("err") or "render timeout")
        return out["code"], out["html"]

RENDERER = _Renderer()

class Fetcher:
    def __init__(self, db, settings, ctx=None):
        self.db, self.s, self.ctx = db, settings, ctx
        self.n_requests = 0
        self._lock = threading.Lock()
        self._tlock = threading.Lock()
        self._next = {}
        self._delay = {}
        self._blocks = {}            # consecutive hard blocks per host (circuit breaker)
        self._robots = {}
        self.health = {}   # host -> {ok, blocked, error, robots, cached}
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": settings["user_agent"], "Accept-Language": "en-US,en;q=0.9",
                                     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7"})

    # ---- overridable network primitives (tests replace _raw_get)
    def _raw_get(self, url, render=False, wait_for=None):
        if render:
            return self._render(url, wait_for)
        r = self.session.get(url, timeout=self.s["request_timeout"], allow_redirects=True)
        r.encoding = r.encoding or "utf-8"
        return r.status_code, r.text

    def _render(self, url, wait_for=None):
        return RENDERER.render(url, self.s, wait_for)

    def _robots_txt(self, host, scheme):
        r = self.session.get(f"{scheme}://{host}/robots.txt", timeout=self.s["request_timeout"])
        return r.status_code, r.text

    # ---- helpers
    def _hit(self, host, key):
        with self._lock:
            h = self.health.setdefault(host, {"ok": 0, "blocked": 0, "error": 0, "robots": 0, "cached": 0})
            h[key] += 1

    def _allowed(self, url):
        u = urlparse(url)
        host = u.netloc.lower()
        if host not in self._robots:
            rp = robotparser.RobotFileParser()
            try:
                code, txt = self._robots_txt(host, u.scheme or "https")
                if code >= 500:
                    rp = None                       # server error -> be conservative
                elif code >= 400:
                    rp.parse([])                    # no robots.txt -> allowed
                else:
                    rp.parse(txt.splitlines())
            except Exception:
                rp = None
            self._robots[host] = rp
        rp = self._robots[host]
        return bool(rp and rp.can_fetch(self.s["user_agent"], url))

    def _start_delay(self, host):
        return self.s.get("host_delays", {}).get(host, self.s["min_delay_per_domain"])

    def _floor(self, host):
        f = self.s.get("host_min_delays", {}).get(host)
        if f is None:
            f = self.s.get("host_min_delays", {}).get("*" + host[host.find("."):] if "." in host else host, None)
        return f if f is not None else min(self._start_delay(host), float(self.s.get("default_min_delay", 0.8)))

    def _adapt(self, host, ok):
        """AIMD pacing: speed up slowly while a site answers normally, back off fast on 'too many requests'."""
        if self.s["min_delay_per_domain"] == 0 or not self.s.get("adaptive_throttle", True):
            return
        with self._tlock:
            d = self._delay.get(host, self._start_delay(host))
            self._delay[host] = max(self._floor(host), d * 0.92) if ok else min(20.0, max(d, 0.5) * 2.5)

    def _throttle(self, host):
        d = 0 if self.s["min_delay_per_domain"] == 0 else self._delay.get(host, self._start_delay(host))
        with self._tlock:
            now = time.time()
            t = max(now, self._next.get(host, 0))
            self._next[host] = t + d
        if t > now:
            time.sleep(t - now)

    def get(self, url, render=False, cache=True, wait_for=None):
        if self.ctx: self.ctx.check()
        host = urlparse(url).netloc.lower()
        if render and not RENDERER.available():
            render = False                              # Playwright not installed -> plain HTTP
        if cache:
            row = self.db.cache_get(url + ("#rendered" if render else ""), self.s["cache_ttl_hours"])
            if row:
                self._hit(host, "cached")
                return Result("ok", row["status"], row["body"], url, cached=True)
        own = self.s.get("ubuy_ignore_robots", True) and ".ubuy." in "." + host     # your own storefront
        if self._blocks.get(host, 0) >= int(self.s.get("block_circuit_breaker", 3)):
            self._hit(host, "blocked")
            return Result("blocked", 0, "", url)          # site has blocked every recent request: skip it this run (same verdict, no waiting)
        if self.s["respect_robots"] and not own and host not in self.s["robots_exempt_hosts"] and not self._allowed(url):
            self._hit(host, "robots")
            return Result("robots", 0, "", url)
        with self._lock:
            if self.n_requests >= self.s["max_requests_per_run"]:
                return Result("budget", 0, "", url)
            self.n_requests += 1
        self._throttle(host)
        last_err = ""
        for attempt in range(self.s["retries"] + 1):
            if self.ctx: self.ctx.check()
            try:
                code, text = self._raw_get(url, render, wait_for) if wait_for else self._raw_get(url, render)
            except Exception as e:                      # timeout / connection problems -> retry with backoff
                last_err = str(e)[:120]
                time.sleep(min(1.5 ** attempt, 4) * (0 if self.s["min_delay_per_domain"] == 0 else 1))
                continue
            low = (text or "")[:6000].lower()
            if code in (429, 503) and "captcha" not in low and attempt < self.s["retries"]:
                self._adapt(host, False)                   # temporary rate limit: slow down and retry (not a block)
                time.sleep(self._delay.get(host, 2.0))
                self._throttle(host)
                last_err = f"HTTP {code}"
                continue
            blocked = code in (401, 403, 407, 429) or (code == 503 and "captcha" in low) or (any(m in low for m in BLOCK_MARKERS) and len(text or "") < 20000)
            if blocked:
                with self._tlock:
                    self._blocks[host] = self._blocks.get(host, 0) + 1
                self._hit(host, "blocked")
                return Result("blocked", code, "", url)       # never retried, never bypassed
            if code >= 500:
                last_err = f"HTTP {code}"
                time.sleep(min(1.5 ** attempt, 4) * (0 if self.s["min_delay_per_domain"] == 0 else 1))
                continue
            if code >= 400:
                self._hit(host, "error")
                return Result("error", code, "", url)
            self._hit(host, "ok"); self._adapt(host, True)
            with self._tlock: self._blocks[host] = 0
            if cache and text:
                self.db.cache_put(url + ("#rendered" if render else ""), code, text)
            return Result("ok", code, text, url)
        self._hit(host, "error")
        return Result("error", 0, last_err, url)
