'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { apiErrorMessage } from '@/app/lib/apiError';
import { authService } from '@/app/services/api';
import AuthShowcase from './AuthShowcase';

/** Submit a neutral password-reset request without exposing account existence. */
export default function ForgotPasswordForm() {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  /** Request a reset email while preserving the backend’s account-enumeration protection. */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await authService.forgotPassword(email);
      setSent(true);
    } catch (err: unknown) {
      setError(apiErrorMessage(err, 'Something went wrong. Please try again.'));
    } finally {
      setLoading(false);
    }
  };

  if (sent) {
    return (
      <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center bg-[#15101C] px-6">
        <div className="w-full max-w-sm rounded-xl border border-[#332844] bg-[#1E1728] p-8 text-center">
          <div className="mx-auto mb-5 flex h-12 w-12 items-center justify-center rounded-full bg-[#FF4D7E]/15">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M4 6l8 6 8-6M4 6h16v12H4V6z"
                stroke="#FF4D7E"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <h2 className="font-serif text-2xl text-[#F5EFE9]">Check your inbox</h2>
          <p className="mt-2 text-sm text-[#9C8FA8]">
            If an account exists for <span className="text-[#F5EFE9]">{email}</span>, we&apos;ve
            sent a link to reset your password.
          </p>
          <Link
            href="/login"
            className="mt-6 inline-block text-sm font-medium text-[#F2C879] hover:text-[#F5D998]"
          >
            Back to sign in
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-[calc(100vh-8rem)] bg-[#15101C]">
      <AuthShowcase
        eyebrow="Account recovery"
        headline="It happens to everyone."
        subhead="Enter your email and we'll send you a link to get back in."
      />

      <div className="flex flex-1 items-center justify-center px-6 py-14">
        <div className="w-full max-w-sm">
          <div className="mb-9">
            <h1 className="font-serif text-3xl text-[#F5EFE9]">Reset your password</h1>
            <p className="mt-2 text-sm text-[#9C8FA8]">
              We&apos;ll email you a link to choose a new one.
            </p>
          </div>

          <form className="space-y-5" onSubmit={handleSubmit}>
            <div>
              <label
                htmlFor="email"
                className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-[#9C8FA8]"
              >
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                maxLength={100}
                autoComplete="email"
                autoFocus
                className="w-full rounded-lg border border-[#332844] bg-[#1E1728] px-4 py-2.5 text-[#F5EFE9] placeholder-[#6E6180] outline-none transition focus:border-[#FF4D7E] focus:ring-2 focus:ring-[#FF4D7E]/30"
                placeholder="Enter your email"
              />
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
              {loading ? 'Sending link…' : 'Send reset link'}
            </button>

            <p className="text-center text-sm text-[#9C8FA8]">
              Remembered it?{' '}
              <Link href="/login" className="font-medium text-[#F2C879] hover:text-[#F5D998]">
                Back to sign in
              </Link>
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
