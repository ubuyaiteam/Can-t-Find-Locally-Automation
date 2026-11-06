import json, os, sqlite3, threading, time
from datetime import datetime, timedelta, timezone

def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY AUTOINCREMENT, country_code TEXT, country_name TEXT,
  period_days INTEGER, category TEXT, max_results INTEGER, status TEXT, stage TEXT, progress REAL DEFAULT 0,
  created_at TEXT, updated_at TEXT, state_json TEXT, counters_json TEXT, health_json TEXT, error TEXT);
CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER, ts TEXT, agent TEXT, level TEXT, message TEXT);
CREATE INDEX IF NOT EXISTS ix_logs_run ON logs(run_id, id);
CREATE TABLE IF NOT EXISTS cache(url TEXT PRIMARY KEY, status INTEGER, body TEXT, fetched_at REAL);
CREATE TABLE IF NOT EXISTS observations(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER, country_code TEXT,
  product_key TEXT, name TEXT, kind TEXT, period_start TEXT, period_end TEXT, value REAL, observed_at TEXT, source TEXT);
CREATE INDEX IF NOT EXISTS ix_obs ON observations(country_code, product_key);
CREATE TABLE IF NOT EXISTS forecasts(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER, country_code TEXT,
  product_key TEXT, made_at TEXT, horizon_days INTEGER, direction TEXT, baseline REAL, outcome TEXT, reviewed_at TEXT);
CREATE TABLE IF NOT EXISTS results(run_id INTEGER, product_key TEXT, bucket TEXT, rank INTEGER, score REAL,
  confidence REAL, payload_json TEXT, PRIMARY KEY(run_id, product_key));
CREATE TABLE IF NOT EXISTS product_verdicts(country_code TEXT, product_key TEXT, name TEXT, gap TEXT, reason TEXT, checked_at TEXT,
  PRIMARY KEY(country_code, product_key));
CREATE TABLE IF NOT EXISTS evidence(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER, product_key TEXT,
  agent TEXT, source TEXT, url TEXT, status TEXT, note TEXT, checked_at TEXT);
