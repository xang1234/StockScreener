/**
 * API client for Filter Presets feature.
 * Handles CRUD operations for saved filter configurations.
 */
import apiClient from './client';

const BASE_PATH = '/v1/filter-presets';

// ================= Presets =================

/**
 * Get all filter presets.
 * @returns {Promise<Object>} List of presets
 */
export const getFilterPresets = async () => {
  const response = await apiClient.get(BASE_PATH);
  return response.data;
};

/**
 * Create a new filter preset.
 * @param {Object} presetData - Preset data { name, description?, filters, sort_by, sort_order }
 * @returns {Promise<Object>} Created preset
 */
export const createFilterPreset = async (presetData) => {
  const response = await apiClient.post(BASE_PATH, presetData);
  return response.data;
};

/**
 * Update a filter preset.
 * @param {number} presetId - The preset ID
 * @param {Object} updates - Fields to update
 * @returns {Promise<Object>} Updated preset
 */
export const updateFilterPreset = async (presetId, updates) => {
  const response = await apiClient.put(`${BASE_PATH}/${presetId}`, updates);
  return response.data;
};

/**
 * Delete a filter preset.
 * @param {number} presetId - The preset ID
 * @returns {Promise<Object>} Deletion confirmation
 */
export const deleteFilterPreset = async (presetId) => {
  const response = await apiClient.delete(`${BASE_PATH}/${presetId}`);
  return response.data;
};

/**
 * Reorder presets.
 * @param {number[]} presetIds - Array of preset IDs in new order
 * @returns {Promise<Object>} Reorder confirmation
 */
export const reorderFilterPresets = async (presetIds) => {
  const response = await apiClient.put(`${BASE_PATH}/reorder`, {
    preset_ids: presetIds,
  });
  return response.data;
};
