'use client';

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';

import { useAudioCall } from '@/app/components/AudioCallProvider';
import { useNotifications } from '@/app/components/NotificationBell';
import { useAuth } from '@/app/context/AuthContext';
import { usersService } from '@/app/services/api';

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL
  || 'http://localhost:5000'
);

const VISIT_DEDUPE_WINDOW_MS = 2_000;

const recentVisitIds = new Map<
  number,
  {
    id: string;
    createdAt: number;
  }
>();

function getProfileVisitId(userId: number) {
  const now = Date.now();
  const recent = recentVisitIds.get(userId);

  if (
    recent
    && now - recent.createdAt < VISIT_DEDUPE_WINDOW_MS
  ) {
    return recent.id;
  }

  const id = globalThis.crypto.randomUUID();

  recentVisitIds.set(userId, {
    id,
    createdAt: now,
  });

  return id;
}

interface Photo {
  id: number;
  url: string;
  isPrimary: boolean;
  position: number;
}

interface ViewedUser {
  id: number;
  username: string;
  firstName: string;
  lastName: string;
  age: number | null;
  gender: 'male' | 'female' | 'non-binary' | null;
  sexualPreferences: (
    'male'
    | 'female'
    | 'non-binary'
  )[];
  biography: string | null;
  profilePicture: string | null;
  photos: Photo[];
  fameRating: number;
  tags: string[];
  isOnline: boolean;
  lastActivity: string | null;
  location: {
    name: string | null;
  } | null;
  isProfileComplete: boolean;
  hasLikedThem: boolean;
  theyLikedMe: boolean;
  isConnected: boolean;
  hasReported: boolean;
}

function pluralize(value: number, unit: string) {
  return `${value} ${unit}${value === 1 ? '' : 's'} ago`;
}

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
    return pluralize(mins, 'minute');
  }

  const hours = Math.floor(mins / 60);

  if (hours < 24) {
    return pluralize(hours, 'hour');
  }

  const days = Math.floor(hours / 24);
  return pluralize(days, 'day');
}

const MISSING_INFORMATION = 'Not provided';

function formatProfileValue(value: string) {
  return value
    .split('-')
    .map(
      (part) => (
        part.charAt(0).toUpperCase()
        + part.slice(1)
      )
    )
    .join('-');
}

function ProfileDetail({
  label,
  value,
  missing = false,
}: {
  label: string;
  value: string;
  missing?: boolean;
}) {
  return (
    <div className="rounded-lg border border-[#332844] bg-[#1A1422] px-4 py-3">
      <p className="text-xs uppercase tracking-wide text-[#766A82]">
        {label}
      </p>

      <p
        className={`mt-1 text-sm ${
          missing
            ? 'italic text-[#766A82]'
            : 'text-[#D8CFE0]'
        }`}
      >
        {value}
      </p>
    </div>
  );
}

