'use client';

import React, { useEffect, useState } from 'react';
import { useAuth } from '@/app/context/AuthContext';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import AuthShowcase from './Authshowcase'



// #15101C
// #FF4D7E
// #F2C879 
export default function LoginForm() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { user, loading: authLoading, login } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!authLoading && user) {
      router.replace('/');
    }
  }, [authLoading, user, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(username, password);
      router.push('/');
    } catch (err: any) {
      setError(err.response?.data?.message || 'Invalid credentials');
    } finally {
      setLoading(false);
    }
  };

  if (authLoading || user) {
    return <div className="min-h-screen bg-[#15101C]" />;
  }

  return (
    <div className="flex min-h-screen bg-[#15101C]">
      <AuthShowcase
        eyebrow="Members"
        headline="Good things start with a conversation."
        subhead="Sign back in and pick up where you left off."
      />

      <div className="flex flex-1 items-center justify-center px-6 py-14">
        <div className="w-full max-w-sm">
          <div className="mb-9">
            <h1 className="font-serif text-3xl text-[#F5EFE9]">Welcome back</h1>
            <p className="mt-2 text-sm text-[#9C8FA8]">
              Sign in to your account to continue.
            </p>
          </div>

          <form className="space-y-5" onSubmit={handleSubmit}>
            <div>
              <label
                htmlFor="username"
                className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-[#9C8FA8]"
              >
                Username
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoComplete="username"
                className="w-full rounded-lg border border-[#332844] bg-[#1E1728] px-4 py-2.5 text-[#F5EFE9] placeholder-[#6E6180] outline-none transition focus:border-[#FF4D7E] focus:ring-2 focus:ring-[#FF4D7E]/30"
                placeholder="Enter your username"
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-[#9C8FA8]"
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                className="w-full rounded-lg border border-[#332844] bg-[#1E1728] px-4 py-2.5 text-[#F5EFE9] placeholder-[#6E6180] outline-none transition focus:border-[#FF4D7E] focus:ring-2 focus:ring-[#FF4D7E]/30"
                placeholder="Enter your password"
              />
            </div>

            <div className="flex justify-end">
              <Link
                href="/forgot-password"
                className="text-sm text-[#9C8FA8] transition hover:text-[#F2C879]"
              >
                Forgot password?
              </Link>
            </div>

            {error && (
              <div className="rounded-lg border border-[#FF6B6B]/30 bg-[#FF6B6B]/10 px-3 py-2 text-sm text-[#FF8A80]">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-[#FF4D7E] py-3 font-medium text-[#15101C] transition hover:bg-[#FF6A93] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? 'Signing in…' : 'Sign in'}
            </button>

            <p className="text-center text-sm text-[#9C8FA8]">
              Don&apos;t have an account?{' '}
              <Link href="/signup" className="font-medium text-[#F2C879] hover:text-[#F5D998]">
                Sign up
              </Link>
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}