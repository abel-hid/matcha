'use client';

import { useEffect, useRef } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { useAuth } from '@/app/context/AuthContext';

export default function OAuthCallbackPage() {
  const params = useSearchParams();
  const router = useRouter();
  const { completeOAuthLogin } = useAuth();
  const hasRun = useRef(false);

  useEffect(() => {
    if (hasRun.current) return;
    hasRun.current = true;

    const error = params.get('error');
    if (error) {
      router.replace(`/login?error=${error}`);
      return;
    }

    completeOAuthLogin()
      .then((user) => router.replace(user.isProfileComplete ? '/' : '/profile'))
      .catch(() => router.replace('/login?error=session_failed'));
  }, [completeOAuthLogin, params, router]);

  return <div className="min-h-screen bg-[#15101C]" />;
}
