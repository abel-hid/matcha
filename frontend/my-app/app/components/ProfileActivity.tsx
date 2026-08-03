'use client';

import { useEffect, useState } from 'react';
import { apiErrorMessage } from '@/app/lib/apiError';
import { profileService } from '@/app/services/api';
import { useNotifications } from '@/app/components/NotificationBell';
import UserCard from './UserCard';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000';

type Tab = 'visits' | 'likedByMe' | 'likedMe' | 'matches';

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

interface ProfileVisit {
  id: number;
  viewedAt: string;
  viewer: ActivityUser;
}

interface ProfileLike {
  likedAt: string;
  user: ActivityUser;
}

interface ProfileMatch {
  matchedAt: string;
  user: ActivityUser;
}

interface ActivityData {
  visits: ProfileVisit[];
  likedByMe: ProfileLike[];
  likedMe: ProfileLike[];
  matches: ProfileMatch[];
}

const EMPTY_ACTIVITY: ActivityData = {
  visits: [],
  likedByMe: [],
  likedMe: [],
  matches: [],
};

/** Load and display profile views, pending likes, and matches by category. */
export default function ProfileActivity() {
  const { presenceByUser } = useNotifications();
  const [tab, setTab] = useState<Tab>('visits');
  const [activity, setActivity] = useState<ActivityData>(EMPTY_ACTIVITY);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    profileService
      .getActivity()
      .then((data) => {
        setActivity({
          visits: data.visits ?? [],
          likedByMe: data.likedByMe ?? [],
          likedMe: data.likedMe ?? [],
          matches: data.matches ?? [],
        });
      })
      .catch((err: unknown) => {
        setError(apiErrorMessage(err, 'Failed to load your activity.'));
      })
      .finally(() => setLoading(false));
  }, []);

  /** Merge live presence updates into an activity user without mutating API data. */
  const withPresence = (user: ActivityUser) => {
    const presence = presenceByUser[user.id];
    if (!presence) {
      return user;
    }

    return {
      ...user,
      isOnline: presence.isOnline,
      lastActivity: presence.lastActivity,
    };
  };

  const counts: Record<Tab, number> = {
    visits: activity.visits.length,
    likedByMe: activity.likedByMe.length,
    likedMe: activity.likedMe.length,
    matches: activity.matches.length,
  };

  const emptyMessages: Record<Tab, string> = {
    visits: 'No one has viewed your profile yet.',
    likedByMe: 'You have no pending likes.',
    likedMe: 'No pending likes received.',
    matches: 'You have no matches yet.',
  };

  const tabs: { id: Tab; label: string }[] = [
    { id: 'visits', label: 'Visits' },
    { id: 'likedByMe', label: 'My likes' },
    { id: 'likedMe', label: 'Liked me' },
    { id: 'matches', label: 'Matches' },
  ];

  return (
    <div className="min-h-screen bg-[#15101C] px-6 py-12">
      <div className="mx-auto max-w-2xl">
        <h1 className="font-serif text-3xl text-[#F5EFE9]">Your activity</h1>
        <p className="mt-1 text-sm text-[#9C8FA8]">
          Review profile visits, pending likes, and mutual matches.
        </p>

        <div className="mt-6 grid grid-cols-2 gap-1 rounded-lg border border-[#332844] bg-[#1E1728] p-1 sm:grid-cols-4">
          {tabs.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setTab(item.id)}
              className={`rounded-md px-2 py-2 text-sm font-medium transition ${
                tab === item.id
                  ? 'bg-[#FF4D7E] text-[#15101C]'
                  : 'text-[#9C8FA8] hover:text-[#F5EFE9]'
              }`}
            >
              {item.label} ({counts[item.id]})
            </button>
          ))}
        </div>

        <div className="mt-4 space-y-2">
          {loading && <div className="h-14 animate-pulse rounded-lg bg-[#1E1728]" />}

          {error && (
            <div className="rounded-lg border border-[#FF6B6B]/30 bg-[#FF6B6B]/10 px-3 py-2 text-sm text-[#FF8A80]">
              {error}
            </div>
          )}

          {!loading && !error && counts[tab] === 0 && (
            <div className="rounded-lg border border-[#332844] bg-[#1E1728]/50 px-4 py-8 text-center">
              <p className="text-sm text-[#9C8FA8]">{emptyMessages[tab]}</p>
            </div>
          )}

          {!loading && tab === 'visits' && activity.visits.map((visit) => (
            <UserCard
              key={visit.id}
              user={withPresence(visit.viewer)}
              apiBaseUrl={API_BASE_URL}
              meta={`Viewed ${new Date(visit.viewedAt).toLocaleString()}`}
            />
          ))}

          {!loading && tab === 'likedByMe' && activity.likedByMe.map((like) => (
            <UserCard
              key={`outgoing-${like.user.id}`}
              user={withPresence(like.user)}
              apiBaseUrl={API_BASE_URL}
              meta={`You liked them ${new Date(like.likedAt).toLocaleString()}`}
            />
          ))}

          {!loading && tab === 'likedMe' && activity.likedMe.map((like) => (
            <UserCard
              key={`incoming-${like.user.id}`}
              user={withPresence(like.user)}
              apiBaseUrl={API_BASE_URL}
              meta={`Liked you ${new Date(like.likedAt).toLocaleString()}`}
            />
          ))}

          {!loading && tab === 'matches' && activity.matches.map((match) => (
            <UserCard
              key={`match-${match.user.id}`}
              user={withPresence(match.user)}
              apiBaseUrl={API_BASE_URL}
              meta={`Matched ${new Date(match.matchedAt).toLocaleString()}`}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
