// #1372/#1373 — reguła race_lock (lustro backendu spell_service.learn_spell).
import { describe, it, expect } from "vitest";
import { canRaceLearnSpell, raceLockList } from "./spells";

describe("raceLockList", () => {
  it("pusty/NULL = legacy pula ludzka", () => {
    expect(raceLockList(null)).toEqual(["human"]);
    expect(raceLockList("")).toEqual(["human"]);
    expect(raceLockList("   ")).toEqual(["human"]);
  });
  it("parsuje CSV, trim + lowercase", () => {
    expect(raceLockList("dwarf")).toEqual(["dwarf"]);
    expect(raceLockList(" Human , Dwarf ")).toEqual(["human", "dwarf"]);
  });
});

describe("canRaceLearnSpell", () => {
  it("legacy (brak race_lock) = tylko ludzie, krasnolud wykluczony", () => {
    expect(canRaceLearnSpell("human", null)).toBe(true);
    expect(canRaceLearnSpell("dwarf", null)).toBe(false);
  });
  it("czar krasnoludzki = tylko krasnolud", () => {
    expect(canRaceLearnSpell("dwarf", "dwarf")).toBe(true);
    expect(canRaceLearnSpell("human", "dwarf")).toBe(false);
  });
  it("czar wielorasowy = obie rasy", () => {
    expect(canRaceLearnSpell("human", "human,dwarf")).toBe(true);
    expect(canRaceLearnSpell("dwarf", "human,dwarf")).toBe(true);
  });
  it("nieznana/pusta rasa traktowana jak human", () => {
    expect(canRaceLearnSpell(undefined, null)).toBe(true);
    expect(canRaceLearnSpell("", "dwarf")).toBe(false);
  });
});
