import test from 'node:test';
import assert from 'node:assert/strict';
import { createPRNG, hashStringToSeed } from '../prng';

test('P1-008 Determinism: createPRNG produces identical sequence for same seed', () => {
  const seed = 428910;
  const prng1 = createPRNG(seed);
  const prng2 = createPRNG(seed);

  const seq1: number[] = [];
  const seq2: number[] = [];

  for (let i = 0; i < 100; i++) {
    seq1.push(prng1());
    seq2.push(prng2());
  }

  assert.deepEqual(seq1, seq2);
  assert.equal(seq1.length, 100);
});

test('P1-008 Determinism: different seeds produce distinct sequences', () => {
  const prngA = createPRNG(1111);
  const prngB = createPRNG(9999);

  const sampleA = [prngA(), prngA(), prngA()];
  const sampleB = [prngB(), prngB(), prngB()];

  assert.notDeepEqual(sampleA, sampleB);
});

test('P1-008 Determinism: hashStringToSeed is deterministic', () => {
  const h1 = hashStringToSeed('cyberpunk-neon-district');
  const h2 = hashStringToSeed('cyberpunk-neon-district');
  const h3 = hashStringToSeed('retro-dungeon-crawler');

  assert.equal(h1, h2);
  assert.notEqual(h1, h3);
});
