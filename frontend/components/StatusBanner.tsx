import styles from "./StatusBanner.module.css";

type Props = {
  loading: boolean;
  error: string | null;
  onRetry: () => void;
};

// Request state over the map: a loading notice, or an error with retry.
export default function StatusBanner({ loading, error, onRetry }: Props) {
  if (error) {
    return (
      <div className={`${styles.banner} ${styles.error}`} role="alert">
        <span>{error}</span>
        <button type="button" className={styles.retry} onClick={onRetry}>
          Retry
        </button>
      </div>
    );
  }

  if (loading) {
    return (
      <div className={`${styles.banner} ${styles.loading}`} role="status">
        <span className={styles.spinner} />
        <span>Calculating evacuation route…</span>
      </div>
    );
  }

  return null;
}
