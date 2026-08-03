'use client';

import React, {
  FormEvent,
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';

import { apiErrorMessage, apiErrorStatus } from '@/app/lib/apiError';
import { useAudioCall } from '@/app/components/AudioCallProvider';
import { useNotifications } from '@/app/components/NotificationBell';
import { useAuth } from '@/app/context/AuthContext';
import { messagesService } from '@/app/services/api';
import type {
  ChatMessage,
  ChatUser,
  ConversationResponse,
  ConversationSummary,
  ConversationsResponse,
} from '@/app/types';

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL
  || 'http://localhost:5000'
);
const CONVERSATION_PAGE_SIZE = 50;
const FALLBACK_POLL_INTERVAL_MS = 8_000;
const MESSAGE_MAX_LENGTH = 1000;

/** Merge live and paginated messages without duplicates and keep chronological order. */
function mergeMessages(current: ChatMessage[], incoming: ChatMessage[]) {
  const messagesById = new Map<number, ChatMessage>();

  for (const message of [...current, ...incoming]) {
    messagesById.set(message.id, message);
  }

  return [...messagesById.values()].sort((left, right) => {
    const timeDifference = (
      new Date(left.createdAt).getTime()
      - new Date(right.createdAt).getTime()
    );

    return timeDifference || left.id - right.id;
  });
}

/** Format a message timestamp for the current browser locale. */
function formatMessageTime(value: string) {
  return new Date(value).toLocaleString([], {
    dateStyle: 'short',
    timeStyle: 'short',
  });
}

/** Describe online or last-seen state for a conversation contact. */
function formatPresence(user: ChatUser) {
  if (user.isOnline) {
    return 'Online';
  }

  if (!user.lastActivity) {
    return 'Offline';
  }

  return `Last seen ${new Date(user.lastActivity).toLocaleString()}`;
}

