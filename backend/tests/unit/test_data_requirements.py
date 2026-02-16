"""Tests for DataRequirements defaults, merging, and screener declarations."""
from app.scanners.base_screener import DataRequirements
from app.scanners.data_preparation import DataPreparationLayer


class TestDataRequirementsDefaults:
    """Verify bare DataRequirements() is minimal — no expensive fetches."""

    def test_defaults_are_minimal(self):
        req = DataRequirements()
        assert req.price_period == "2y"
        assert req.needs_fundamentals is False
        assert req.needs_quarterly_growth is False
        assert req.needs_benchmark is False
        assert req.needs_earnings_history is False


class TestMergeRequirements:
    """Test merge logic via DataPreparationLayer.merge_requirements."""

    def setup_method(self):
        self.data_layer = DataPreparationLayer.__new__(DataPreparationLayer)

    def test_empty_list_returns_minimal(self):
        merged = self.data_layer.merge_requirements([])
        assert merged.needs_fundamentals is False
        assert merged.needs_benchmark is False
        assert merged.needs_quarterly_growth is False
        assert merged.needs_earnings_history is False

    def test_single_requirement_passthrough(self):
        single = DataRequirements(
            price_period="5y",
            needs_fundamentals=True,
            needs_benchmark=True,
            needs_quarterly_growth=True,
            needs_earnings_history=True,
        )
        merged = self.data_layer.merge_requirements([single])
        assert merged.price_period == "5y"
        assert merged.needs_fundamentals is True
        assert merged.needs_benchmark is True
        assert merged.needs_quarterly_growth is True
        assert merged.needs_earnings_history is True

    def test_merge_takes_union_of_booleans(self):
        a = DataRequirements(needs_fundamentals=True, needs_benchmark=False)
        b = DataRequirements(needs_fundamentals=False, needs_benchmark=True)
        merged = self.data_layer.merge_requirements([a, b])
        assert merged.needs_fundamentals is True
        assert merged.needs_benchmark is True

    def test_merge_takes_longest_period(self):
        short = DataRequirements(price_period="1y")
        long = DataRequirements(price_period="5y")
        merged = self.data_layer.merge_requirements([short, long])
        assert merged.price_period == "5y"

    def test_merge_three_requirements(self):
        a = DataRequirements(needs_fundamentals=True)
        b = DataRequirements(needs_quarterly_growth=True, price_period="5y")
        c = DataRequirements(needs_benchmark=True, needs_earnings_history=True)
        merged = self.data_layer.merge_requirements([a, b, c])
        assert merged.needs_fundamentals is True
        assert merged.needs_quarterly_growth is True
        assert merged.needs_benchmark is True
        assert merged.needs_earnings_history is True
        assert merged.price_period == "5y"


class TestScreenerRequirements:
    """Spot-check that screeners declare correct requirements."""

    def test_canslim_needs_fundamentals_and_benchmark(self):
        from app.scanners.canslim_scanner import CANSLIMScanner

        req = CANSLIMScanner().get_data_requirements()
        assert req.needs_fundamentals is True
        assert req.needs_benchmark is True
        assert req.needs_quarterly_growth is True
        assert req.needs_earnings_history is False  # Uses eps_growth_yy from quarterly_growth

    def test_minervini_skips_fundamentals(self):
        from app.scanners.minervini_scanner_v2 import MinerviniScannerV2

        req = MinerviniScannerV2().get_data_requirements()
        assert req.needs_fundamentals is False
        assert req.needs_benchmark is True
        assert req.needs_quarterly_growth is False  # Informational only, not used in scoring

    def test_volume_breakthrough_needs_long_history(self):
        from app.scanners.volume_breakthrough_scanner import VolumeBreakthroughScanner

        req = VolumeBreakthroughScanner().get_data_requirements()
        assert req.price_period == "5y"
        assert req.needs_fundamentals is True
        assert req.needs_benchmark is False
