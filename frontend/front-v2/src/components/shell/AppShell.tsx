import { Suspense } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { CircleNotch } from "@phosphor-icons/react";
import { Topbar } from "./Topbar";
import { TabBar } from "./TabBar";

// Skorupa: topbar → treść → dolny tabbar (mobile). Combat/panele = zakładki w grze.
export function AppShell() {
  const { pathname } = useLocation();
  const inGame = pathname.startsWith("/gra/");

  return (
    <div className="relative z-10 flex h-[100dvh] flex-col">
      <Topbar inGame={inGame} />

      <main
        className="min-h-0 flex-1 overflow-y-auto"
        // Zapas na dolny tabbar (mobile). Desktop: tabbar ukryty.
        style={{ scrollbarGutter: "stable" }}
      >
        <div className="mx-auto w-full max-w-3xl px-4 py-4 pb-28 lg:pb-6">
          <Suspense fallback={<RouteFallback />}>
            <Outlet />
          </Suspense>
        </div>
      </main>

      <TabBar inGame={inGame} />
    </div>
  );
}

function RouteFallback() {
  return (
    <div className="flex items-center justify-center gap-2 py-20 text-text-3">
      <CircleNotch className="animate-spin" size={22} />
      <span className="font-ui text-body">Wczytywanie…</span>
    </div>
  );
}
