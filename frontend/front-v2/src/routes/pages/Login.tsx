import { Flame } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";

// F-01 placeholder — pełny auth flow w KROKU 2/8 (#1229).
export default function Login() {
  return (
    <div className="mx-auto flex max-w-sm flex-col items-center gap-6 py-10">
      <div className="flex flex-col items-center gap-2">
        <Flame weight="fill" className="text-ember" size={44} />
        <h1 className="font-serif text-title-xl text-text">ŻAR</h1>
        <p className="text-body text-text-3">Wejdź w mrok opowieści</p>
      </div>
      <Card className="w-full p-5">
        <form className="flex flex-col gap-3" onSubmit={(e) => e.preventDefault()}>
          <Input placeholder="E-mail" type="email" autoComplete="username" />
          <Input placeholder="Hasło" type="password" autoComplete="current-password" />
          <Button className="mt-1 w-full">Zaloguj</Button>
          <Button variant="ghost" className="w-full">
            Nowy gracz — załóż konto
          </Button>
        </form>
      </Card>
    </div>
  );
}
