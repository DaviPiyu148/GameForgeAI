import { Router } from 'express';
import { createBuild } from '../services/buildService';

const router = Router();

router.post('/', (req, res) => {
  const { prompt, parameters } = req.body || {};

  if (!prompt || typeof prompt !== 'string') {
    return res.status(400).json({
      status: 'ERROR',
      message: 'Prompt is required and must be a string.'
    });
  }

  if (prompt.length > 5000) {
    return res.status(400).json({
      status: 'ERROR',
      message: 'Prompt exceeds maximum length of 5000 characters.'
    });
  }

  const result = createBuild(prompt, parameters);

  if ('status' in result && result.status === 'ERROR') {
    return res.status(400).json(result);
  }

  return res.json(result);
});

export default router;
