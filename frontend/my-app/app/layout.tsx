import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { AuthProvider } from '@/app/context/AuthContext';
import { Providers } from './test';
const inter = Inter({ subsets: ['latin'] });

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
      <body className={inter.className} suppressHydrationWarning={true}>
        <AuthProvider>
          <Providers>
          {children}
          </Providers>
        </AuthProvider>
      </body>
    </html>
  );
}