import axios from 'axios';
import Cookies from 'js-cookie';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000';

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const token = Cookies.get('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 || error.response?.status === 422) {
      Cookies.remove('token');
      Cookies.remove('refreshToken');
      Cookies.remove('user');
      if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export const authService = {
  login: async (username: string, password: string) => {
    const response = await api.post('/api/auth/login', { username, password });
    return response.data;
  },

  signup: async (userData: any) => {
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

  logout: () => {
    Cookies.remove('token');
    Cookies.remove('refreshToken');
    Cookies.remove('user');
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
    gender?: string;
    sexualPreferences?: string;
    biography?: string;
  }) => {
    const response = await api.put('/api/profile', data);
    return response.data;
  },

  getAllTags: async () => {
    const response = await api.get('/api/profile/tags');
    return response.data;
  },

  setMyTags: async (tags: string[]) => {
    const response = await api.put('/api/profile/tags', { tags });
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

  updateLocationManual: async (locationName: string) => {
    const response = await api.put('/api/profile/location', {
      gpsConsent: false,
      locationName,
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
};

export const usersService = {
  getUser: async (userId: number) => {
    const response = await api.get(`/api/users/${userId}`);
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