"""

def now():
    return _utcnow().strftime("%Y-%m-%d %H:%M:%S")

class DB:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.path = path
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
        self.conn.row_factory = sqlite3.Row
        try:
            self.conn.execute("PRAGMA journal_mode=WAL")
        except Exception:
            pass
        self.conn.executescript(SCHEMA)
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(runs)").fetchall()}
        if "parent_id" not in cols:                       # migration for databases created by v1
            self.conn.execute("ALTER TABLE runs ADD COLUMN parent_id INTEGER")
        self.conn.commit()

    def q(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def x(self, sql, args=()):
        with self.lock:
            cur = self.conn.execute(sql, args)
            self.conn.commit()
            return cur.lastrowid

    # ---- runs
    def create_run(self, country_code, country_name, period, category, max_results, parent_id=None):
        return self.x("INSERT INTO runs(country_code,country_name,period_days,category,max_results,status,stage,created_at,updated_at,state_json,parent_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                      (country_code, country_name, period, category, max_results, "queued", "queued", now(), now(), "{}", parent_id))

    def update_run(self, run_id, **kw):
        kw["updated_at"] = now()
        cols = ",".join(f"{k}=?" for k in kw)
        self.x(f"UPDATE runs SET {cols} WHERE id=?", list(kw.values()) + [run_id])

    def get_run(self, run_id):
        r = self.q("SELECT * FROM runs WHERE id=?", (run_id,))
        return r[0] if r else None

    def list_runs(self, limit=50):
        return self.q("SELECT id,country_code,country_name,period_days,category,status,stage,progress,created_at,counters_json,parent_id FROM runs ORDER BY id DESC LIMIT ?", (limit,))

    def children(self, parent_id):
        return self.q("SELECT id,country_code,country_name,status,counters_json FROM runs WHERE parent_id=? ORDER BY id", (parent_id,))

    def mark_interrupted(self):
        self.x("UPDATE runs SET status='interrupted' WHERE status IN ('running','queued')")

    # ---- logs
    def log(self, run_id, agent, message, level="info"):
        self.x("INSERT INTO logs(run_id,ts,agent,level,message) VALUES(?,?,?,?,?)", (run_id, now(), agent, level, message[:600]))

    def get_logs(self, run_id, after=0, limit=200):
        return self.q("SELECT id,ts,agent,level,message FROM logs WHERE run_id=? AND id>? ORDER BY id LIMIT ?", (run_id, after, limit))

    # ---- cache
    def cache_get(self, url, ttl_hours):
        r = self.q("SELECT status,body,fetched_at FROM cache WHERE url=?", (url,))
        if r and time.time() - r[0]["fetched_at"] < ttl_hours * 3600:
            return r[0]
        return None

    def cache_put(self, url, status, body):
        self.x("INSERT OR REPLACE INTO cache(url,status,body,fetched_at) VALUES(?,?,?,?)", (url, status, body[:600000], time.time()))

    # ---- observations / forecasts
    def add_observations(self, run_id, cc, key, name, kind, series, source):
        with self.lock:
            for (s, e, v) in series:
                self.conn.execute("INSERT INTO observations(run_id,country_code,product_key,name,kind,period_start,period_end,value,observed_at,source) VALUES(?,?,?,?,?,?,?,?,?,?)",
                                  (run_id, cc, key, name, kind, s, e, v, now(), source))
            self.conn.commit()

    def add_forecast(self, run_id, cc, key, horizon, direction, baseline):
        self.x("INSERT INTO forecasts(run_id,country_code,product_key,made_at,horizon_days,direction,baseline) VALUES(?,?,?,?,?,?,?)",
               (run_id, cc, key, now(), horizon, direction, baseline))

    def review_forecasts(self, cc, key, current_level):
        """Compare earlier forecasts (whose horizon has elapsed) with the newly observed level."""
        out = []
        for f in self.q("SELECT * FROM forecasts WHERE country_code=? AND product_key=? AND outcome IS NULL", (cc, key)):
            made = datetime.strptime(f["made_at"], "%Y-%m-%d %H:%M:%S")
            if (_utcnow() - made).days < f["horizon_days"]:
                continue
            b = f["baseline"] or 0.0
            d = f["direction"]
            if d.startswith("Rising"):
                ok = current_level >= max(b * 1.1, 0.5)
            elif d.startswith("Falling"):
                ok = current_level <= b * 0.9
            else:
                ok = abs(current_level - b) <= max(0.2 * b, 0.5)
            outcome = "supported" if ok else "not supported"
            self.x("UPDATE forecasts SET outcome=?, reviewed_at=? WHERE id=?", (outcome, now(), f["id"]))
            out.append(outcome)
        return out

    def forecast_track_record(self, cc=None):
        sql = "SELECT outcome, COUNT(*) n FROM forecasts WHERE outcome IS NOT NULL"
        args = ()
        if cc:
            sql += " AND country_code=?"; args = (cc,)
        return {r["outcome"]: r["n"] for r in self.q(sql + " GROUP BY outcome", args)}

    # ---- results
    def save_results(self, run_id, rows):
        with self.lock:
            self.conn.execute("DELETE FROM results WHERE run_id=?", (run_id,))
            for r in rows:
                self.conn.execute("INSERT OR REPLACE INTO results VALUES(?,?,?,?,?,?,?)",
                                  (run_id, r["key"], r["bucket"], r.get("rank") or 0, r.get("score") or 0, r.get("confidence") or 0, json.dumps(r, default=str)))
            self.conn.commit()

    def get_results(self, run_id, bucket=None):
        sql = "SELECT payload_json FROM results WHERE run_id=?"
        args = [run_id]
        if bucket:
            sql += " AND bucket=?"; args.append(bucket)
        sql += " ORDER BY CASE WHEN rank>0 THEN rank ELSE 99999 END, score DESC"
        return [json.loads(r["payload_json"]) for r in self.q(sql, args)]

    # ---- verdict memory (variety between runs: products confirmed as sold locally are skipped for a while)
    def put_verdict(self, cc, key, name, gap, reason=""):
        self.x("INSERT OR REPLACE INTO product_verdicts VALUES(?,?,?,?,?,?)", (cc, key, name, gap, (reason or "")[:200], now()))

    def recent_verdicts(self, cc, days, gaps=("NO_GAP",)):
        cutoff = (_utcnow() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        q = "SELECT product_key FROM product_verdicts WHERE country_code=? AND checked_at>=? AND gap IN (%s)" % ",".join("?" * len(gaps))
        return {r["product_key"] for r in self.q(q, (cc, cutoff, *gaps))}

    def prune_cache(self, days=7):
        self.x("DELETE FROM cache WHERE fetched_at < ?", (time.time() - days * 86400,))

    def add_evidence(self, run_id, key, agent, source, url, status, note=""):
        self.x("INSERT INTO evidence(run_id,product_key,agent,source,url,status,note,checked_at) VALUES(?,?,?,?,?,?,?,?)",
               (run_id, key, agent, source, url, status, note[:300], now()))
