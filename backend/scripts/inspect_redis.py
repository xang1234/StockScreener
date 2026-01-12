#!/usr/bin/env python
"""
Debug script to check what's actually in Redis.
"""
import os
import sys

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import redis
from app.config import settings

# Connect to Redis DB 2 (cache DB)
r = redis.Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    db=2,  # Cache DB
    decode_responses=True
)

print("=" * 80)
print("REDIS CACHE INSPECTION (DB 2)")
print("=" * 80)
print()

# Check SPY benchmark keys
print("[1] SPY Benchmark Keys:")
print("-" * 80)
spy_2y = "benchmark:SPY:2y"
spy_1y = "benchmark:SPY:1y"

print(f"  {spy_2y}: {'EXISTS' if r.exists(spy_2y) else 'NOT FOUND'}")
if r.exists(spy_2y):
    ttl = r.ttl(spy_2y)
    print(f"    TTL: {ttl}s ({ttl/3600:.1f}h)")

print(f"  {spy_1y}: {'EXISTS' if r.exists(spy_1y) else 'NOT FOUND'}")
if r.exists(spy_1y):
    ttl = r.ttl(spy_1y)
    print(f"    TTL: {ttl}s ({ttl/3600:.1f}h)")
print()

# Check price keys
print("[2] Price Cache Keys:")
print("-" * 80)
price_keys = r.keys("price:*")
print(f"  Total price keys: {len(price_keys)}")

# Count unique symbols
symbols = set()
for key in price_keys:
    parts = key.split(':')
    if len(parts) >= 2:
        symbols.add(parts[1])

print(f"  Unique symbols cached: {len(symbols)}")
if symbols:
    print(f"  Symbols: {', '.join(sorted(list(symbols))[:20])}")
    if len(symbols) > 20:
        print(f"           ... and {len(symbols) - 20} more")
print()

# Check fundamentals keys
print("[3] Fundamentals Cache Keys:")
print("-" * 80)
fund_keys = r.keys("fundamentals:*")
print(f"  Total fundamentals keys: {len(fund_keys)}")

fund_symbols = set()
for key in fund_keys:
    parts = key.split(':')
    if len(parts) >= 2:
        fund_symbols.add(parts[1])

print(f"  Unique symbols with fundamentals: {len(fund_symbols)}")
print()

# Check quarterly keys
print("[4] Quarterly Cache Keys:")
print("-" * 80)
quarterly_keys = r.keys("quarterly:*")
print(f"  Total quarterly keys: {len(quarterly_keys)}")
print()

# Summary
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"SPY Benchmark: {'✓ Cached' if r.exists(spy_2y) else '✗ Not Cached'}")
print(f"Price Cache: {len(symbols)} symbols")
print(f"Fundamentals Cache: {len(fund_symbols)} symbols")
print(f"Quarterly Cache: {len(quarterly_keys)} keys")
print()
