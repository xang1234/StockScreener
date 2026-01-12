"""
finvizfinance Data Validator

Validates finvizfinance data quality and completeness.

Note: Range validation checks are used to produce warnings, not to block data.
Values outside expected ranges may indicate data quality issues but the data
is still used (e.g., institutional_ownership can legitimately exceed 100%
due to overlapping reporting periods).
"""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class FinvizValidator:
    """Validator for finvizfinance data"""

    # Reasonable ranges for various metrics
    VALIDATION_RULES = {
        # Growth metrics can be extreme but should be within reason
        'eps_growth_qq': (-1000, 10000),  # -1000% to +10000%
        'sales_growth_qq': (-1000, 10000),
        'eps_growth_yy': (-1000, 10000),
        'sales_growth_yy': (-1000, 10000),

        # PE ratios can be high but should be positive (or None for loss-making companies)
        'pe_ratio': (0, 10000),
        'forward_pe': (0, 10000),

        # Margins can be negative but should be reasonable
        'profit_margin': (-1000, 1000),
        'operating_margin': (-1000, 1000),
        'gross_margin': (-1000, 1000),

        # Returns can be negative but should be within bounds
        'roe': (-500, 500),
        'roa': (-100, 100),
        'roic': (-100, 500),

        # Debt ratios can vary widely
        'debt_to_equity': (0, 1000),
        'lt_debt_to_equity': (0, 1000),

        # Liquidity ratios
        'current_ratio': (0, 100),
        'quick_ratio': (0, 100),

        # Ownership percentages
        'insider_ownership': (0, 200),
        'institutional_ownership': (0, 200),  # Can exceed 100% due to overlapping reporting periods
        'short_percent': (0, 100),

        # Market cap should be positive
        'market_cap': (0, None),  # No upper limit
        'shares_outstanding': (0, None),

        # Beta can be negative (inverse correlation)
        'beta': (-10, 10),
    }

    @classmethod
    def validate_growth_metrics(cls, data: Dict) -> tuple[bool, List[str]]:
        """
        Validate growth metrics are within reasonable ranges.

        Args:
            data: Dict with growth metrics

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        growth_fields = ['eps_growth_qq', 'sales_growth_qq', 'eps_growth_yy', 'sales_growth_yy']

        for field in growth_fields:
            value = data.get(field)

            if value is None:
                continue  # Missing data is OK

            min_val, max_val = cls.VALIDATION_RULES.get(field, (-1000, 10000))

            if not (min_val <= value <= max_val):
                errors.append(
                    f"{field} value {value} is outside reasonable range [{min_val}, {max_val}]"
                )

        return len(errors) == 0, errors

    @classmethod
    def validate_fundamentals(cls, data: Dict) -> tuple[bool, List[str]]:
        """
        Validate fundamental metrics are within reasonable ranges.

        Args:
            data: Dict with fundamental metrics

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        for field, value in data.items():
            if value is None:
                continue

            # Skip string fields
            if isinstance(value, str):
                continue

            # Get validation rule if exists
            if field in cls.VALIDATION_RULES:
                min_val, max_val = cls.VALIDATION_RULES[field]

                # Check minimum
                if min_val is not None and value < min_val:
                    errors.append(
                        f"{field} value {value} is below minimum {min_val}"
                    )

                # Check maximum
                if max_val is not None and value > max_val:
                    errors.append(
                        f"{field} value {value} exceeds maximum {max_val}"
                    )

        return len(errors) == 0, errors

    @classmethod
    def is_data_complete(cls, data: Dict, required_fields: Optional[List[str]] = None) -> tuple[bool, float]:
        """
        Check if data has sufficient field coverage.

        Args:
            data: Dict with parsed data
            required_fields: Optional list of required field names

        Returns:
            Tuple of (is_complete, completeness_percentage)
        """
        if required_fields:
            # Check specific required fields
            missing_fields = [f for f in required_fields if data.get(f) is None]
            completeness = (len(required_fields) - len(missing_fields)) / len(required_fields) * 100
            is_complete = len(missing_fields) == 0
        else:
            # General completeness check - count non-None values
            total_fields = len(data)
            if total_fields == 0:
                return False, 0.0

            non_none_fields = sum(1 for v in data.values() if v is not None)
            completeness = (non_none_fields / total_fields) * 100

            # Consider data complete if >50% of fields are populated
            is_complete = completeness > 50

        return is_complete, completeness

    @classmethod
    def validate_all(cls, fundamentals: Dict, growth: Dict, strict: bool = True) -> tuple[bool, Dict]:
        """
        Comprehensive validation of all data.

        Args:
            fundamentals: Fundamental data dict
            growth: Growth data dict
            strict: If True, require high data quality. If False, be more lenient.

        Returns:
            Tuple of (is_valid, validation_report dict)
        """
        report = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'completeness': {},
        }

        # Validate growth metrics
        growth_valid, growth_errors = cls.validate_growth_metrics(growth)
        if not growth_valid:
            report['errors'].extend(growth_errors)
            report['valid'] = False

        # Validate fundamentals
        fund_valid, fund_errors = cls.validate_fundamentals(fundamentals)
        if not fund_valid:
            if strict:
                report['errors'].extend(fund_errors)
                report['valid'] = False
            else:
                # In non-strict mode, treat as warnings
                report['warnings'].extend(fund_errors)

        # Check completeness
        fund_complete, fund_pct = cls.is_data_complete(fundamentals)
        growth_complete, growth_pct = cls.is_data_complete(growth)

        report['completeness'] = {
            'fundamentals': fund_pct,
            'growth': growth_pct,
        }

        # In strict mode, require decent completeness
        if strict:
            if fund_pct < 30:
                report['errors'].append(
                    f"Fundamental data completeness too low: {fund_pct:.1f}%"
                )
                report['valid'] = False

            if growth_pct < 25:  # At least 1 growth metric out of 4
                report['warnings'].append(
                    f"Growth data completeness low: {growth_pct:.1f}%"
                )

        return report['valid'], report

    @classmethod
    def should_fallback_to_yfinance(cls, validation_report: Dict) -> bool:
        """
        Determine if we should fall back to yfinance based on validation.

        Args:
            validation_report: Report from validate_all()

        Returns:
            True if should fallback to yfinance
        """
        # Fallback if validation failed
        if not validation_report['valid']:
            return True

        # Fallback if completeness is very low
        fund_completeness = validation_report['completeness'].get('fundamentals', 0)
        if fund_completeness < 30:
            return True

        # Otherwise, finviz data is good enough
        return False
