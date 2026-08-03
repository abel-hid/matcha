'use client';

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';
import { io, Socket } from 'socket.io-client';

import { useAuth } from '@/app/context/AuthContext';
import { api } from '@/app/services/api';
import type { DateEvent } from '@/app/types';

const API_BASE = (
  process.env.NEXT_PUBLIC_API_URL
  ?? 'http://localhost:5000'
);
const SOCKET_URL = (
  process.env.NEXT_PUBLIC_SOCKET_URL
  ?? API_BASE
);
const FALLBACK_POLL_INTERVAL_MS = 8_000;
const NOTIFICATION_TOAST_DURATION_MS = 4_500;

export interface Notification {
  id: number;
  type: 'like' | 'view' | 'message' | 'match' | 'unlike' | string;
  content: string | null;
  isRead: boolean;
  createdAt: string;
  fromUser: {
    id: number;
    username: string;
    profilePicture: string | null;
  } | null;
}

interface PresenceUpdate {
  userId: number;
  isOnline: boolean;
  lastActivity: string | null;
}

export interface RealtimeMessage {
  id: number;
  senderId: number;
  receiverId: number;
  content: string;
  isRead: boolean;
  createdAt: string;
}

export interface ConversationStatusUpdate {
  userId: number;
  canMessage: boolean;
  reason: 'match' | 'unlike' | 'block' | string;
  actorId: number;
}

export interface MessageReadUpdate {
  readerId: number;
  messageIds: number[];
}

interface NotificationContextValue {
  unreadCount: number;
  notifications: Notification[];
  loading: boolean;
  connected: boolean;
  presenceByUser: Record<number, PresenceUpdate>;
  latestMessage: RealtimeMessage | null;
  latestReadReceipt: MessageReadUpdate | null;
  conversationStatus: ConversationStatusUpdate | null;
  latestDateEvent: DateEvent | null;
  socket: Socket | null;
  refresh: () => Promise<void>;
  markRead: (id: number) => Promise<void>;
  markAllRead: () => Promise<void>;
}

const NotificationContext = (
  createContext<NotificationContextValue | null>(null)
);

