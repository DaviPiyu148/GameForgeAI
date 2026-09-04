/**
 * synergy.ts
 *
 * Step 3: Pure deterministic Inspiration Synergy computation.
 *
 * RULES:
 * - Pure function: only checks factual intersections between attached inspirations.
 * - Zero LLM, zero Gemini, zero fabricated semantic prose.
 * - Intersections require >= 2 inspirations sharing the exact normalized attribute.
 * - Returns empty collections when inspirations < 2.
 */

import type { ProjectInspirationRecord } from '../types';

export interface InspirationSynergy {
  sharedGenres: string[];
  sharedTags: string[];
  sharedPlayerModes: string[];
  totalInspirations: number;
}

/**
 * Normalizes a list of strings, counts frequencies across distinct inspiration records,
 * and returns items shared by at least `minOccurrences` (default 2) records.
 */
function findSharedItems(
  itemsPerRecord: string[][],
  minOccurrences: number = 2
): string[] {
  const frequencyMap = new Map<string, { canonical: string; count: number }>();

  for (const recordItems of itemsPerRecord) {
    // Unique per record so duplicate tags within a single game are only counted once
    const seenInRecord = new Set<string>();

    for (const rawItem of recordItems) {
      const trimmed = (rawItem || '').trim();
      if (!trimmed) continue;
      const normalized = trimmed.toLowerCase();

      if (!seenInRecord.has(normalized)) {
        seenInRecord.add(normalized);
        const existing = frequencyMap.get(normalized);
        if (existing) {
          existing.count += 1;
        } else {
          frequencyMap.set(normalized, { canonical: trimmed, count: 1 });
        }
      }
    }
  }

  const shared: string[] = [];
  for (const { canonical, count } of frequencyMap.values()) {
    if (count >= minOccurrences) {
      shared.push(canonical);
    }
  }

  return shared;
}

/**
 * Computes deterministic synergy between 2 or more attached inspirations.
 */
export function computeInspirationSynergy(
  inspirations: ProjectInspirationRecord[]
): InspirationSynergy {
  if (!inspirations || inspirations.length < 2) {
    return {
      sharedGenres: [],
      sharedTags: [],
      sharedPlayerModes: [],
      totalInspirations: inspirations ? inspirations.length : 0,
    };
  }

  const genresPerRecord = inspirations.map((i) => i.genres || []);
  const tagsPerRecord = inspirations.map((i) => i.tags || []);
  const modesPerRecord = inspirations.map((i) => i.playerModes || []);

  const sharedGenres = findSharedItems(genresPerRecord, 2);
  const sharedTags = findSharedItems(tagsPerRecord, 2).slice(0, 10);
  const sharedPlayerModes = findSharedItems(modesPerRecord, 2);

  return {
    sharedGenres,
    sharedTags,
    sharedPlayerModes,
    totalInspirations: inspirations.length,
  };
}
