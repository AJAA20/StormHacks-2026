import type { Metadata } from "next";
// Bundled with the app (no download at build time), so builds work offline.
import "@fontsource-variable/dosis";
import "./globals.css";

export const metadata: Metadata = {
  title: "SatRelief",
  description: "Satellite-aware flood evacuation routing",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
