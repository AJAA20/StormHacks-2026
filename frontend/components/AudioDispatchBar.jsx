"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import styles from "./AudioDispatchBar.module.css";

/**
 * AudioDispatchBar
 *
 * Hands-free emergency dispatch audio bar. Fetches ElevenLabs-generated (or
 * fallback) MP3 audio from POST /api/audio-alert and plays it, with a live
 * transcript banner and waveform-style pulsation while broadcasting.
 *
 * Zero-crash guarantee: if the backend request fails entirely (network down,
 * 503 from the API), falls back to window.speechSynthesis so the demo never
 * goes silent.
 */

const STATES = {
  IDLE: "idle",
  GENERATING: "generating",
  BROADCASTING: "broadcasting",
  ERROR: "error",
};

export default function AudioDispatchBar({
  apiBase = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000",
  routeSummary, // { primary_blocked_road, safe_detour_road, flooded_edges_count, detour_added_km, eta_minutes }
  autoBroadcast = false, // "Hands-Free Auto-Broadcast" toggle
}) {
  const [state, setState] = useState(STATES.IDLE);
  const [transcript, setTranscript] = useState("");
  const [muted, setMuted] = useState(false);
  const audioRef = useRef(null);
  const objectUrlRef = useRef(null);

  const cleanupObjectUrl = useCallback(() => {
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
  }, []);

  const speakFallback = useCallback((text) => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  }, []);

  const dispatchBroadcast = useCallback(async () => {
    if (!routeSummary) return;
    setState(STATES.GENERATING);

    try {
      const res = await fetch(`${apiBase}/api/audio-alert`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(routeSummary),
      });

      const scriptHeader = res.headers.get("X-Dispatch-Script") || "";
      setTranscript(scriptHeader);

      if (!res.ok) throw new Error(`audio-alert failed: ${res.status}`);

      const blob = await res.blob();
      cleanupObjectUrl();
      const url = URL.createObjectURL(blob);
      objectUrlRef.current = url;

      if (audioRef.current) {
        audioRef.current.src = url;
        audioRef.current.muted = muted;
        await audioRef.current.play();
      }
      setState(STATES.BROADCASTING);
    } catch (err) {
      console.warn("ElevenLabs audio alert unavailable, falling back to speechSynthesis:", err);
      const fallbackText =
        transcript ||
        `Primary route via ${routeSummary.primary_blocked_road ?? "the primary route"} is blocked. ` +
          `Rerouting via ${routeSummary.safe_detour_road ?? "an alternate route"}.`;
      setTranscript(fallbackText);
      speakFallback(fallbackText);
      setState(STATES.BROADCASTING);
    }
  }, [apiBase, routeSummary, muted, cleanupObjectUrl, speakFallback, transcript]);

  const handlePause = () => audioRef.current?.pause();
  const handlePlay = () => audioRef.current?.play().catch(() => {});
  const handleReplay = () => {
    if (audioRef.current) {
      audioRef.current.currentTime = 0;
      audioRef.current.play().catch(() => {});
    }
  };
  const handleMuteToggle = () => {
    setMuted((m) => {
      const next = !m;
      if (audioRef.current) audioRef.current.muted = next;
      return next;
    });
  };

  const handleAudioEnded = () => setState(STATES.IDLE);

  // Auto-trigger on new route calculation if hands-free toggle is active.
  useEffect(() => {
    if (autoBroadcast && routeSummary) {
      dispatchBroadcast();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeSummary, autoBroadcast]);

  useEffect(() => cleanupObjectUrl, [cleanupObjectUrl]);

  const stateLabel = {
    [STATES.IDLE]: "Idle",
    [STATES.GENERATING]: "Generating Audio...",
    [STATES.BROADCASTING]: "🟢 Broadcasting Live",
    [STATES.ERROR]: "Audio Unavailable",
  }[state];

  return (
    <div className={styles.bar} data-state={state}>
      <button
        className={styles.dispatchButton}
        onClick={dispatchBroadcast}
        disabled={state === STATES.GENERATING || !routeSummary}
      >
        🔊 Dispatch Emergency Broadcast
      </button>

      <div className={styles.stateIndicator}>
        <span className={styles.stateDot} data-active={state === STATES.BROADCASTING} />
        {stateLabel}
      </div>

      <div className={styles.controls}>
        <button onClick={handlePlay} title="Play" aria-label="Play">▶</button>
        <button onClick={handlePause} title="Pause" aria-label="Pause">⏸</button>
        <button onClick={handleReplay} title="Replay" aria-label="Replay">⟲</button>
        <button onClick={handleMuteToggle} title="Mute" aria-label="Mute" data-active={muted}>
          {muted ? "🔇" : "🔈"}
        </button>
      </div>

      {state === STATES.BROADCASTING && (
        <div className={styles.waveform} aria-hidden="true">
          {Array.from({ length: 12 }).map((_, i) => (
            <span key={i} className={styles.waveBar} style={{ animationDelay: `${i * 0.05}s` }} />
          ))}
        </div>
      )}

      {transcript && (
        <div className={styles.transcript} role="status" aria-live="polite">
          {transcript}
        </div>
      )}

      <audio ref={audioRef} onEnded={handleAudioEnded} hidden />
    </div>
  );
}
