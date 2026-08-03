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

/** Complete the cookie-based OAuth return flow and route the user safely. */
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

/** Render this application route and delegate its feature logic to the page component. */
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
