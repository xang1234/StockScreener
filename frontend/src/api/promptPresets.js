/**
 * API client for Prompt Presets feature.
 * Handles CRUD operations for saved chat prompts.
 */
import apiClient from './client';

const BASE_PATH = '/v1/prompt-presets';

// ================= Presets =================

/**
 * Get all prompt presets.
 * @returns {Promise<Object>} List of presets
 */
export const getPromptPresets = async () => {
  const response = await apiClient.get(BASE_PATH);
  return response.data;
};

/**
 * Create a new prompt preset.
 * @param {Object} presetData - Preset data { name, content, description? }
 * @returns {Promise<Object>} Created preset
 */
export const createPromptPreset = async (presetData) => {
  const response = await apiClient.post(BASE_PATH, presetData);
  return response.data;
};

/**
 * Update a prompt preset.
 * @param {number} presetId - The preset ID
 * @param {Object} updates - Fields to update
 * @returns {Promise<Object>} Updated preset
 */
export const updatePromptPreset = async (presetId, updates) => {
  const response = await apiClient.put(`${BASE_PATH}/${presetId}`, updates);
  return response.data;
};

/**
 * Delete a prompt preset.
 * @param {number} presetId - The preset ID
 * @returns {Promise<Object>} Deletion confirmation
 */
export const deletePromptPreset = async (presetId) => {
  const response = await apiClient.delete(`${BASE_PATH}/${presetId}`);
  return response.data;
};

/**
 * Reorder presets.
 * @param {number[]} presetIds - Array of preset IDs in new order
 * @returns {Promise<Object>} Reorder confirmation
 */
export const reorderPromptPresets = async (presetIds) => {
  const response = await apiClient.put(`${BASE_PATH}/reorder`, {
    preset_ids: presetIds,
  });
  return response.data;
};
