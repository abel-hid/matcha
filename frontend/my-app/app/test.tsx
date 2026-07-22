'use client';

import { NotificationProvider } from '@/app/components/NotificationBell';

export function Providers({ children }: { children: React.ReactNode }) {
  return <NotificationProvider>{children}</NotificationProvider>;
}