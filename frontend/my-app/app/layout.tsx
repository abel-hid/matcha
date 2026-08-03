import type { Metadata } from 'next';
import './globals.css';
import { AuthProvider } from '@/app/context/AuthContext';
import { Providers } from './test';

export const metadata: Metadata = {
  title: 'Matcha - Dating App',
  description: 'Find your perfect match',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body suppressHydrationWarning={true}>
        <AuthProvider>
          <Providers>
          {children}
          </Providers>
        </AuthProvider>
      </body>
    </html>
  );
}