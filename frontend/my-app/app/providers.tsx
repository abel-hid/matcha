'use client';

import { AudioCallProvider } from '@/app/components/AudioCallProvider';
import { NotificationProvider } from '@/app/components/NotificationBell';

/** Compose global client providers once so every authenticated page receives live events. */
export function Providers({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <NotificationProvider>
      <AudioCallProvider>{children}</AudioCallProvider>
    </NotificationProvider>
  );
}
