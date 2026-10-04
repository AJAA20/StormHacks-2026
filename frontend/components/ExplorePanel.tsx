"use client";

import { useEffect, useState } from "react";
import LocationSelector from "./LocationSelector";
import { getAnalysisJob, startFloodAnalysis, type ExplorationMode, type Job, type Region } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { shortName, type SelectedLocation } from "@/lib/location";
import styles from "./Controls.module.css";

const MODES: { value: ExplorationMode; label: string; description: string }[] = [
  {
    value: "latest",
    label: "Latest available",
    description: "View flooding from the most recent available satellite observation for a location.",
  },
  {
    value: "historical",
    label: "Historical",
    description: "Explore past flood conditions and how routes would have been affected.",
  },
];

const POLL_MS = 1500;
const today = new Date().toISOString().slice(0, 10);

type Props = {
  mode: ExplorationMode;
  onModeChange: (mode: ExplorationMode) => void;
  location: SelectedLocation | null;
  onLocationChange: (location: SelectedLocation) => void;
  requestedDate: string;
  onDateChange: (date: string) => void;
  // Called with the finished job (its details say which observation was used).
  onDone: (job: Job, mode: ExplorationMode, location: SelectedLocation, requestedDate: string | null) => void;
  // Committed example flood events, shown instantly without a new analysis.
  examples: Region[];
  onExample: (region: Region) => void;
  // False in mock mode (no backend to analyse with).
  canAnalyze: boolean;
};

// Where to look (shared location selector) + how (latest / historical date) + one action.
export default function ExplorePanel({
  mode, onModeChange, location, onLocationChange, requestedDate, onDateChange,
  onDone, examples, onExample, canAnalyze,
}: Props) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  // What the running job was asked for (inputs may change while it runs).
  const [request, setRequest] = useState<{ mode: ExplorationMode; location: SelectedLocation; date: string | null } | null>(null);

  const running = job !== null && (job.status === "queued" || job.status === "running");

  useEffect(() => {
    if (!job || !running || !request) return;
    const timer = setTimeout(() => {
      getAnalysisJob(job.id)
        .then((next) => {
          setJob(next);
          if (next.status === "done") onDone(next, request.mode, request.location, request.date);
          if (next.status === "error") setError(next.error ?? "Analysis failed.");
        })
        .catch((err: unknown) => {
          setJob(null);
          setError(err instanceof Error ? err.message : String(err));
        });
    }, POLL_MS);
    return () => clearTimeout(timer);
  }, [job, running, request, onDone]);

  const needsDate = mode === "historical";
  const ready = location !== null && (!needsDate || requestedDate !== "") && !running && canAnalyze;

  const analyze = () => {
    if (!location || !ready) return;
    const date = needsDate ? requestedDate : null;
    setError(null);
    setRequest({ mode, location, date });
    startFloodAnalysis({
      mode,
      latitude: location.latitude,
      longitude: location.longitude,
      location_name: shortName(location.displayName),
      ...(date ? { requested_date: date } : {}),
    })
      .then((started) => {
        setJob(started);
        if (started.status === "done") onDone(started, mode, location, date);
        if (started.status === "error") setError(started.error ?? "Analysis failed.");
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)));
  };

  const current = MODES.find((m) => m.value === mode)!;

  return (
    <div className={styles.section}>
      <div className={styles.modeGroup} role="radiogroup" aria-label="Exploration mode">
        {MODES.map((m) => (
          <button
            key={m.value}
            type="button"
            role="radio"
            aria-checked={mode === m.value}
            className={mode === m.value ? styles.modeActive : styles.mode}
            onClick={() => onModeChange(m.value)}
            disabled={running}
          >
            {m.label}
          </button>
        ))}
      </div>
      <p className={styles.meta}>{current.description}</p>

      <LocationSelector value={location} onChange={onLocationChange} disabled={running} />

      {needsDate && (
        <>
          <label className={styles.label} htmlFor="requested-date">Date</label>
          <input
            id="requested-date"
            type="date"
            className={styles.input}
            min="2015-07-01"
            max={today}
            value={requestedDate}
            onChange={(e) => onDateChange(e.target.value)}
            disabled={running}
          />
          <p className={styles.meta}>
            Satellites don&apos;t photograph every place every day; SatRelief uses the nearest
            usable Sentinel-2 image within 3 weeks and shows its real date.
          </p>
        </>
      )}

      {running && job && (
        <div className={styles.progress} role="status">
          <div className={styles.progressBar}><span style={{ width: `${Math.round(job.progress * 100)}%` }} /></div>
          <span className={styles.meta}>{job.stage}…</span>
        </div>
      )}
      {error && <p className={styles.error} role="alert">{error}</p>}
      {!canAnalyze && <p className={styles.meta}>Analysis needs the backend (mock data mode).</p>}

      <button type="button" className={styles.primary} onClick={analyze} disabled={!ready}>
        {running ? "Analysing…" : "Analyze flood conditions"}
      </button>

      {examples.length > 0 && (
        <div className={styles.examples}>
          <span className={styles.meta}>Example flood events (instant):</span>
          {examples.map((r) => (
            <button key={r.id} type="button" className={styles.link} onClick={() => onExample(r)} disabled={running}>
              {r.name}{r.flood_scene ? ` · ${formatDate(r.flood_scene.date)}` : ""}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
