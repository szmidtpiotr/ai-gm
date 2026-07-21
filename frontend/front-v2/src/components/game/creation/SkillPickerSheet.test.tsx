// #1523 — arkusz wyboru umiejętności zastąpił natywny <select>.
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SkillPickerSheet } from "./SkillPickerSheet";
import type { SkillRow } from "@/lib/creation";

const CANDIDATES: SkillRow[] = [
  { key: "stealth", label: "Skradanie", stat: "DEX", hint: "Poruszanie się bez hałasu." },
  { key: "athletics", label: "Atletyka", stat: "STR", hint: "Bieganie, skoki, wspinaczka." },
  { key: "survival", label: "Przetrwanie", stat: "WIS", hint: "Tropienie i obóz." },
  { key: "lore", label: "Wiedza", stat: "INT", hint: "Historia i legendy." },
];

function open(onPick = vi.fn()) {
  render(
    <SkillPickerSheet
      open
      onOpenChange={() => {}}
      currentLabel="Unik"
      candidates={CANDIDATES}
      onPick={onPick}
    />,
  );
  return onPick;
}

describe("SkillPickerSheet", () => {
  it("pokazuje wszystkie kandydatki z opisem", () => {
    open();
    expect(screen.getByText("Skradanie")).toBeInTheDocument();
    expect(screen.getByText("Poruszanie się bez hałasu.")).toBeInTheDocument();
    expect(screen.getByText("Historia i legendy.")).toBeInTheDocument();
  });

  it("tytuł mówi, co zamieniamy", () => {
    open();
    expect(screen.getByText("Zamień: Unik")).toBeInTheDocument();
  });

  it("grupuje po cesze wiodącej", () => {
    open();
    for (const stat of ["DEX", "STR", "WIS", "INT"]) {
      expect(screen.getAllByText(stat).length).toBeGreaterThan(0);
    }
  });

  it("szuka po nazwie", () => {
    open();
    fireEvent.change(screen.getByLabelText("Szukaj umiejętności"), {
      target: { value: "skrad" },
    });
    expect(screen.getByText("Skradanie")).toBeInTheDocument();
    expect(screen.queryByText("Atletyka")).not.toBeInTheDocument();
  });

  it("szuka bez polskich znaków (gracz mobilny pisze bez ogonków)", () => {
    open();
    fireEvent.change(screen.getByLabelText("Szukaj umiejętności"), {
      target: { value: "przetrwanie" },
    });
    expect(screen.getByText("Przetrwanie")).toBeInTheDocument();
  });

  it("szuka też po treści opisu", () => {
    open();
    fireEvent.change(screen.getByLabelText("Szukaj umiejętności"), {
      target: { value: "wspinaczka" },
    });
    expect(screen.getByText("Atletyka")).toBeInTheDocument();
    expect(screen.queryByText("Skradanie")).not.toBeInTheDocument();
  });

  it("informuje, gdy nic nie pasuje", () => {
    open();
    fireEvent.change(screen.getByLabelText("Szukaj umiejętności"), {
      target: { value: "zzz" },
    });
    expect(screen.getByText("Nic nie pasuje do wyszukiwania.")).toBeInTheDocument();
  });

  it("klik w pozycję zwraca klucz umiejętności", () => {
    const onPick = open();
    fireEvent.click(screen.getByText("Wiedza"));
    expect(onPick).toHaveBeenCalledWith("lore");
  });
});
