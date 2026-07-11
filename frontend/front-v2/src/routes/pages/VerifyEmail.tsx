import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { EnvelopeOpen, EnvelopeSimple, CheckCircle, ArrowClockwise } from "@phosphor-icons/react";
import { AuthBrand } from "@/components/shell/AuthLayout";
import { Field, FormNotice } from "@/components/ui/field";
import { Button } from "@/components/ui/button";
import { useVerifyEmail } from "@/hooks/useAuth";
import { apiFetch, APIError } from "@/lib/api";

// F-03 Weryfikacja e-mail. Z linku (?token=) auto-potwierdza; bez tokenu —
// ekran „sprawdź skrzynkę" + ponowne wysłanie. #895: ponowne wysłanie idzie
// publicznym endpointem po adresie e-mail (bez tokenu), by rozbić deadlock
// niezweryfikowanego konta z wygasłym linkiem.
export default function VerifyEmail() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const navigate = useNavigate();
  const verify = useVerifyEmail();
  const fired = useRef(false);
  const [resent, setResent] = useState<null | "ok" | "err">(null);
  const [busy, setBusy] = useState(false);
  const [email, setEmail] = useState(params.get("email") ?? "");

  useEffect(() => {
    if (token && !fired.current) {
      fired.current = true;
      verify.mutate(token, {
        onSuccess: (d) => {
          if (d.access_token) setTimeout(() => navigate("/bohaterowie", { replace: true }), 1200);
        },
      });
    }
  }, [token, verify, navigate]);

  async function resend() {
    const addr = email.trim().toLowerCase();
    if (!addr || !addr.includes("@")) {
      setResent("err");
      return;
    }
    setBusy(true);
    try {
      // Publiczny wariant: zawsze 200, rate-limit 120s po stronie serwera.
      await apiFetch("/auth/resend-verification-public", {
        method: "POST",
        body: { email: addr },
        anon: true,
      });
      setResent("ok");
    } catch {
      setResent("err");
    } finally {
      setBusy(false);
    }
  }

  const err = verify.error as APIError | null;
  // Ponowne wysłanie ma sens dopóki adres nie został właśnie potwierdzony.
  const showResend = !verify.isSuccess;

  return (
    <div className="text-center">
      <AuthBrand sub="Potwierdź e-mail" />

      <div className="flex flex-col gap-4">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-xl border border-line text-ember-glow">
          {verify.isSuccess ? (
            <CheckCircle weight="fill" size={34} className="text-success" />
          ) : (
            <EnvelopeOpen size={30} />
          )}
        </div>

        {token ? (
          verify.isPending ? (
            <p className="font-ui text-body text-text-2">Potwierdzam adres…</p>
          ) : verify.isSuccess ? (
            <FormNotice kind="success">
              Adres potwierdzony. Wchodzę do gry…
            </FormNotice>
          ) : (
            <FormNotice kind="error">
              {err?.status === 410
                ? "Link wygasł. Wyślij nowy poniżej."
                : err?.status === 409
                  ? "Ten link został już użyty."
                  : "Nieprawidłowy link weryfikacyjny."}
            </FormNotice>
          )
        ) : (
          <p className="font-ui text-body text-text-2">
            Wysłaliśmy link weryfikacyjny na Twój adres e-mail. Otwórz go, aby
            aktywować konto.
          </p>
        )}

        {resent === "ok" && (
          <FormNotice kind="success">
            Jeśli konto wymaga weryfikacji, nowy link jest już w drodze. Sprawdź
            skrzynkę (także spam).
          </FormNotice>
        )}
        {resent === "err" && (
          <FormNotice kind="error">
            Podaj poprawny adres e-mail konta, aby wysłać nowy link.
          </FormNotice>
        )}

        {showResend && (
          <>
            <Field
              icon={EnvelopeSimple}
              type="email"
              inputMode="email"
              autoComplete="email"
              placeholder="Adres e-mail konta"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <Button variant="secondary" onClick={resend} disabled={busy}>
              <ArrowClockwise size={18} /> {busy ? "Wysyłam…" : "Wyślij link ponownie"}
            </Button>
          </>
        )}

        <Link to="/login" className="font-ui text-label text-text-3 hover:text-ember-glow">
          Wróć do logowania
        </Link>
      </div>
    </div>
  );
}
