'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { apiErrorMessage } from '@/app/lib/apiError';
import { authService } from '@/app/services/api';

type Status = 'checking' | 'success' | 'already' | 'error';

/** Verify an email token and provide controlled retry states. */
export default function VerifyEmailForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get('token');

  const [status, setStatus] = useState<Status>('checking');
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setMessage('This link is missing its verification token.');
      return;
    }

    authService
      .verifyEmail(token)
      .then((data) => {
        setStatus('success');
        setMessage(data.message || 'Email verified successfully.');
      })
      .catch((err: unknown) => {
        const msg = apiErrorMessage(err, 'This link is invalid or has expired.');
        if (msg.toLowerCase().includes('already verified')) {
          setStatus('already');
        } else {
          setStatus('error');
        }
        setMessage(msg);
      });
  }, [token]);

  return (
    <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center bg-[#15101C] px-6">
      <div className="w-full max-w-sm rounded-xl border border-[#332844] bg-[#1E1728] p-8 text-center">
        {status === 'checking' && (
          <>
            <div className="mx-auto mb-5 h-12 w-12 animate-pulse rounded-full bg-[#332844]" />
            <h2 className="font-serif text-2xl text-[#F5EFE9]">Verifying your email…</h2>
            <p className="mt-2 text-sm text-[#9C8FA8]">This will just take a moment.</p>
          </>
        )}

        {(status === 'success' || status === 'already') && (
          <>
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
            <h2 className="font-serif text-2xl text-[#F5EFE9]">
              {status === 'already' ? 'Already verified' : 'Email verified'}
            </h2>
            <p className="mt-2 text-sm text-[#9C8FA8]">
              {status === 'already'
                ? 'This email was already confirmed - you can sign in.'
                : 'Your account is ready. You can sign in now.'}
            </p>
            <Link
              href="/login"
              className="mt-6 inline-block rounded-lg bg-[#FF4D7E] px-5 py-2.5 text-sm font-medium text-[#15101C] transition hover:bg-[#FF6A93]"
            >
              Sign in
            </Link>
          </>
        )}

        {status === 'error' && (
          <>
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
            <h2 className="font-serif text-2xl text-[#F5EFE9]">Verification failed</h2>
            <p className="mt-2 text-sm text-[#9C8FA8]">{message}</p>
            <Link
              href="/login"
              className="mt-6 inline-block text-sm font-medium text-[#F2C879] hover:text-[#F5D998]"
            >
              Back to sign in
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
