"""Command-line source health check.   Usage:  python diagnose.py NG   (any ISO country code; several allowed: python diagnose.py NG KE ZA)"""
import sys
from opportunity_research import settings, healthcheck
from opportunity_research.database import DB
from opportunity_research.net import Fetcher

def main(codes):
    s = settings.load()
    f = Fetcher(DB(s["db_path"]), s)
    for code in codes or ["NG"]:
        r = healthcheck.run(f, s, code)
        print(f"\n=== {r['country']} ({r['code']}) - sample product '{r['sample']}' - {r['ok']}/{r['total']} sources OK")
        print("Verdict:", r["verdict"])
        for row in r["rows"]:
            print(f"  [{'OK ' if row['ok'] else 'FAIL'}] {row['source']:<45} {row['seconds']:>5}s  {row['detail']}")

if __name__ == "__main__":
    main([a.upper() for a in sys.argv[1:]])
