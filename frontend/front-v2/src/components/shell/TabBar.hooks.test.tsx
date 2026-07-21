// #1517 — regresja React #310 („Rendered more hooks than expected").
// TabBar żyje w AppShell, POZA <Outlet/>, więc SPA-nawigacja „poza grą → w grze"
// trafia w ten sam fiber: render nr 1 kończył się wcześnie (`if (!inGame) return null`),
// render nr 2 wołał hook stojący PONIŻEJ tego returna. Test odtwarza dokładnie tę
// sekwencję — przed poprawką rzuca, po poprawce przechodzi.
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TabBar } from "./TabBar";

function wrapper(children: React.ReactNode) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("TabBar — kolejność hooków", () => {
  it("przeżywa przejście inGame false → true na tym samym fibrze", () => {
    const { rerender } = render(wrapper(<TabBar inGame={false} />));
    expect(() => rerender(wrapper(<TabBar inGame />))).not.toThrow();
  });

  it("przeżywa też powrót do gry → poza grę", () => {
    const { rerender } = render(wrapper(<TabBar inGame />));
    expect(() => rerender(wrapper(<TabBar inGame={false} />))).not.toThrow();
  });
});
