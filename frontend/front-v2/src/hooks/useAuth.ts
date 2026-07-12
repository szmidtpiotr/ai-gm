// Auth mutations (F-01..F-05). Server-state via TanStack Query mutations;
// the persisted session lives in appStore (Zustand) + localStorage.
import { useMutation } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useAppStore, type LoginPayload } from "@/store/appStore";

export function useLogin() {
  const login = useAppStore((s) => s.login);
  return useMutation({
    mutationFn: (vars: { username: string; password: string }) =>
      apiFetch<LoginPayload>("/auth/login", { method: "POST", body: vars, anon: true }),
    onSuccess: (data) => login(data),
  });
}

export interface RegisterVars {
  username: string;
  password: string;
  invite_code: string;
  email?: string;
}

export function useRegister() {
  const login = useAppStore((s) => s.login);
  return useMutation({
    mutationFn: (vars: RegisterVars) =>
      apiFetch<LoginPayload & { ok: boolean }>("/auth/register", {
        method: "POST",
        body: vars,
        anon: true,
      }),
    onSuccess: (data) => {
      // Register issues a token pair too — log the new player straight in.
      if (data.access_token) login(data);
    },
  });
}

export function useVerifyEmail() {
  const login = useAppStore((s) => s.login);
  return useMutation({
    mutationFn: (token: string) =>
      apiFetch<LoginPayload & { ok: boolean }>("/auth/verify-email", {
        method: "POST",
        body: { token },
        anon: true,
      }),
    onSuccess: (data) => {
      if (data.access_token) login(data);
    },
  });
}

export function useForgotPassword() {
  return useMutation({
    mutationFn: (email: string) =>
      apiFetch<{ ok: boolean; message?: string }>("/auth/forgot-password", {
        method: "POST",
        body: { email },
        anon: true,
      }),
  });
}

export function useResetPassword() {
  const login = useAppStore((s) => s.login);
  return useMutation({
    mutationFn: (vars: { token: string; password: string }) =>
      apiFetch<LoginPayload & { ok: boolean }>("/auth/reset-password", {
        method: "POST",
        body: vars,
        anon: true,
      }),
    onSuccess: (data) => {
      if (data.access_token) login(data);
    },
  });
}
