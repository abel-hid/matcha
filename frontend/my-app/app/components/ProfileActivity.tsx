'use client';

import React, { useEffect, useState } from 'react';
import { profileService } from '@/app/services/api';
import UserCard from './UserCard';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000';

type Tab = 'viewers' | 'likes';

interface ActivityUser {
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

export default function ProfileActivity() {
  const [tab, setTab] = useState<Tab>('viewers');
  const [viewers, setViewers] = useState<ActivityUser[] | null>(null);
  const [likes, setLikes] = useState<ActivityUser[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([profileService.getViewers(), profileService.getLikes()])
      .then(([viewersData, likesData]) => {
        setViewers(viewersData.viewers);
        setLikes(likesData.likes);
      })
      .catch((err: any) => {
        setError(err.response?.data?.message || 'Failed to load your activity.');
      })
      .finally(() => setLoading(false));
  }, []);

  const activeList = tab === 'viewers' ? viewers : likes;

  return (
    <div className="min-h-screen bg-[#15101C] px-6 py-12">
      <div className="mx-auto max-w-lg">
        <h1 className="font-serif text-3xl text-[#F5EFE9]">Your activity</h1>
        <p className="mt-1 text-sm text-[#9C8FA8]">See who&apos;s been checking you out.</p>

        <div className="mt-6 flex gap-1 rounded-lg border border-[#332844] bg-[#1E1728] p-1">
          <button
            type="button"
            onClick={() => setTab('viewers')}
            className={`flex-1 rounded-md py-2 text-sm font-medium transition ${
              tab === 'viewers'
                ? 'bg-[#FF4D7E] text-[#15101C]'
                : 'text-[#9C8FA8] hover:text-[#F5EFE9]'
            }`}
          >
            Viewed you {viewers !== null && `(${viewers.length})`}
          </button>
          <button
            type="button"
            onClick={() => setTab('likes')}
            className={`flex-1 rounded-md py-2 text-sm font-medium transition ${
              tab === 'likes'
                ? 'bg-[#FF4D7E] text-[#15101C]'
                : 'text-[#9C8FA8] hover:text-[#F5EFE9]'
            }`}
          >
            Liked you {likes !== null && `(${likes.length})`}
          </button>
        </div>

        <div className="mt-4 space-y-2">
          {loading && <div className="h-14 animate-pulse rounded-lg bg-[#1E1728]" />}

          {error && (
            <div className="rounded-lg border border-[#FF6B6B]/30 bg-[#FF6B6B]/10 px-3 py-2 text-sm text-[#FF8A80]">
              {error}
            </div>
          )}

          {!loading && !error && activeList && activeList.length === 0 && (
            <div className="rounded-lg border border-[#332844] bg-[#1E1728]/50 px-4 py-8 text-center">
              <p className="text-sm text-[#9C8FA8]">
                {tab === 'viewers'
                  ? 'No one has viewed your profile yet.'
                  : 'No one has liked you yet.'}
              </p>
            </div>
          )}

          {!loading &&
            activeList &&
            activeList.map((u) => <UserCard key={u.id} user={u} apiBaseUrl={API_BASE_URL} />)}
        </div>
      </div>
    </div>
  );
}