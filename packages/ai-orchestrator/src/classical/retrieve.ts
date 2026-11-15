import {
  CLASSICAL_CORPUS,
  type ClassicalPassage,
} from "./corpus";

export interface ClassicalHit {
  id: string;
  source: string;
  title: string;
  text: string;
  score: number;
}

const STOP = new Set([
  "a",
  "an",
  "the",
  "and",
  "or",
  "of",
  "to",
  "in",
  "on",
  "for",
  "is",
  "are",
  "with",
  "by",
  "from",
  "as",
  "at",
  "be",
  "this",
  "that",
  "it",
  "its",
  "when",
  "than",
  "into",
  "can",
  "may",
  "not",
  "only",
]);

function tokenize(text: string): string[] {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, " ")
    .split(/\s+/)
    .map((t) => t.trim())
    .filter((t) => t.length > 1 && !STOP.has(t));
}

function termFreq(tokens: string[]): Map<string, number> {
  const tf = new Map<string, number>();
  for (const token of tokens) {
    tf.set(token, (tf.get(token) ?? 0) + 1);
  }
  return tf;
}

/** Build a sparse TF-IDF-like vector: tf * log((N+1)/(df+1)). */
function buildVector(
  tokens: string[],
  df: Map<string, number>,
  docCount: number,
): Map<string, number> {
  const tf = termFreq(tokens);
  const vec = new Map<string, number>();
  for (const [term, count] of tf) {
    const idf = Math.log((docCount + 1) / ((df.get(term) ?? 0) + 1)) + 1;
    vec.set(term, count * idf);
  }
  return vec;
}

function cosine(a: Map<string, number>, b: Map<string, number>): number {
  let dot = 0;
  let normA = 0;
  let normB = 0;
  for (const [term, weight] of a) {
    normA += weight * weight;
    const other = b.get(term);
    if (other) dot += weight * other;
  }
  for (const weight of b.values()) {
    normB += weight * weight;
  }
  if (normA === 0 || normB === 0) return 0;
  return dot / (Math.sqrt(normA) * Math.sqrt(normB));
}

interface IndexedPassage {
  passage: ClassicalPassage;
  vector: Map<string, number>;
}

function buildIndex(corpus: ClassicalPassage[]): {
  docs: IndexedPassage[];
  df: Map<string, number>;
} {
  const tokenized = corpus.map((passage) => ({
    passage,
    tokens: tokenize(
      `${passage.title} ${passage.tags.join(" ")} ${passage.text}`,
    ),
  }));
  const df = new Map<string, number>();
  for (const doc of tokenized) {
    for (const term of new Set(doc.tokens)) {
      df.set(term, (df.get(term) ?? 0) + 1);
    }
  }
  const docs = tokenized.map((doc) => ({
    passage: doc.passage,
    vector: buildVector(doc.tokens, df, corpus.length),
  }));
  return { docs, df };
}

const INDEX = buildIndex(CLASSICAL_CORPUS);

/**
 * In-process classical retrieval using TF-IDF cosine similarity.
 * Hermetic: no network, no external vector DB. Knowledge library only -
 * never used as chart memory.
 */
export function searchClassical(
  query: string,
  topK = 3,
): ClassicalHit[] {
  const cleaned = query.trim();
  if (cleaned.length < 2) return [];

  const qVec = buildVector(tokenize(cleaned), INDEX.df, CLASSICAL_CORPUS.length);
  const scored = INDEX.docs
    .map((doc) => ({
      passage: doc.passage,
      score: cosine(qVec, doc.vector),
    }))
    .filter((row) => row.score > 0.02)
    .sort((a, b) => b.score - a.score)
    .slice(0, Math.max(1, Math.min(topK, 8)));

  return scored.map((row) => ({
    id: row.passage.id,
    source: row.passage.source,
    title: row.passage.title,
    text: row.passage.text,
    score: Number(row.score.toFixed(4)),
  }));
}
