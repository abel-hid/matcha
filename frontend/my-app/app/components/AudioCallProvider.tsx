'use client';

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';

import { useNotifications } from '@/app/components/NotificationBell';
import type { CallUser } from '@/app/types';

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL
  || 'http://localhost:5000'
);
const STUN_URL = (
  process.env.NEXT_PUBLIC_WEBRTC_STUN_URL
  || 'stun:stun.l.google.com:19302'
);
const RING_TIMEOUT_MS = 30_000;

interface CallContextValue {
  startAudioCall: (user: CallUser) => Promise<void>;
  callBusy: boolean;
}

type CallPhase = (
  'idle'
  | 'incoming'
  | 'outgoing'
  | 'connecting'
  | 'active'
);

interface IncomingCallPayload {
  callId: string;
  caller: CallUser;
}

interface CallSignalPayload {
  callId: string;
  type: 'offer' | 'answer' | 'ice';
  signal: RTCSessionDescriptionInit | RTCIceCandidateInit | null;
}

const AudioCallContext = createContext<CallContextValue | null>(null);

/** Manage global audio-only WebRTC calls and Socket.IO signaling. */
export function AudioCallProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const { socket, connected } = useNotifications();
  const [phase, setPhase] = useState<CallPhase>('idle');
  const [callId, setCallId] = useState<string | null>(null);
  const [partner, setPartner] = useState<CallUser | null>(null);
  const [muted, setMuted] = useState(false);
  const [notice, setNotice] = useState('');
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  const phaseRef = useRef<CallPhase>('idle');
  const callIdRef = useRef<string | null>(null);
  const directionRef = useRef<'incoming' | 'outgoing' | null>(null);
  const localStreamRef = useRef<MediaStream | null>(null);
  const peerRef = useRef<RTCPeerConnection | null>(null);
  const remoteAudioRef = useRef<HTMLAudioElement>(null);
  const pendingIceRef = useRef<RTCIceCandidateInit[]>([]);
  const ringTimeoutRef = useRef<number | null>(null);
  const noticeTimeoutRef = useRef<number | null>(null);
  const acceptedLocallyRef = useRef(false);
  const startAttemptRef = useRef(0);

  const updatePhase = useCallback((next: CallPhase) => {
    phaseRef.current = next;
    setPhase(next);
  }, []);

  const updateCallId = useCallback((next: string | null) => {
    callIdRef.current = next;
    setCallId(next);
  }, []);

  const updatePartner = useCallback((next: CallUser | null) => {
    setPartner(next);
  }, []);

  const updateDirection = useCallback((next: 'incoming' | 'outgoing' | null) => {
    directionRef.current = next;
  }, []);

  const showNotice = useCallback((message: string) => {
    setNotice(message);

    if (noticeTimeoutRef.current !== null) {
      window.clearTimeout(noticeTimeoutRef.current);
    }

    noticeTimeoutRef.current = window.setTimeout(() => {
      setNotice('');
      noticeTimeoutRef.current = null;
    }, 4_000);
  }, []);

  const clearRingTimeout = useCallback(() => {
    if (ringTimeoutRef.current !== null) {
      window.clearTimeout(ringTimeoutRef.current);
      ringTimeoutRef.current = null;
    }
  }, []);

  const cleanupMedia = useCallback(() => {
    clearRingTimeout();

    pendingIceRef.current = [];

    if (peerRef.current) {
      peerRef.current.onicecandidate = null;
      peerRef.current.ontrack = null;
      peerRef.current.onconnectionstatechange = null;
      peerRef.current.close();
      peerRef.current = null;
    }

    if (localStreamRef.current) {
      for (const track of localStreamRef.current.getTracks()) {
        track.stop();
      }
      localStreamRef.current = null;
    }

    if (remoteAudioRef.current) {
      remoteAudioRef.current.srcObject = null;
    }

    acceptedLocallyRef.current = false;
    setMuted(false);
    setStartedAt(null);
    setElapsedSeconds(0);
  }, [clearRingTimeout]);

  const resetCall = useCallback((message?: string) => {
    startAttemptRef.current += 1;
    cleanupMedia();
    updatePhase('idle');
    updateCallId(null);
    updatePartner(null);
    updateDirection(null);

    if (message) {
      showNotice(message);
    }
  }, [
    cleanupMedia,
    showNotice,
    updateCallId,
    updateDirection,
    updatePartner,
    updatePhase,
  ]);

  const ensureLocalAudio = useCallback(async () => {
    if (localStreamRef.current) {
      return localStreamRef.current;
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error('Audio calls are not supported by this browser');
    }

    const stream = await navigator.mediaDevices.getUserMedia({
      audio: true,
      video: false,
    });

    localStreamRef.current = stream;
    return stream;
  }, []);

  const createPeer = useCallback(async () => {
    if (peerRef.current) {
      return peerRef.current;
    }

    const stream = await ensureLocalAudio();
    const peer = new RTCPeerConnection({
      iceServers: STUN_URL
        ? [{ urls: STUN_URL }]
        : [],
    });

    for (const track of stream.getAudioTracks()) {
      peer.addTrack(track, stream);
    }

    peer.onicecandidate = (event) => {
      const activeCallId = callIdRef.current;
      if (!activeCallId || !event.candidate || !socket) {
        return;
      }

      socket.emit('call_signal', {
        callId: activeCallId,
        type: 'ice',
        signal: event.candidate.toJSON(),
      });
    };

    peer.ontrack = (event) => {
      const [remoteStream] = event.streams;
      if (!remoteAudioRef.current || !remoteStream) {
        return;
      }

      remoteAudioRef.current.srcObject = remoteStream;
      void remoteAudioRef.current.play().catch(() => undefined);
    };

    peer.onconnectionstatechange = () => {
      if (peer.connectionState === 'connected') {
        updatePhase('active');
        setStartedAt(Date.now());
      }

      if (peer.connectionState === 'failed') {
        const activeCallId = callIdRef.current;
        if (activeCallId && socket) {
          socket.emit('call_end', { callId: activeCallId });
        }
        resetCall('The audio connection failed.');
      }
    };

    peerRef.current = peer;
    return peer;
  }, [ensureLocalAudio, resetCall, socket, updatePhase]);

  const startAudioCall = useCallback(async (target: CallUser) => {
    if (!socket?.connected) {
      showNotice('The real-time connection is not ready yet.');
      return;
    }

    if (phaseRef.current !== 'idle') {
      showNotice('Finish the current call first.');
      return;
    }

    const attemptId = startAttemptRef.current + 1;
    startAttemptRef.current = attemptId;

    setNotice('');
    updatePartner(target);
    updateDirection('outgoing');
    updatePhase('outgoing');

    socket.emit(
      'call_start',
      { recipientId: target.id },
      (response: {
        ok: boolean;
        callId?: string;
        message?: string;
      }) => {
        if (
          attemptId !== startAttemptRef.current
          || phaseRef.current !== 'outgoing'
        ) {
          if (response?.ok && response.callId) {
            socket.emit('call_end', { callId: response.callId });
          }
          return;
        }

        if (!response?.ok || !response.callId) {
          resetCall(response?.message || 'The audio call could not be started.');
          return;
        }

        updateCallId(response.callId);
        ringTimeoutRef.current = window.setTimeout(() => {
          socket.emit('call_end', { callId: response.callId });
          resetCall('No answer.');
        }, RING_TIMEOUT_MS);
      }
    );
  }, [
    resetCall,
    showNotice,
    socket,
    updateCallId,
    updateDirection,
    updatePartner,
    updatePhase,
  ]);

  const acceptIncoming = useCallback(async () => {
    const activeCallId = callIdRef.current;
    if (!socket || !activeCallId || phaseRef.current !== 'incoming') {
      return;
    }

    try {
      await createPeer();
    } catch {
      socket.emit('call_decline', { callId: activeCallId });
      resetCall('Microphone permission is required for audio calls.');
      return;
    }

    acceptedLocallyRef.current = true;
    updatePhase('connecting');
    socket.emit(
      'call_accept',
      { callId: activeCallId },
      (response: { ok: boolean; message?: string }) => {
        if (!response?.ok) {
          resetCall(response?.message || 'The call is no longer available.');
        }
      }
    );
  }, [createPeer, resetCall, socket, updatePhase]);

  const declineIncoming = useCallback(() => {
    const activeCallId = callIdRef.current;
    if (socket && activeCallId) {
      socket.emit('call_decline', { callId: activeCallId });
    }
    resetCall();
  }, [resetCall, socket]);

  const endCall = useCallback(() => {
    const activeCallId = callIdRef.current;
    if (socket && activeCallId) {
      socket.emit('call_end', { callId: activeCallId });
    }
    resetCall();
  }, [resetCall, socket]);

  const toggleMute = useCallback(() => {
    const stream = localStreamRef.current;
    if (!stream) {
      return;
    }

    setMuted((current) => {
      const next = !current;
      for (const track of stream.getAudioTracks()) {
        track.enabled = !next;
      }
      return next;
    });
  }, []);

  useEffect(() => {
    if (!connected && phaseRef.current !== 'idle') {
      resetCall('The real-time connection was interrupted.');
    }
  }, [connected, resetCall]);

  useEffect(() => {
    if (!startedAt || phase !== 'active') {
      return;
    }

    /** Update the displayed call duration from the established connection time. */

    const updateElapsed = () => {
      setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000));
    };

    updateElapsed();
    const interval = window.setInterval(updateElapsed, 1_000);
    return () => window.clearInterval(interval);
  }, [phase, startedAt]);

  useEffect(() => {
    if (!socket) {
      if (phaseRef.current !== 'idle') {
        resetCall('The real-time connection was interrupted.');
      }
      return;
    }

    /** Validate an incoming invitation and expose it through the global call overlay. */

    const onIncoming = (payload: IncomingCallPayload) => {
      if (phaseRef.current !== 'idle') {
        socket.emit('call_decline', { callId: payload.callId });
        return;
      }

      updateCallId(payload.callId);
      updatePartner(payload.caller);
      updateDirection('incoming');
      updatePhase('incoming');
    };

    /** Continue caller-side WebRTC negotiation after the recipient accepts. */

    const onAccepted = async (payload: { callId: string }) => {
      if (payload.callId !== callIdRef.current) {
        return;
      }

      if (directionRef.current === 'incoming') {
        if (!acceptedLocallyRef.current) {
          resetCall('The call was answered in another tab.');
        }
        return;
      }

      if (directionRef.current !== 'outgoing') {
        return;
      }

      clearRingTimeout();
      updatePhase('connecting');

      try {
        const peer = await createPeer();
        const offer = await peer.createOffer();
        await peer.setLocalDescription(offer);
        socket.emit('call_signal', {
          callId: payload.callId,
          type: 'offer',
          signal: offer,
        });
      } catch {
        socket.emit('call_end', { callId: payload.callId });
        resetCall('Microphone permission is required for audio calls.');
      }
    };

    /** Close the outgoing-call state when the recipient declines or is busy. */

    const onDeclined = (payload: { callId: string }) => {
      if (payload.callId === callIdRef.current) {
        resetCall('The audio call was declined.');
      }
    };

    /** Release audio resources when the backend reports that a call has ended. */

    const onEnded = (payload: { callId: string; reason?: string }) => {
      if (payload.callId !== callIdRef.current) {
        return;
      }

      const messages: Record<string, string> = {
        block: 'The call ended because one user was blocked.',
        unlike: 'The call ended because the connection was removed.',
        disconnected: 'The other user disconnected.',
        connection_lost: 'The connection is no longer active.',
      };
      resetCall(messages[payload.reason || ''] || undefined);
    };

    /** Forward validated SDP or ICE signaling data to the active peer connection. */

    const onSignal = async (payload: CallSignalPayload) => {
      if (
        payload.callId !== callIdRef.current
        || !payload.signal
      ) {
        return;
      }

      try {
        const peer = await createPeer();

        if (payload.type === 'offer') {
          await peer.setRemoteDescription(
            payload.signal as RTCSessionDescriptionInit
          );

          for (const candidate of pendingIceRef.current) {
            await peer.addIceCandidate(candidate);
          }
          pendingIceRef.current = [];

          const answer = await peer.createAnswer();
          await peer.setLocalDescription(answer);
          socket.emit('call_signal', {
            callId: payload.callId,
            type: 'answer',
            signal: answer,
          });
          return;
        }

        if (payload.type === 'answer') {
          await peer.setRemoteDescription(
            payload.signal as RTCSessionDescriptionInit
          );

          for (const candidate of pendingIceRef.current) {
            await peer.addIceCandidate(candidate);
          }
          pendingIceRef.current = [];
          return;
        }

        const candidate = payload.signal as RTCIceCandidateInit;
        if (peer.remoteDescription) {
          await peer.addIceCandidate(candidate);
        } else {
          pendingIceRef.current.push(candidate);
        }
      } catch {
        socket.emit('call_end', { callId: payload.callId });
        resetCall('The audio call could not be connected.');
      }
    };

    socket.on('call_incoming', onIncoming);
    socket.on('call_accepted', onAccepted);
    socket.on('call_declined', onDeclined);
    socket.on('call_ended', onEnded);
    socket.on('call_signal', onSignal);

    return () => {
      socket.off('call_incoming', onIncoming);
      socket.off('call_accepted', onAccepted);
      socket.off('call_declined', onDeclined);
      socket.off('call_ended', onEnded);
      socket.off('call_signal', onSignal);
    };
  }, [
    clearRingTimeout,
    createPeer,
    resetCall,
    socket,
    updateCallId,
    updateDirection,
    updatePartner,
    updatePhase,
  ]);

  useEffect(() => () => {
    cleanupMedia();
    if (noticeTimeoutRef.current !== null) {
      window.clearTimeout(noticeTimeoutRef.current);
    }
  }, [cleanupMedia]);

  return (
    <AudioCallContext.Provider value={{
      startAudioCall,
      callBusy: phase !== 'idle',
    }}>
      {children}

      <audio ref={remoteAudioRef} autoPlay playsInline />

      {notice && (
        <div className="fixed bottom-5 left-1/2 z-[70] -translate-x-1/2 rounded-lg border border-[#332844] bg-[#1E1728] px-4 py-2 text-sm text-[#F5EFE9] shadow-xl">
          {notice}
        </div>
      )}

      {phase === 'incoming' && partner && (
        <div className="fixed inset-0 z-[65] flex items-center justify-center bg-black/60 px-4 backdrop-blur-sm">
          <div className="w-full max-w-sm rounded-2xl border border-[#332844] bg-[#1E1728] p-6 text-center shadow-2xl">
            <CallAvatar user={partner} />
            <p className="mt-4 text-xs uppercase tracking-wide text-[#9C8FA8]">
              Incoming audio call
            </p>
            <h2 className="mt-1 font-serif text-2xl text-[#F5EFE9]">
              {partner.firstName} {partner.lastName}
            </h2>
            <div className="mt-6 flex justify-center gap-3">
              <button
                type="button"
                onClick={declineIncoming}
                className="rounded-full bg-[#FF6B6B] px-5 py-2.5 text-sm font-medium text-[#15101C]"
              >
                Decline
              </button>
              <button
                type="button"
                onClick={acceptIncoming}
                className="rounded-full bg-[#4ADE80] px-5 py-2.5 text-sm font-medium text-[#15101C]"
              >
                Accept
              </button>
            </div>
          </div>
        </div>
      )}

      {phase !== 'idle' && phase !== 'incoming' && partner && (
        <div className="fixed bottom-5 left-1/2 z-[65] w-[calc(100%-2rem)] max-w-sm -translate-x-1/2 rounded-2xl border border-[#332844] bg-[#1E1728] p-4 shadow-2xl">
          <div className="flex items-center gap-3">
            <CallAvatar user={partner} compact />
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium text-[#F5EFE9]">
                {partner.firstName} {partner.lastName}
              </p>
              <p className="text-xs text-[#9C8FA8]">
                {phase === 'outgoing' && 'Calling…'}
                {phase === 'connecting' && 'Connecting audio…'}
                {phase === 'active' && formatDuration(elapsedSeconds)}
              </p>
            </div>

            {phase === 'active' && (
              <button
                type="button"
                onClick={toggleMute}
                className="rounded-full border border-[#332844] px-3 py-2 text-xs text-[#F5EFE9] hover:bg-[#332844]"
              >
                {muted ? 'Unmute' : 'Mute'}
              </button>
            )}

            <button
              type="button"
              onClick={endCall}
              className="rounded-full bg-[#FF6B6B] px-4 py-2 text-xs font-medium text-[#15101C]"
            >
              End
            </button>
          </div>
        </div>
      )}
    </AudioCallContext.Provider>
  );
}

/** Render a safe fallback avatar for the other call participant. */
function CallAvatar({
  user,
  compact = false,
}: {
  user: CallUser;
  compact?: boolean;
}) {
  const size = compact ? 'h-11 w-11' : 'mx-auto h-20 w-20';

  return (
    <div className={`${size} shrink-0 overflow-hidden rounded-full bg-[#332844]`}>
      {user.profilePicture ? (
        <img
          src={`${API_BASE_URL}${user.profilePicture}`}
          alt=""
          className="h-full w-full object-cover"
        />
      ) : (
        <div className="flex h-full items-center justify-center text-lg font-medium text-[#F5EFE9]">
          {user.firstName[0]?.toUpperCase() || '?'}
        </div>
      )}
    </div>
  );
}

/** Format elapsed call seconds as minutes and seconds. */
function formatDuration(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

/** Expose the audio-call controller to protected pages. */
export function useAudioCall() {
  const context = useContext(AudioCallContext);
  if (!context) {
    throw new Error('useAudioCall must be used inside AudioCallProvider');
  }
  return context;
}
