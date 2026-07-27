'use client';

import { useEffect, useRef } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { useAuth } from '@/app/context/AuthContext';

export default function OAuthCallbackPage() {
  const params = useSearchParams();
  const router = useRouter();
  const { setTokens } = useAuth();
  const hasRun = useRef(false);

  useEffect(() => {
    if (hasRun.current) return;
    hasRun.current = true;

    const token = params.get('token');
    const refreshToken = params.get('refreshToken');
    const error = params.get('error');

    if (error) {
      router.replace(`/login?error=${error}`);
      return;
    }

    if (token && refreshToken) {
      setTokens(token, refreshToken)
        .then(() => router.replace('/'))
        .catch(() => router.replace('/login?error=token_exchange_failed'));
    } else {
      router.replace('/login');
    }
  }, [params, router, setTokens]);

  return <div className="min-h-screen bg-[#15101C]" />;
}