'use client';

import React from 'react';
import Link from 'next/link';

interface UserCardUser {
  id: number;
  username: string;
  firstName: string;
  lastName: string;
  profilePicture: string | null;
  fameRating: number;
  isOnline: boolean;
  lastActivity: string | null;
  tags: string[];
}

interface UserCardProps {
  user: UserCardUser;
  apiBaseUrl: string;
  meta?: React.ReactNode;
}

/** Convert a last-activity timestamp into a concise relative label. */
function formatLastSeen(iso: string | null) {
  if (!iso) {
    return 'a while ago';
  }

  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60000);

  if (mins < 1) {
    return 'just now';
  }

  if (mins < 60) {
    return `${mins}m ago`;
  }

  const hours = Math.floor(mins / 60);

  if (hours < 24) {
    return `${hours}h ago`;
  }

  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

/** Render one discover or search result with ranking and presence information. */
export default function UserCard({
  user,
  apiBaseUrl,
  meta,
}: UserCardProps) {
  return (
    <Link
      href={`/users/${encodeURIComponent(user.username)}`}
      className="flex items-center gap-3 rounded-lg border border-[#332844] bg-[#1E1728] p-3 transition hover:border-[#FF4D7E]/40"
    >
      <div className="relative h-14 w-14 shrink-0 overflow-hidden rounded-full bg-[#332844]">
        {user.profilePicture ? (
          <img
            src={`${apiBaseUrl}${user.profilePicture}`}
            alt={user.firstName}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-lg text-[#6E6180]">
            {user.firstName?.[0]?.toUpperCase() || '?'}
          </div>
        )}

        {user.isOnline && (
          <span className="absolute bottom-0 right-0 h-3 w-3 rounded-full border-2 border-[#1E1728] bg-[#4ADE80]" />
        )}
      </div>

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-[#F5EFE9]">
          {user.firstName} {user.lastName}
        </p>

        <p className="truncate text-xs text-[#9C8FA8]">
          @{user.username} ·{' '}
          {user.isOnline ? (
            <span className="text-[#4ADE80]">
              Online
            </span>
          ) : (
            formatLastSeen(user.lastActivity)
          )}
        </p>

        {meta && (
          <p className="mt-0.5 text-xs text-[#6E6180]">
            {meta}
          </p>
        )}
      </div>

      <div className="shrink-0 text-right">
        <p className="text-[10px] uppercase tracking-wide text-[#6E6180]">
          Fame
        </p>

        <p className="text-sm font-medium text-[#F2C879]">
          {user.fameRating ?? 0}
        </p>
      </div>
    </Link>
  );
}
