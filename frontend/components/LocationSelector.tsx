"use client";

import { useState, type FormEvent } from "react";
import { locateUser, searchLocation, shortName, type SelectedLocation } from "@/lib/location";
import styles from "./Controls.module.css";

type Props = {
  value: SelectedLocation | null;
  onChange: (location: SelectedLocation) => void;
  disabled?: boolean;
};

// Shared by both exploration modes: search any place, or use the browser's location.
// The location does not have to be where the user is.
export default function LocationSelector({ value, onChange, disabled = false }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SelectedLocation[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [locating, setLocating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = (e: FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setError(null);
    searchLocation(query)
      .then((found) => {
        setResults(found);
        if (found.length === 0) setError("No places found. Try another name.");
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setSearching(false));
  };

  const choose = (location: SelectedLocation) => {
    setResults(null);
    setQuery(shortName(location.displayName));
    onChange(location);
  };

  // Only ever called from the button: no location prompt on page load.
  const useMyLocation = () => {
    setLocating(true);
    setError(null);
    setResults(null);
    locateUser()
      .then((location) => {
        setQuery(""); // the search text no longer describes the selection
        onChange(location);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLocating(false));
  };

  return (
    <fieldset className={styles.fieldset} disabled={disabled}>
      <span className={styles.label}>Location</span>
      <form className={styles.searchRow} onSubmit={search}>
        <input
          className={styles.input}
          placeholder="Search for a place"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search for a place"
        />
        <button type="submit" className={styles.small} disabled={searching || !query.trim()}>
          {searching ? "…" : "Search"}
        </button>
      </form>
      {results && results.length > 0 && (
        <ul className={styles.results}>
          {results.map((r) => (
            <li key={`${r.displayName}-${r.latitude}-${r.longitude}`}>
              <button type="button" className={styles.result} onClick={() => choose(r)}>{r.displayName}</button>
            </li>
          ))}
        </ul>
      )}
      <span className={styles.or}>or</span>
      <button type="button" className={styles.secondary} onClick={useMyLocation} disabled={locating}>
        {locating ? "Locating…" : "Use my location"}
      </button>
      {error && <p className={styles.error} role="alert">{error}</p>}
      {value && !error && (
        <p className={styles.meta}>
          {value.source === "device" ? "Your location: " : "Selected: "}
          <strong>{shortName(value.displayName)}</strong>
        </p>
      )}
    </fieldset>
  );
}
