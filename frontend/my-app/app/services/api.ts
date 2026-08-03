import axios, { type InternalAxiosRequestConfig } from 'axios';
import Cookies from 'js-cookie';

import type { User } from '@/app/types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000';
const SAFE_METHODS = new Set(['get', 'head', 'options']);

interface RetryRequestConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

export interface ProfileUpdatePayload {
  firstName?: string;
  lastName?: string;
  email?: string;
  birthDate?: string;
  gender?: string;
  sexualPreferences?: string[];
  biography?: string;
}

export interface DiscoveryFilters {
  minAge: number;
  maxAge: number;
  minFame: number;
  maxFame: number;
  location: string;
  tagIds: number[];
  sort: string;
  order: string;
}

export interface DateProposalPayload {
  scheduledFor: string;
  location: string;
  note?: string;
}

/** Return whether the browser still has either readable CSRF cookie. */
export function hasAuthenticationCookieHint(): boolean {
  return Boolean(Cookies.get('csrf_access_token') || Cookies.get('csrf_refresh_token'));
}

/** Remove readable CSRF hints after an authentication failure. */
export function clearAuthenticationCookieHints(): void {
  Cookies.remove('csrf_access_token');
  Cookies.remove('csrf_refresh_token');
}

/** Return the correct CSRF token for an unsafe request, when available. */
function csrfTokenFor(url?: string): string | undefined {
  const cookie = url?.startsWith('/api/auth/refresh')
    ? 'csrf_refresh_token'
    : 'csrf_access_token';
  return Cookies.get(cookie);
}

/** Return whether a failed request is eligible for one access-token refresh retry. */
function shouldRefresh(url?: string): boolean {
  if (!url) {
    return false;
  }

  const authenticationEndpoints = [
    '/api/auth/login',
    '/api/auth/register',
    '/api/auth/refresh',
    '/api/auth/forgot-password',
    '/api/auth/reset-password',
    '/api/auth/resend-verification',
  ];
  return !authenticationEndpoints.some((path) => url.startsWith(path));
}

