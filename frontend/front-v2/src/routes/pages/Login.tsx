import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { EnvelopeSimple, LockSimple, SignIn } from "@phosphor-icons/react";
import { AuthBrand } from "@/components/shell/AuthLayout";
import { Field, FormNotice } from "@/components/ui/field";
import { Button } from "@/components/ui/button";
import { useLogin } from "@/hooks/useAuth";
import { APIError } from "@/lib/api";

// F-01 Login. Makieta 1:1 → zar8-login.html.
export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [params] = useSearchParams();
  const join = params.get("join");
  const campaign = params.get("campaign");
  const navigate = useNavigate();
  const login = useLogin();

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    login.mutate(
      { username: username.trim(), password },
      {
        onSuccess: () => {
          // Deep-link: po zalogowaniu wróć do celu zaproszenia / gry (§11).
          if (campaign) navigate(`/gra/${encodeURIComponent(campaign)}`, { replace: true });
          else if (join) navigate(`/bohaterowie?join=${encodeURIComponent(join)}`, { replace: true });
          else navigate("/bohaterowie", { replace: true });
        },
      },
    );
  }

  const err = login.error as APIError | null;

  return (
    <div className="text-center">
      <AuthBrand />

      <form onSubmit={onSubmit} className="flex flex-col gap-2.5 text-left">
        {join && (
          <FormNotice kind="info">
            Masz zaproszenie do gry. Zaloguj się na swoje konto, aby dołączyć —
            albo{" "}
            <Link
              to={`/rejestracja?join=${encodeURIComponent(join)}`}
              className="font-semibold text-ember-glow"
            >
              załóż nowe
            </Link>
            .
          </FormNotice>
        )}

        <Field
          icon={EnvelopeSimple}
          type="text"
          inputMode="email"
          autoComplete="username"
          placeholder="Adres e-mail lub nazwa gracza"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
        />
        <Field
          icon={LockSimple}
          type="password"
          revealable
          autoComplete="current-password"
          placeholder="Hasło"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />

        <Link
          to="/zapomniane-haslo"
          className="-mt-0.5 text-right font-ui text-[12.5px] text-text-2 hover:text-ember-glow"
        >
          Nie pamiętasz hasła?
        </Link>

        {err && (
          <FormNotice kind="error">
            {err.status === 403
              ? "Potwierdź swój adres e-mail, aby się zalogować."
              : err.status === 423
                ? "Konto tymczasowo zablokowane. Spróbuj ponownie za chwilę."
                : "Nieprawidłowy login lub hasło."}
          </FormNotice>
        )}

        <Button type="submit" size="lg" className="mt-2" disabled={login.isPending}>
          <SignIn weight="fill" size={18} />
          {login.isPending ? "Wchodzę…" : "Wejdź do gry"}
        </Button>
      </form>

      <div className="my-4 flex items-center gap-3 font-ui text-[11px] uppercase tracking-[0.12em] text-text-3">
        <span className="h-px flex-1 bg-line" />
        albo
        <span className="h-px flex-1 bg-line" />
      </div>

      <p className="font-ui text-body text-text-2">
        Pierwszy raz w Kresach?{" "}
        <Link
          to={join ? `/rejestracja?join=${encodeURIComponent(join)}` : "/rejestracja"}
          className="font-semibold text-ember-glow"
        >
          Załóż konto
        </Link>
      </p>
    </div>
  );
}
