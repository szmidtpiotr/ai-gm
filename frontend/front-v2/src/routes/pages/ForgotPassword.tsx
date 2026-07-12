import { useState } from "react";
import { Link } from "react-router-dom";
import { EnvelopeSimple, PaperPlaneTilt } from "@phosphor-icons/react";
import { AuthBrand } from "@/components/shell/AuthLayout";
import { Field, FormNotice } from "@/components/ui/field";
import { Button } from "@/components/ui/button";
import { useForgotPassword } from "@/hooks/useAuth";

// F-04 Zapomniane hasło — wysyłka linku resetującego.
export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const forgot = useForgotPassword();

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    forgot.mutate(email.trim());
  }

  return (
    <div className="text-center">
      <AuthBrand sub="Reset hasła" />

      {forgot.isSuccess ? (
        <div className="flex flex-col gap-4">
          <FormNotice kind="success">
            Jeśli ten adres istnieje w systemie, wysłaliśmy link resetujący.
            Sprawdź skrzynkę.
          </FormNotice>
          <Link to="/login" className="font-ui text-body text-ember-glow">
            Wróć do logowania
          </Link>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="flex flex-col gap-2.5 text-left">
          <p className="mb-1 text-center font-ui text-body text-text-2">
            Podaj adres e-mail — wyślemy link do ustawienia nowego hasła.
          </p>
          <Field
            icon={EnvelopeSimple}
            type="email"
            inputMode="email"
            autoComplete="email"
            placeholder="Adres e-mail"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <Button type="submit" size="lg" className="mt-2" disabled={forgot.isPending}>
            <PaperPlaneTilt weight="fill" size={18} />
            {forgot.isPending ? "Wysyłam…" : "Wyślij link"}
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