// All API requests include HttpOnly JWT cookies. JavaScript reads only the
// separate CSRF cookies required by Flask-JWT-Extended for unsafe methods.
export const api = axios.create({
  baseURL: API_URL,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

const refreshClient = axios.create({
  baseURL: API_URL,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const method = config.method?.toLowerCase();
  if (method && !SAFE_METHODS.has(method)) {
    const token = csrfTokenFor(config.url);
    if (token) {
      config.headers.set('X-CSRF-TOKEN', token);
    }
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config as RetryRequestConfig | undefined;
    const status = error.response?.status;
    const canRetry = original
      && !original._retry
      && (status === 401 || status === 422)
      && shouldRefresh(original.url)
      && Cookies.get('csrf_refresh_token');

    if (!canRetry || !original) {
      return Promise.reject(error);
    }

    original._retry = true;
    try {
      const refreshCsrf = Cookies.get('csrf_refresh_token');
      await refreshClient.post('/api/auth/refresh', {}, {
        headers: refreshCsrf ? { 'X-CSRF-TOKEN': refreshCsrf } : {},
      });

      const method = original.method?.toLowerCase();
      if (method && !SAFE_METHODS.has(method)) {
        const accessCsrf = Cookies.get('csrf_access_token');
        if (accessCsrf) {
          original.headers.set('X-CSRF-TOKEN', accessCsrf);
        }
      }
      return api(original);
    } catch {
      clearAuthenticationCookieHints();
      return Promise.reject(error);
    }
  },
);

// ---------------------------------------------------------------- authentication

export const authService = {
  bootstrap: async () => {
    const response = await api.post('/api/auth/refresh/bootstrap');
    return response.data as { authenticated: boolean; user: User | null };
  },

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

// ---------------------------------------------------------------------- profile

export const profileService = {
  getProfile: async () => {
    const response = await api.get('/api/profile');
    return response.data;
  },

  updateProfile: async (data: ProfileUpdatePayload) => {
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

  replacePhoto: async (photoId: number, file: File) => {
    const formData = new FormData();
    formData.append('photo', file);
    const response = await api.put(`/api/profile/photos/${photoId}`, formData, {
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
    const response = await api.get('/api/profile/location/search', { params: { q: query } });
    return response.data;
  },

  updateLocationManual: async (locationName: string, latitude: number, longitude: number) => {
    const response = await api.put('/api/profile/location', {
      gpsConsent: false,
      locationName,
      latitude,
      longitude,
    });
    return response.data;
  },

  getViewers: async () => (await api.get('/api/profile/viewers')).data,
  getLikes: async () => (await api.get('/api/profile/likes')).data,
  getActivity: async () => (await api.get('/api/profile/activity')).data,
};

// --------------------------------------------------------------- public profiles

export const usersService = {
  getBlockedUsers: async () => (await api.get('/api/users/blocked')).data,

  getUserByUsername: async (username: string) => {
    const response = await api.get(`/api/users/by-username/${encodeURIComponent(username)}`);
    return response.data;
  },

  recordVisit: async (userId: number, visitId: string) => {
    const response = await api.post(`/api/users/${userId}/visit`, { visitId });
    return response.data;
  },

  like: async (userId: number) => (await api.post(`/api/users/${userId}/like`)).data,
  unlike: async (userId: number) => (await api.delete(`/api/users/${userId}/like`)).data,
  block: async (userId: number) => (await api.post(`/api/users/${userId}/block`)).data,
  unblock: async (userId: number) => (await api.delete(`/api/users/${userId}/block`)).data,
  report: async (userId: number) => (await api.post(`/api/users/${userId}/report`)).data,
};

// ------------------------------------------------------------ browse and search

/** Serialize typed discovery filters into the query parameters expected by Flask. */
function discoveryParams(filters: DiscoveryFilters) {
  return {
    minAge: filters.minAge,
    maxAge: filters.maxAge,
    minFame: filters.minFame,
    maxFame: filters.maxFame,
    location: filters.location || undefined,
    tagIds: filters.tagIds.length ? filters.tagIds.join(',') : undefined,
    sort: filters.sort,
    order: filters.order,
  };
}

export const discoverService = {
  getProfiles: async (filters: DiscoveryFilters, page: number, pageSize = 12) => {
    const response = await api.get('/api/discover', {
      params: { ...discoveryParams(filters), page, pageSize },
    });
    return response.data;
  },

  getMapProfiles: async (filters: DiscoveryFilters) => {
    const response = await api.get('/api/discover/map', {
      params: discoveryParams(filters),
    });
    return response.data;
  },
};

// --------------------------------------------------------------------- messages

export const messagesService = {
  getConversations: async () => (await api.get('/api/messages')).data,

  getConversation: async (userId: number, page = 1, pageSize = 50) => {
    const response = await api.get(`/api/messages/${userId}`, { params: { page, pageSize } });
    return response.data;
  },

  sendMessage: async (userId: number, content: string) => {
    const response = await api.post(`/api/messages/${userId}`, { content });
    return response.data;
  },

  markConversationRead: async (userId: number) => {
    const response = await api.put(`/api/messages/${userId}/read`);
    return response.data;
  },
};

// ------------------------------------------------------------------------ dates

export const datesService = {
  getEvents: async () => (await api.get('/api/dates')).data,

  createEvent: async (userId: number, data: DateProposalPayload) => {
    const response = await api.post(`/api/dates/${userId}`, data);
    return response.data;
  },

  respond: async (eventId: number, status: 'accepted' | 'declined') => {
    const response = await api.put(`/api/dates/${eventId}/respond`, { status });
    return response.data;
  },

  cancel: async (eventId: number) => {
    const response = await api.put(`/api/dates/${eventId}/cancel`);
    return response.data;
  },
};
