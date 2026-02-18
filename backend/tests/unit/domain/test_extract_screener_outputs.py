"""Tests for extract_screener_outputs domain function."""

import pytest

from app.domain.feature_store.models import extract_screener_outputs


class TestExtractScreenerOutputs:
    """Tests for the details blob → ScreenerOutputDomain extraction."""

    def test_valid_screeners(self):
        details = {
            "details": {
                "screeners": {
                    "minervini": {
                        "score": 75.0,
                        "passes": True,
                        "rating": "Buy",
                        "breakdown": {"rs_rating": 18, "stage": 15},
                        "details": {"rs_value": 88},
                    },
                    "canslim": {
                        "score": 60.0,
                        "passes": False,
                        "rating": "Watch",
                        "breakdown": {"current_earnings": 15},
                        "details": {},
                    },
                }
            }
        }
        result = extract_screener_outputs(details)
        assert len(result) == 2
        assert result["minervini"].score == 75.0
        assert result["minervini"].passes is True
        assert result["minervini"].rating == "Buy"
        assert result["minervini"].breakdown == {"rs_rating": 18, "stage": 15}
        assert result["canslim"].score == 60.0
        assert result["canslim"].passes is False

    def test_missing_details_key(self):
        result = extract_screener_outputs({})
        assert result == {}

    def test_missing_screeners_key(self):
        result = extract_screener_outputs({"details": {}})
        assert result == {}

    def test_screeners_not_dict(self):
        result = extract_screener_outputs({"details": {"screeners": "bad"}})
        assert result == {}

    def test_empty_screeners(self):
        result = extract_screener_outputs({"details": {"screeners": {}}})
        assert result == {}

    def test_malformed_screener_entry_skipped(self):
        """Non-dict screener entries are silently skipped."""
        details = {
            "details": {
                "screeners": {
                    "good": {
                        "score": 50.0,
                        "passes": True,
                        "rating": "Watch",
                        "breakdown": {},
                        "details": {},
                    },
                    "bad": "not a dict",
                }
            }
        }
        result = extract_screener_outputs(details)
        assert len(result) == 1
        assert "good" in result

    def test_missing_score_defaults_to_zero(self):
        details = {
            "details": {
                "screeners": {
                    "test": {
                        "passes": False,
                        "rating": "Pass",
                        "breakdown": {},
                        "details": {},
                    }
                }
            }
        }
        result = extract_screener_outputs(details)
        assert result["test"].score == 0.0

    def test_invalid_score_skipped(self):
        """Score that can't be converted to float is skipped."""
        details = {
            "details": {
                "screeners": {
                    "bad_score": {
                        "score": "not_a_number",
                        "passes": True,
                        "rating": "Buy",
                        "breakdown": {},
                        "details": {},
                    }
                }
            }
        }
        result = extract_screener_outputs(details)
        assert "bad_score" not in result
