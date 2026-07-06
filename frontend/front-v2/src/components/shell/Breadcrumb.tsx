import { Link, useLocation, useParams } from "react-router-dom";
import { CaretRight } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";

interface Crumb {
  label: string;
  to?: string;
}

// Breadcrumb poza grą (sekcja 11): „Bohaterowie › Wiga › Kampania", człony klikalne.
function useCrumbs(): Crumb[] {
  const { pathname } = useLocation();
  const { heroId } = useParams();

  if (pathname.startsWith("/bohaterowie/") && pathname.includes("/kampanie")) {
    return [
      { label: "Bohaterowie", to: "/bohaterowie" },
      { label: heroId ? `Bohater #${heroId}` : "Bohater", to: undefined },
    ];
  }
  if (pathname === "/bohaterowie") return [{ label: "Bohaterowie" }];
  if (pathname === "/profil")
    return [{ label: "Bohaterowie", to: "/bohaterowie" }, { label: "Profil" }];
  if (pathname === "/login") return [{ label: "Logowanie" }];
  return [{ label: "Bohaterowie", to: "/bohaterowie" }];
}

export function Breadcrumb() {
  const crumbs = useCrumbs();
  return (
    <nav
      aria-label="Ścieżka"
      className="flex min-w-0 items-center gap-1.5 font-ui text-label"
    >
      {crumbs.map((c, i) => {
        const last = i === crumbs.length - 1;
        return (
          <span key={i} className="flex min-w-0 items-center gap-1.5">
            {c.to && !last ? (
              <Link
                to={c.to}
                className="truncate text-text-3 transition-colors hover:text-ember-glow"
              >
                {c.label}
              </Link>
            ) : (
              <span
                className={cn(
                  "truncate",
                  last ? "text-text" : "text-text-3",
                )}
              >
                {c.label}
              </span>
            )}
            {!last && (
              <CaretRight size={12} className="shrink-0 text-text-3/60" />
            )}
          </span>
        );
      })}
    </nav>
  );
}
