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