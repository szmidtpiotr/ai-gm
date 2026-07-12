import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  EnvelopeSimple,
  LockSimple,
  User,
  Ticket,
  UserPlus,
} from "@phosphor-icons/react";
import { AuthBrand } from "@/components/shell/AuthLayout";
import { Field, FormNotice } from "@/components/ui/field";
import { Button } from "@/components/ui/button";
import { useRegister } from "@/hooks/useAuth";
import { APIError } from "@/lib/api";

// F-02 Rejestracja — konto przez kod zaproszenia (rejestracja zamknięta).
export default function Register() {
  const [params] = useSearchParams();
  const join = params.get("join");
  const [form, setForm] = useState({
    username: "",
    email: "",
    invite_code: params.get("invite") ?? "",
    password: "",
  });
  const navigate = useNavigate();
  const register = useRegister();
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    register.mutate(
      {
        username: form.username.trim(),
        password: form.password,
        invite_code: form.invite_code.trim(),
        email: form.email.trim() || undefined,
      },
      {
        onSuccess: (data) => {
          if (data.access_token) {
            if (join) navigate(`/bohaterowie?join=${encodeURIComponent(join)}`, { replace: true });
            else navigate("/bohaterowie", { replace: true });
          } else {
            navigate("/weryfikacja-email", { replace: true });
          }
        },
      },
    );
  }

  const err = register.error as APIError | null;

  return (
    <div className="text-center">
      <AuthBrand sub="Załóż konto" />

      <form onSubmit={onSubmit} className="flex flex-col gap-2.5 text-left">
        <Field
          icon={Ticket}
          placeholder="Kod zaproszenia"
          value={form.invite_code}
          onChange={set("invite_code")}
          autoComplete="off"
          required
        />
        <Field
          icon={User}
          placeholder="Nazwa gracza (3–30 znaków)"
          value={form.username}
          onChange={set("username")}
          autoComplete="username"
          required
        />
        <Field
          icon={EnvelopeSimple}
          type="email"
          inputMode="email"
          placeholder="Adres e-mail"
          value={form.email}
          onChange={set("email")}
          autoComplete="email"
        />
        <Field
          icon={LockSimple}
          type="password"
          revealable
          placeholder="Hasło (min. 8 znaków)"
          value={form.password}
          onChange={set("password")}
          autoComplete="new-password"
          required
        />

        {err && <FormNotice kind="error">{err.message}</FormNotice>}

        <Button type="submit" size="lg" className="mt-2" disabled={register.isPending}>
          <UserPlus weight="fill" size={18} />
          {register.isPending ? "Zakładam konto…" : "Załóż konto"}
        </Button>
      </form>

      <p className="mt-5 font-ui text-body text-text-2">
        Masz już konto?{" "}
        <Link
          to={join ? `/login?join=${encodeURIComponent(join)}` : "/login"}
          className="font-semibold text-ember-glow"
        >
          Zaloguj się
        </Link>
      </p>
    </div>
  );
}
