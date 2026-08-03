import type { Metadata } from 'next';

import { AuthProvider } from '@/app/context/AuthContext';
import { Providers } from '@/app/providers';

import './globals.css';

export const metadata: Metadata = {
  title: 'Matcha - Dating App',
  description: 'Discover compatible people, connect, chat, call, and plan dates.',
};

/** Wrap every route with authentication, notification, and audio-call state. */
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body suppressHydrationWarning>
        <AuthProvider>
          <Providers>{children}</Providers>
        </AuthProvider>
      </body>
    </html>
  );
}
