import type { Region } from "@/lib/api";
import styles from "./Controls.module.css";

type Props = {
  regions: Region[];
  value: string | null;
  onChange: (regionId: string) => void;
  onAnalyzeNew: () => void;
  // False in mock mode (no backend to analyse with).
  canAnalyze: boolean;
  disabled?: boolean;
};

// Which analysed area is shown, plus the entry point to analyse a new one.
export default function RegionSelector({ regions, value, onChange, onAnalyzeNew, canAnalyze, disabled }: Props) {
  const region = regions.find((r) => r.id === value) ?? null;
  const presets = regions.filter((r) => r.preset);
  const mine = regions.filter((r) => !r.preset);

  return (
    <div className={styles.section}>
      <label className={styles.label} htmlFor="region-select">Area</label>
      <select
        id="region-select"
        className={styles.select}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled || regions.length === 0}
      >
        {regions.length === 0 && <option value="">Loading areas…</option>}
        {presets.length > 0 && (
          <optgroup label="Examples">
            {presets.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
          </optgroup>
        )}
        {mine.length > 0 && (
          <optgroup label="Analysed areas">
            {mine.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
          </optgroup>
        )}
      </select>

      {region?.flood_scene && (
        <p className={styles.meta}>
          Sentinel-2 · {formatDate(region.flood_scene.date)} · {Math.round(region.flood_scene.aoi_clear_pct)}% cloud-free
          {region.preflood_scene ? ` · baseline ${formatDate(region.preflood_scene.date)}` : ""}
        </p>
      )}
      {region?.warnings?.map((w) => <p key={w} className={styles.warning}>{w}</p>)}

      {canAnalyze && (
        <button type="button" className={styles.secondary} onClick={onAnalyzeNew} disabled={disabled}>
          + Analyze a new area
        </button>
      )}
    </div>
  );
}

export function formatDate(iso: string) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}
