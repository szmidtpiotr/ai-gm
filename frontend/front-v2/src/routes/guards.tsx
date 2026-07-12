import { Navigate, Outlet, useLocation, useSearchParams } from "react-router-dom";
import { useAppStore } from "@/store/appStore";
import { getAccessToken } from "@/lib/auth";

function isAuthed(): boolean {
  return !!getAccessToken() && !!useAppStore.getState().currentUser;
}

// Gate for the logged-in surfaces (hub, profil, kampanie, gra).
// Preserves any deep-link query so ?join / ?campaign survive the login round-trip.
export function RequireAuth() {
  const user = useAppStore((s) => s.currentUser);
  const location = useLocation();
  if (!user || !getAccessToken()) {
    const search = location.search || "";
    return <Navigate to={`/login${search}`} replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}

// Index route — one place that resolves deep-links (frontend_design.md §11):
//   ?campaign=ID  → prosto do gry (jeśli zalogowany)
//   ?join=TOKEN   → wylogowany: LOGIN z notką (NIE rejestracja); zalogowany: hub
//   inaczej       → hub bohaterów / login
export function RootRedirect() {
  const [params] = useSearchParams();
  const campaign = params.get("campaign");
  const join = params.get("join");
  const authed = isAuthed();

  if (!authed) {
    // Zaproszony gość ze starym kontem ląduje na logowaniu (poprawka flow #4).
    if (join) return <Navigate to={`/login?join=${encodeURIComponent(join)}`} replace />;
    // Deep-link scenariusza (admin ▶ Graj) — zachowaj campaign przez logowanie.
    if (campaign) return <Navigate to={`/login?campaign=${encodeURIComponent(campaign)}`} replace />;
    return <Navigate to="/login" replace />;
  }

  if (campaign) return <Navigate to={`/gra/${encodeURIComponent(campaign)}`} replace />;
  if (join) return <Navigate to={`/bohaterowie?join=${encodeURIComponent(join)}`} replace />;
  return <Navigate to="/bohaterowie" replace />;
}
