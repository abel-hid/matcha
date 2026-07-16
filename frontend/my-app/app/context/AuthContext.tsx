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

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = Cookies.get('token');
    
    if (!token) {
      setLoading(false);
      return;
    }

    console.log("token from cookie:", token);
    authService.getCurrentUser()
      .then((data) => {
        console.log("Current user data:", data);
        setUser(data.user);
        setLoading(false);
      })
      .catch((error) => {
        console.error('Error fetching current user:', error);
        if (error.response?.status === 401 || error.response?.status === 422) {
          // Invalid token – clear cookies
          // Cookies.remove('token');
          // Cookies.remove('refreshToken');
          // Cookies.remove('user');
        }
        setLoading(false);
      });
  }, []);

  const login = async (username: string, password: string) => {
    const data = await authService.login(username, password);
    // Set cookies with 7-day expiry (matching backend expiry if you increased it)
    Cookies.set('token', data.token, { expires: 7, sameSite: 'lax', secure: process.env.NODE_ENV === 'production' });
    Cookies.set('refreshToken', data.refreshToken, { expires: 7, sameSite: 'lax', secure: process.env.NODE_ENV === 'production' });
    Cookies.set('user', JSON.stringify(data.user), { expires: 7, sameSite: 'lax', secure: process.env.NODE_ENV === 'production' });
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