'use client';

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import {
  authService,
  clearAuthenticationCookieHints,
  hasAuthenticationCookieHint,
} from '@/app/services/api';
import { User } from '@/app/types';
import Cookies from 'js-cookie';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<User>;
  signup: (userData: unknown) => Promise<void>;
  logout: () => Promise<void>;
  completeOAuthLogin: () => Promise<User>;
  updateUser: (user: User) => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Cookies.remove('token');
    Cookies.remove('refreshToken');
    Cookies.remove('user');

    if (!hasAuthenticationCookieHint()) {
      setLoading(false);
      return;
    }

    authService.bootstrap()
      .then((data) => {
        setUser(data.authenticated ? data.user : null);

        if (!data.authenticated) {
          clearAuthenticationCookieHints();
        }
      })
      .catch(() => {
        clearAuthenticationCookieHints();
        setUser(null);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const data = await authService.login(username, password);
    setUser(data.user);
    return data.user as User;
  }, []);

  const signup = useCallback(async (userData: unknown) => {
    await authService.signup(userData);
  }, []);

  const completeOAuthLogin = useCallback(async () => {
    const data = await authService.bootstrap();

    if (!data.authenticated || !data.user) {
      throw new Error('OAuth session could not be established');
    }

    setUser(data.user);
    return data.user;
  }, []);

  const updateUser = useCallback((updatedUser: User) => {
    setUser(updatedUser);
  }, []);

  const logout = useCallback(async () => {
    const session = await authService.bootstrap();

    if (session.authenticated) {
      await authService.logout();
    }

    clearAuthenticationCookieHints();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{
      user,
      loading,
      login,
      signup,
      logout,
      completeOAuthLogin,
      updateUser,
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
