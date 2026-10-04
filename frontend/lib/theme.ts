// Map colours, shared by the map layers and the legend so they always match.
// Based on the ColorBrewer "Paired" scheme used in cartography.

export const MAP_COLORS = {
  floodFill: "#1f78b4",
  floodFillOpacity: 0.5,
  floodEdge: "#a6cee3",
  floodedRoad: "#e31a1c",
  // Original route: orange while it is the current route, grey dashed once blocked.
  routeCurrent: "#ff7f00",
  routeBlocked: "#e0e0e0",
  routeCasing: "#1d2327",
  safeRoute: "#33a02c",
  safeRouteCasing: "#0b2e0b",
  // Purple: not used by any data layer, and visible on satellite imagery.
  startMarker: "#6a3d9a",
  endMarker: "#33a02c",
} as const;
