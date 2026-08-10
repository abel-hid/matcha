'use client';

import React, {
  FormEvent,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';

import { apiErrorMessage } from '@/app/lib/apiError';
import { useNotifications } from '@/app/components/NotificationBell';
import { useAuth } from '@/app/context/AuthContext';
import {
  datesService,
  messagesService,
} from '@/app/services/api';
import type {
  ConversationSummary,
  ConversationsResponse,
  DateEvent,
} from '@/app/types';

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL
  || 'http://localhost:5000'
);


function DatesPageContent() {
  const params = useSearchParams();
  const requestedUsername = params.get('with');
  const { user } = useAuth();
  const {
    latestDateEvent,
    conversationStatus,
  } = useNotifications();

  const [connections, setConnections] = useState<ConversationSummary[]>([]);
  const [events, setEvents] = useState<DateEvent[]>([]);
  const [selectedUserId, setSelectedUserId] = useState('');
  const [scheduledFor, setScheduledFor] = useState('');
  const [location, setLocation] = useState('');
  const [note, setNote] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [pendingEventId, setPendingEventId] = useState<number | null>(null);
  const [error, setError] = useState('');

  const replaceEvent = useCallback((updated: DateEvent) => {
    setEvents((current) => {
      const exists = current.some((event) => event.id === updated.id);
      const next = exists
        ? current.map((event) => event.id === updated.id ? updated : event)
        : [...current, updated];

      return next.sort((a, b) => (
        new Date(a.scheduledFor).getTime()
        - new Date(b.scheduledFor).getTime()
      ));
    });
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');

    try {
      const [dateData, conversationData] = await Promise.all([
        datesService.getEvents(),
        messagesService.getConversations(),
      ]);

      const availableConnections = (
        conversationData as ConversationsResponse
      ).conversations.filter((conversation) => conversation.canMessage);

      setConnections(availableConnections);
      setEvents((dateData.events ?? []) as DateEvent[]);
      setSelectedUserId((current) => {
        if (
          current
          && availableConnections.some(
            (conversation) => String(conversation.user.id) === current
          )
        ) {
          return current;
        }

        const requested = availableConnections.find(
          (conversation) => conversation.user.username === requestedUsername
        );
        return String(requested?.user.id ?? availableConnections[0]?.user.id ?? '');
      });
    } catch (requestError: unknown) {
      setError(
        apiErrorMessage(requestError, 'Date proposals could not be loaded.')
      );
    } finally {
      setLoading(false);
    }
  }, [requestedUsername]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (latestDateEvent) {
      replaceEvent(latestDateEvent);
    }
  }, [latestDateEvent, replaceEvent]);

  useEffect(() => {
    if (conversationStatus) {
      void load();
    }
  }, [conversationStatus, load]);

  const connectedUserIds = useMemo(() => new Set(
    connections.map((connection) => connection.user.id)
  ), [connections]);

  const upcoming = useMemo(() => events.filter((event) => {
    const otherUserId = event.proposer.id === user?.id
      ? event.recipient.id
      : event.proposer.id;

    return (
      connectedUserIds.has(otherUserId)
      && new Date(event.scheduledFor).getTime() > Date.now()
      && ['pending', 'accepted'].includes(event.status)
    );
  }), [connectedUserIds, events, user?.id]);

  const history = useMemo(() => events.filter((event) => (
    !upcoming.some((upcomingEvent) => upcomingEvent.id === event.id)
  )).reverse(), [events, upcoming]);

  
  const submit = async (event: FormEvent) => {
    event.preventDefault();

    const targetUserId = Number(selectedUserId);
    if (!targetUserId || !scheduledFor || !location.trim()) {
      setError('Choose a connection, date, time, and location.');
      return;
    }

    const selectedDate = new Date(scheduledFor);
    if (Number.isNaN(selectedDate.getTime())) {
      setError('Choose a valid date and time.');
      return;
    }

    setSaving(true);
    setError('');

    try {
      const data = await datesService.createEvent(targetUserId, {
        scheduledFor: selectedDate.toISOString(),
        location: location.trim(),
        note: note.trim() || undefined,
      });

      replaceEvent(data.event as DateEvent);
      setScheduledFor('');
      setLocation('');
      setNote('');
    } catch (requestError: unknown) {
      setError(
        apiErrorMessage(requestError, 'The date proposal could not be created.')
      );
    } finally {
      setSaving(false);
    }
  };

  
  const respond = async (eventId: number, status: 'accepted' | 'declined') => {
    setPendingEventId(eventId);
    setError('');

    try {
      const data = await datesService.respond(eventId, status);
      replaceEvent(data.event as DateEvent);
    } catch (requestError: unknown) {
      setError(
        apiErrorMessage(requestError, 'The proposal could not be updated.')
      );
    } finally {
      setPendingEventId(null);
    }
  };

  
  const cancel = async (eventId: number) => {
    setPendingEventId(eventId);
    setError('');

    try {
      const data = await datesService.cancel(eventId);
      replaceEvent(data.event as DateEvent);
    } catch (requestError: unknown) {
      setError(
        apiErrorMessage(requestError, 'The date could not be cancelled.')
      );
    } finally {
      setPendingEventId(null);
    }
  };

  if (loading) {
    return <div className="min-h-screen bg-[#15101C]" />;
  }

  return (
    <div className="min-h-screen bg-[#15101C] px-4 py-8 sm:px-6">
      <div className="mx-auto max-w-5xl">
        <div>
          <h1 className="font-serif text-3xl text-[#F5EFE9]">
            Dates
          </h1>
          <p className="mt-2 text-sm text-[#9C8FA8]">
            Propose a real-life date to a connected user and keep the response in one place.
          </p>
        </div>

        {error && (
          <div className="mt-5 rounded-lg border border-[#FF6B6B]/30 bg-[#FF6B6B]/10 px-4 py-3 text-sm text-[#FF8A80]">
            {error}
          </div>
        )}

        <div className="mt-6 grid gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
          <form
            onSubmit={submit}
            className="h-fit rounded-xl border border-[#332844] bg-[#1E1728] p-5"
          >
            <h2 className="font-serif text-xl text-[#F5EFE9]">
              Propose a date
            </h2>

            {connections.length === 0 ? (
              <p className="mt-4 text-sm text-[#9C8FA8]">
                You need a match before scheduling a date.
              </p>
            ) : (
              <>
                <label className="mt-4 block">
                  <span className="text-xs uppercase tracking-wide text-[#9C8FA8]">
                    Connected user
                  </span>
                  <select
                    value={selectedUserId}
                    onChange={(event) => setSelectedUserId(event.target.value)}
                    className="mt-1.5 w-full rounded-lg border border-[#332844] bg-[#15101C] px-3 py-2 text-sm text-[#F5EFE9] outline-none focus:border-[#FF4D7E]"
                  >
                    {connections.map((connection) => (
                      <option key={connection.user.id} value={connection.user.id}>
                        {connection.user.firstName} {connection.user.lastName}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="mt-4 block">
                  <span className="text-xs uppercase tracking-wide text-[#9C8FA8]">
                    Date and time
                  </span>
                  <input
                    type="datetime-local"
                    value={scheduledFor}
                    min={minimumLocalDateTime()}
                    onChange={(event) => setScheduledFor(event.target.value)}
                    required
                    className="mt-1.5 w-full rounded-lg border border-[#332844] bg-[#15101C] px-3 py-2 text-sm text-[#F5EFE9] outline-none focus:border-[#FF4D7E]"
                  />
                </label>

                <label className="mt-4 block">
                  <span className="text-xs uppercase tracking-wide text-[#9C8FA8]">
                    Location
                  </span>
                  <input
                    type="text"
                    value={location}
                    onChange={(event) => setLocation(event.target.value)}
                    maxLength={150}
                    required
                    placeholder="Café, park, or address"
                    className="mt-1.5 w-full rounded-lg border border-[#332844] bg-[#15101C] px-3 py-2 text-sm text-[#F5EFE9] outline-none placeholder:text-[#6E6180] focus:border-[#FF4D7E]"
                  />
                </label>

                <label className="mt-4 block">
                  <span className="text-xs uppercase tracking-wide text-[#9C8FA8]">
                    Note
                  </span>
                  <textarea
                    value={note}
                    onChange={(event) => setNote(event.target.value)}
                    maxLength={500}
                    rows={4}
                    placeholder="Optional details"
                    className="mt-1.5 w-full resize-none rounded-lg border border-[#332844] bg-[#15101C] px-3 py-2 text-sm text-[#F5EFE9] outline-none placeholder:text-[#6E6180] focus:border-[#FF4D7E]"
                  />
                </label>

                <button
                  type="submit"
                  disabled={saving}
                  className="mt-5 w-full rounded-lg bg-[#FF4D7E] px-4 py-2.5 text-sm font-medium text-[#15101C] hover:bg-[#FF6A93] disabled:opacity-50"
                >
                  {saving ? 'Sending…' : 'Send proposal'}
                </button>
              </>
            )}
          </form>

          <div className="space-y-6">
            <DateSection
              title="Upcoming"
              empty="No upcoming dates."
              events={upcoming}
              currentUserId={user?.id ?? 0}
              pendingEventId={pendingEventId}
              onRespond={respond}
              onCancel={cancel}
            />

            <DateSection
              title="History"
              empty="No previous date proposals."
              events={history}
              currentUserId={user?.id ?? 0}
              pendingEventId={pendingEventId}
              onRespond={respond}
              onCancel={cancel}
              history
            />
          </div>
        </div>
      </div>
    </div>
  );
}


function DateSection({
  title,
  empty,
  events,
  currentUserId,
  pendingEventId,
  onRespond,
  onCancel,
  history = false,
}: {
  title: string;
  empty: string;
  events: DateEvent[];
  currentUserId: number;
  pendingEventId: number | null;
  onRespond: (eventId: number, status: 'accepted' | 'declined') => void;
  onCancel: (eventId: number) => void;
  history?: boolean;
}) {
  return (
    <section className="rounded-xl border border-[#332844] bg-[#1E1728] p-5">
      <h2 className="font-serif text-xl text-[#F5EFE9]">
        {title}
      </h2>

      {events.length === 0 ? (
        <p className="mt-4 text-sm text-[#766A82]">
          {empty}
        </p>
      ) : (
        <div className="mt-4 space-y-3">
          {events.map((event) => {
            const incoming = event.recipient.id === currentUserId;
            const other = incoming ? event.proposer : event.recipient;
            const pending = pendingEventId === event.id;

            return (
              <article
                key={event.id}
                className="rounded-xl border border-[#332844] bg-[#17111F] p-4"
              >
                <div className="flex items-start gap-3">
                  <div className="h-11 w-11 shrink-0 overflow-hidden rounded-full bg-[#332844]">
                    {other.profilePicture ? (
                      <img
                        src={`${API_BASE_URL}${other.profilePicture}`}
                        alt=""
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <div className="flex h-full items-center justify-center text-sm text-[#F5EFE9]">
                        {other.firstName[0]?.toUpperCase()}
                      </div>
                    )}
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <Link
                        href={`/users/${encodeURIComponent(other.username)}`}
                        className="font-medium text-[#F5EFE9] hover:text-[#FF8FAE]"
                      >
                        {other.firstName} {other.lastName}
                      </Link>
                      <StatusBadge status={event.status} />
                    </div>

                    <p className="mt-1 text-sm text-[#D8CFE0]">
                      {formatDateTime(event.scheduledFor)}
                    </p>
                    <p className="mt-1 text-sm text-[#9C8FA8]">
                      {event.location}
                    </p>
                    {event.note && (
                      <p className="mt-2 whitespace-pre-wrap text-sm text-[#9C8FA8]">
                        {event.note}
                      </p>
                    )}
                    <p className="mt-2 text-xs text-[#6E6180]">
                      {incoming ? 'Proposed to you' : 'Proposed by you'}
                    </p>
                  </div>
                </div>

                {!history && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {incoming && event.status === 'pending' && (
                      <>
                        <button
                          type="button"
                          disabled={pending}
                          onClick={() => onRespond(event.id, 'accepted')}
                          className="rounded-lg bg-[#4ADE80] px-4 py-2 text-xs font-medium text-[#15101C] disabled:opacity-50"
                        >
                          Accept
                        </button>
                        <button
                          type="button"
                          disabled={pending}
                          onClick={() => onRespond(event.id, 'declined')}
                          className="rounded-lg border border-[#FF6B6B]/40 px-4 py-2 text-xs text-[#FF8A80] disabled:opacity-50"
                        >
                          Decline
                        </button>
                      </>
                    )}

                    {['pending', 'accepted'].includes(event.status) && (
                      <button
                        type="button"
                        disabled={pending}
                        onClick={() => onCancel(event.id)}
                        className="rounded-lg border border-[#332844] px-4 py-2 text-xs text-[#9C8FA8] hover:text-[#F5EFE9] disabled:opacity-50"
                      >
                        Cancel
                      </button>
                    )}
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}


function StatusBadge({ status }: { status: DateEvent['status'] }) {
  const classes: Record<DateEvent['status'], string> = {
    pending: 'bg-[#F2C879]/10 text-[#F2C879]',
    accepted: 'bg-[#4ADE80]/10 text-[#4ADE80]',
    declined: 'bg-[#FF6B6B]/10 text-[#FF8A80]',
    cancelled: 'bg-[#332844] text-[#9C8FA8]',
  };

  return (
    <span className={`rounded-full px-2.5 py-1 text-xs ${classes[status]}`}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}


function formatDateTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}


function minimumLocalDateTime() {
  const date = new Date(Date.now() + 60_000);
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}


export default function DatesPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#15101C]" />}>
      <DatesPageContent />
    </Suspense>
  );
}