export function NotificationProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user } = useAuth();
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);
  const [connected, setConnected] = useState(false);
  const [presenceByUser, setPresenceByUser] = useState<
    Record<number, PresenceUpdate>
  >({});
  const [latestMessage, setLatestMessage] = (
    useState<RealtimeMessage | null>(null)
  );
  const [latestReadReceipt, setLatestReadReceipt] = (
    useState<MessageReadUpdate | null>(null)
  );
  const [conversationStatus, setConversationStatus] = (
    useState<ConversationStatusUpdate | null>(null)
  );
  const [latestDateEvent, setLatestDateEvent] = (
    useState<DateEvent | null>(null)
  );
  const [socket, setSocket] = useState<Socket | null>(null);
  const [toastQueue, setToastQueue] = useState<Notification[]>([]);
  const socketRef = useRef<Socket | null>(null);
  const knownNotificationIdsRef = useRef<Set<number>>(new Set());
  const notificationsInitializedRef = useRef(false);

  const enqueueToast = useCallback((notification: Notification) => {
    setToastQueue((previous) => {
      if (previous.some((item) => item.id === notification.id)) {
        return previous;
      }

      return [...previous, notification];
    });
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);

    try {
      const response = await api.get('/api/notifications');
      const data = response.data;

      const receivedNotifications = (
        data.notifications ?? []
      ) as Notification[];

      const newNotifications = receivedNotifications.filter(
        (notification) => (
          !knownNotificationIdsRef.current.has(notification.id)
        )
      );

      for (const notification of receivedNotifications) {
        knownNotificationIdsRef.current.add(notification.id);
      }

      if (notificationsInitializedRef.current) {
        for (const notification of [...newNotifications].reverse()) {
          if (!notification.isRead) {
            enqueueToast(notification);
          }
        }
      }

      notificationsInitializedRef.current = true;
      setNotifications(receivedNotifications);
      setUnreadCount(data.unreadCount ?? 0);
    } catch {
      // Preserve the last known state during a temporary network failure.
    } finally {
      setLoading(false);
    }
  }, [enqueueToast]);

  const markRead = useCallback(async (id: number) => {
    try {
      const response = await api.put(
        `/api/notifications/${id}/read`
      );

      setNotifications((previous) => previous.map(
        (notification) => (
          notification.id === id
            ? { ...notification, isRead: true }
            : notification
        )
      ));
      setUnreadCount(response.data.unreadCount ?? 0);
    } catch {
      await refresh();
    }
  }, [refresh]);

  const markAllRead = useCallback(async () => {
    try {
      const response = await api.put(
        '/api/notifications/read-all'
      );

      setNotifications((previous) => previous.map(
        (notification) => ({
          ...notification,
          isRead: true,
        })
      ));
      setUnreadCount(response.data.unreadCount ?? 0);
    } catch {
      await refresh();
    }
  }, [refresh]);

  const dismissToast = useCallback((notificationId: number) => {
    setToastQueue((previous) => previous.filter(
      (notification) => notification.id !== notificationId
    ));
  }, []);

  useEffect(() => {
    if (!user?.isProfileComplete) {
      if (socketRef.current) {
        socketRef.current.disconnect();
        socketRef.current = null;
      }

      setConnected(false);
      setNotifications([]);
      setUnreadCount(0);
      setPresenceByUser({});
      setLatestMessage(null);
      setLatestReadReceipt(null);
      setConversationStatus(null);
      setLatestDateEvent(null);
      setSocket(null);
      setToastQueue([]);
      knownNotificationIdsRef.current.clear();
      notificationsInitializedRef.current = false;
      return;
    }

    refresh();

    const socket = io(SOCKET_URL, {
      withCredentials: true,
      transports: ['websocket'],
      autoConnect: true,
      reconnection: true,
      reconnectionAttempts: Infinity,
    });

    socketRef.current = socket;
    setSocket(socket);

    socket.on('connect', () => {
      setConnected(true);
      refresh();
    });
    socket.on('disconnect', () => setConnected(false));
    socket.on('connect_error', () => setConnected(false));

    socket.on('notification', (notification: Notification) => {
      if (knownNotificationIdsRef.current.has(notification.id)) {
        return;
      }

      knownNotificationIdsRef.current.add(notification.id);

      setNotifications((previous) => [notification, ...previous]);

      if (!notification.isRead) {
        setUnreadCount((count) => count + 1);
      }

      enqueueToast(notification);
    });

    socket.on('presence', (presence: PresenceUpdate) => {
      setPresenceByUser((previous) => ({
        ...previous,
        [presence.userId]: presence,
      }));
    });

    socket.on('message', (message: RealtimeMessage) => {
      setLatestMessage(message);
    });

    socket.on('message_read', (receipt: MessageReadUpdate) => {
      setLatestReadReceipt(receipt);
    });

    socket.on('date_event', (event: DateEvent) => {
      setLatestDateEvent(event);
    });

    socket.on(
      'conversation_status',
      (status: ConversationStatusUpdate) => {
        setConversationStatus(status);

        window.setTimeout(() => {
          setConversationStatus((current) => (
            current?.userId === status.userId
            && current.actorId === status.actorId
            && current.reason === status.reason
              ? null
              : current
          ));
        }, 2_000);
      }
    );

    return () => {
      socket.disconnect();
      socketRef.current = null;
      setSocket((current) => current === socket ? null : current);
    };
  }, [enqueueToast, refresh, user]);

  useEffect(() => {
    if (!user?.isProfileComplete || connected) {
      return;
    }

    const interval = window.setInterval(
      refresh,
      FALLBACK_POLL_INTERVAL_MS
    );

    return () => window.clearInterval(interval);
  }, [connected, refresh, user]);

  return (
    <NotificationContext.Provider
      value={{
        unreadCount,
        notifications,
        loading,
        connected,
        presenceByUser,
        latestMessage,
        latestReadReceipt,
        conversationStatus,
        latestDateEvent,
        socket,
        refresh,
        markRead,
        markAllRead,
      }}
    >
      {children}

      {toastQueue.length > 0 && (
        <div
          aria-live="polite"
          className="fixed right-4 top-20 z-50 flex max-h-[calc(100vh-6rem)] w-[calc(100%-2rem)] max-w-sm flex-col gap-3 overflow-y-auto"
        >
          {toastQueue.map((notification) => (
            <NotificationToast
              key={notification.id}
              notification={notification}
              onClose={dismissToast}
            />
          ))}
        </div>
      )}
    </NotificationContext.Provider>
  );
}

