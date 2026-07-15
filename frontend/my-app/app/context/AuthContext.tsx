'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { authService } from '@/app/services/api';
import { User } from '@/app/types';

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
    const token = localStorage.getItem('token');
    
    if (!token) {
      setLoading(false);
      return;
    }

    // Only attempt to fetch if token exists
    authService.getCurrentUser()
      .then((data) => {
        setUser(data.user);
        setLoading(false);
      })
      .catch((error) => {
        // If token is invalid/expired, clear it
        console.error('Error fetching current user:', error);
        if (error.response?.status === 401 || error.response?.status === 422) {
          localStorage.removeItem('token');
          localStorage.removeItem('user');
        }
        setLoading(false);
      });
  }, []);

  const login = async (username: string, password: string) => {
    const data = await authService.login(username, password);
    localStorage.setItem('token', data.token);
    localStorage.setItem('user', JSON.stringify(data.user));
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