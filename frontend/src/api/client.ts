import axios, { AxiosError } from 'axios';

export interface ApiError {
  error: {
    code: string;
    message: string;
    request_id: string;
  };
}

// Extend ApiError representation for the frontend
export interface FrontendApiError {
  status: number;
  code: string;
  message: string;
  request_id: string | undefined;
}

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiError>) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      window.dispatchEvent(new Event('unauthorized'));
    }
    return Promise.reject(error);
  }
);

export function parseApiError(error: unknown): FrontendApiError {
  if (axios.isAxiosError(error) && error.response) {
    const data = error.response.data as ApiError | undefined;
    return {
      status: error.response.status,
      code: data?.error?.code || 'UNKNOWN_ERROR',
      message: data?.error?.message || 'An unexpected error occurred',
      request_id: data?.error?.request_id,
    };
  }
  return {
    status: 0,
    code: 'NETWORK_ERROR',
    message: 'Could not connect to the server',
    request_id: undefined,
  };
}
