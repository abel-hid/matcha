'use client';

import { useEffect, useState } from 'react';
import { apiErrorMessage } from '@/app/lib/apiError';
import { usersService } from '@/app/services/api';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000';

interface BlockedUser {
  id: number;
  username: string;
  firstName: string;
  lastName: string;
  profilePicture: string | null;
}

interface BlockEntry {
  blockedAt: string;
  user: BlockedUser;
}

/** Render this application route and delegate its feature logic to the page component. */
export default function BlockedUsersPage() {
  const [blocks, setBlocks] = useState<BlockEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    usersService.getBlockedUsers()
      .then((data) => setBlocks(data.blocks ?? []))
      .catch((err: unknown) => {
        setError(apiErrorMessage(err, 'Failed to load blocked users.'));
      })
      .finally(() => setLoading(false));
  }, []);

  /** Remove a block and update the list only after the API confirms success. */
  const handleUnblock = async (userId: number) => {
    setBusyId(userId);
    setError('');

    try {
      await usersService.unblock(userId);
      setBlocks((current) => current.filter((block) => block.user.id !== userId));
    } catch (err: unknown) {
      setError(apiErrorMessage(err, 'Failed to unblock this user.'));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="min-h-screen bg-[#15101C] px-6 py-12">
      <div className="mx-auto max-w-lg">
        <h1 className="font-serif text-3xl text-[#F5EFE9]">Blocked users</h1>
        <p className="mt-1 text-sm text-[#9C8FA8]">
          Unblock someone to allow profiles and interactions again.
        </p>

        {error && (
          <div className="mt-5 rounded-lg border border-[#FF6B6B]/30 bg-[#FF6B6B]/10 px-3 py-2 text-sm text-[#FF8A80]">
            {error}
          </div>
        )}

        <div className="mt-6 space-y-3">
          {loading && <div className="h-20 animate-pulse rounded-lg bg-[#1E1728]" />}

          {!loading && blocks.length === 0 && (
            <div className="rounded-lg border border-[#332844] bg-[#1E1728]/50 px-4 py-8 text-center text-sm text-[#9C8FA8]">
              You have not blocked anyone.
            </div>
          )}

          {blocks.map((block) => (
            <div
              key={block.user.id}
              className="flex items-center gap-3 rounded-lg border border-[#332844] bg-[#1E1728] p-3"
            >
              <div className="h-14 w-14 shrink-0 overflow-hidden rounded-full bg-[#332844]">
                {block.user.profilePicture ? (
                  <img
                    src={`${API_BASE_URL}${block.user.profilePicture}`}
                    alt={block.user.firstName}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center text-lg text-[#6E6180]">
                    {block.user.firstName?.[0]?.toUpperCase() || '?'}
                  </div>
                )}
              </div>

              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-[#F5EFE9]">
                  {block.user.firstName} {block.user.lastName}
                </p>
                <p className="truncate text-xs text-[#9C8FA8]">@{block.user.username}</p>
                <p className="mt-0.5 text-xs text-[#6E6180]">
                  Blocked {new Date(block.blockedAt).toLocaleString()}
                </p>
              </div>

              <button
                type="button"
                onClick={() => handleUnblock(block.user.id)}
                disabled={busyId === block.user.id}
                className="rounded-lg border border-[#FF4D7E]/50 px-3 py-2 text-sm text-[#FF8FAE] transition hover:bg-[#FF4D7E]/10 disabled:opacity-50"
              >
                {busyId === block.user.id ? '…' : 'Unblock'}
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
