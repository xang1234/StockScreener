/**
 * Centralized formatting utility functions for consistent display across components
 *
 * These functions handle formatting of large numbers, dates, and percentages
 * for stock data display.
 */

/**
 * Format a large number with K/M/B/T suffix
 * @param {number|null} value - Number to format
 * @param {string} prefix - Optional prefix (e.g., '$')
 * @returns {string} Formatted string with suffix
 */
export const formatLargeNumber = (value, prefix = '') => {
  if (value == null) return '-';
  if (value >= 1e12) return `${prefix}${(value / 1e12).toFixed(1)}T`;
  if (value >= 1e9) return `${prefix}${(value / 1e9).toFixed(1)}B`;
  if (value >= 1e6) return `${prefix}${(value / 1e6).toFixed(1)}M`;
  if (value >= 1e3) return `${prefix}${(value / 1e3).toFixed(0)}K`;
  return `${prefix}${value}`;
};

/**
 * Format market cap with higher precision (2 decimal places)
 * @param {number|null} value - Market cap value
 * @returns {string} Formatted string with $ prefix
 */
export const formatMarketCap = (value) => {
  if (value == null) return '-';
  if (value >= 1e12) return `$${(value / 1e12).toFixed(2)}T`;
  if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
  if (value >= 1e6) return `$${(value / 1e6).toFixed(2)}M`;
  if (value >= 1e3) return `$${(value / 1e3).toFixed(2)}K`;
  return `$${value.toFixed(2)}`;
};

/**
 * Format IPO date as age in years or months
 * @param {string|null} ipoDate - ISO date string
 * @returns {string} Formatted age string (e.g., "2.5y" or "8mo")
 */
export const formatIpoAge = (ipoDate) => {
  if (!ipoDate) return '-';
  const ipo = new Date(ipoDate);
  const now = new Date();
  const diffMs = now - ipo;
  const diffDays = diffMs / (1000 * 60 * 60 * 24);
  const diffMonths = diffDays / 30.44;
  const diffYears = diffDays / 365.25;

  if (diffYears >= 1) {
    return `${diffYears.toFixed(1)}y`;
  } else {
    return `${Math.round(diffMonths)}mo`;
  }
};

/**
 * Get color for IPO age (newer IPOs get highlight)
 * @param {string|null} ipoDate - ISO date string
 * @returns {string} MUI color path
 */
export const getIpoAgeColor = (ipoDate) => {
  if (!ipoDate) return 'text.secondary';
  const ipo = new Date(ipoDate);
  const now = new Date();
  const diffDays = (now - ipo) / (1000 * 60 * 60 * 24);
  const diffYears = diffDays / 365.25;

  if (diffYears <= 1) return 'success.main';
  if (diffYears <= 3) return 'warning.main';
  return 'text.secondary';
};

/**
 * Format a percentage with optional sign
 * @param {number|null} value - Percentage value
 * @param {number} decimals - Decimal places (default: 1)
 * @returns {string} Formatted percentage string
 */
export const formatPercent = (value, decimals = 1) => {
  if (value == null) return '-';
  return `${value >= 0 ? '+' : ''}${value.toFixed(decimals)}%`;
};

/**
 * Format a ratio value
 * @param {number|null} value - Ratio value
 * @param {number} decimals - Decimal places (default: 2)
 * @returns {string} Formatted ratio string
 */
export const formatRatio = (value, decimals = 2) => {
  if (value == null) return '-';
  return value.toFixed(decimals);
};
