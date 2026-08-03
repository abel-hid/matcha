'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { apiErrorMessage, apiErrorReason } from '@/app/lib/apiError';
import { authService } from '@/app/services/api';
import AuthShowcase from './AuthShowcase';
import { resetPasswordSchema, ResetPasswordFormData } from '@/app/lib/authValidation';

const inputClasses =
  'mt-1.5 w-full rounded-lg border border-[#332844] bg-[#1E1728] px-4 py-2.5 text-[#F5EFE9] placeholder-[#6E6180] outline-none transition focus:border-[#FF4D7E] focus:ring-2 focus:ring-[#FF4D7E]/30';

const labelClasses = 'block text-xs font-medium uppercase tracking-wide text-[#9C8FA8]';

type TokenStatus = 'checking' | 'valid' | 'invalid';

const REASON_COPY: Record<string, { title: string; body: string }> = {
  expired: {
    title: 'This link has expired',
    body: 'Password reset links only work for 1 hour. Request a new one below.',
  },
  used: {
    title: 'This link was already used',
    body: 'Each reset link only works once. Request a new one if you need to change your password again.',
  },
  invalid: {
    title: 'This link isn\u2019t valid',
    body: 'The link looks broken or incomplete. Request a new one below.',
  },
};

/** Validate the reset token and submit a strong replacement password. */
export default function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get('token');

  const [tokenStatus, setTokenStatus] = useState<TokenStatus>('checking');
  const [invalidReason, setInvalidReason] = useState<string>('invalid');

  const [error, setError] = useState('');
  const [errorReason, setErrorReason] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ResetPasswordFormData>({
    resolver: zodResolver(resetPasswordSchema),
  });

  useEffect(() => {
    if (!token) {
      setTokenStatus('invalid');
      setInvalidReason('invalid');
      return;
    }

    let cancelled = false;

    authService
      .verifyResetToken(token)
      .then(() => {
        if (!cancelled) setTokenStatus('valid');
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setInvalidReason(apiErrorReason(err) || 'invalid');
        setTokenStatus('invalid');
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  /** Validate and submit the new password with the reset token from the URL. */
  const onSubmit = async (data: ResetPasswordFormData) => {
    if (!token) return;
    setError('');
    setLoading(true);

    try {
      await authService.resetPassword(token, data.password);
      setSuccess(true);
      setTimeout(() => router.push('/login'), 3000);
    } catch (err: unknown) {
      const reason = apiErrorReason(err);
      setErrorReason(reason ?? null);
      setError(
        apiErrorMessage(err, 'This link is invalid or has expired. Please request a new one.')
      );
      if (reason === 'used' || reason === 'expired' || reason === 'invalid') {
        setTokenStatus('invalid');
        setInvalidReason(reason);
      }
    } finally {
      setLoading(false);
    }
  };

  if (tokenStatus === 'checking') {
    return <div className="min-h-[calc(100vh-8rem)] bg-[#15101C]" />;
  }

  if (tokenStatus === 'invalid') {
    const copy = REASON_COPY[invalidReason] || REASON_COPY.invalid;
    return (
      <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center bg-[#15101C] px-6">
        <div className="w-full max-w-sm rounded-xl border border-[#332844] bg-[#1E1728] p-8 text-center">
          <div className="mx-auto mb-5 flex h-12 w-12 items-center justify-center rounded-full bg-[#FF6B6B]/15">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M12 8v5M12 16h.01M12 3l9 16H3L12 3z"
                stroke="#FF8A80"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <h2 className="font-serif text-2xl text-[#F5EFE9]">{copy.title}</h2>
          <p className="mt-2 text-sm text-[#9C8FA8]">{copy.body}</p>
          <Link
            href="/forgot-password"
            className="mt-6 inline-block rounded-lg bg-[#FF4D7E] px-5 py-2.5 text-sm font-medium text-[#15101C] transition hover:bg-[#FF6A93]"
          >
            Request a new link
          </Link>
        </div>
      </div>
    );
  }

  if (success) {
    return (
      <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center bg-[#15101C] px-6">
        <div className="w-full max-w-sm rounded-xl border border-[#332844] bg-[#1E1728] p-8 text-center">
          <div className="mx-auto mb-5 flex h-12 w-12 items-center justify-center rounded-full bg-[#FF4D7E]/15">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M5 13l4 4L19 7"
                stroke="#FF4D7E"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <h2 className="font-serif text-2xl text-[#F5EFE9]">Password reset</h2>
          <p className="mt-2 text-sm text-[#9C8FA8]">
            You can now sign in with your new password.
          </p>
          <p className="mt-5 text-xs uppercase tracking-wide text-[#6E6180]">
            Redirecting to login…
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-[calc(100vh-8rem)] bg-[#15101C]">
      <AuthShowcase
        eyebrow="Account recovery"
        headline="Almost there."
        subhead="Choose a new password to finish getting back into your account."
      />

      <div className="flex flex-1 items-center justify-center px-6 py-14">
        <div className="w-full max-w-sm">
          <div className="mb-9">
            <h1 className="font-serif text-3xl text-[#F5EFE9]">Choose a new password</h1>
            <p className="mt-2 text-sm text-[#9C8FA8]">
              Make it something you haven&apos;t used before.
            </p>
          </div>

          <form className="space-y-5" onSubmit={handleSubmit(onSubmit)}>
            <div>
              <label htmlFor="password" className={labelClasses}>New password</label>
              <input
                id="password"
                type="password"
                {...register('password')}
                className={inputClasses}
                placeholder="Enter a new password"
                autoFocus
              />
              {errors.password && (
                <p className="mt-1 text-sm text-[#FF8A80]">{errors.password.message}</p>
              )}
            </div>

            <div>
              <label htmlFor="confirmPassword" className={labelClasses}>Confirm password</label>
              <input
                id="confirmPassword"
                type="password"
                {...register('confirmPassword')}
                className={inputClasses}
                placeholder="Confirm your new password"
              />
              {errors.confirmPassword && (
                <p className="mt-1 text-sm text-[#FF8A80]">{errors.confirmPassword.message}</p>
              )}
            </div>

            {error && (
              <div className="rounded-lg border border-[#FF6B6B]/30 bg-[#FF6B6B]/10 px-3 py-2 text-sm text-[#FF8A80]">
                {error}
                {(errorReason === 'expired' || errorReason === 'used') && (
                  <Link href="/forgot-password" className="ml-1 underline">
                    Request a new link
                  </Link>
                )}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-[#FF4D7E] py-3 font-medium text-[#15101C] transition hover:bg-[#FF6A93] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? 'Resetting…' : 'Reset password'}
            </button>

            <p className="text-center text-sm text-[#9C8FA8]">
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
