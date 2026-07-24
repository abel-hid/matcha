
'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/app/context/AuthContext';
import { profileService } from '@/app/services/api';

interface Stats {
  fameRating: number;
  isProfileComplete: boolean;
  viewersCount: number;
  likesCount: number;
  photosCount: number;
}

export default function Dashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([
      profileService.getProfile(),
      profileService.getViewers(),
      profileService.getLikes(),
    ])
      .then(([profileData, viewersData, likesData]) => {
        setStats({
          fameRating: profileData.user.fameRating ?? 0,
          isProfileComplete: profileData.user.isProfileComplete,
          viewersCount: viewersData.viewers.length,
          likesCount: likesData.likes.length,
          photosCount: profileData.user.photos?.length ?? 0,
        });
      })
      .catch((err: any) => setError(err.response?.data?.message || 'Failed to load your dashboard.'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="font-serif text-3xl text-[#F5EFE9]">
        Welcome back{user?.firstName ? `, ${user.firstName}` : ''}.
      </h1>
      <p className="mt-1 text-sm text-[#9C8FA8]">Here&apos;s what&apos;s happening with your profile.</p>

      {error && (
        <div className="mt-6 rounded-lg border border-[#FF6B6B]/30 bg-[#FF6B6B]/10 px-4 py-3 text-sm text-[#FF8A80]">
          {error}
        </div>
      )}

      {loading ? (
        <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-24 animate-pulse rounded-xl border border-[#332844] bg-[#1E1728]" />
          ))}
        </div>
      ) : stats ? (
        <>
          {!stats.isProfileComplete && (
            <Link
              href="/profile"
              className="mt-6 flex items-center justify-between rounded-lg border border-[#F2C879]/30 bg-[#F2C879]/10 px-4 py-3 text-sm text-[#F2C879] transition hover:bg-[#F2C879]/15"
            >
              <span>Your profile isn&apos;t complete — finish it to start appearing to others.</span>
              <span className="whitespace-nowrap font-medium">Complete it &rarr;</span>
            </Link>
          )}

          <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatCard label="Fame rating" value={stats.fameRating} accent="#F2C879" />
            <StatCard label="Photos" value={`${stats.photosCount}/5`} accent="#FF4D7E" />
            <Link href="/profile/activity">
              <StatCard label="Profile views" value={stats.viewersCount} accent="#9C8FA8" clickable />
            </Link>
            <Link href="/profile/activity">
              <StatCard label="Likes received" value={stats.likesCount} accent="#FF4D7E" clickable />
            </Link>
          </div>

          <div className="mt-10 grid gap-4 sm:grid-cols-2">
            <QuickLink
              href="/"
              title="Discover people"
              body="Browse profiles matched to your preferences, location, and interests."
            />
            <QuickLink
              href="/search"
              title="Search"
              body="Find people by age range, fame rating, location, or tags."
            />
            <QuickLink
              href="/messages"
              title="Messages"
              body="Chat with people you're connected with."
            />
            <QuickLink
              href="/profile"
              title="Edit your profile"
              body="Update your photos, bio, interests, and location."
            />
          </div>
        </>
      ) : null}
    </div>
  );
}


function StatCard({
  label,
  value,
  accent,
  clickable,
}: {
  label: string;
  value: string | number;
  accent: string;
  clickable?: boolean;
}) {
  return (
    <div
      className={`rounded-xl border border-[#332844] bg-[#1E1728] p-4 transition ${
        clickable ? 'cursor-pointer hover:border-[#FF4D7E]/40' : ''
      }`}
    >
      <p className="text-xs uppercase tracking-wide text-[#9C8FA8]">{label}</p>
      <p className="mt-1 font-serif text-2xl" style={{ color: accent }}>
        {value}
      </p>
    </div>
  );
}

function QuickLink({ href, title, body }: { href: string; title: string; body: string }) {
  return (
    <Link
      href={href}
      className="rounded-xl border border-[#332844] bg-[#1E1728]/50 p-5 transition hover:border-[#FF4D7E]/40 hover:bg-[#1E1728]"
    >
      <h3 className="font-serif text-lg text-[#F5EFE9]">{title}</h3>
      <p className="mt-1 text-sm text-[#9C8FA8]">{body}</p>
    </Link>
  );
}