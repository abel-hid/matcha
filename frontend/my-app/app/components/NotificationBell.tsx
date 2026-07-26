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
import Cookie from 'js-cookie';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:5000';
const SOCKET_URL = process.env.NEXT_PUBLIC_SOCKET_URL ?? API_BASE;

export interface Notification {
  id: number;
  type: 'like' | 'view' | 'message' | 'match' | 'unlike' | string;
  content: string | null;
  isRead: boolean;
  createdAt: string;
  fromUser: { id: number; username: string; profilePicture: string | null } | null;
}

interface NotificationContextValue {
  unreadCount: number;
  notifications: Notification[];
  loading: boolean;
  connected: boolean;
  refresh: () => Promise<void>;
  markRead: (id: number) => Promise<void>;
  markAllRead: () => Promise<void>;
}

const NotificationContext = createContext<NotificationContextValue | null>(null);

function authToken(): string | null {
  return typeof window !== 'undefined' ? Cookie.get('token') ?? null : null;
}

function authHeaders(): HeadersInit {
  const token = authToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function NotificationProvider({ children }: { children: React.ReactNode }) {
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);
  const [connected, setConnected] = useState(false);
  const socketRef = useRef<Socket | null>(null) ;

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/notifications`, { headers: authHeaders() });
      if (!res.ok) return;
      const data = await res.json();
      setNotifications(data.notifications ?? []);
      setUnreadCount(data.unreadCount ?? 0);
    } finally {
      setLoading(false);
    }
  }, []);

  const markRead = useCallback(async (id: number) => {
    setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, isRead: true } : n)));
    setUnreadCount((prev) => Math.max(0, prev - 1));
    try {
      await fetch(`${API_BASE}/api/notifications/${id}/read`, { method: 'PUT', headers: authHeaders() });
    } catch {
      
    }
  }, []);

  const markAllRead = useCallback(async () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, isRead: true })));
    setUnreadCount(0);
    try {
      await fetch(`${API_BASE}/api/notifications/read-all`, { method: 'PUT', headers: authHeaders() });
    } catch {
      
    }
  }, []);

  useEffect(() => {
    const token = authToken();
    if (!token) return;

    refresh();

    const socket = io(SOCKET_URL, {
      auth: { token },
      transports: ['websocket'],
      autoConnect: true,
      reconnection: true,
      reconnectionAttempts: Infinity,

    });
    socketRef.current = socket;

    socket.on('connect', () => setConnected(true));
    socket.on('disconnect', () => setConnected(false));
    socket.on('connect_error', () => setConnected(false));

    socket.on('notification', (notif: Notification) => {
      setNotifications((prev) => [notif, ...prev]);
      setUnreadCount((prev) => prev + 1);
    });

    return () => {
      socket.disconnect();
      socketRef.current = null;
    };
  }, []);

  return (
    <NotificationContext.Provider
      value={{ unreadCount, notifications, loading, connected, refresh, markRead, markAllRead }}
    >
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotifications() {
  const ctx = useContext(NotificationContext);
  if (!ctx) throw new Error('useNotifications must be used inside NotificationProvider');
  return ctx;
}

export function NotificationBell() {
  const { unreadCount, notifications, loading, connected, refresh, markRead, markAllRead } =
    useNotifications();
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) refresh();
  }, [open, refresh]);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, []);

  return (
    <div ref={boxRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="Notifications"
        className="relative flex h-9 w-9 items-center justify-center rounded-full text-[#F5EFE9] hover:bg-[#332844]"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path d="M13.73 21a2 2 0 01-3.46 0" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
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
            <span className="text-sm font-medium text-[#F5EFE9]">Notifications</span>
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
              <p className="px-4 py-6 text-center text-sm text-[#6E6180]">Loading…</p>
            )}
            {!loading && notifications.length === 0 && (
              <p className="px-4 py-6 text-center text-sm text-[#6E6180]">No notifications yet</p>
            )}
            {notifications.map((n) => (
              <button
                key={n.id}
                type="button"
                onClick={() => !n.isRead && markRead(n.id)}
                className={`flex w-full items-start gap-2 border-b border-[#332844] px-4 py-3 text-left text-sm last:border-b-0 ${
                  n.isRead ? 'text-[#9C8FA8]' : 'bg-[#FF4D7E]/5 text-[#F5EFE9]'
                }`}
              >
                <span
                  className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-[#FF4D7E]"
                  style={{ visibility: n.isRead ? 'hidden' : 'visible' }}
                />
                <span>
                  {notificationLabel(n)}
                  <span className="mt-0.5 block text-xs text-[#6E6180]">
                    {new Date(n.createdAt).toLocaleString()}
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

function notificationLabel(n: Notification) {
  const name = n.fromUser?.username ?? 'Someone';
  switch (n.type) {
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
    default:
      return n.content ?? 'New notification';
  }
}