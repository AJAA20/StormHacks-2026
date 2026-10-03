"use client";

import dynamic from "next/dynamic";

// MapLibre needs `window`, so the map is rendered on the client only.
const MapView = dynamic(() => import("./MapView"), { ssr: false });

export default function MapLoader() {
  return <MapView />;
}
