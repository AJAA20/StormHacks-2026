import type { ReactNode } from "react";
import type { RouteResponse, Scenario } from "@/lib/api";
import styles from "./StatusPanel.module.css";

type Props = {
  // null until a route has been calculated (e.g. a new area with no points yet).
  data: RouteResponse | null;
  scenario: Scenario;
  // Controls shown under the header, e.g. the scenario selector.
  children?: ReactNode;
  // Hidden until the analysis has run.
  showMetrics?: boolean;
};

// Route metrics from the /api/route response (architecture.md §9).
export default function StatusPanel({ data, scenario, children, showMetrics = true }: Props) {
  return (
    <aside className={styles.panel}>
      <header className={styles.header}>
        <h1 className={styles.title}>SatRelief</h1>
        <p className={styles.scenario}>{data?.scenario ?? scenario} flood scenario</p>
      </header>

      {children}

      {showMetrics && data && <Metrics data={data} />}
    </aside>
  );
}

function Metrics({ data }: { data: RouteResponse }) {
  const isSafe = data.route_found && data.route_status === "safe";
  // Only claim a reroute when the response confirms one.
  const rerouted = (data.detour_added_km ?? 0) > 0 || (data.flooded_edges_avoided ?? 0) > 0;
  const statusLabel = !data.route_found
    ? "NO SAFE ROUTE"
    : isSafe && rerouted
      ? "REROUTED"
      : (data.route_status ?? "route found").replace(/_/g, " ").toUpperCase();

  return (
    <>
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
          <dd className={styles.value}>{detour(data.detour_added_km)}</dd>
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
    </>
  );
}

// Missing values show as a dash rather than breaking the panel.
function km(value: number | null, prefix = "") {
  return value === null ? "—" : `${prefix}${value.toFixed(1)} km`;
}

function detour(value: number | null) {
  return value === 0 ? "None" : km(value, "+");
}
