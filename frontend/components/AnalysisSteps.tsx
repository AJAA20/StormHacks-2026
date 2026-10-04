import type { AnalysisStep } from "@/lib/analysis";
import styles from "./AnalysisSteps.module.css";

export type Phase = "before" | "analysing" | "complete";

type Props = {
  phase: Phase;
  steps: AnalysisStep[];
  // Index of the running step while analysing.
  current: number;
  canRun: boolean;
  onRun: () => void;
};

// "Run analysis" button, then the step-by-step progress of the sequence.
export default function AnalysisSteps({ phase, steps, current, canRun, onRun }: Props) {
  if (phase === "before") {
    return (
      <div className={styles.intro}>
        <p className={styles.text}>
          Current evacuation route shown. Check it against satellite flood observations.
        </p>
        <button type="button" className={styles.run} onClick={onRun} disabled={!canRun}>
          Run analysis
        </button>
      </div>
    );
  }

  return (
    <div className={styles.wrapper}>
      <ol className={styles.steps}>
        {steps.map((step, i) => {
          const state = phase === "complete" || i < current ? "done" : i === current ? "active" : "pending";
          return (
            <li key={step.label} className={styles[state]}>
              <span className={styles.icon} aria-hidden="true">
                {state === "done" ? "✓" : ""}
              </span>
              <span>
                <span className={styles.label}>{step.label}</span>
                {step.detail && state !== "pending" && (
                  <span className={styles.detail}>{step.detail}</span>
                )}
              </span>
            </li>
          );
        })}
      </ol>
      {phase === "complete" && (
        <button type="button" className={styles.replay} onClick={onRun} disabled={!canRun}>
          Replay analysis
        </button>
      )}
    </div>
  );
}
