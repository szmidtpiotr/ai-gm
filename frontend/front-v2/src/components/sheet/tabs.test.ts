// #1375 — zakładka Receptury pojawia się dopiero po nauczeniu pierwszej receptury.
import { describe, expect, it } from "vitest";
import { visibleSheetTabs } from "./tabs";

const keys = (hasMana: boolean, hasRecipes: boolean) =>
  visibleSheetTabs(hasMana, hasRecipes).map((t) => t.key);

describe("visibleSheetTabs — recipes gating (#1375)", () => {
  it("hides Receptury when hasRecipes=false", () => {
    expect(keys(false, false)).not.toContain("recipes");
  });

  it("shows Receptury when hasRecipes=true", () => {
    expect(keys(false, true)).toContain("recipes");
  });

  it("defaults hasRecipes to false when omitted", () => {
    expect(visibleSheetTabs(false).map((t) => t.key)).not.toContain("recipes");
  });

  it("still gates spells by mana independently", () => {
    expect(keys(false, true)).not.toContain("spells");
    expect(keys(true, true)).toContain("spells");
  });
});
