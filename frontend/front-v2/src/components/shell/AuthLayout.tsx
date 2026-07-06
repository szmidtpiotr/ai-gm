import { Outlet } from "react-router-dom";
import { Flame } from "@phosphor-icons/react";

// Pełnoekranowa scena „żaru" dla ekranów wejścia (login/register/reset).
// Bez topbaru/tabbaru — 1:1 z makietą zar8-login.
export function AuthLayout() {
  return (
    <div
      className="relative flex min-h-[100dvh] items-center justify-center overflow-hidden px-6"
      style={{
        paddingTop: "max(24px, var(--sa-top))",
        paddingBottom: "max(24px, var(--sa-bottom))",
        background:
          "radial-gradient(60% 45% at 50% 18%, rgba(255,122,61,.16), transparent 60%)," +
          "radial-gradient(80% 60% at 50% 120%, rgba(20,14,9,1), transparent 70%)," +
          "linear-gradient(180deg,#221812,#100b07)",
      }}
    >
      {/* iskry */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(2px 2px at 20% 70%, rgba(255,150,90,.5), transparent)," +
            "radial-gradient(2px 2px at 70% 60%, rgba(255,150,90,.4), transparent)," +
            "radial-gradient(1.5px 1.5px at 40% 80%, rgba(255,180,120,.5), transparent)," +
            "radial-gradient(1.5px 1.5px at 85% 78%, rgba(255,150,90,.4), transparent)",
        }}
      />
      <div className="relative z-10 w-full max-w-sm animate-fade-in">
        <Outlet />
      </div>
    </div>
  );
}

// Godło ŻAR — znak żaru + tytuł + podtytuł.
export function AuthBrand({
  title = "Mistrz Gry",
  sub = "Kroniki Kresów",
}: {
  title?: string;
  sub?: string;
}) {
  return (
    <div className="mb-7 text-center">
      <div
        className="mx-auto mb-3.5 flex h-16 w-16 items-center justify-center rounded-xl border border-line-ember text-ember-glow"
        style={{
          background:
            "radial-gradient(circle at 40% 35%, rgba(255,122,61,.3), rgba(36,28,19,.9))",
          boxShadow: "0 0 30px rgba(255,122,61,.25)",
        }}
      >
        <Flame weight="fill" size={32} />
      </div>
      <h1 className="font-serif text-title-xl font-semibold text-text">{title}</h1>
      <p className="mt-1.5 font-ui text-[12.5px] uppercase tracking-[0.18em] text-text-3">
        {sub}
      </p>
    </div>
  );
}
