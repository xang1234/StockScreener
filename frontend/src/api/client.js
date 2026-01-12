/**
 * Axios API client for Stock Scanner backend
 */
import axios from 'axios';

// API base URL - defaults to localhost:8000/api, can be overridden with env var
// In Docker, VITE_API_URL is set to '/api' for nginx proxy
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

// Create axios instance with default config
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30 second timeout
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for logging (development only)
apiClient.interceptors.request.use(
  (config) => {
    if (import.meta.env.DEV) {
      console.log(`API Request: ${config.method.toUpperCase()} ${config.url}`);
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (error.response) {
      // Server responded with error status
      console.error('API Error Response:', {
        status: error.response.status,
        data: error.response.data,
        url: error.config.url,
      });
    } else if (error.request) {
      // Request made but no response
      console.error('API No Response:', error.request);
    } else {
      // Error in request setup
      console.error('API Request Error:', error.message);
    }
    return Promise.reject(error);
  }
);

export default apiClient;
