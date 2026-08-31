# GameForge AI — Discovery Experience Product Audit

## 1. Executive Summary

An audit of the current Discovery codebase (`HomePage.tsx`, `ProfilePage.tsx`, `discovery_service.py`, `preference_service.py`, `ranker.py`) was performed against the 10 Discovery Experience product questions.

While Discovery Intelligence V1 provides high retrieval quality (RRF fusion, intent parsing, FAISS vector indexing, mode multipliers, grounded explanations), the player-facing presentation still operates largely as a search box with result cards rather than an intuitive, personalized discovery companion.

---

## 2. Answers to the 10 Product Audit Questions

### 1. What does a brand-new user see?
- A hero header, a search prompt input, four pre-baked suggestion chips ("Cyberpunk RPG", "Co-op Sci-Fi", "Retro Platformer", "Survival Horror"), and an empty result area. No cold-start preference setup exists; a new user has an empty Game DNA until they interact.

### 2. How can they establish preferences?
- Only passively by searching, clicking "Save to Discovery" (saving to DB), clicking "Build Similar", or thumbs up/down on results. There is no onboarding flow or explicit selection mechanism.

### 3. Where can they see Game DNA?
- In `ProfilePage.tsx` under a "Game DNA" tab. However, it displays only top raw genre percentages and interaction counts in a basic grid. It does not clearly explain what the user tends to avoid, what kinds of experiences they explore, or why the system thinks so.

### 4. How can they influence recommendations?
- By typing natural language instructions (e.g. "without combat", "relaxing") or by changing the 4 mode tabs (`BEST_MATCH`, `DISCOVER`, `HIDDEN_GEMS`, `POPULAR`). There is no temporary in-session "Tune" panel or explicit preference slider.

### 5. How can they reject a recommendation?
- Thumbs-down button and "Less Like This" button exist on result cards (`handleFeedback(gameId, 'less_like_this')`). This records a negative signal and removes the card from the UI. However, feedback toast messaging is missing, leaving the player unsure of what happened.

### 6. How can they compare games?
- Currently impossible. There is no multi-game comparison modal, comparison drawer, or side-by-side metadata table.

### 7. How can they discover something without writing a query?
- Currently, if the search bar is empty and the user hits Enter, they are routed to `/build`. There are no default discovery feeds (e.g. "For You", "Hidden Gems", "Popular", "Because You Saved...") rendered on the home page when idle.

### 8. Can they understand why a game was recommended?
- Yes, individual cards display `match_highlights`, `explanation`, and `trade_offs`. However, top-level "Why These?" summary at the top of the search results is not prominently highlighted, and "Why #1?" is not differentiated.

### 9. Can they reset personalization?
- Currently impossible. There is no backend endpoint or UI button to reset `UserGenrePreference` without deleting the user account.

### 10. Can discovery intent flow into Build?
- Yes, clicking "Build Similar" extracts `BuildInspirationResponse` and pre-populates the prompt and modules in the builder. However, when a query yields no results, or when a user wants to "Build This Idea" from their active search filters, the flow is disconnected.

---

## 3. Top UX Gaps Identified

1. **Missing Cold-Start Onboarding**: New users face a blank slate with zero guidance to set their favorite genres, mechanics, and avoidances.
2. **Missing In-Session "Tune My Recommendations"**: Users cannot easily tweak session intent (e.g. "More Story", "Less Combat", "Quick Session") without editing the text prompt manually.
3. **No Browse/Feed Mode**: The home page is blank when no search has been entered; there are no "For You", "Hidden Gems", or "Because You Saved" feeds.
4. **No Game Comparison**: Users cannot select 2-3 titles to inspect trade-offs, genre overlaps, ratings, or gameplay mechanics side-by-side.
5. **No Game DNA Control & Reset**: Users cannot clear learned preferences when their taste shifts without losing their account history.
