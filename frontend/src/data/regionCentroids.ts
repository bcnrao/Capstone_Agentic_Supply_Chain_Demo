// [longitude, latitude] centroids for regions and hubs in seed network data.
export type LonLat = [number, number];

export const REGION_CENTROIDS: Record<string, LonLat> = {
  China: [121.47, 31.23],
  India: [72.87, 19.07],
  Vietnam: [106.63, 10.82],
  Netherlands: [4.48, 51.92],
  USA: [-118.24, 34.05],
  "North America": [-74.0, 40.7],
  Pacific: [139.69, 35.68],
};

export const HUB_CENTROIDS: Record<string, LonLat> = {
  Shanghai: [121.47, 31.23],
  Mumbai: [72.87, 19.07],
  Rotterdam: [4.48, 51.92],
  "Los Angeles": [-118.24, 34.05],
  Dallas: [-96.8, 32.78],
  Dubai: [55.27, 25.2],
  "Ho Chi Minh": [106.63, 10.82],
  "New York": [-74.0, 40.7],
  Bangalore: [77.59, 12.97],
};

export function resolveCoordinates(
  label: string,
  region?: string | null,
  lat?: number | null,
  lon?: number | null,
): LonLat | null {
  if (lat != null && lon != null) {
    return [lon, lat];
  }
  const normalized = label.trim();
  for (const [hub, coords] of Object.entries(HUB_CENTROIDS)) {
    if (normalized.toLowerCase().includes(hub.toLowerCase())) {
      return coords;
    }
  }
  if (region && REGION_CENTROIDS[region]) {
    return REGION_CENTROIDS[region];
  }
  if (REGION_CENTROIDS[normalized]) {
    return REGION_CENTROIDS[normalized];
  }
  return null;
}

export function parseLaneEndpoints(laneName: string): [string, string] {
  const parts = laneName.split("-").map((part) => part.trim());
  if (parts.length >= 2) {
    return [parts[0], parts.slice(1).join("-")];
  }
  return [laneName, laneName];
}
