import { GameEntry, RecommendationMatch, RecommendationResponse } from '../types';
import gamesData from '../data/games.json';

const games: GameEntry[] = gamesData as GameEntry[];

const STOP_WORDS = new Set([
  'with', 'and', 'the', 'a', 'an', 'is', 'it', 'to', 'in', 'on', 'of', 'for', 'game', 'games', 'play', 'make', 'create'
]);

function normalizeToken(token: string): string {
  let word = token.toLowerCase().trim();
  if (word.endsWith('ies') && word.length > 4) {
    word = word.slice(0, -3) + 'y';
  } else if (word.endsWith('es') && word.length > 4 && !word.endsWith('ches') && !word.endsWith('shes')) {
    word = word.slice(0, -2);
  } else if (word.endsWith('s') && !word.endsWith('ss') && word.length > 3) {
    word = word.slice(0, -1);
  }
  return word;
}

export function recommendGames(prompt: string): RecommendationResponse {
  if (!prompt || typeof prompt !== 'string') {
    return { query: prompt || '', matches: [] };
  }

  const rawPrompt = prompt.trim();
  const lowerPrompt = rawPrompt.toLowerCase();

  const rawTokens = lowerPrompt
    .replace(/[^a-z0-9\s-]/g, ' ')
    .split(/\s+/)
    .filter(t => t.length > 1);

  const normalizedTokens = rawTokens.map(normalizeToken);
  const tokenSet = new Set([...rawTokens, ...normalizedTokens]);

  const scoredMatches: RecommendationMatch[] = [];

  for (const game of games) {
    let rawScore = 0;
    const reasonsMap = new Map<string, string>();
    const matchedTokens = new Set<string>();

    // 1. Genre match (+30)
    for (const genre of game.genres) {
      const normGenre = normalizeToken(genre);
      const genreLower = genre.toLowerCase();
      if (
        tokenSet.has(normGenre) ||
        tokenSet.has(genreLower) ||
        lowerPrompt.includes(genreLower)
      ) {
        if (!matchedTokens.has(normGenre)) {
          rawScore += 30;
          matchedTokens.add(normGenre);
          reasonsMap.set(`genre_${genre}`, `${genre} genre`);
        }
      }
    }

    // 2. Theme match (+25)
    for (const theme of game.themes) {
      const normTheme = normalizeToken(theme);
      const themeLower = theme.toLowerCase();
      if (
        tokenSet.has(normTheme) ||
        tokenSet.has(themeLower) ||
        lowerPrompt.includes(themeLower)
      ) {
        if (!matchedTokens.has(normTheme)) {
          rawScore += 25;
          matchedTokens.add(normTheme);
          reasonsMap.set(`theme_${theme}`, `${theme} theme`);
        }
      }
    }

    // 3. Mechanic match (+20)
    for (const mechanic of game.mechanics) {
      const normMech = normalizeToken(mechanic);
      const mechLower = mechanic.toLowerCase();
      const isCoopMatch =
        (mechLower.includes('co-op') || mechLower.includes('coop')) &&
        (lowerPrompt.includes('co-op') || lowerPrompt.includes('coop') || lowerPrompt.includes('co op'));

      if (
        isCoopMatch ||
        tokenSet.has(normMech) ||
        tokenSet.has(mechLower) ||
        lowerPrompt.includes(mechLower)
      ) {
        if (!matchedTokens.has(normMech) && !matchedTokens.has(mechLower)) {
          rawScore += 20;
          matchedTokens.add(normMech);
          matchedTokens.add(mechLower);
          reasonsMap.set(`mech_${mechanic}`, `${mechanic} mechanics`);
        }
      }
    }

    // 4. Tag match (+15)
    for (const tag of game.tags) {
      const normTag = normalizeToken(tag);
      const tagLower = tag.toLowerCase();
      if (
        tokenSet.has(normTag) ||
        tokenSet.has(tagLower) ||
        lowerPrompt.includes(tagLower)
      ) {
        if (!matchedTokens.has(normTag)) {
          rawScore += 15;
          matchedTokens.add(normTag);
          const formattedTag = tag.charAt(0).toUpperCase() + tag.slice(1);
          reasonsMap.set(`tag_${tag}`, `${formattedTag} tag`);
        }
      }
    }

    // 5. General keyword match (+10)
    const titleLower = game.title.toLowerCase();
    const descLower = game.description.toLowerCase();
    for (const token of tokenSet) {
      if (token.length > 3 && !STOP_WORDS.has(token) && !matchedTokens.has(token)) {
        if (titleLower.includes(token) || descLower.includes(token)) {
          rawScore += 10;
          matchedTokens.add(token);
          if (!reasonsMap.has('keyword')) {
            const capitalizedToken = token.charAt(0).toUpperCase() + token.slice(1);
            reasonsMap.set('keyword', `Matches '${capitalizedToken}' keyword`);
          }
        }
      }
    }

    const finalScore = Math.min(100, Math.round(rawScore));
    const reasons = Array.from(reasonsMap.values());

    if (finalScore >= 25 && reasons.length > 0) {
      scoredMatches.push({
        id: game.id,
        title: game.title,
        description: game.description,
        score: finalScore,
        reasons: reasons.slice(0, 4)
      });
    }
  }

  scoredMatches.sort((a, b) => b.score - a.score);

  const topMatches = scoredMatches.slice(0, 3);

  if (topMatches.length === 0 || topMatches[0].score < 25) {
    return { query: rawPrompt, matches: [] };
  }

  return { query: rawPrompt, matches: topMatches };
}