function NotificationToast({
  notification,
  onClose,
}: {
  notification: Notification;
  onClose: (notificationId: number) => void;
}) {
  useEffect(() => {
    const timeout = window.setTimeout(() => {
      onClose(notification.id);
    }, NOTIFICATION_TOAST_DURATION_MS);

    return () => window.clearTimeout(timeout);
  }, [notification.id, onClose]);

  return (
    <div
      role="status"
      className="w-full shrink-0 rounded-xl border border-[#FF4D7E]/30 bg-[#1E1728] p-4 shadow-2xl shadow-black/40"
    >
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-full bg-[#332844] text-sm font-semibold text-[#F5EFE9]">
          {notification.fromUser?.profilePicture ? (
            <img
              src={`${API_BASE}${notification.fromUser.profilePicture}`}
              alt=""
              className="h-full w-full object-cover"
            />
          ) : (
            notification.fromUser?.username?.[0]?.toUpperCase() ?? '!'
          )}
        </div>

        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-[#FF8FAE]">
            New notification
          </p>
          <p className="mt-1 text-sm text-[#F5EFE9]">
            {notificationLabel(notification)}
          </p>
        </div>

        <button
          type="button"
          onClick={() => onClose(notification.id)}
          aria-label="Dismiss notification"
          className="shrink-0 text-[#766A82] hover:text-[#F5EFE9]"
        >
          ×
        </button>
      </div>
    </div>
  );
}

export function useNotifications() {
  const context = useContext(NotificationContext);

  if (!context) {
    throw new Error(
      'useNotifications must be used inside NotificationProvider'
    );
  }

  return context;
}

export function NotificationBell() {
  const {
    unreadCount,
    notifications,
    loading,
    connected,
    refresh,
    markRead,
    markAllRead,
  } = useNotifications();
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) {
      refresh();
    }
  }, [open, refresh]);

  useEffect(() => {
    function onClickOutside(event: MouseEvent) {
      if (
        boxRef.current
        && !boxRef.current.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    }

    document.addEventListener('mousedown', onClickOutside);

    return () => {
      document.removeEventListener('mousedown', onClickOutside);
    };
  }, []);

  return (
    <div ref={boxRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-label="Notifications"
        className="relative flex h-9 w-9 items-center justify-center rounded-full text-[#F5EFE9] hover:bg-[#332844]"
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M13.73 21a2 2 0 01-3.46 0"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </svg>

        {unreadCount > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-[#FF4D7E] px-1 text-[10px] font-semibold text-white">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}

        {!connected && (
          <span
            title="Reconnecting…"
            className="absolute -bottom-0.5 -right-0.5 h-2 w-2 rounded-full bg-[#6E6180] ring-2 ring-[#15101C]"
          />
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-30 mt-2 w-80 rounded-lg border border-[#332844] bg-[#1D1726] shadow-lg">
          <div className="flex items-center justify-between border-b border-[#332844] px-4 py-2">
            <span className="text-sm font-medium text-[#F5EFE9]">
              Notifications
            </span>

            {unreadCount > 0 && (
              <button
                type="button"
                onClick={markAllRead}
                className="text-xs text-[#9C8FA8] hover:text-[#F5EFE9]"
              >
                Mark all read
              </button>
            )}
          </div>

          <div className="max-h-96 overflow-y-auto">
            {loading && notifications.length === 0 && (
              <p className="px-4 py-6 text-center text-sm text-[#6E6180]">
                Loading…
              </p>
            )}

            {!loading && notifications.length === 0 && (
              <p className="px-4 py-6 text-center text-sm text-[#6E6180]">
                No notifications yet
              </p>
            )}

            {notifications.map((notification) => (
              <button
                key={notification.id}
                type="button"
                onClick={() => {
                  if (!notification.isRead) {
                    markRead(notification.id);
                  }
                }}
                className={`flex w-full items-start gap-2 border-b border-[#332844] px-4 py-3 text-left text-sm last:border-b-0 ${
                  notification.isRead
                    ? 'text-[#9C8FA8]'
                    : 'bg-[#FF4D7E]/5 text-[#F5EFE9]'
                }`}
              >
                <span
                  className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-[#FF4D7E]"
                  style={{
                    visibility: notification.isRead
                      ? 'hidden'
                      : 'visible',
                  }}
                />

                <span>
                  {notificationLabel(notification)}
                  <span className="mt-0.5 block text-xs text-[#6E6180]">
                    {new Date(
                      notification.createdAt
                    ).toLocaleString()}
                  </span>
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function notificationLabel(notification: Notification) {
  const name = notification.fromUser?.username ?? 'Someone';

  switch (notification.type) {
    case 'like':
      return `${name} liked you`;
    case 'view':
      return `${name} viewed your profile`;
    case 'message':
      return `${name} sent you a message`;
    case 'match':
      return `You and ${name} liked each other`;
    case 'unlike':
      return `${name} unliked you`;
    case 'date':
      return notification.content ?? `${name} updated a date`;
    default:
      return notification.content ?? 'New notification';
  }
}
