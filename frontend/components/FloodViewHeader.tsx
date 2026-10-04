import type { ExplorationMode, SceneInfo } from "@/lib/api";
import { formatAcquisition, formatDate } from "@/lib/format";
import styles from "./Controls.module.css";

// What is on the map: which mode, where, and the REAL satellite acquisition date.
export type FloodView = {
  mode: ExplorationMode;
  // A committed example event shown without a request (no requested date).
  example: boolean;
  locationName: string;
  requestedDate: string | null;
  observation: SceneInfo | null;
  source: string | null;
  note: string | null;
  warnings: string[];
};

export default function FloodViewHeader({ view }: { view: FloodView }) {
  const historical = view.mode === "historical";
  const obs = view.observation;
  const observed = obs ? (obs.datetime ? formatAcquisition(obs.datetime) : formatDate(obs.date)) : "Unknown";

  return (
    <div className={styles.section}>
      <span className={historical ? styles.badgeHistorical : styles.badgeLatest}>
        {historical ? "Historical flood view" : "Latest available flood view"}
      </span>
      <p className={styles.heading}>{view.locationName}</p>
      <dl className={styles.facts}>
        {historical && view.requestedDate && (
          <>
            <dt>Requested date</dt>
            <dd>{formatDate(view.requestedDate)}</dd>
          </>
        )}
        <dt>{historical ? "Satellite observation" : "Latest available observation"}</dt>
        <dd>{observed}</dd>
        <dt>Satellite</dt>
        <dd>
          {obs?.mission ?? "Sentinel-2"}
          {obs ? ` · ${Math.round(obs.aoi_clear_pct)}% cloud-free` : ""}
        </dd>
        <dt>Data source</dt>
        <dd>{view.source ?? "Copernicus Sentinel-2"}</dd>
      </dl>
      {view.note && <p className={styles.meta}>{view.note}</p>}
      {view.warnings.map((w) => <p key={w} className={styles.warning}>{w}</p>)}
      <p className={styles.disclaimer}>
        {historical
          ? "Historical simulation for informational and educational use, not a current evacuation instruction."
          : "Based on the satellite observation above, which is a snapshot, not a live feed. Not a certified emergency navigation system: follow official evacuation orders."}
      </p>
    </div>
  );
}
