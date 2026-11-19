// Avatar art for the six-animal pool. Pure data plus two pure functions.
// Drop into frontend/src/avatars/animals.ts. No dependencies.
//
// Blind-condition rules (do not break):
// - The animal for a seat depends ONLY on (sessionId, label). Never on participant type.
// - Every animal uses the same animation classes and the same timing.

export type AnimalKey = "fox" | "wolf" | "owl" | "cat" | "penguin" | "parrot";
export type SparkKey = "tear" | "dia" | "star" | "bolt" | "bub" | "leaf";

export interface Animal {
  name: string;
  color: string;
  spark: SparkKey;
  art: (id: string) => string;
}

export const SPARK_PATHS: Record<SparkKey, string> = {
  tear: "M5 0C8 4 9 6 5 10C1 6 2 4 5 0Z",
  dia: "M5 0L10 5L5 10L0 5Z",
  star: "M5 0L6.2 3.8L10 5L6.2 6.2L5 10L3.8 6.2L0 5L3.8 3.8Z",
  bolt: "M6 0L1 6H5L4 10L9 4H5Z",
  bub: "M5 .5A4.5 4.5 0 1 0 5.01 .5Z",
  leaf: "M1 9C1 4 4 1 9 1C9 6 6 9 1 9Z",
};

const grad = (id: string, a: string, b: string) =>
  `<defs><linearGradient id="f${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${a}"/><stop offset="1" stop-color="${b}"/></linearGradient></defs>`;

