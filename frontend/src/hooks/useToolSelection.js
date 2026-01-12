/**
 * Hook for managing chatbot tool selection with localStorage persistence.
 */
import { useState, useCallback, useEffect } from 'react';
import {
  createDefaultToolSelection,
  getAllToolNames,
  getTotalToolCount,
  TOOL_SELECTION_STORAGE_KEY,
} from '../config/chatbotTools';

/**
 * Load enabled tools from localStorage.
 * @returns {Set<string>} Set of enabled tool names
 */
function loadFromStorage() {
  try {
    const stored = localStorage.getItem(TOOL_SELECTION_STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      if (Array.isArray(parsed)) {
        return new Set(parsed);
      }
    }
  } catch (e) {
    console.warn('Failed to load tool selection from localStorage:', e);
  }
  // Default: all tools enabled
  return createDefaultToolSelection();
}

/**
 * Save enabled tools to localStorage.
 * @param {Set<string>} enabledTools Set of enabled tool names
 */
function saveToStorage(enabledTools) {
  try {
    localStorage.setItem(
      TOOL_SELECTION_STORAGE_KEY,
      JSON.stringify([...enabledTools])
    );
  } catch (e) {
    console.warn('Failed to save tool selection to localStorage:', e);
  }
}

/**
 * Hook for managing tool selection state.
 *
 * @returns {Object} Tool selection state and handlers
 * @property {Set<string>} enabledTools - Set of currently enabled tool names
 * @property {function} toggleTool - Toggle a single tool on/off
 * @property {function} toggleCategory - Toggle all tools in a category on/off
 * @property {function} enableAll - Enable all tools
 * @property {function} disableAll - Disable all tools
 * @property {function} getEnabledToolsArray - Get enabled tools as array (null if all enabled)
 * @property {number} enabledCount - Count of enabled tools
 * @property {number} totalCount - Total count of all tools
 * @property {boolean} allEnabled - Whether all tools are enabled
 */
export function useToolSelection() {
  const [enabledTools, setEnabledTools] = useState(() => loadFromStorage());
  const totalCount = getTotalToolCount();

  // Persist to localStorage whenever selection changes
  useEffect(() => {
    saveToStorage(enabledTools);
  }, [enabledTools]);

  /**
   * Toggle a single tool on/off.
   * @param {string} toolName Name of the tool to toggle
   */
  const toggleTool = useCallback((toolName) => {
    setEnabledTools((prev) => {
      const next = new Set(prev);
      if (next.has(toolName)) {
        next.delete(toolName);
      } else {
        next.add(toolName);
      }
      return next;
    });
  }, []);

  /**
   * Toggle all tools in a category on/off.
   * If all are enabled, disable all. Otherwise, enable all.
   * @param {string[]} toolNames Array of tool names in the category
   */
  const toggleCategory = useCallback((toolNames) => {
    setEnabledTools((prev) => {
      const next = new Set(prev);
      const allEnabled = toolNames.every((name) => next.has(name));

      if (allEnabled) {
        // Disable all in category
        toolNames.forEach((name) => next.delete(name));
      } else {
        // Enable all in category
        toolNames.forEach((name) => next.add(name));
      }
      return next;
    });
  }, []);

  /**
   * Enable all tools.
   */
  const enableAll = useCallback(() => {
    setEnabledTools(createDefaultToolSelection());
  }, []);

  /**
   * Disable all tools.
   */
  const disableAll = useCallback(() => {
    setEnabledTools(new Set());
  }, []);

  /**
   * Get enabled tools as array for API calls.
   * Returns null if all tools are enabled (to skip filtering on backend).
   * @returns {string[]|null} Array of enabled tool names, or null if all enabled
   */
  const getEnabledToolsArray = useCallback(() => {
    const allTools = getAllToolNames();
    if (enabledTools.size === allTools.length) {
      // All enabled, return null to skip filtering
      return null;
    }
    return [...enabledTools];
  }, [enabledTools]);

  return {
    enabledTools,
    toggleTool,
    toggleCategory,
    enableAll,
    disableAll,
    getEnabledToolsArray,
    enabledCount: enabledTools.size,
    totalCount,
    allEnabled: enabledTools.size === totalCount,
  };
}

export default useToolSelection;
