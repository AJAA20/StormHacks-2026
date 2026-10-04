"use client";

import { useEffect, useState, type FormEvent } from "react";
import { getJob, searchPlaces, startAnalysis, type BBox, type Job, type Place } from "@/lib/api";
import { MAX_AREA_KM } from "@/lib/config";
import styles from "./Controls.module.css";

type Props = {
  // Area that will be analysed: the current map view, capped at MAX_AREA_KM.
  areaBox: BBox | null;
  areaKm: [number, number] | null;
  onFlyTo: (box: BBox) => void;
  onCancel: () => void;
  onDone: (regionId: string) => void;
};

// A real flood with a clear Sentinel-2 image (31 Mar 2019), not a preset, so
// "Try an example" exercises the full live pipeline.
const EXAMPLE = {
  name: "Fremont, Nebraska (Mar 2019)",
  bbox: [-96.55, 41.38, -96.40, 41.47] as BBox,
  floodStart: "2019-03-16",
  floodEnd: "2019-04-05",
};

const today = new Date().toISOString().slice(0, 10);
const POLL_MS = 1500;

// Analyse a new area: find the place, frame it on the map, pick the flood dates.
export default function AnalyzeAreaPanel({ areaBox, areaKm, onFlyTo, onCancel, onDone }: Props) {
  const [query, setQuery] = useState("");
  const [places, setPlaces] = useState<Place[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [name, setName] = useState("");
  const [floodStart, setFloodStart] = useState("");
  const [floodEnd, setFloodEnd] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);

  const running = job !== null && (job.status === "queued" || job.status === "running");

  // Poll the background job until it finishes.
  useEffect(() => {
    if (!job || !running) return;
    const timer = setTimeout(() => {
      getJob(job.id)
        .then((next) => {
          setJob(next);
          if (next.status === "done") onDone(next.region_id);
          if (next.status === "error") setError(next.error ?? "Analysis failed.");
        })
        .catch((err: unknown) => {
          setJob(null);
          setError(err instanceof Error ? err.message : String(err));
        });
    }, POLL_MS);
    return () => clearTimeout(timer);
  }, [job, running, onDone]);

  const search = (e: FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setError(null);
    searchPlaces(query)
      .then((results) => {
        setPlaces(results);
        if (results.length === 0) setError("No places found. Try another name, or pan the map yourself.");
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setSearching(false));
  };

  const choose = (place: Place) => {
    setName(place.name.split(",").slice(0, 2).join(",").trim());
    setPlaces(null);
    onFlyTo(place.bbox);
  };

  const tryExample = () => {
    setName(EXAMPLE.name);
    setFloodStart(EXAMPLE.floodStart);
    setFloodEnd(EXAMPLE.floodEnd);
    setPlaces(null);
    setError(null);
    onFlyTo(EXAMPLE.bbox);
  };

  const datesValid = floodStart !== "" && floodEnd !== "" && floodStart <= floodEnd;
  const canAnalyze = areaBox !== null && datesValid && !running;

  const analyze = () => {
    if (!areaBox || !datesValid) return;
    setError(null);
    startAnalysis({ name: name.trim() || "Custom area", bbox: areaBox, flood_dates: `${floodStart}/${floodEnd}` })
      .then((started) => {
        setJob(started);
        if (started.status === "done") onDone(started.region_id); // already analysed: cached
        if (started.status === "error") setError(started.error ?? "Analysis failed.");
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)));
  };

  return (
    <div className={styles.section}>
      <div className={styles.headingRow}>
        <span className={styles.heading}>Analyze a new area</span>
        <button type="button" className={styles.link} onClick={onCancel} disabled={running}>Cancel</button>
      </div>

      <fieldset className={styles.fieldset} disabled={running}>
        <form className={styles.searchRow} onSubmit={search}>
          <input
            className={styles.input}
            placeholder="Search a place, e.g. Chilliwack"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search a place"
          />
          <button type="submit" className={styles.small} disabled={searching || !query.trim()}>
            {searching ? "…" : "Search"}
          </button>
        </form>
        {places && places.length > 0 && (
          <ul className={styles.results}>
            {places.map((p) => (
              <li key={`${p.name}-${p.center.join(",")}`}>
                <button type="button" className={styles.result} onClick={() => choose(p)}>{p.name}</button>
              </li>
            ))}
          </ul>
        )}
        <button type="button" className={styles.link} onClick={tryExample}>
          Try an example: {EXAMPLE.name}
        </button>

        <p className={styles.meta}>
          {areaKm
            ? `Area to analyse: ${areaKm[0].toFixed(0)} × ${areaKm[1].toFixed(0)} km (orange box). Pan and zoom the map to adjust; max ${MAX_AREA_KM} km.`
            : "Pan and zoom the map to frame the area."}
        </p>

        <label className={styles.label} htmlFor="area-name">Name</label>
        <input id="area-name" className={styles.input} value={name} placeholder="Custom area"
          onChange={(e) => setName(e.target.value)} maxLength={80} />

        <span className={styles.label}>Flood dates (when the water was there)</span>
        <div className={styles.pair}>
          <input type="date" className={styles.input} aria-label="Flood start date" min="2015-07-01" max={today}
            value={floodStart} onChange={(e) => setFloodStart(e.target.value)} />
          <input type="date" className={styles.input} aria-label="Flood end date" min="2015-07-01" max={today}
            value={floodEnd} onChange={(e) => setFloodEnd(e.target.value)} />
        </div>
        <p className={styles.meta}>
          A 2–4 week window works best: SatRelief picks the clearest Sentinel-2 image in it,
          plus a dry-weather baseline from the months before.
        </p>
      </fieldset>

      {job && running && (
        <div className={styles.progress} role="status">
          <div className={styles.progressBar}><span style={{ width: `${Math.round(job.progress * 100)}%` }} /></div>
          <span className={styles.meta}>{job.stage}…</span>
        </div>
      )}
      {error && <p className={styles.error} role="alert">{error}</p>}

      <button type="button" className={styles.primary} onClick={analyze} disabled={!canAnalyze}>
        {running ? "Analysing…" : "Analyze area"}
      </button>
    </div>
  );
}