export const ANIMALS: Record<AnimalKey, Animal> = {
  fox: {
    name: "Fox",
    color: "#ff7a2f",
    spark: "tear",
    art: (i) =>
      grad(i, "#ffa24d", "#e5481f") +
      `<path d="M50 88L12 52L15 12L38 33Q50 29 62 33L85 12L88 52Z" fill="url(#f${i})"/><path d="M19 22L33 36L18 43Z M81 22L67 36L82 43Z" fill="#8a2a12"/><path d="M50 88L24 59Q50 67 76 59Z" fill="#fff3e6"/><g class="eye"><ellipse cx="36" cy="52" rx="4" ry="5" fill="#2a1208"/><ellipse cx="64" cy="52" rx="4" ry="5" fill="#2a1208"/><circle cx="37.3" cy="50.2" r="1.4" fill="#ffd9a8"/><circle cx="65.3" cy="50.2" r="1.4" fill="#ffd9a8"/></g><circle cx="50" cy="79" r="4" fill="#2a1208"/>`,
  },
  wolf: {
    name: "Wolf",
    color: "#38bdf8",
    spark: "dia",
    art: (i) =>
      grad(i, "#b6c2e6", "#5a6a98") +
      `<path d="M50 90L14 55L17 6L40 31Q50 28 60 31L83 6L86 55Z" fill="url(#f${i})"/><path d="M22 18L34 33L21 42Z M78 18L66 33L79 42Z" fill="#2e3558"/><path d="M50 90L28 64Q50 52 72 64Z" fill="#eaf0ff"/><g class="eye"><path d="M28 51L44 54L40 59L28 56Z M72 51L56 54L60 59L72 56Z" fill="#5fe3ff"/></g><path d="M45 78L55 78L50 85Z" fill="#151a2e"/>`,
  },
  owl: {
    name: "Owl",
    color: "#a78bfa",
    spark: "star",
    art: (i) =>
      grad(i, "#bda4ff", "#5b3fd1") +
      `<path d="M20 14L38 30L17 40Z M80 14L62 30L83 40Z" fill="#7a5cf0"/><circle cx="50" cy="56" r="35" fill="url(#f${i})"/><path d="M36 82Q50 92 64 82Q50 76 36 82Z M40 72Q50 80 60 72Q50 67 40 72Z" fill="#e6dcff" opacity=".45"/><circle cx="36" cy="52" r="12" fill="#f4efff"/><circle cx="64" cy="52" r="12" fill="#f4efff"/><g class="eye"><circle cx="37" cy="53" r="6" fill="#1d1240"/><circle cx="63" cy="53" r="6" fill="#1d1240"/><circle cx="39" cy="51" r="1.8" fill="#fff"/><circle cx="65" cy="51" r="1.8" fill="#fff"/></g><path d="M45 62L55 62L50 72Z" fill="#ffcf5a"/>`,
  },
  cat: {
    name: "Cat",
    color: "#f5a70b",
    spark: "bolt",
    art: (i) =>
      grad(i, "#ffe27a", "#f59e0b") +
      `<path d="M50 88Q14 82 14 50L16 12L38 32Q50 29 62 32L84 12L86 50Q86 82 50 88Z" fill="url(#f${i})"/><path d="M21 22L33 34L20 41Z M79 22L67 34L80 41Z" fill="#8a5a00"/><g class="eye"><ellipse cx="36" cy="52" rx="6" ry="6.5" fill="#fff6d0"/><ellipse cx="64" cy="52" rx="6" ry="6.5" fill="#fff6d0"/><ellipse cx="36" cy="52" rx="2" ry="5.5" fill="#2a1a00"/><ellipse cx="64" cy="52" rx="2" ry="5.5" fill="#2a1a00"/></g><path d="M46 66L54 66L50 71Z" fill="#c2410c"/><path d="M12 64L32 68M12 74L32 72M88 64L68 68M88 74L68 72" stroke="#fff6d0" stroke-width="1.6" stroke-linecap="round" opacity=".85"/>`,
  },
  penguin: {
    name: "Penguin",
    color: "#3b82f6",
    spark: "bub",
    art: (i) =>
      grad(i, "#3b6cff", "#1b2f8f") +
      `<ellipse cx="50" cy="54" rx="34" ry="38" fill="url(#f${i})"/><ellipse cx="50" cy="62" rx="22" ry="26" fill="#eaf6ff"/><g class="eye"><circle cx="40" cy="48" r="4.5" fill="#0b1440"/><circle cx="60" cy="48" r="4.5" fill="#0b1440"/><circle cx="41.4" cy="46.6" r="1.5" fill="#fff"/><circle cx="61.4" cy="46.6" r="1.5" fill="#fff"/></g><path d="M43 58L57 58L50 70Z" fill="#ffa21f"/>`,
  },
  parrot: {
    name: "Parrot",
    color: "#22c55e",
    spark: "leaf",
    art: (i) =>
      grad(i, "#86efac", "#16a34a") +
      `<path d="M38 24Q42 4 50 16Q58 4 62 24Z" fill="#ff5a5f"/><circle cx="50" cy="54" r="34" fill="url(#f${i})"/><circle cx="36" cy="48" r="10" fill="#f4fff8"/><circle cx="64" cy="48" r="10" fill="#f4fff8"/><g class="eye"><circle cx="37" cy="49" r="4.5" fill="#0d2a16"/><circle cx="63" cy="49" r="4.5" fill="#0d2a16"/><circle cx="38.5" cy="47.5" r="1.4" fill="#fff"/><circle cx="64.5" cy="47.5" r="1.4" fill="#fff"/></g><path d="M41 58Q50 52 59 58Q57 76 50 79Q43 76 41 58Z" fill="#ffb020"/><path d="M45 66Q50 69 55 66" stroke="#b45309" stroke-width="1.6" fill="none" stroke-linecap="round"/>`,
  },
};

export const ANIMAL_KEYS = Object.keys(ANIMALS) as AnimalKey[];

// xmur3 string hash -> 32-bit seed
function hashSeed(str: string): number {
  let h = 1779033703 ^ str.length;
  for (let i = 0; i < str.length; i++) {
    h = Math.imul(h ^ str.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  h = Math.imul(h ^ (h >>> 16), 2246822507);
  h = Math.imul(h ^ (h >>> 13), 3266489909);
  return (h ^ (h >>> 16)) >>> 0;
}

// mulberry32 PRNG
function rng(seed: number): () => number {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Deal distinct animals to the player labels for one session.
 * Same (sessionId, labels) -> same result in every browser, so all viewers
 * see the same animal for the same player. Input is ONLY the session id and
 * the label list. It must never take participant type, presence or order of joining.
 */
export function dealAnimals(sessionId: string, labels: string[]): Record<string, AnimalKey> {
  const rand = rng(hashSeed(sessionId));
  const pool = ANIMAL_KEYS.slice();
  for (let i = pool.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [pool[i], pool[j]] = [pool[j], pool[i]];
  }
  const out: Record<string, AnimalKey> = {};
  labels.forEach((label, idx) => {
    out[label] = pool[idx % pool.length];
  });
  return out;
}