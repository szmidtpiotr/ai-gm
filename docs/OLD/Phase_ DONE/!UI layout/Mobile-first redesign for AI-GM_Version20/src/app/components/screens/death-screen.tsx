import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Skull, RotateCcw, Home, Flame } from "lucide-react";

interface DeathScreenProps {
  causeOfDeath?: string;
  onRestart: () => void;
  onMainMenu: () => void;
}

export function DeathScreen({
  causeOfDeath = "Uległeś swoim ranom...",
  onRestart,
  onMainMenu,
}: DeathScreenProps) {
  return (
    <div
      id="death-screen"
      className="flex min-h-screen flex-col items-center justify-center p-4 bg-gradient-to-b from-[#0a0806] via-[#1a0a0a] to-[#0a0806]"
    >
      {/* Tombstone Card */}
      <Card className="relative w-full max-w-sm border-destructive/40 bg-gradient-to-b from-[#1a1410] to-[#0f0b09] p-8 text-center shadow-[0_0_40px_rgba(185,28,28,0.3)]">
        {/* Decorative top arch */}
        <div className="absolute -top-8 left-1/2 -translate-x-1/2 w-32 h-16 rounded-t-full bg-gradient-to-b from-[#1a1410] to-transparent border-t border-l border-r border-destructive/40" />

        {/* Skull Icon */}
        <div className="mb-6 flex justify-center relative">
          <div className="absolute inset-0 blur-xl opacity-50">
            <Skull className="size-20 text-destructive mx-auto" />
          </div>
          <Skull className="size-20 text-destructive relative z-10" />
        </div>

        {/* Epitaph */}
        <div className="mb-6 space-y-3">
          <div className="h-px w-24 mx-auto bg-gradient-to-r from-transparent via-destructive to-transparent opacity-50" />
          <h1 className="text-3xl font-bold tracking-wider text-destructive">
            REQUIESCAT
          </h1>
          <h2 className="text-lg font-semibold text-destructive/80">
            IN PACE
          </h2>
          <div className="h-px w-24 mx-auto bg-gradient-to-r from-transparent via-destructive to-transparent opacity-50" />
        </div>

        {/* Cause of Death */}
        <div className="mb-8 px-4">
          <p className="text-sm text-muted italic leading-relaxed">
            "{causeOfDeath}"
          </p>
          <div className="mt-3 flex items-center justify-center gap-2">
            <Flame className="size-3 text-destructive/60" />
            <p className="text-xs text-muted-foreground">
              Niech Twoja dusza spocznie w mroku
            </p>
            <Flame className="size-3 text-destructive/60" />
          </div>
        </div>

        {/* Actions */}
        <div className="space-y-2">
          <Button
            id="death-restart"
            onClick={onRestart}
            className="w-full gap-2 bg-destructive hover:bg-destructive/90 text-white font-semibold"
            size="lg"
          >
            <RotateCcw className="size-4" />
            Powstań na nowo
          </Button>
          <Button
            id="death-main-menu"
            onClick={onMainMenu}
            variant="outline"
            className="w-full gap-2 border-destructive/30 hover:bg-destructive/10"
          >
            <Home className="size-4" />
            Powrót do menu
          </Button>
        </div>

        {/* Decorative flames */}
        <div className="absolute -bottom-2 left-0 right-0 flex justify-center gap-4 opacity-30">
          <Flame className="size-4 text-destructive" />
          <Flame className="size-4 text-destructive" />
          <Flame className="size-4 text-destructive" />
        </div>
      </Card>

      {/* Background atmosphere */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden -z-10">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-destructive/5 rounded-full blur-[120px]" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-destructive/5 rounded-full blur-[120px]" />
      </div>
    </div>
  );
}
