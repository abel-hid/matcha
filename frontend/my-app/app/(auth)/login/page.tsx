import { Suspense } from 'react';

import LoginForm from '@/app/components/auth/LoginForm';

/** Render this application route and delegate its feature logic to the page component. */
export default function LoginPage() {
  return (
    <Suspense
      fallback={(
        <div className="min-h-screen bg-[#15101C]" />
      )}
    >
      <LoginForm />
    </Suspense>
  );
}
