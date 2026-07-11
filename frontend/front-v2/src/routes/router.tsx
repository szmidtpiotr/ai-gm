import { lazy } from "react";
import { createBrowserRouter } from "react-router-dom";
import { AppShell } from "@/components/shell/AppShell";
import { AuthLayout } from "@/components/shell/AuthLayout";
import { RequireAuth, RootRedirect } from "./guards";

// Lazy per trasa — każdy ekran to osobny bundle (frontend_design.md §2, §4).
const Login = lazy(() => import("./pages/Login"));
const Register = lazy(() => import("./pages/Register"));
const VerifyEmail = lazy(() => import("./pages/VerifyEmail"));
const ForgotPassword = lazy(() => import("./pages/ForgotPassword"));
const ResetPassword = lazy(() => import("./pages/ResetPassword"));
const Heroes = lazy(() => import("./pages/Heroes"));
const Campaigns = lazy(() => import("./pages/Campaigns"));
const CampaignHistory = lazy(() => import("./pages/CampaignHistory"));
const CreateCharacter = lazy(() => import("./pages/CreateCharacter"));
const Game = lazy(() => import("./pages/Game"));
// FE15 (#1264) — Lobby MP (F-13): team builder, zaproszenia, timer, start.
const Lobby = lazy(() => import("./pages/Lobby"));
const Profile = lazy(() => import("./pages/Profile"));
const NotFound = lazy(() => import("./pages/NotFound"));
// FE10 (#1237) — publiczny podgląd modali wyników walki (QA/Playwright vs makiety).
const OutcomePreview = lazy(() => import("./pages/OutcomePreview"));

// Flow (sekcja 11): Login → Bohaterowie → Kampanie bohatera → Gra.
// Deep-linki (?campaign / ?join) rozwiązuje RootRedirect na „/".
export const router = createBrowserRouter(
  [
    { index: true, element: <RootRedirect /> },

    // FE10 podgląd modali wyników — publiczny, tylko QA wizualne (bez shellu/auth).
    { path: "podglad/wyniki", element: <OutcomePreview /> },

    // Ekrany wejścia — pełnoekranowa scena, bez shellu (publiczne).
    {
      element: <AuthLayout />,
      children: [
        { path: "login", element: <Login /> },
        { path: "rejestracja", element: <Register /> },
        { path: "weryfikacja-email", element: <VerifyEmail /> },
        { path: "zapomniane-haslo", element: <ForgotPassword /> },
        { path: "reset-hasla", element: <ResetPassword /> },
      ],
    },

    // Surface gracza — wymaga zalogowania, w shellu (topbar/breadcrumb/tabbar).
    {
      element: <RequireAuth />,
      children: [
        {
          element: <AppShell />,
          children: [
            { path: "bohaterowie", element: <Heroes /> },
            { path: "bohaterowie/nowy", element: <CreateCharacter /> },
            { path: "bohaterowie/:heroId/kampanie", element: <Campaigns /> },
            {
              path: "bohaterowie/:heroId/historia/:campaignId",
              element: <CampaignHistory />,
            },
            { path: "druzyna/:campaignId", element: <Lobby /> },
            { path: "gra/:campaignId", element: <Game /> },
            { path: "profil", element: <Profile /> },
            { path: "*", element: <NotFound /> },
          ],
        },
      ],
    },
  ],
  { basename: "/graj" },
);