export default function UserProfileView() {
  const params = useParams();
  const router = useRouter();
  const { user: currentUser } = useAuth();
  const { startAudioCall, callBusy } = useAudioCall();
  const {
    presenceByUser,
    conversationStatus,
  } = useNotifications();

  const username = Array.isArray(params.username)
    ? params.username[0]
    : params.username;

  const currentUserId = currentUser?.id;

  const [user, setUser] = useState<ViewedUser | null>(null);
  const [activePhoto, setActivePhoto] = useState(0);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [actionError, setActionError] = useState('');
  const [likePending, setLikePending] = useState(false);
  const [blockPending, setBlockPending] = useState(false);
  const [reported, setReported] = useState(false);
  const [confirmBlock, setConfirmBlock] = useState(false);

  const viewedUserId = user?.id;

  useEffect(() => {
    if (!username) {
      setNotFound(true);
      setLoading(false);
      return;
    }

    setLoading(true);
    setNotFound(false);
    setActionError('');
    setActivePhoto(0);

    usersService
      .getUserByUsername(username)
      .then((data) => {
        const loadedUser = data.user as ViewedUser;

        setUser(loadedUser);
        setReported(Boolean(loadedUser.hasReported));

        return usersService.recordVisit(
          loadedUser.id,
          getProfileVisitId(loadedUser.id)
        );
      })
      .catch((err: any) => {
        if (err.response?.status === 404) {
          setNotFound(true);
          setUser(null);
          return;
        }

        setActionError(
          err.response?.data?.message
          || 'The profile could not be loaded completely.'
        );
      })
      .finally(() => setLoading(false));
  }, [username]);

  useEffect(() => {
    if (
      !viewedUserId
      || !currentUserId
      || !conversationStatus
      || conversationStatus.userId !== viewedUserId
    ) {
      return;
    }

    if (conversationStatus.reason === 'block') {
      setUser(null);
      setNotFound(true);
      return;
    }

    if (conversationStatus.reason === 'match') {
      setUser((current) => current ? {
        ...current,
        hasLikedThem: true,
        theyLikedMe: true,
        isConnected: true,
      } : current);
      return;
    }

    if (conversationStatus.reason === 'unlike') {
      setUser((current) => {
        if (!current) {
          return current;
        }

        return {
          ...current,
          hasLikedThem: (
            conversationStatus.actorId === currentUserId
              ? false
              : current.hasLikedThem
          ),
          theyLikedMe: (
            conversationStatus.actorId === viewedUserId
              ? false
              : current.theyLikedMe
          ),
          isConnected: false,
        };
      });
    }
  }, [conversationStatus, currentUserId, viewedUserId]);

  const handleLikeToggle = async () => {
    if (!user) {
      return;
    }

    setActionError('');
    setLikePending(true);

    try {
      if (user.hasLikedThem) {
        await usersService.unlike(user.id);

        setUser({
          ...user,
          hasLikedThem: false,
          isConnected: false,
        });
      } else {
        const data = await usersService.like(user.id);

        setUser({
          ...user,
          hasLikedThem: true,
          isConnected: data.isConnected,
        });
      }
    } catch (err: any) {
      setActionError(
        err.response?.data?.message
        || 'Something went wrong.'
      );
    } finally {
      setLikePending(false);
    }
  };

  const handleBlock = async () => {
    if (!user) {
      return;
    }

    setActionError('');
    setBlockPending(true);

    try {
      await usersService.block(user.id);
      router.replace('/settings/blocked');
    } catch (err: any) {
      setActionError(
        err.response?.data?.message
        || 'Failed to block this user.'
      );

      setBlockPending(false);
    }
  };

  const handleReport = async () => {
    if (!user) {
      return;
    }

    setActionError('');

    try {
      await usersService.report(user.id);
      setReported(true);
    } catch (err: any) {
      setActionError(
        err.response?.data?.message
        || 'Failed to submit report.'
      );
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#15101C]" />
    );
  }

  if (notFound || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#15101C] px-6">
        <div className="text-center">
          <h2 className="font-serif text-2xl text-[#F5EFE9]">
            Profile not found
          </h2>

          <p className="mt-2 text-sm text-[#9C8FA8]">
            This user doesn&apos;t exist, or isn&apos;t
            available to view.
          </p>

          <Link
            href="/"
            className="mt-6 inline-block text-sm font-medium text-[#F2C879] hover:text-[#F5D998]"
          >
            Return to dashboard
          </Link>
        </div>
      </div>
    );
  }

  const presence = presenceByUser[user.id];
  const isOnline = presence?.isOnline ?? user.isOnline;

  const lastActivity = (
    presence?.lastActivity
    ?? user.lastActivity
  );

  const photos = user.photos?.length
    ? [...user.photos].sort(
        (a, b) => (
          Number(b.isPrimary)
          - Number(a.isPrimary)
          || a.position - b.position
          || a.id - b.id
        )
      )
    : [];

  const currentPhoto = photos[activePhoto];
  const biography = user.biography?.trim() || '';
  const locationName = user.location?.name?.trim() || '';

  const preferences = user.sexualPreferences?.length
    ? user.sexualPreferences
        .map(formatProfileValue)
        .join(', ')
    : '';

  const presenceLabel = isOnline
    ? 'Online now'
    : lastActivity
      ? `Last seen ${formatLastSeen(lastActivity)}`
      : 'Last seen information unavailable';

  return (
    <div className="min-h-screen bg-[#15101C] px-6 py-12">
      <div className="mx-auto max-w-2xl">
        {(user.theyLikedMe || user.isConnected) && (
          <div className="mb-4 rounded-lg border border-[#FF4D7E]/30 bg-[#FF4D7E]/10 px-4 py-2.5 text-sm text-[#FF8FAE]">
            {user.isConnected
              ? 'You’re connected — you can chat.'
              : 'This user liked you.'}
          </div>
        )}

        <div className="overflow-hidden rounded-xl border border-[#332844] bg-[#1E1728]">
          <div className="relative aspect-[4/3] w-full">
            {currentPhoto ? (
              <img
                src={`${API_BASE_URL}${currentPhoto.url}`}
                alt={user.firstName}
                className="h-full w-full object-cover"
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-[#6E6180]">
                No photos yet
              </div>
            )}

            {currentPhoto?.isPrimary && (
              <span className="absolute left-3 top-3 rounded-full bg-[#FF4D7E] px-2.5 py-1 text-xs font-medium text-[#15101C]">
                Primary photo
              </span>
            )}

            {isOnline && (
              <span className="absolute right-3 top-3 rounded-full bg-[#4ADE80]/15 px-2.5 py-1 text-xs font-medium text-[#4ADE80]">
                Online
              </span>
            )}
          </div>

          {photos.length > 1 && (
            <div className="flex gap-1.5 p-2">
              {photos.map((photo, index) => (
                <button
                  key={photo.id}
                  type="button"
                  onClick={() => setActivePhoto(index)}
                  aria-label={
                    photo.isPrimary
                      ? 'View primary photo'
                      : `View photo ${index + 1}`
                  }
                  className={`relative h-14 w-14 shrink-0 overflow-hidden rounded-md border-2 transition ${
                    index === activePhoto
                      ? 'border-[#FF4D7E]'
                      : 'border-transparent opacity-60'
                  }`}
                >
                  <img
                    src={`${API_BASE_URL}${photo.url}`}
                    alt=""
                    className="h-full w-full object-cover"
                  />

                  {photo.isPrimary && (
                    <span className="absolute bottom-0 left-0 right-0 bg-[#FF4D7E] py-0.5 text-[9px] font-medium text-[#15101C]">
                      Primary
                    </span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="mt-5 flex items-start justify-between gap-4">
          <div>
            <h1 className="font-serif text-3xl text-[#F5EFE9]">
              {user.firstName} {user.lastName}
            </h1>

            <p className="mt-1 text-sm text-[#9C8FA8]">
              @{user.username}
            </p>
          </div>

          <div className="shrink-0 text-right">
            <p className="text-xs uppercase tracking-wide text-[#9C8FA8]">
              Fame rating
            </p>

            <p className="font-serif text-2xl text-[#F2C879]">
              {user.fameRating ?? 0}
            </p>
          </div>
        </div>

        <section className="mt-5 rounded-xl border border-[#332844] bg-[#1E1728] p-5">
          <h2 className="font-serif text-xl text-[#F5EFE9]">
            Profile information
          </h2>

          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <ProfileDetail
              label="Age"
              value={
                user.age !== null
                  ? `${user.age} years old`
                  : MISSING_INFORMATION
              }
              missing={user.age === null}
            />

            <ProfileDetail
              label="Gender"
              value={
                user.gender
                  ? formatProfileValue(user.gender)
                  : MISSING_INFORMATION
              }
              missing={!user.gender}
            />

            <ProfileDetail
              label="Interested in"
              value={preferences || MISSING_INFORMATION}
              missing={!preferences}
            />

            <ProfileDetail
              label="Location"
              value={locationName || MISSING_INFORMATION}
              missing={!locationName}
            />

            <ProfileDetail
              label="Presence"
              value={presenceLabel}
            />
          </div>
        </section>

        <section className="mt-4 rounded-xl border border-[#332844] bg-[#1E1728] p-5">
          <h2 className="font-serif text-xl text-[#F5EFE9]">
            Biography
          </h2>

          <p
            className={`mt-3 text-sm leading-relaxed ${
              biography
                ? 'text-[#D8CFE0]'
                : 'italic text-[#766A82]'
            }`}
          >
            {biography || MISSING_INFORMATION}
          </p>
        </section>

        <section className="mt-4 rounded-xl border border-[#332844] bg-[#1E1728] p-5">
          <h2 className="font-serif text-xl text-[#F5EFE9]">
            Interests
          </h2>

          {user.tags.length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {user.tags.map((tag) => (
                <span
                  key={tag}
                  className="rounded-full bg-[#FF4D7E]/15 px-2.5 py-1 text-xs font-medium text-[#FF8FAE]"
                >
                  #{tag}
                </span>
              ))}
            </div>
          ) : (
            <p className="mt-3 text-sm italic text-[#766A82]">
              {MISSING_INFORMATION}
            </p>
          )}
        </section>

        {actionError && (
          <div className="mt-5 rounded-lg border border-[#FF6B6B]/30 bg-[#FF6B6B]/10 px-3 py-2 text-sm text-[#FF8A80]">
            {actionError}
          </div>
        )}

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={handleLikeToggle}
            disabled={likePending}
            className={`rounded-lg px-6 py-2.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${
              user.hasLikedThem
                ? 'border border-[#FF4D7E]/50 text-[#FF4D7E] hover:bg-[#FF4D7E]/10'
                : 'bg-[#FF4D7E] text-[#15101C] hover:bg-[#FF6A93]'
            }`}
          >
            {likePending
              ? '…'
              : user.hasLikedThem
                ? 'Unlike'
                : 'Like'}
          </button>

          {user.isConnected && (
            <>
              <Link
                href={`/messages?with=${encodeURIComponent(user.username)}`}
                className="rounded-lg bg-[#F2C879] px-5 py-2.5 text-sm font-medium text-[#15101C] transition hover:bg-[#F5D998]"
              >
                Message
              </Link>

              <button
                type="button"
                disabled={callBusy}
                onClick={() => {
                  void startAudioCall({
                    id: user.id,
                    username: user.username,
                    firstName: user.firstName,
                    lastName: user.lastName,
                    profilePicture: user.profilePicture,
                  });
                }}
                className="rounded-lg bg-[#4ADE80] px-5 py-2.5 text-sm font-medium text-[#15101C] transition hover:bg-[#6EE99A] disabled:cursor-not-allowed disabled:opacity-50"
              >
                Audio call
              </button>

              <Link
                href={`/dates?with=${encodeURIComponent(user.username)}`}
                className="rounded-lg border border-[#332844] px-4 py-2.5 text-sm text-[#9C8FA8] transition hover:text-[#F5EFE9]"
              >
                Schedule date
              </Link>
            </>
          )}

          {!confirmBlock ? (
            <button
              type="button"
              onClick={() => setConfirmBlock(true)}
              className="rounded-lg border border-[#332844] px-4 py-2.5 text-sm text-[#9C8FA8] transition hover:border-[#FF6B6B]/40 hover:text-[#FF8A80]"
            >
              Block
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-sm text-[#9C8FA8]">
                Block this user?
              </span>

              <button
                type="button"
                onClick={handleBlock}
                disabled={blockPending}
                className="rounded-lg bg-[#FF6B6B] px-3 py-1.5 text-xs font-medium text-[#15101C] disabled:opacity-50"
              >
                {blockPending ? '…' : 'Confirm'}
              </button>

              <button
                type="button"
                onClick={() => setConfirmBlock(false)}
                className="rounded-lg border border-[#332844] px-3 py-1.5 text-xs text-[#9C8FA8]"
              >
                Cancel
              </button>
            </div>
          )}

          <button
            type="button"
            onClick={handleReport}
            disabled={reported}
            className="rounded-lg border border-[#332844] px-4 py-2.5 text-sm text-[#9C8FA8] transition hover:border-[#F2C879]/40 hover:text-[#F2C879] disabled:opacity-50"
          >
            {reported
              ? 'Reported as fake account'
              : 'Report as fake account'}
          </button>
        </div>
      </div>
    </div>
  );
}