import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { LockSimple, Check } from "@phosphor-icons/react";
import { AuthBrand } from "@/components/shell/AuthLayout";
import { Field, FormNotice } from "@/components/ui/field";
import { Button } from "@/components/ui/button";
import { useResetPassword } from "@/hooks/useAuth";
import { APIError } from "@/lib/api";

// F-05 Reset hasła — nowe hasło z tokenu w linku (?token=).
export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [mismatch, setMismatch] = useState(false);
  const navigate = useNavigate();
  const reset = useResetPassword();

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setMismatch(true);
      return;
    }
    setMismatch(false);
    reset.mutate(
      { token, password },
      {
        onSuccess: (d) => {
          if (d.access_token) setTimeout(() => navigate("/bohaterowie", { replace: true }), 1000);
        },
      },
    );
  }

  const err = reset.error as APIError | null;

  if (!token) {
    return (
      <div className="text-center">
        <AuthBrand sub="Reset hasła" />
        <FormNotice kind="error">
          Brak tokenu resetu. Otwórz link z wiadomości e-mail.
        </FormNotice>
        <Link to="/zapomniane-haslo" className="mt-4 inline-block font-ui text-body text-ember-glow">
          Wyślij nowy link
        </Link>
      </div>
    );
  }

  return (
    <div className="text-center">
      <AuthBrand sub="Nowe hasło" />

      {reset.isSuccess ? (
        <FormNotice kind="success">
          Hasło zmienione. Wchodzę do gry…
        </FormNotice>
      ) : (
        <form onSubmit={onSubmit} className="flex flex-col gap-2.5 text-left">
          <Field
            icon={LockSimple}
            type="password"
            revealable
            autoComplete="new-password"
            placeholder="Nowe hasło (min. 8 znaków)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <Field
            icon={LockSimple}
            type="password"
            autoComplete="new-password"
            placeholder="Powtórz hasło"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
          />
          {mismatch && <FormNotice kind="error">Hasła nie są takie same.</FormNotice>}
          {err && (
            <FormNotice kind="error">
              {err.status === 410
                ? "Link resetujący wygasł."
                : err.status === 409
                  ? "Link został już użyty."
                  : err.message}
            </FormNotice>
          )}
          <Button type="submit" size="lg" className="mt-2" disabled={reset.isPending}>
            <Check weight="bold" size={18} />
            {reset.isPending ? "Zapisuję…" : "Ustaw nowe hasło"}
          </Button>
          <Link
            to="/login"
            className="mt-1 text-center font-ui text-label text-text-3 hover:text-ember-glow"
          >
            Wróć do logowania
          </Link>
        </form>
      )}
    </div>
  );
}
