'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';

import { useAuth } from '@/app/context/AuthContext';
import { apiErrorMessage } from '@/app/lib/apiError';

import AuthShowcase from './Authshowcase';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000';

/** Authenticate local credentials or start a configured OAuth flow. */
export default function LoginForm() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { user, loading: authLoading, login } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    if (!authLoading && user) {
      router.replace(user.isProfileComplete ? '/' : '/profile');
    }
  }, [authLoading, user, router]);

  useEffect(() => {
    const oauthError = searchParams.get('error');
    if (oauthError) {
      setError(oauthErrorMessage(oauthError));
    }
  }, [searchParams]);

  /** Authenticate the credentials and route the user according to profile completion. */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const loggedInUser = await login(username, password);
      router.push(loggedInUser.isProfileComplete ? '/' : '/profile');
    } catch (err: unknown) {
      setError(apiErrorMessage(err, 'Invalid credentials'));
    } finally {
      setLoading(false);
    }
  };

  if (authLoading || user) {
    return <div className="min-h-[calc(100vh-8rem)] bg-[#15101C]" />;
  }

  return (
    <div className="flex min-h-[calc(100vh-8rem)] bg-[#15101C]">
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
                minLength={3}
                maxLength={50}
                pattern="[A-Za-z0-9_]+"
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
                maxLength={72}
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

          <div className="my-7 flex items-center gap-3">
            <div className="h-px flex-1 bg-[#332844]" />
            <span className="text-xs uppercase tracking-wide text-[#6E6180]">or continue with</span>
            <div className="h-px flex-1 bg-[#332844]" />
          </div>

          <div className="space-y-3">
            <a
              href={`${API_URL}/api/auth/oauth/42/login`}
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-[#332844] bg-[#1E1728] py-2.5 text-sm font-medium text-[#F5EFE9] transition hover:border-[#FF4D7E]/50 hover:bg-[#241B30]"
            >
              <FortyTwoIcon />
              Continue with 42
            </a>

            <a
              href={`${API_URL}/api/auth/oauth/google/login`}
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-[#332844] bg-[#1E1728] py-2.5 text-sm font-medium text-[#F5EFE9] transition hover:border-[#F2C879]/50 hover:bg-[#241B30]"
            >
              <GoogleIcon />
              Continue with Google
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

/** Translate a safe OAuth error code into a user-facing message. */
function oauthErrorMessage(code: string): string {
  switch (code) {
    case 'invalid_state':
      return 'Login session expired. Please try again.';
    case 'missing_code':
    case 'access_denied':
      return 'Login was cancelled.';
    case 'token_exchange_failed':
    case 'profile_fetch_failed':
    case 'provider_unavailable':
    case 'invalid_provider_response':
    case 'invalid_provider_profile':
      return 'Something went wrong connecting to that provider. Please try again.';
    case 'email_not_verified':
      return 'Your Google email must be verified to sign in.';
    case 'session_failed':
      return 'The login completed, but the secure session could not be created.';
    case 'oauth_identity_conflict':
      return 'This provider identity is already linked to another account.';
    default:
      return 'Login failed. Please try again.';
  }
}

/** Render the compact 42 provider mark. */
function FortyTwoIcon() {
  return (
    <img src="/42_Logo.svg" alt="42" width={18} height={18} />
  );
}

/** Render the compact Google provider mark. */
function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
        fill="#4285F4"
      />
      <path
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.99.66-2.26 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.85A10.99 10.99 0 0012 23z"
        fill="#34A853"
      />
      <path
        d="M5.84 14.09A6.6 6.6 0 015.5 12c0-.73.13-1.43.34-2.09V7.06H2.18A11 11 0 001 12c0 1.77.43 3.45 1.18 4.94l3.66-2.85z"
        fill="#FBBC05"
      />
      <path
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.85C6.71 7.31 9.14 5.38 12 5.38z"
        fill="#EA4335"
      />
    </svg>
  );
}
