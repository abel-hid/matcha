import { Suspense } from 'react';
import VerifyEmailForm from '@/app/components/auth/VerifyEmailForm';

/** Render this application route and delegate its feature logic to the page component. */
export default function VerifyPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#15101C]" />}>
      <VerifyEmailForm />
    </Suspense>
  );
}
