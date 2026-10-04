import type { ReactNode } from "react";
import { USE_MOCK, type RouteResponse, type Scenario } from "@/lib/api";
import styles from "./StatusPanel.module.css";

type Props = {
  scenario: Scenario;
  // null until the first route response arrives.
  data: RouteResponse | null;
  // Hidden until the analysis has run.
  showMetrics: boolean;
  // Area, route point, scenario and analysis controls.
  children?: ReactNode;
  legend: ReactNode;
};

// The map sheet: title block, controls, route metrics (architecture.md §9) and legend.
export default function StatusPanel({ scenario, data, showMetrics, children, legend }: Props) {
  return (
    <aside className={styles.sheet}>
      <header className={styles.section}>
        <p className={styles.brand}>SatRelief</p>
        <h1 className={styles.title}>Flood evacuation map</h1>
        {/* The area and its Sentinel-2 scene date are shown by the area selector below. */}
        <p className={styles.meta}>
          <span className={styles.scenario}>{scenario}</span> flood scenario
          {USE_MOCK && " · mock data, not satellite-derived"}
        </p>
      </header>

      <div className={styles.section}>{children}</div>

      {showMetrics && data && (
        <dl className={`${styles.section} ${styles.rows}`}>
          <div className={styles.row}>
            <dt>Route</dt>
            <dd className={statusClass(data)}>{statusText(data)}</dd>
          </div>
          <div className={styles.row}>
            <dt>Distance</dt>
            <dd>{km(data.distance_km)}</dd>
          </div>
          <div className={styles.row}>
            <dt>Detour</dt>
            <dd>{data.detour_added_km === 0 ? "None" : km(data.detour_added_km, "+")}</dd>
          </div>
          <div className={styles.row}>
            <dt>Flooded roads</dt>
            <dd>{data.flooded_edges ?? "—"}</dd>
          </div>
          <div className={styles.row}>
            <dt>On original route</dt>
            <dd>{data.flooded_edges_avoided ?? "—"}</dd>
          </div>
        </dl>
      )}

      <div className={styles.section}>{legend}</div>
    </aside>
  );
}

// Only claim a reroute when the response confirms one.
function isRerouted(d: RouteResponse) {
  return (d.detour_added_km ?? 0) > 0 || (d.flooded_edges_avoided ?? 0) > 0;
}

function statusText(d: RouteResponse) {
  if (!d.route_found) return "No safe route";
  if (d.route_status === "safe") return isRerouted(d) ? "Rerouted" : "Safe";
  const s = (d.route_status ?? "route found").replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function statusClass(d: RouteResponse) {
  return d.route_found && d.route_status === "safe" ? styles.ok : styles.alert;
}

// Missing values show as a dash rather than breaking the panel.
function km(value: number | null, prefix = "") {
  return value === null ? "—" : `${prefix}${value.toFixed(1)} km`;
}
