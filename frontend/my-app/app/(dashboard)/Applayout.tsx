'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '@/app/context/AuthContext';

const NAV_LINKS = [
  { href: '/', label: 'Discover' },
  { href: '/search', label: 'Search' },
  { href: '/profile/activity', label: 'Activity' },
  { href: '/messages', label: 'Messages' },
  { href: '/profile', label: 'Profile' },
];

interface AppLayoutProps {
  children: React.ReactNode;
}

export default function AppLayout({ children }: AppLayoutProps) {
  const { user, loading, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    if (!loading && !user) {
      router.replace('/login');
    }
  }, [loading, user, router]);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  const handleLogout = () => {
    logout();
    router.push('/login');
  };

  if (loading || !user) {
    return <div className="min-h-screen bg-[#15101C]" />;
  }

  return (
    <div className="flex min-h-screen flex-col bg-[#15101C]">
      {/* Header */}
      <header className="sticky top-0 z-20 border-b border-[#332844] bg-[#15101C]/95 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <Link href="/" className="font-serif text-xl text-[#F5EFE9]">
            matcha
          </Link>

          {/* Desktop nav */}
          <nav className="hidden items-center gap-1 md:flex">
            {NAV_LINKS.map((link) => {
              const active = pathname === link.href;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                    active
                      ? 'bg-[#FF4D7E]/15 text-[#FF8FAE]'
                      : 'text-[#9C8FA8] hover:text-[#F5EFE9]'
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>

          <div className="hidden items-center gap-3 md:flex">
            <Link
              href="/profile"
              className="flex h-9 w-9 items-center justify-center overflow-hidden rounded-full bg-[#332844] text-sm font-medium text-[#F5EFE9]"
            >
              {user.firstName?.[0]?.toUpperCase() || user.username?.[0]?.toUpperCase() || '?'}
            </Link>
            <button
              type="button"
              onClick={handleLogout}
              className="rounded-lg border border-[#332844] px-3 py-1.5 text-sm text-[#9C8FA8] transition hover:border-[#FF6B6B]/40 hover:text-[#FF8A80]"
            >
              Log out
            </button>
          </div>

          {/* Mobile menu button */}
          <button
            type="button"
            onClick={() => setMobileOpen((v) => !v)}
            className="flex h-9 w-9 items-center justify-center rounded-md text-[#F5EFE9] md:hidden"
            aria-label="Toggle menu"
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              {mobileOpen ? (
                <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              ) : (
                <path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              )}
            </svg>
          </button>
        </div>

        {/* Mobile nav */}
        {mobileOpen && (
          <nav className="border-t border-[#332844] px-6 py-3 md:hidden">
            <div className="flex flex-col gap-1">
              {NAV_LINKS.map((link) => {
                const active = pathname === link.href;
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={`rounded-md px-3 py-2 text-sm font-medium transition ${
                      active
                        ? 'bg-[#FF4D7E]/15 text-[#FF8FAE]'
                        : 'text-[#9C8FA8] hover:text-[#F5EFE9]'
                    }`}
                  >
                    {link.label}
                  </Link>
                );
              })}
              <button
                type="button"
                onClick={handleLogout}
                className="mt-1 rounded-md px-3 py-2 text-left text-sm text-[#FF8A80]"
              >
                Log out
              </button>
            </div>
          </nav>
        )}
      </header>

      {/* Main */}
      <main className="flex-1">{children}</main>

      {/* Footer */}
      <footer className="border-t border-[#332844] px-6 py-6">
        <div className="mx-auto flex max-w-5xl flex-col items-center justify-between gap-2 text-xs text-[#6E6180] sm:flex-row">
          <span>&copy; {new Date().getFullYear()} Matcha</span>
          <div className="flex gap-4">
            <Link href="/profile" className="hover:text-[#9C8FA8]">Profile</Link>
            <Link href="/profile/activity" className="hover:text-[#9C8FA8]">Activity</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}