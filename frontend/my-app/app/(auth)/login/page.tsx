import { Suspense } from 'react';

import LoginForm from '@/app/components/auth/LoginForm';

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
