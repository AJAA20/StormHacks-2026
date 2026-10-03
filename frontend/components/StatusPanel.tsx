import type { ReactNode } from "react";
import type { RouteResponse } from "@/lib/api";
import styles from "./StatusPanel.module.css";

type Props = {
  data: RouteResponse;
  // Controls shown under the header, e.g. the scenario selector.
  children?: ReactNode;
};

// Route metrics from the /api/route response (architecture.md §9).
export default function StatusPanel({ data, children }: Props) {
  const isSafe = data.route_found && data.route_status === "safe";
  const statusLabel = data.route_found
    ? (data.route_status ?? "route found").replace(/_/g, " ").toUpperCase()
    : "NO SAFE ROUTE";

  return (
    <aside className={styles.panel}>
      <header className={styles.header}>
        <h1 className={styles.title}>SatRelief</h1>
        <p className={styles.scenario}>{data.scenario} flood scenario</p>
      </header>

      {children}

      <div className={styles.status}>
        <span className={styles.label}>Route status</span>
        <span className={isSafe ? styles.safe : styles.unsafe}>{statusLabel}</span>
      </div>

      <dl className={styles.metrics}>
        <div>
          <dt className={styles.label}>Distance</dt>
          <dd className={styles.value}>{km(data.distance_km)}</dd>
        </div>
        <div>
          <dt className={styles.label}>Detour added</dt>
          <dd className={styles.value}>{km(data.detour_added_km, "+")}</dd>
        </div>
        <div>
          <dt className={styles.label}>Flooded roads</dt>
          <dd className={styles.value}>{data.flooded_edges ?? "—"}</dd>
        </div>
        <div>
          <dt className={styles.label}>Roads avoided</dt>
          <dd className={styles.value}>{data.flooded_edges_avoided ?? "—"}</dd>
        </div>
      </dl>
    </aside>
  );
}

// Missing values show as a dash rather than breaking the panel.
function km(value: number | null, prefix = "") {
  return value === null ? "—" : `${prefix}${value.toFixed(1)} km`;
}
