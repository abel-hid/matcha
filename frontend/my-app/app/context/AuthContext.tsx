'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { authService } from '@/app/services/api';
import { User } from '@/app/types';
import Cookies from 'js-cookie';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  signup: (userData: any) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const COOKIE_OPTS = {
  expires: 7,
  sameSite: 'lax' as const,
  secure: process.env.NODE_ENV === 'production',
};

function clearAuthCookies() {
  Cookies.remove('token');
  Cookies.remove('refreshToken');
  Cookies.remove('user');
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = Cookies.get('token');

    if (!token) {
      setLoading(false);
      return;
    }

    authService.getCurrentUser()
      .then((data) => {
        setUser(data.user);
        setLoading(false);
      })
      .catch((error) => {
        if (error.response?.status === 401 || error.response?.status === 422) {
          clearAuthCookies();
        }
        setUser(null);
        setLoading(false);
      });
  }, []);

  const login = async (username: string, password: string) => {
    const data = await authService.login(username, password);
    Cookies.set('token', data.token, COOKIE_OPTS);
    Cookies.set('refreshToken', data.refreshToken, COOKIE_OPTS);
    Cookies.set('user', JSON.stringify(data.user), COOKIE_OPTS);
    setUser(data.user);
  };

  const signup = async (userData: any) => {
    const data = await authService.signup(userData);
    return data;
  };

  const logout = () => {
    authService.logout();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{
      user,
      loading,
      login,
      signup,
      logout,
      isAuthenticated: !!user,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}