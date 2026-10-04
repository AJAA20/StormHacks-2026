import type { CSSProperties } from "react";
import { MAP_COLORS } from "@/lib/theme";
import styles from "./LayerControls.module.css";

export type LayerKey = "flood" | "floodedRoads" | "originalRoute" | "safeRoute" | "satellite";
export type LayerVisibility = Record<LayerKey, boolean>;

const line = (color: string): CSSProperties => ({ height: 4, background: color });

type Props = {
  visibility: LayerVisibility;
  onToggle: (key: LayerKey) => void;
  // Matches OriginalRouteLayer: solid "current route" until flooding blocks it.
  routeCompromised: boolean;
};

// Map legend that doubles as layer toggles. Swatches use the map's own colours.
export default function LayerControls({ visibility, onToggle, routeCompromised }: Props) {
  const rows: { key: LayerKey; label: string; swatch: CSSProperties }[] = [
    { key: "safeRoute", label: "Evacuation route", swatch: line(MAP_COLORS.safeRoute) },
    routeCompromised
      ? {
          key: "originalRoute",
          label: "Original route (blocked)",
          // Light dashes over the dark casing, as drawn on the map.
          swatch: {
            height: 5,
            background: `repeating-linear-gradient(90deg, ${MAP_COLORS.routeBlocked} 0 6px, ${MAP_COLORS.routeCasing} 6px 10px)`,
          },
        }
      : { key: "originalRoute", label: "Current route", swatch: line(MAP_COLORS.routeCurrent) },
    { key: "floodedRoads", label: "Flooded road", swatch: line(MAP_COLORS.floodedRoad) },
    {
      key: "flood",
      label: "Flood extent",
      swatch: {
        height: 12,
        border: `1.5px solid ${MAP_COLORS.floodEdge}`,
        background: MAP_COLORS.floodFill,
        opacity: 0.85,
      },
    },
    {
      key: "satellite",
      label: "Sentinel-2 image (flood date)",
      swatch: { height: 12, background: "linear-gradient(135deg, #3f6212, #a16207 55%, #78716c)" },
    },
  ];

  return (
    <section>
      <h2 className={styles.title}>Legend</h2>
      <ul className={styles.list}>
        {rows.map(({ key, label, swatch }) => (
          <li key={key}>
            <label className={styles.row}>
              <input
                type="checkbox"
                checked={visibility[key]}
                onChange={() => onToggle(key)}
              />
              <span className={styles.swatch} style={swatch} />
              <span>{label}</span>
            </label>
          </li>
        ))}
      </ul>
    </section>
  );
}
