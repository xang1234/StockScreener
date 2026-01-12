/**
 * Centralized color utility functions for consistent styling across components
 *
 * These functions return color values for various stock metrics like stage,
 * ratings, growth percentages, and industry group rankings.
 */

/**
 * Get color for Minervini stock stage (1-4)
 * @param {number} stage - Stage number (1-4)
 * @returns {string} Hex color code
 */
export const getStageColor = (stage) => {
  switch (stage) {
    case 1:
      return '#9e9e9e'; // Gray - Basing
    case 2:
      return '#4caf50'; // Green - Advancing
    case 3:
      return '#ff9800'; // Orange - Topping
    case 4:
      return '#f44336'; // Red - Declining
    default:
      return '#9e9e9e';
  }
};

/**
 * Get MUI color name for stock rating (Strong Buy, Buy, Watch, Hold)
 * @param {string} rating - Rating string
 * @returns {string} MUI color name (success, warning, default)
 */
export const getRatingColor = (rating) => {
  switch (rating) {
    case 'Strong Buy':
    case 'Buy':
      return 'success';
    case 'Watch':
      return 'warning';
    default:
      return 'default';
  }
};

/**
 * Get color for growth percentage values
 * @param {number|null} value - Growth percentage
 * @returns {string} MUI color path or hex color
 */
export const getGrowthColor = (value) => {
  if (value == null) return 'text.secondary';
  if (value >= 20) return 'success.main';
  if (value >= 0) return 'success.light';
  if (value >= -10) return 'warning.main';
  return 'error.main';
};

/**
 * Get hex color for growth percentage (for components requiring hex)
 * @param {number|null} value - Growth percentage
 * @returns {string} Hex color code
 */
export const getGrowthColorHex = (value) => {
  if (value == null) return '#9e9e9e';
  if (value >= 20) return '#4caf50'; // Green
  if (value >= 0) return '#8bc34a'; // Light Green
  if (value >= -10) return '#ff9800'; // Orange
  return '#f44336'; // Red
};

/**
 * Get color for EPS Rating (0-99 scale, IBD-style)
 * @param {number|null} value - EPS rating value
 * @returns {string} MUI color path
 */
export const getEpsRatingColor = (value) => {
  if (value == null) return 'text.secondary';
  if (value >= 80) return 'success.main';
  if (value >= 50) return 'text.primary';
  return 'error.main';
};

/**
 * Get hex color for EPS Rating (for components requiring hex)
 * @param {number|null} value - EPS rating value
 * @returns {string} Hex color code
 */
export const getEpsRatingColorHex = (value) => {
  if (value == null) return '#9e9e9e';
  if (value >= 80) return '#4caf50'; // Strong - green
  if (value >= 50) return '#000000'; // Neutral - inherit/black
  return '#f44336'; // Weak - red
};

/**
 * Get color for IBD industry group rank (1-197)
 * @param {number|null} rank - Group rank
 * @returns {string} MUI color path
 */
export const getGroupRankColor = (rank) => {
  if (rank == null) return 'text.secondary';
  if (rank <= 20) return 'success.main';   // Top ~10%
  if (rank >= 177) return 'error.main';    // Bottom ~10%
  return 'warning.main';                    // Middle
};
