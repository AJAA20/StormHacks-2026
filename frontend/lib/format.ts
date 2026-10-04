// Date formatting for satellite metadata. Dates are shown exactly as acquired, never
// shifted to "today" or to the date the user asked for.

export function formatDate(iso: string): string {
  return new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

// "Nov 21, 2021, 19:20 UTC" from an ISO timestamp (acquisition times are UTC).
export function formatAcquisition(isoDateTime: string): string {
  const d = new Date(isoDateTime);
  const day = d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
  const time = d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC" });
  return `${day}, ${time} UTC`;
}
