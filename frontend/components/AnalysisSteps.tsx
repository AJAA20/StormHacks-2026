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

// "Run analysis" button, the step-by-step progress, then a one-line summary.
export default function AnalysisSteps({ phase, steps, current, canRun, onRun }: Props) {
  if (phase === "before") {
    return (
      <>
        <p className={styles.text}>
          Showing the normal route to the evacuation point. Run the analysis to check it against
          the flood extent.
        </p>
        <button type="button" className={styles.run} onClick={onRun} disabled={!canRun}>
          Run analysis
        </button>
      </>
    );
  }

  if (phase === "complete") {
    return (
      <p className={styles.summary}>
        <span>Analysis complete</span>
        <button type="button" className={styles.replay} onClick={onRun} disabled={!canRun}>
          Replay
        </button>
      </p>
    );
  }

  return (
    <ol className={styles.steps}>
      {steps.map((step, i) => {
        const state = i < current ? "done" : i === current ? "active" : "pending";
        return (
          <li key={step.label} className={styles[state]}>
            <span className={styles.icon} aria-hidden="true">
              {state === "done" ? "✓" : ""}
            </span>
            <span>
              {step.label}
              {step.detail && state !== "pending" && (
                <span className={styles.detail}>{step.detail}</span>
              )}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
