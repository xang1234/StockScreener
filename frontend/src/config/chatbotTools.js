/**
 * Chatbot tool categories configuration.
 * Defines the hierarchical structure of tools for the ToolSelector component.
 */

// Icons for categories (imported where needed)
export const CATEGORY_ICONS = {
  yahoo_finance: 'ShowChart',
  database: 'Storage',
  web_search: 'Language',
  documents: 'Description',
};

// Colors for categories
export const CATEGORY_COLORS = {
  yahoo_finance: '#6366f1',  // Indigo
  database: '#10b981',       // Emerald
  web_search: '#f59e0b',     // Amber
  documents: '#8b5cf6',      // Purple
};

/**
 * Tool categories with their constituent tools.
 * Each category has a label, icon, color, and list of tools.
 */
export const TOOL_CATEGORIES = {
  yahoo_finance: {
    id: 'yahoo_finance',
    label: 'Yahoo Finance',
    icon: 'ShowChart',
    color: '#6366f1',
    tools: [
      { name: 'yfinance_quote', label: 'Stock Quote' },
      { name: 'yfinance_fundamentals', label: 'Fundamentals' },
      { name: 'yfinance_history', label: 'Price History' },
      { name: 'yfinance_earnings', label: 'Earnings' },
      { name: 'compare_stocks', label: 'Compare Stocks' },
    ],
  },
  database: {
    id: 'database',
    label: 'Database',
    icon: 'Storage',
    color: '#10b981',
    tools: [
      { name: 'get_scan_results', label: 'Scan Results' },
      { name: 'search_stocks', label: 'Search Stocks' },
      { name: 'get_theme_data', label: 'Theme Data' },
      { name: 'get_trending_themes', label: 'Trending Themes' },
      { name: 'get_breadth_data', label: 'Breadth Data' },
      { name: 'get_top_rated_stocks', label: 'Top Rated Stocks' },
      { name: 'get_db_fundamentals', label: 'DB Fundamentals' },
      { name: 'get_db_price_history', label: 'DB Price History' },
      { name: 'advanced_stock_search', label: 'Advanced Search' },
    ],
  },
  web_search: {
    id: 'web_search',
    label: 'Web Search',
    icon: 'Language',
    color: '#f59e0b',
    tools: [
      { name: 'web_search', label: 'Web Search' },
      { name: 'search_news', label: 'News Search' },
      { name: 'search_finance', label: 'Finance Search' },
    ],
  },
  documents: {
    id: 'documents',
    label: 'Documents',
    icon: 'Description',
    color: '#8b5cf6',
    tools: [
      { name: 'get_sec_10k', label: 'SEC 10-K' },
      { name: 'read_ir_pdf', label: 'IR PDF Reader' },
    ],
  },
};

/**
 * Get all tool names as a flat array.
 * @returns {string[]} Array of all tool names
 */
export function getAllToolNames() {
  const names = [];
  Object.values(TOOL_CATEGORIES).forEach((category) => {
    category.tools.forEach((tool) => {
      names.push(tool.name);
    });
  });
  return names;
}

/**
 * Get total count of all tools.
 * @returns {number} Total number of tools
 */
export function getTotalToolCount() {
  return getAllToolNames().length;
}

/**
 * Create default tool selection (all tools enabled).
 * @returns {Set<string>} Set of all tool names
 */
export function createDefaultToolSelection() {
  return new Set(getAllToolNames());
}

/**
 * LocalStorage key for persisting tool selection.
 */
export const TOOL_SELECTION_STORAGE_KEY = 'chatbot_enabled_tools';
