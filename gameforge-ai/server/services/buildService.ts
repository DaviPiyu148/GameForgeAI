import { BuildParams, BuildResponseSuccess, BuildResponseError } from '../types';

export function createBuild(
  prompt: string,
  parameters?: Partial<BuildParams>
): BuildResponseSuccess | BuildResponseError {
  if (!prompt || typeof prompt !== 'string') {
    return {
      status: 'ERROR',
      message: 'Prompt is required and must be a string.'
    };
  }

  if (prompt.length > 5000) {
    return {
      status: 'ERROR',
      message: 'Prompt exceeds maximum length of 5000 characters.'
    };
  }

  // Exact-word boundary check: /\bERROR\b/i
  const hasError = /\bERROR\b/i.test(prompt);

  if (hasError) {
    return {
      status: 'ERROR',
      message: 'BUILD_FAILED'
    };
  }

  const defaultParams: BuildParams = {
    engine: 'Unreal Engine 5 Core',
    artDensity: 50,
    physics: 80,
    modules: ['Procedural Gen', 'Advanced NPC AI']
  };

  const finalParams: BuildParams = {
    engine: parameters?.engine || defaultParams.engine,
    artDensity: typeof parameters?.artDensity === 'number' ? parameters.artDensity : defaultParams.artDensity,
    physics: typeof parameters?.physics === 'number' ? parameters.physics : defaultParams.physics,
    modules: Array.isArray(parameters?.modules) ? parameters.modules : defaultParams.modules
  };

  const title = prompt.substring(0, 40).trim() || 'UNTITLED PROJECT';

  return {
    id: `proj_${Date.now().toString(16)}`,
    title,
    prompt,
    genre: 'Generated Concept',
    status: 'PLAYABLE',
    lastModified: 'Just now',
    parameters: finalParams,
    createdAt: new Date().toISOString()
  };
}
