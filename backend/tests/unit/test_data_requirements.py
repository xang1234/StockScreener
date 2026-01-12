#!/usr/bin/env python
"""
Test to verify Minervini scan only fetches price data and quarterly growth,
NOT fundamental data.
"""
import os
import sys

# Add backend directory to path (go up 3 levels: unit -> tests -> backend)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.scanners.screener_registry import screener_registry
from app.scanners.minervini_scanner_v2 import MinerviniScannerV2
from app.scanners.data_preparation import DataPreparationLayer

print("=" * 80)
print("MINERVINI DATA REQUIREMENTS TEST")
print("=" * 80)
print()

# 1. Check if MinerviniScannerV2 is registered
print("[1] Checking screener registry...")
print("-" * 80)
screeners = screener_registry.list_screeners()
print(f"Registered screeners: {screeners}")

if "minervini" in screeners:
    print("✓ Minervini screener is registered")
else:
    print("✗ ERROR: Minervini screener NOT registered!")
    sys.exit(1)

print()

# 2. Get the minervini screener
print("[2] Getting Minervini screener from registry...")
print("-" * 80)
minervini = screener_registry.get("minervini")
print(f"Screener class: {minervini.__class__.__name__}")
print(f"Screener name: {minervini.screener_name}")

if isinstance(minervini, MinerviniScannerV2):
    print("✓ Using MinerviniScannerV2 (correct)")
else:
    print(f"✗ WARNING: Using {minervini.__class__.__name__} instead of MinerviniScannerV2")

print()

# 3. Check data requirements
print("[3] Checking Minervini data requirements...")
print("-" * 80)
requirements = minervini.get_data_requirements()

print(f"Price period: {requirements.price_period}")
print(f"Needs fundamentals: {requirements.needs_fundamentals}")
print(f"Needs quarterly growth: {requirements.needs_quarterly_growth}")
print(f"Needs benchmark: {requirements.needs_benchmark}")
print(f"Needs earnings history: {requirements.needs_earnings_history}")
print()

# Verify requirements
if requirements.needs_fundamentals:
    print("✗ ERROR: Minervini should NOT need fundamentals!")
    print("  Minervini only uses price data, not fundamental metrics like PE ratio")
else:
    print("✓ CORRECT: needs_fundamentals=False")

if not requirements.needs_quarterly_growth:
    print("⚠ WARNING: Minervini should need quarterly growth data!")
else:
    print("✓ CORRECT: needs_quarterly_growth=True")

if not requirements.needs_benchmark:
    print("✗ ERROR: Minervini should need benchmark (SPY) for RS rating!")
else:
    print("✓ CORRECT: needs_benchmark=True")

print()

# 4. Test merge requirements with multiple screeners
print("[4] Testing merged requirements for multi-screener scan...")
print("-" * 80)
data_prep = DataPreparationLayer()

# Get CANSLIM screener (which needs fundamentals)
canslim = screener_registry.get("canslim")
if canslim:
    canslim_reqs = canslim.get_data_requirements()
    print(f"\nCANSLIM requirements:")
    print(f"  needs_fundamentals: {canslim_reqs.needs_fundamentals}")
    print(f"  needs_quarterly_growth: {canslim_reqs.needs_quarterly_growth}")

    # Merge requirements
    merged = data_prep.merge_requirements([requirements, canslim_reqs])

    print(f"\nMerged requirements (Minervini + CANSLIM):")
    print(f"  needs_fundamentals: {merged.needs_fundamentals}")
    print(f"  needs_quarterly_growth: {merged.needs_quarterly_growth}")

    if merged.needs_fundamentals:
        print("✓ CORRECT: Merged requirements include fundamentals (needed by CANSLIM)")
    else:
        print("✗ ERROR: Merged requirements should include fundamentals!")
else:
    print("CANSLIM screener not found - skipping merge test")

print()

# Summary
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print()

if not requirements.needs_fundamentals and requirements.needs_quarterly_growth:
    print("✓ TEST PASSED")
    print()
    print("Minervini scan will only fetch:")
    print("  - Price data (2y period)")
    print("  - Quarterly growth data (EPS/sales)")
    print("  - Benchmark data (SPY for RS rating)")
    print()
    print("It will NOT fetch:")
    print("  - Fundamental data (PE ratio, market cap, etc.)")
    print()
    print("This means running a Minervini scan should be faster and")
    print("should not show 'downloading fundamental data' in the logs.")
else:
    print("✗ TEST FAILED")
    print()
    print("Minervini scan configuration is incorrect!")

print()
