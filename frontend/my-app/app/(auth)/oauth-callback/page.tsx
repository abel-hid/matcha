'use client';

import {
  Suspense,
  useEffect,
  useRef,
} from 'react';
import {
  useRouter,
  useSearchParams,
} from 'next/navigation';

import { useAuth } from '@/app/context/AuthContext';

function OAuthCallbackContent() {
  const params = useSearchParams();
  const router = useRouter();
  const { completeOAuthLogin } = useAuth();
  const hasRun = useRef(false);

  useEffect(() => {
    if (hasRun.current) {
      return;
    }

    hasRun.current = true;

    const error = params.get('error');

    if (error) {
      router.replace(`/login?error=${error}`);
      return;
    }

    completeOAuthLogin()
      .then((user) => {
        router.replace(
          user.isProfileComplete
            ? '/'
            : '/profile'
        );
      })
      .catch(() => {
        router.replace('/login?error=session_failed');
      });
  }, [
    completeOAuthLogin,
    params,
    router,
  ]);

  return <div className="min-h-[calc(100vh-8rem)] bg-[#15101C]" />;
}

export default function OAuthCallbackPage() {
  return (
    <Suspense
      fallback={(
        <div className="min-h-[calc(100vh-8rem)] bg-[#15101C]" />
      )}
    >
      <OAuthCallbackContent />
    </Suspense>
  );
}