/** Coordinate conversation loading, live messages, read receipts, and audio calls. */
function MessagesPageContent() {
  const searchParams = useSearchParams();
  const requestedUsername = searchParams.get('with');
  const { user } = useAuth();
  const { startAudioCall, callBusy } = useAudioCall();
  const {
    connected,
    presenceByUser,
    latestMessage,
    latestReadReceipt,
    conversationStatus,
  } = useNotifications();

  const [conversations, setConversations] = useState<
    ConversationSummary[]
  >([]);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [partner, setPartner] = useState<ChatUser | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [canMessage, setCanMessage] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [draft, setDraft] = useState('');
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [loadingConversation, setLoadingConversation] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);
  const shouldScrollToBottomRef = useRef(true);

  const loadConversations = useCallback(async () => {
    try {
      const data = (
        await messagesService.getConversations()
      ) as ConversationsResponse;

      setConversations(data.conversations ?? []);
      setError('');

      setSelectedUserId((current) => {
        if (
          current
          && data.conversations.some(
            (conversation) => conversation.user.id === current
          )
        ) {
          return current;
        }

        if (requestedUsername) {
          const requested = data.conversations.find(
            (conversation) => (
              conversation.user.username === requestedUsername
            )
          );

          if (requested) {
            return requested.user.id;
          }
        }

        return data.conversations[0]?.user.id ?? null;
      });
    } catch (requestError: unknown) {
      setError(
        apiErrorMessage(requestError, 'Conversations could not be loaded.')
      );
    } finally {
      setLoadingConversations(false);
    }
  }, [requestedUsername]);

  const loadConversation = useCallback(async (
    userId: number,
    requestedPage = 1,
    replace = true,
    preservePage = false,
    scrollToBottom = true
  ) => {
    const data = (
      await messagesService.getConversation(
        userId,
        requestedPage,
        CONVERSATION_PAGE_SIZE
      )
    ) as ConversationResponse;

    setPartner(data.partner);
    setCanMessage(Boolean(data.canMessage));
    shouldScrollToBottomRef.current = scrollToBottom;

    if (!preservePage) {
      setPage(data.pagination.page);
    }

    setTotalPages(data.pagination.totalPages);
    setMessages((current) => (
      replace
        ? data.messages
        : mergeMessages(current, data.messages)
    ));

    await messagesService.markConversationRead(userId)
      .catch(() => undefined);

    setConversations((current) => current.map((conversation) => (
      conversation.user.id === userId
        ? { ...conversation, unreadCount: 0 }
        : conversation
    )));
  }, []);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  useEffect(() => {
    if (!selectedUserId) {
      setPartner(null);
      setMessages([]);
      setCanMessage(false);
      return;
    }

    setLoadingConversation(true);
    setError('');

    loadConversation(selectedUserId)
      .catch((requestError: unknown) => {
        setError(
          apiErrorMessage(requestError, 'The conversation could not be loaded.')
        );
        setPartner(null);
        setMessages([]);
        setCanMessage(false);
      })
      .finally(() => setLoadingConversation(false));
  }, [loadConversation, selectedUserId]);

  useEffect(() => {
    if (shouldScrollToBottomRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }

    shouldScrollToBottomRef.current = true;
  }, [messages]);

  useEffect(() => {
    if (!latestMessage || !user) {
      return;
    }

    const otherUserId = (
      latestMessage.senderId === user.id
        ? latestMessage.receiverId
        : latestMessage.senderId
    );

    if (otherUserId === selectedUserId) {
      shouldScrollToBottomRef.current = true;
      setMessages((current) => mergeMessages(
        current,
        [latestMessage]
      ));

      if (latestMessage.receiverId === user.id) {
        messagesService.markConversationRead(otherUserId)
          .catch(() => undefined);
      }
    }

    loadConversations();
  }, [latestMessage, loadConversations, selectedUserId, user]);

  useEffect(() => {
    setConversations((current) => current.map((conversation) => {
      const presence = presenceByUser[conversation.user.id];

      if (!presence) {
        return conversation;
      }

      return {
        ...conversation,
        user: {
          ...conversation.user,
          isOnline: presence.isOnline,
          lastActivity: presence.lastActivity,
        },
      };
    }));

    setPartner((current) => {
      if (!current) {
        return current;
      }

      const presence = presenceByUser[current.id];

      if (!presence) {
        return current;
      }

      return {
        ...current,
        isOnline: presence.isOnline,
        lastActivity: presence.lastActivity,
      };
    });
  }, [presenceByUser]);

  useEffect(() => {
    if (!latestReadReceipt) {
      return;
    }

    const readMessageIds = new Set(latestReadReceipt.messageIds);

    setMessages((current) => current.map((message) => (
      readMessageIds.has(message.id)
        ? { ...message, isRead: true }
        : message
    )));

    setConversations((current) => current.map((conversation) => {
      if (
        conversation.user.id !== latestReadReceipt.readerId
        || !conversation.lastMessage
        || !readMessageIds.has(conversation.lastMessage.id)
      ) {
        return conversation;
      }

      return {
        ...conversation,
        lastMessage: {
          ...conversation.lastMessage,
          isRead: true,
        },
      };
    }));
  }, [latestReadReceipt]);

  useEffect(() => {
    if (
      !conversationStatus
      || conversationStatus.userId !== selectedUserId
    ) {
      return;
    }

    if (conversationStatus.reason === 'block') {
      setConversations((current) => current.filter(
        (conversation) => (
          conversation.user.id !== conversationStatus.userId
        )
      ));
      setSelectedUserId(null);
      setPartner(null);
      setMessages([]);
      setCanMessage(false);
      setError('This conversation is no longer available.');
      return;
    }

    setCanMessage(conversationStatus.canMessage);
    loadConversations();
  }, [conversationStatus, loadConversations, selectedUserId]);

  useEffect(() => {
    if (connected || !selectedUserId) {
      return;
    }

    const interval = window.setInterval(() => {
      loadConversations();
      loadConversation(
        selectedUserId,
        1,
        false,
        true,
        false
      ).catch(() => undefined);
    }, FALLBACK_POLL_INTERVAL_MS);

    return () => window.clearInterval(interval);
  }, [
    connected,
    loadConversation,
    loadConversations,
    selectedUserId,
  ]);

  /** Send a trimmed message and reconcile the optimistic conversation state. */
  const handleSend = async (event: FormEvent) => {
    event.preventDefault();

    if (!selectedUserId || !canMessage || sending) {
      return;
    }

    const content = draft.trim();

    if (!content) {
      setError('Message cannot be empty.');
      return;
    }

    if (content.length > MESSAGE_MAX_LENGTH) {
      setError(
        `Message must be at most ${MESSAGE_MAX_LENGTH} characters long.`
      );
      return;
    }

    setSending(true);
    setError('');

    try {
      const data = await messagesService.sendMessage(
        selectedUserId,
        content
      );

      shouldScrollToBottomRef.current = true;
      setMessages((current) => mergeMessages(
        current,
        [data.message as ChatMessage]
      ));
      setDraft('');
      await loadConversations();
    } catch (requestError: unknown) {
      const status = apiErrorStatus(requestError);

      if (status === 403 || status === 404) {
        setCanMessage(false);
      }

      setError(
        apiErrorMessage(requestError, 'The message could not be sent.')
      );
    } finally {
      setSending(false);
    }
  };

  /** Fetch the previous conversation page without disturbing newer messages. */
  const handleLoadOlder = async () => {
    if (!selectedUserId || loadingOlder || page >= totalPages) {
      return;
    }

    setLoadingOlder(true);
    setError('');

    try {
      await loadConversation(
        selectedUserId,
        page + 1,
        false,
        false,
        false
      );
    } catch (requestError: unknown) {
      setError(
        apiErrorMessage(requestError, 'Older messages could not be loaded.')
      );
    } finally {
      setLoadingOlder(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-73px)] bg-[#15101C] px-4 py-6 sm:px-6">
      <div className="mx-auto grid max-w-5xl overflow-hidden rounded-xl border border-[#332844] bg-[#1E1728] lg:grid-cols-[300px_minmax(0,1fr)]">
        <aside className="border-b border-[#332844] lg:border-b-0 lg:border-r">
          <div className="border-b border-[#332844] px-4 py-4">
            <h1 className="font-serif text-2xl text-[#F5EFE9]">
              Messages
            </h1>
            <p className="mt-1 text-xs text-[#766A82]">
              Only connected users can send messages.
            </p>
          </div>

          <div className="max-h-72 overflow-y-auto lg:max-h-[650px]">
            {loadingConversations && (
              <p className="px-4 py-8 text-center text-sm text-[#766A82]">
                Loading conversations…
              </p>
            )}

            {!loadingConversations && conversations.length === 0 && (
              <div className="px-4 py-8 text-center">
                <p className="text-sm text-[#9C8FA8]">
                  No conversations yet.
                </p>
                <Link
                  href="/"
                  className="mt-3 inline-block text-sm text-[#F2C879] hover:text-[#F5D998]"
                >
                  Discover profiles
                </Link>
              </div>
            )}

            {conversations.map((conversation) => {
              const active = (
                conversation.user.id === selectedUserId
              );

              return (
                <button
                  key={conversation.user.id}
                  type="button"
                  onClick={() => setSelectedUserId(
                    conversation.user.id
                  )}
                  className={`flex w-full items-center gap-3 border-b border-[#332844] px-4 py-3 text-left transition ${
                    active
                      ? 'bg-[#FF4D7E]/10'
                      : 'hover:bg-[#261D31]'
                  }`}
                >
                  <div className="relative h-11 w-11 shrink-0 overflow-hidden rounded-full bg-[#332844]">
                    {conversation.user.profilePicture ? (
                      <img
                        src={`${API_BASE_URL}${conversation.user.profilePicture}`}
                        alt={conversation.user.firstName}
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center text-sm text-[#F5EFE9]">
                        {conversation.user.firstName[0]?.toUpperCase()}
                      </div>
                    )}

                    {conversation.user.isOnline && (
                      <span className="absolute bottom-0 right-0 h-3 w-3 rounded-full border-2 border-[#1E1728] bg-[#4ADE80]" />
                    )}
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <p className="truncate text-sm font-medium text-[#F5EFE9]">
                        {conversation.user.firstName}{' '}
                        {conversation.user.lastName}
                      </p>

                      {conversation.unreadCount > 0 && (
                        <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-[#FF4D7E] px-1 text-[10px] font-semibold text-white">
                          {conversation.unreadCount > 9
                            ? '9+'
                            : conversation.unreadCount}
                        </span>
                      )}
                    </div>

                    <p className="truncate text-xs text-[#766A82]">
                      {conversation.lastMessage?.content
                        || (
                          conversation.canMessage
                            ? 'Start a conversation'
                            : 'Disconnected'
                        )}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
        </aside>

        <section className="flex min-h-[560px] flex-col">
          {!selectedUserId && !loadingConversations && (
            <div className="flex flex-1 items-center justify-center px-6 text-center text-sm text-[#766A82]">
              Select a connected user to start chatting.
            </div>
          )}

          {selectedUserId && loadingConversation && (
            <div className="flex flex-1 items-center justify-center text-sm text-[#766A82]">
              Loading conversation…
            </div>
          )}

          {selectedUserId && !loadingConversation && partner && (
            <>
              <header className="flex items-center justify-between gap-3 border-b border-[#332844] px-4 py-3">
                <div className="min-w-0">
                  <Link
                    href={`/users/${encodeURIComponent(partner.username)}`}
                    className="font-medium text-[#F5EFE9] hover:text-[#FF8FAE]"
                  >
                    {partner.firstName} {partner.lastName}
                  </Link>
                  <p className="text-xs text-[#766A82]">
                    {formatPresence(partner)}
                  </p>
                </div>

                {canMessage && (
                  <div className="flex shrink-0 gap-2">
                    <Link
                      href={`/dates?with=${encodeURIComponent(partner.username)}`}
                      className="rounded-lg border border-[#332844] px-3 py-2 text-xs text-[#9C8FA8] hover:text-[#F5EFE9]"
                    >
                      Schedule date
                    </Link>
                    <button
                      type="button"
                      disabled={callBusy}
                      onClick={() => {
                        void startAudioCall(partner);
                      }}
                      className="rounded-lg bg-[#4ADE80] px-3 py-2 text-xs font-medium text-[#15101C] disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Audio call
                    </button>
                  </div>
                )}
              </header>

              {!canMessage && (
                <div className="border-b border-[#F2C879]/20 bg-[#F2C879]/10 px-4 py-2 text-sm text-[#F2C879]">
                  This conversation is read-only because you are no longer connected.
                </div>
              )}

              <div className="flex-1 overflow-y-auto px-4 py-4">
                {page < totalPages && (
                  <div className="mb-4 text-center">
                    <button
                      type="button"
                      onClick={handleLoadOlder}
                      disabled={loadingOlder}
                      className="rounded-lg border border-[#332844] px-3 py-1.5 text-xs text-[#9C8FA8] hover:text-[#F5EFE9] disabled:opacity-50"
                    >
                      {loadingOlder
                        ? 'Loading…'
                        : 'Load older messages'}
                    </button>
                  </div>
                )}

                {messages.length === 0 && (
                  <p className="py-12 text-center text-sm text-[#766A82]">
                    No messages yet.
                  </p>
                )}

                <div className="space-y-3">
                  {messages.map((message) => {
                    const mine = message.senderId === user?.id;

                    return (
                      <div
                        key={message.id}
                        className={`flex ${
                          mine ? 'justify-end' : 'justify-start'
                        }`}
                      >
                        <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 ${
                          mine
                            ? 'bg-[#FF4D7E] text-[#15101C]'
                            : 'bg-[#332844] text-[#F5EFE9]'
                        }`}>
                          <p className="whitespace-pre-wrap break-words text-sm">
                            {message.content}
                          </p>
                          <p className={`mt-1 text-[10px] ${
                            mine
                              ? 'text-[#15101C]/60'
                              : 'text-[#9C8FA8]'
                          }`}>
                            {formatMessageTime(message.createdAt)}
                            {mine && message.isRead ? ' · Seen' : ''}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>

                <div ref={bottomRef} />
              </div>

              {error && (
                <div className="border-t border-[#FF6B6B]/20 bg-[#FF6B6B]/10 px-4 py-2 text-sm text-[#FF8A80]">
                  {error}
                </div>
              )}

              {canMessage && (
                <form
                  onSubmit={handleSend}
                  className="border-t border-[#332844] p-4"
                >
                  <textarea
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    rows={3}
                    maxLength={MESSAGE_MAX_LENGTH}
                    placeholder="Write a message…"
                    className="w-full resize-none rounded-lg border border-[#332844] bg-[#15101C] px-3 py-2 text-sm text-[#F5EFE9] outline-none placeholder:text-[#6E6180] focus:border-[#FF4D7E]"
                  />

                  <div className="mt-2 flex items-center justify-between gap-3">
                    <span className="text-xs text-[#6E6180]">
                      {draft.length}/{MESSAGE_MAX_LENGTH}
                    </span>
                    <button
                      type="submit"
                      disabled={sending || !draft.trim()}
                      className="rounded-lg bg-[#FF4D7E] px-5 py-2 text-sm font-medium text-[#15101C] transition hover:bg-[#FF6A93] disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {sending ? 'Sending…' : 'Send'}
                    </button>
                  </div>
                </form>
              )}
            </>
          )}

          {selectedUserId && !loadingConversation && !partner && error && (
            <div className="flex flex-1 items-center justify-center px-6 text-center text-sm text-[#FF8A80]">
              {error}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

/** Render this application route and delegate its feature logic to the page component. */
export default function MessagesPage() {
  return (
    <Suspense
      fallback={(
        <div className="min-h-screen bg-[#15101C]" />
      )}
    >
      <MessagesPageContent />
    </Suspense>
  );
}
