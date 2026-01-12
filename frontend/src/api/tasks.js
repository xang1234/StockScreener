/**
 * API client for Scheduled Tasks endpoints.
 */
import apiClient from './client';

/**
 * Get all scheduled tasks with their schedules and last run info.
 *
 * @returns {Promise<Object>} Task list response with tasks array and total_tasks
 */
export const getScheduledTasks = async () => {
  const response = await apiClient.get('/v1/tasks/scheduled');
  return response.data;
};

/**
 * Manually trigger a scheduled task.
 *
 * @param {string} taskName - Name of the task to trigger (e.g., 'daily-cache-warmup')
 * @returns {Promise<Object>} Trigger response with task_id, status, message
 */
export const triggerTask = async (taskName) => {
  const response = await apiClient.post(`/v1/tasks/${taskName}/run`);
  return response.data;
};

/**
 * Get the status of a running task.
 *
 * @param {string} taskName - Name of the task
 * @param {string} taskId - Celery task ID from triggerTask response
 * @returns {Promise<Object>} Status response with status, progress, result/error
 */
export const getTaskStatus = async (taskName, taskId) => {
  const response = await apiClient.get(`/v1/tasks/${taskName}/status/${taskId}`);
  return response.data;
};
