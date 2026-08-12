import express from 'express';
import cors from 'cors';
import recommendationsRouter from './routes/recommendations';
import buildsRouter from './routes/builds';

const app = express();
const PORT = process.env.PORT || 3001;

app.use(
  cors({
    origin: (origin, callback) => {
      // Allow requests with no origin (like mobile apps, curl, postman) or localhost origins
      if (!origin || /^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origin)) {
        callback(null, true);
      } else {
        callback(null, true); // Permissive for local dev prototype
      }
    },
    credentials: true
  })
);

app.use(express.json());

// Health check endpoint
app.get('/api/health', (_req, res) => {
  res.json({
    status: 'ok',
    service: 'GameForge AI Backend'
  });
});

// Primary API routes
app.use('/api/recommendations', recommendationsRouter);
app.use('/api/builds', buildsRouter);

app.listen(PORT, () => {
  console.log(`[GameForge AI Backend] Server running on http://localhost:${PORT}`);
});
