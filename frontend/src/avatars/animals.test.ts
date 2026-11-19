import { describe, expect, it } from "vitest";
import { ANIMAL_KEYS, dealAnimals } from "./animals";

const LABELS = ["Player A", "Player B", "Player C"];

describe("dealAnimals", () => {
  it("gives the same deal for the same seed (every browser agrees)", () => {
    expect(dealAnimals("3f9a1c0be27d4a55", LABELS)).toEqual(dealAnimals("3f9a1c0be27d4a55", LABELS));
  });

  it("gives every label a distinct animal from the pool", () => {
    for (let i = 0; i < 200; i++) {
      const deal = dealAnimals(`seed-${i}`, LABELS);
      expect(Object.keys(deal).sort()).toEqual(LABELS);
      expect(new Set(Object.values(deal)).size).toBe(LABELS.length);
      for (const animal of Object.values(deal)) expect(ANIMAL_KEYS).toContain(animal);
    }
  });

  it("varies across seeds, and every animal reaches every seat", () => {
    const deals = Array.from({ length: 300 }, (_, i) => dealAnimals(`seed-${i}`, LABELS));
    expect(new Set(deals.map((d) => JSON.stringify(d))).size).toBeGreaterThan(50);
    for (const label of LABELS) {
      expect(new Set(deals.map((d) => d[label])).size).toBe(ANIMAL_KEYS.length);
    }
  });

  it("takes only the seed and the label list (no participant-type input)", () => {
    expect(dealAnimals.length).toBe(2);
    // Extra arguments, such as a type map, cannot change the result.
    const withExtra = (dealAnimals as (...args: unknown[]) => unknown)("s", LABELS, { "Player A": "ai" });
    expect(withExtra).toEqual(dealAnimals("s", LABELS));
  });
});
