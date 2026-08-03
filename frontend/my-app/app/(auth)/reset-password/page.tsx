import { Suspense } from 'react';
import ResetPasswordForm from '@/app/components/auth/ResetPasswordForm';

/** Render this application route and delegate its feature logic to the page component. */
export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#15101C]" />}>
      <ResetPasswordForm />
    </Suspense>
  );
}
