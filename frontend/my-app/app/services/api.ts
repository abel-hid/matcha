import axios, { InternalAxiosRequestConfig } from 'axios';
import Cookies from 'js-cookie';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000';

interface RetryRequestConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

export const api = axios.create({
  baseURL: API_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

const refreshClient = axios.create({
  baseURL: API_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const method = config.method?.toLowerCase();
  if (method && !['get', 'head', 'options'].includes(method)) {
    const cookieName = config.url === '/api/auth/refresh'
      ? 'csrf_refresh_token'
      : 'csrf_access_token';
    const csrfToken = Cookies.get(cookieName);
    if (csrfToken) {
      config.headers.set('X-CSRF-TOKEN', csrfToken);
    }
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config as RetryRequestConfig | undefined;
    const status = error.response?.status;

    if (
      originalRequest &&
      !originalRequest._retry &&
      (status === 401 || status === 422) &&
      shouldRefresh(originalRequest.url)
    ) {
      originalRequest._retry = true;

      try {
        const csrfToken = Cookies.get('csrf_refresh_token');
        await refreshClient.post('/api/auth/refresh', {}, {
          headers: csrfToken ? { 'X-CSRF-TOKEN': csrfToken } : {},
        });

        const method = originalRequest.method?.toLowerCase();
        if (method && !['get', 'head', 'options'].includes(method)) {
          const newAccessCsrf = Cookies.get('csrf_access_token');
          if (newAccessCsrf) {
            originalRequest.headers.set('X-CSRF-TOKEN', newAccessCsrf);
          }
        }

        return api(originalRequest);
      } catch {
        return Promise.reject(error);
      }
    }

    return Promise.reject(error);
  }
);

function shouldRefresh(url?: string): boolean {
  if (!url) return false;

  return ![
    '/api/auth/login',
    '/api/auth/register',
    '/api/auth/refresh',
    '/api/auth/forgot-password',
    '/api/auth/reset-password',
    '/api/auth/resend-verification',
  ].some((path) => url.startsWith(path));
}

export const authService = {
  login: async (username: string, password: string) => {
    const response = await api.post('/api/auth/login', { username, password });
    return response.data;
  },

  signup: async (userData: unknown) => {
    const response = await api.post('/api/auth/register', userData);
    return response.data;
  },

  verifyEmail: async (token: string) => {
    const response = await api.get(`/api/auth/verify/${token}`);
    return response.data;
  },

  forgotPassword: async (email: string) => {
    const response = await api.post('/api/auth/forgot-password', { email });
    return response.data;
  },

  resetPassword: async (token: string, password: string) => {
    const response = await api.post('/api/auth/reset-password', { token, password });
    return response.data;
  },

  logout: async () => {
    const response = await api.post('/api/auth/logout');
    return response.data;
  },

  getCurrentUser: async () => {
    const response = await api.get('/api/auth/me');
    return response.data;
  },

  verifyResetToken: async (token: string) => {
    const response = await api.get(`/api/auth/verify-reset-token/${token}`);
    return response.data;
  },
};


export const profileService = {
  getProfile: async () => {
    const response = await api.get('/api/profile');
    return response.data;
  },

  updateProfile: async (data: {
    firstName?: string;
    lastName?: string;
    email?: string;
    birthDate?: string;
    gender?: string;
    sexualPreferences?: string[];
    biography?: string;
  }) => {
    const response = await api.put('/api/profile', data);
    return response.data;
  },

  getAllTags: async () => {
    const response = await api.get('/api/profile/tags');
    return response.data;
  },

  setMyTags: async (tagIds: number[]) => {
    const response = await api.put('/api/profile/tags', { tagIds });
    return response.data;
  },

  uploadPhoto: async (file: File) => {
    const formData = new FormData();
    formData.append('photo', file);
    const response = await api.post('/api/profile/photos', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  deletePhoto: async (photoId: number) => {
    const response = await api.delete(`/api/profile/photos/${photoId}`);
    return response.data;
  },

  setPrimaryPhoto: async (photoId: number) => {
    const response = await api.put(`/api/profile/photos/${photoId}/primary`);
    return response.data;
  },

  updateLocationGps: async (latitude: number, longitude: number, locationName?: string) => {
    const response = await api.put('/api/profile/location', {
      gpsConsent: true,
      latitude,
      longitude,
      locationName,
    });
    return response.data;
  },

  searchLocations: async (query: string) => {
    const response = await api.get('/api/profile/location/search', {
      params: { q: query },
    });
    return response.data;
  },

  updateLocationManual: async (
    locationName: string,
    latitude: number,
    longitude: number
  ) => {
    const response = await api.put('/api/profile/location', {
      gpsConsent: false,
      locationName,
      latitude,
      longitude,
    });
    return response.data;
  },

  getViewers: async () => {
    const response = await api.get('/api/profile/viewers');
    return response.data;
  },

  getLikes: async () => {
    const response = await api.get('/api/profile/likes');
    return response.data;
  },

  getActivity: async () => {
    const response = await api.get('/api/profile/activity');
    return response.data;
  },
};

export const usersService = {
  getBlockedUsers: async () => {
    const response = await api.get('/api/users/blocked');
    return response.data;
  },

  getUser: async (userId: number) => {
    const response = await api.get(`/api/users/${userId}`);
    return response.data;
  },

  recordVisit: async (userId: number, visitId: string) => {
    const response = await api.post(`/api/users/${userId}/visit`, { visitId });
    return response.data;
  },
 
  like: async (userId: number) => {
    const response = await api.post(`/api/users/${userId}/like`);
    return response.data;
  },
 
  unlike: async (userId: number) => {
    const response = await api.delete(`/api/users/${userId}/like`);
    return response.data;
  },
 
  block: async (userId: number) => {
    const response = await api.post(`/api/users/${userId}/block`);
    return response.data;
  },
 
  unblock: async (userId: number) => {
    const response = await api.delete(`/api/users/${userId}/block`);
    return response.data;
  },
 
  report: async (userId: number) => {
    const response = await api.post(`/api/users/${userId}/report`);
    return response.data;
  },
};