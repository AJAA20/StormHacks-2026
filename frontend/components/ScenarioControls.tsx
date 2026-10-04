import type { Scenario } from "@/lib/api";
import styles from "./ScenarioControls.module.css";

const SCENARIOS: { value: Scenario; label: string }[] = [
  { value: "low", label: "Low" },
  { value: "moderate", label: "Moderate" },
  { value: "severe", label: "Severe" },
];

type Props = {
  value: Scenario;
  onChange: (scenario: Scenario) => void;
  // True while a route request is in flight.
  disabled?: boolean;
};

// Flood scenario selector (architecture.md §9).
export default function ScenarioControls({ value, onChange, disabled = false }: Props) {
  return (
    <>
      <span className={styles.label} id="scenario-label">Flood scenario</span>
      <div className={styles.group} role="radiogroup" aria-labelledby="scenario-label">
        {SCENARIOS.map((s) => (
          <button
            key={s.value}
            type="button"
            role="radio"
            aria-checked={value === s.value}
            disabled={disabled}
            className={value === s.value ? styles.active : styles.option}
            onClick={() => onChange(s.value)}
          >
            {s.label}
          </button>
        ))}
      </div>
    </>
  );
}
