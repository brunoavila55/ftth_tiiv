/**
 * Utilitários geodésicos e geométricos para cálculo de distâncias e snap a estruturas
 */

const EARTH_RADIUS_METERS = 6371000;

/**
 * Converte graus para radianos
 */
function toRadians(degrees: number): number {
  return (degrees * Math.PI) / 180;
}

/**
 * Calcula a distância ortodrômica precisa (fórmula de Haversine) entre dois pontos WGS84 em metros
 * @param coord1 [longitude, latitude]
 * @param coord2 [longitude, latitude]
 */
export function haversineDistance(
  coord1: [number, number],
  coord2: [number, number]
): number {
  const [lon1, lat1] = coord1;
  const [lon2, lat2] = coord2;

  const dLat = toRadians(lat2 - lat1);
  const dLon = toRadians(lon2 - lon1);

  const lat1Rad = toRadians(lat1);
  const lat2Rad = toRadians(lat2);

  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(lat1Rad) * Math.cos(lat2Rad) * Math.sin(dLon / 2) * Math.sin(dLon / 2);

  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

  return EARTH_RADIUS_METERS * c;
}

/**
 * Calcula a extensão total acumulada de uma linha composta por múltiplos vértices [lon, lat]
 */
export function calculateLineLength(coordinates: [number, number][]): number {
  if (coordinates.length < 2) return 0;

  let totalMeters = 0;
  for (let i = 0; i < coordinates.length - 1; i++) {
    totalMeters += haversineDistance(coordinates[i], coordinates[i + 1]);
  }

  return Math.round(totalMeters * 10) / 10;
}

/** Insere um vértice no trecho mais próximo, preservando a ordem do LineString. */
export function insertVertexAtNearestSegment(
  coordinates: [number, number][],
  vertex: [number, number]
): [number, number][] {
  if (coordinates.length < 2) return [...coordinates, vertex];

  let nearestSegmentIndex = 0;
  let nearestSquaredDistance = Number.POSITIVE_INFINITY;

  for (let index = 0; index < coordinates.length - 1; index += 1) {
    const [startX, startY] = coordinates[index];
    const [endX, endY] = coordinates[index + 1];
    const deltaX = endX - startX;
    const deltaY = endY - startY;
    const lengthSquared = deltaX * deltaX + deltaY * deltaY;
    const projection =
      lengthSquared === 0
        ? 0
        : Math.max(
            0,
            Math.min(
              1,
              ((vertex[0] - startX) * deltaX + (vertex[1] - startY) * deltaY) /
                lengthSquared
            )
          );
    const projectedX = startX + projection * deltaX;
    const projectedY = startY + projection * deltaY;
    const squaredDistance =
      (vertex[0] - projectedX) ** 2 + (vertex[1] - projectedY) ** 2;

    if (squaredDistance < nearestSquaredDistance) {
      nearestSquaredDistance = squaredDistance;
      nearestSegmentIndex = index;
    }
  }

  const next = [...coordinates];
  next.splice(nearestSegmentIndex + 1, 0, vertex);
  return next;
}

export interface SnapCandidate {
  id: string;
  code: string;
  entity_type: string;
  coordinates: [number, number];
  distanceMeters: number;
}

/**
 * Encontra a estrutura mais próxima do cursor dentro de um raio de tolerância (em metros).
 * Utilizado exclusivamente para auxílio visual de precisão geométrica (snap magnético).
 */
export function findNearestSnapCandidate(
  cursor: [number, number],
  candidates: { id: string; code: string; entity_type: string; coordinates: [number, number] }[],
  thresholdMeters: number = 25
): SnapCandidate | null {
  let nearest: SnapCandidate | null = null;
  let minDistance = Infinity;

  for (const candidate of candidates) {
    const dist = haversineDistance(cursor, candidate.coordinates);
    if (dist <= thresholdMeters && dist < minDistance) {
      minDistance = dist;
      nearest = {
        id: candidate.id,
        code: candidate.code,
        entity_type: candidate.entity_type,
        coordinates: candidate.coordinates,
        distanceMeters: Math.round(dist * 10) / 10,
      };
    }
  }

  return nearest;
}
