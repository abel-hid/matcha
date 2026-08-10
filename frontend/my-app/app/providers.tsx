'use client';

import { AudioCallProvider } from '@/app/components/AudioCallProvider';
import { NotificationProvider } from '@/app/components/NotificationBell';

export function Providers({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <NotificationProvider>
      <AudioCallProvider>{children}</AudioCallProvider>
    </NotificationProvider>
  );
}
