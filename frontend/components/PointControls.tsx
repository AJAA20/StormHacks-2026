import styles from "./Controls.module.css";

export type PickMode = "start" | "end" | null;

type Props = {
  mode: PickMode;
  onModeChange: (mode: PickMode) => void;
  hasStart: boolean;
  hasEnd: boolean;
};

// Choose start / destination by clicking the map (markers can also be dragged).
export default function PointControls({ mode, onModeChange, hasStart, hasEnd }: Props) {
  const toggle = (next: Exclude<PickMode, null>) => onModeChange(mode === next ? null : next);
  const hint =
    mode === "start" ? "Click the map inside the dashed box to place the start."
    : mode === "end" ? "Click the map inside the dashed box to place the destination."
    : !hasStart || !hasEnd ? "Place a start and a destination to plan an evacuation route."
    : "Drag the markers or use the buttons to move them.";

  return (
    <div className={styles.section}>
      <span className={styles.label}>Route</span>
      <div className={styles.pair}>
        <button
          type="button"
          className={mode === "start" ? styles.pickActive : styles.pick}
          onClick={() => toggle("start")}
          aria-pressed={mode === "start"}
        >
          <span className={styles.dotStart} /> {hasStart ? "Move start" : "Set start"}
        </button>
        <button
          type="button"
          className={mode === "end" ? styles.pickActive : styles.pick}
          onClick={() => toggle("end")}
          aria-pressed={mode === "end"}
        >
          <span className={styles.dotEnd} /> {hasEnd ? "Move destination" : "Set destination"}
        </button>
      </div>
      <p className={styles.meta}>{hint}</p>
    </div>
  );
}
