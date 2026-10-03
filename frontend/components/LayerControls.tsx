import styles from "./LayerControls.module.css";

export type LayerKey = "flood" | "floodedRoads" | "originalRoute" | "safeRoute";
export type LayerVisibility = Record<LayerKey, boolean>;

// Top to bottom in the panel; swatches mirror each layer's map styling.
const LAYERS: { key: LayerKey; label: string; swatch: string }[] = [
  { key: "safeRoute", label: "Safe evacuation route", swatch: styles.swatchSafe },
  { key: "originalRoute", label: "Original route", swatch: styles.swatchOriginal },
  { key: "floodedRoads", label: "Flooded roads", swatch: styles.swatchFloodedRoads },
  { key: "flood", label: "Flood area (Sentinel-2)", swatch: styles.swatchFlood },
];

type Props = {
  visibility: LayerVisibility;
  onToggle: (key: LayerKey) => void;
};

// Legend that doubles as layer toggles.
export default function LayerControls({ visibility, onToggle }: Props) {
  return (
    <section className={styles.panel}>
      <h2 className={styles.title}>Map layers</h2>
      <ul className={styles.list}>
        {LAYERS.map(({ key, label, swatch }) => (
          <li key={key}>
            <label className={styles.row}>
              <input
                type="checkbox"
                checked={visibility[key]}
                onChange={() => onToggle(key)}
              />
              <span className={`${styles.swatch} ${swatch}`} />
              <span>{label}</span>
            </label>
          </li>
        ))}
      </ul>
    </section>
  );
}
