/**
 * API client for Market Scan feature.
 * Handles watchlist CRUD operations.
 */
import apiClient from './client';

const BASE_PATH = '/v1/market-scan';

/**
 * Get all symbols in a watchlist.
 * @param {string} listName - The watchlist identifier (e.g., 'key_markets')
 * @returns {Promise<Object>} Watchlist data with symbols array
 */
export const getWatchlist = async (listName) => {
  const response = await apiClient.get(`${BASE_PATH}/watchlist/${listName}`);
  return response.data;
};

/**
 * Add a symbol to a watchlist.
 * @param {string} listName - The watchlist identifier
 * @param {Object} symbolData - Symbol data { symbol, display_name?, notes? }
 * @returns {Promise<Object>} Created symbol
 */
export const addSymbol = async (listName, symbolData) => {
  const response = await apiClient.post(
    `${BASE_PATH}/watchlist/${listName}`,
    symbolData
  );
  return response.data;
};

/**
 * Update a symbol in a watchlist.
 * @param {string} listName - The watchlist identifier
 * @param {number} symbolId - The symbol ID to update
 * @param {Object} updates - Fields to update { display_name?, notes?, position? }
 * @returns {Promise<Object>} Updated symbol
 */
export const updateSymbol = async (listName, symbolId, updates) => {
  const response = await apiClient.put(
    `${BASE_PATH}/watchlist/${listName}/${symbolId}`,
    updates
  );
  return response.data;
};

/**
 * Remove a symbol from a watchlist.
 * @param {string} listName - The watchlist identifier
 * @param {number} symbolId - The symbol ID to remove
 * @returns {Promise<Object>} Deletion confirmation
 */
export const removeSymbol = async (listName, symbolId) => {
  const response = await apiClient.delete(
    `${BASE_PATH}/watchlist/${listName}/${symbolId}`
  );
  return response.data;
};

/**
 * Reorder symbols in a watchlist.
 * @param {string} listName - The watchlist identifier
 * @param {number[]} symbolIds - Array of symbol IDs in new order
 * @returns {Promise<Object>} Reorder confirmation
 */
export const reorderSymbols = async (listName, symbolIds) => {
  const response = await apiClient.put(
    `${BASE_PATH}/watchlist/${listName}/reorder`,
    { symbol_ids: symbolIds }
  );
  return response.data;
};
