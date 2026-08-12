import { Router } from 'express';
import { recommendGames } from '../services/recommendationService';

const router = Router();

router.post('/', (req, res) => {
  const { prompt } = req.body || {};

  if (!prompt || typeof prompt !== 'string') {
    return res.status(400).json({ error: 'Prompt is required and must be a string.' });
  }

  if (prompt.length > 5000) {
    return res.status(400).json({ error: 'Prompt exceeds maximum length of 5000 characters.' });
  }

  const response = recommendGames(prompt);
  return res.json(response);
});

export default router;
