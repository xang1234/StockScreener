/**
 * API client for User-defined Themes feature.
 * Handles CRUD operations for themes, subgroups, and stocks.
 */
import apiClient from './client';

const BASE_PATH = '/v1/user-themes';

// ================= Themes =================

/**
 * Get all user themes.
 * @returns {Promise<Object>} List of themes
 */
export const getThemes = async () => {
  const response = await apiClient.get(BASE_PATH);
  return response.data;
};

/**
 * Create a new theme.
 * @param {Object} themeData - Theme data { name, description?, color? }
 * @returns {Promise<Object>} Created theme
 */
export const createTheme = async (themeData) => {
  const response = await apiClient.post(BASE_PATH, themeData);
  return response.data;
};

/**
 * Update a theme.
 * @param {number} themeId - The theme ID
 * @param {Object} updates - Fields to update
 * @returns {Promise<Object>} Updated theme
 */
export const updateTheme = async (themeId, updates) => {
  const response = await apiClient.put(`${BASE_PATH}/${themeId}`, updates);
  return response.data;
};

/**
 * Delete a theme (cascades to subgroups and stocks).
 * @param {number} themeId - The theme ID
 * @returns {Promise<Object>} Deletion confirmation
 */
export const deleteTheme = async (themeId) => {
  const response = await apiClient.delete(`${BASE_PATH}/${themeId}`);
  return response.data;
};

/**
 * Reorder themes.
 * @param {number[]} themeIds - Array of theme IDs in new order
 * @returns {Promise<Object>} Reorder confirmation
 */
export const reorderThemes = async (themeIds) => {
  const response = await apiClient.put(`${BASE_PATH}/reorder`, {
    theme_ids: themeIds,
  });
  return response.data;
};

/**
 * Get complete theme data with subgroups, stocks, sparklines, and price changes.
 * @param {number} themeId - The theme ID
 * @returns {Promise<Object>} Theme data with market info
 */
export const getThemeData = async (themeId) => {
  const response = await apiClient.get(`${BASE_PATH}/${themeId}/data`);
  return response.data;
};

// ================= Subgroups =================

/**
 * Create a new subgroup within a theme.
 * @param {number} themeId - The theme ID
 * @param {Object} subgroupData - Subgroup data { name }
 * @returns {Promise<Object>} Created subgroup
 */
export const createSubgroup = async (themeId, subgroupData) => {
  const response = await apiClient.post(
    `${BASE_PATH}/${themeId}/subgroups`,
    subgroupData
  );
  return response.data;
};

/**
 * Update a subgroup.
 * @param {number} subgroupId - The subgroup ID
 * @param {Object} updates - Fields to update { name?, position?, is_collapsed? }
 * @returns {Promise<Object>} Updated subgroup
 */
export const updateSubgroup = async (subgroupId, updates) => {
  const response = await apiClient.put(
    `${BASE_PATH}/subgroups/${subgroupId}`,
    updates
  );
  return response.data;
};

/**
 * Delete a subgroup (cascades to stocks).
 * @param {number} subgroupId - The subgroup ID
 * @returns {Promise<Object>} Deletion confirmation
 */
export const deleteSubgroup = async (subgroupId) => {
  const response = await apiClient.delete(`${BASE_PATH}/subgroups/${subgroupId}`);
  return response.data;
};

/**
 * Reorder subgroups within a theme.
 * @param {number} themeId - The theme ID
 * @param {number[]} subgroupIds - Array of subgroup IDs in new order
 * @returns {Promise<Object>} Reorder confirmation
 */
export const reorderSubgroups = async (themeId, subgroupIds) => {
  const response = await apiClient.put(
    `${BASE_PATH}/${themeId}/subgroups/reorder`,
    { subgroup_ids: subgroupIds }
  );
  return response.data;
};

// ================= Stocks =================

/**
 * Add a stock to a subgroup.
 * @param {number} subgroupId - The subgroup ID
 * @param {Object} stockData - Stock data { symbol, display_name?, notes? }
 * @returns {Promise<Object>} Created stock
 */
export const addStock = async (subgroupId, stockData) => {
  const response = await apiClient.post(
    `${BASE_PATH}/subgroups/${subgroupId}/stocks`,
    stockData
  );
  return response.data;
};

/**
 * Update a stock.
 * @param {number} stockId - The stock ID
 * @param {Object} updates - Fields to update { display_name?, notes?, position?, subgroup_id? }
 * @returns {Promise<Object>} Updated stock
 */
export const updateStock = async (stockId, updates) => {
  const response = await apiClient.put(`${BASE_PATH}/stocks/${stockId}`, updates);
  return response.data;
};

/**
 * Remove a stock from its subgroup.
 * @param {number} stockId - The stock ID
 * @returns {Promise<Object>} Deletion confirmation
 */
export const removeStock = async (stockId) => {
  const response = await apiClient.delete(`${BASE_PATH}/stocks/${stockId}`);
  return response.data;
};

/**
 * Reorder stocks within a subgroup.
 * @param {number} subgroupId - The subgroup ID
 * @param {number[]} stockIds - Array of stock IDs in new order
 * @returns {Promise<Object>} Reorder confirmation
 */
export const reorderStocks = async (subgroupId, stockIds) => {
  const response = await apiClient.put(
    `${BASE_PATH}/subgroups/${subgroupId}/stocks/reorder`,
    { stock_ids: stockIds }
  );
  return response.data;
};
