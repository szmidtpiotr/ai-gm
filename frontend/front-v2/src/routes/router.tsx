import { lazy } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppShell } from "@/components/shell/AppShell";

// Lazy per trasa — każdy ekran to osobny bundle (frontend_design.md §2, §4).
const Login = lazy(() => import("./pages/Login"));
const Heroes = lazy(() => import("./pages/Heroes"));
const Campaigns = lazy(() => import("./pages/Campaigns"));
const Game = lazy(() => import("./pages/Game"));
const Profile = lazy(() => import("./pages/Profile"));
const NotFound = lazy(() => import("./pages/NotFound"));

// Flow (sekcja 11): Login → Bohaterowie → Kampanie bohatera → Gra.
export const router = createBrowserRouter(
  [
    {
      element: <AppShell />,
      children: [
        { index: true, element: <Navigate to="/bohaterowie" replace /> },
        { path: "login", element: <Login /> },
        { path: "bohaterowie", element: <Heroes /> },
        { path: "bohaterowie/:heroId/kampanie", element: <Campaigns /> },
        { path: "gra/:campaignId", element: <Game /> },
        { path: "profil", element: <Profile /> },
        { path: "*", element: <NotFound /> },
      ],
    },
  ],
  { basename: "/v2" },
);
