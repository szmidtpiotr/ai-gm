import { useState } from "react";
import { LoginScreen } from "./screens/login-screen";
import { CharacterCreation } from "./screens/character-creation";
import { GameScreen } from "./screens/game-screen";
import { DeathScreen } from "./screens/death-screen";
import { CombatUI } from "./combat-ui";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Eye, X } from "lucide-react";

export function DemoShowcase() {
  const [activeView, setActiveView] = useState<"all" | "login" | "wizard" | "game" | "death">("all");

  // Mock data for game screen
  const mockGameState = {
    character: {
      name: "Aragorn",
      level: 3,
      hp: 18,
      maxHp: 25,
      str: 16,
      dex: 14,
      con: 15,
      int: 10,
      wis: 12,
      cha: 14,
      lck: 11,
    },
    combat: {
      enemy: {
        name: "Goblin Łucznik",
        hp: 12,
        maxHp: 18,
        level: 2,
        armor: 13,
      },
      playerTurn: true,
    },
  };

  const mockMessages = [
    {
      id: "1",
      type: "gm" as const,
      content: "Witaj, wędrowcze. Znajdujesz się w ponurej tawernie 'Srebrny Smok'.",
      timestamp: "14:32",
    },
    {
      id: "2",
      type: "player" as const,
      content: "Rozglądam się po tawernie.",
      timestamp: "14:33",
    },
    {
      id: "3",
      type: "gm" as const,
      content: "Dostrzegasz tajemniczą postać w kapturze siedzącą w kącie. Nagle z cienia wyskakuje goblin!",
      timestamp: "14:33",
    },
    {
      id: "4",
      type: "system" as const,
      content: "Walka rozpoczęta! Goblin Łucznik atakuje!",
      timestamp: "14:33",
    },
  ];

  const mockEnemy = {
    name: "Goblin Łucznik",
    hp: 12,
    maxHp: 18,
    level: 2,
    armor: 13,
  };

  const screens = [
    {
      id: "login",
      name: "Login Screen",
      description: "Punkt wejścia z fantasy estetyką",
      component: <LoginScreen onLogin={() => {}} />
    },
    {
      id: "wizard",
      name: "Character Wizard",
      description: "4-krokowy kreator postaci",
      component: <CharacterCreation onComplete={() => {}} />,
    },
    {
      id: "game",
      name: "Game Screen",
      description: "Główny ekran z czatem i walką",
      component: (
        <GameScreen
          gameState={mockGameState}
          messages={mockMessages}
          onSendMessage={() => {}}
          onAttack={() => {}}
          onFlee={() => {}}
          onLogout={() => {}}
        />
      ),
    },
    {
      id: "death",
      name: "Death Screen",
      description: "Gotycki ekran śmierci",
      component: (
        <DeathScreen
          causeOfDeath="Uległeś swoim ranom w walce z goblinem..."
          onRestart={() => {}}
          onMainMenu={() => {}}
        />
      ),
    },
  ];

  // Full screen view of selected screen
  if (activeView !== "all") {
    const screen = screens.find((s) => s.id === activeView);
    return (
      <div className="relative min-h-screen">
        <div className="fixed top-4 right-4 z-50">
          <Button
            onClick={() => setActiveView("all")}
            variant="outline"
            className="gap-2 bg-[var(--panel)] border-accent/30 shadow-lg"
          >
            <X className="size-4" />
            Zamknij
          </Button>
        </div>
        {screen?.component}
      </div>
    );
  }

  // Grid overview of all screens
  return (
    <div className="min-h-screen bg-gradient-to-b from-[#0a0806] via-[#12100d] to-[#0a0806] p-4 md:p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-accent-light mb-3">
            AI-GM Design Showcase
          </h1>
          <p className="text-muted-foreground mb-1">
            Mroczna gra fantasy RPG • Mobile-first design
          </p>
          <p className="text-sm text-muted-foreground/60 italic">
            Kliknij na ekran, aby zobaczyć go w pełnej wersji
          </p>
        </div>

        {/* Screen Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          {screens.map((screen) => (
            <button
              key={screen.id}
              onClick={() => setActiveView(screen.id as any)}
              className="group relative rounded-xl border border-accent/20 bg-[var(--panel)] overflow-hidden hover:border-accent/50 transition-all hover:shadow-[0_0_30px_rgba(183,122,43,0.25)]"
            >
              {/* Screen Label */}
              <div className="absolute top-3 left-3 z-10 px-3 py-1.5 rounded-lg bg-[var(--bg)]/95 backdrop-blur border border-accent/30 shadow-lg">
                <h2 className="text-sm font-semibold text-accent-light">
                  {screen.name}
                </h2>
                <p className="text-xs text-muted-foreground">
                  {screen.description}
                </p>
              </div>

              {/* Hover Overlay */}
              <div className="absolute inset-0 bg-gradient-to-t from-[var(--bg)] via-transparent to-transparent opacity-0 group-hover:opacity-70 transition-opacity z-10 pointer-events-none" />

              {/* Click to View Button */}
              <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20 opacity-0 group-hover:opacity-100 transition-opacity">
                <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent text-[var(--bg)] font-semibold text-sm shadow-lg">
                  <Eye className="size-4" />
                  Kliknij aby zobaczyć
                </div>
              </div>

              {/* Screen Preview (scaled down) */}
              <div className="aspect-[9/16] overflow-hidden scale-50 origin-top-left w-[200%] h-[200%] pointer-events-none">
                {screen.component}
              </div>
            </button>
          ))}
        </div>

        {/* Combat Panel Demo */}
        <div className="max-w-2xl mx-auto mb-8">
          <div className="rounded-xl border border-accent/20 bg-[var(--panel)]/50 backdrop-blur p-6">
            <h3 className="text-lg font-semibold text-accent-light mb-3">Panel Walki (Combat UI)</h3>
            <p className="text-sm text-muted-foreground mb-4">
              Zwijany banner - minimalizowany pokazuje HP wroga, rozwinięty pokazuje akcje walki
            </p>

            <div className="space-y-4">
              <div>
                <p className="text-xs text-accent mb-2">Stan domyślny (zminimalizowany):</p>
                <Card className="p-4 bg-[var(--bg)]">
                  <CombatUI
                    enemy={mockEnemy}
                    playerTurn={true}
                    onAttack={() => {}}
                    onFlee={() => {}}
                  />
                </Card>
                <p className="text-xs text-muted-foreground mt-2 italic">
                  ⬆️ Kliknij na panel aby rozwinąć i zobaczyć przyciski akcji
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Project Info */}
        <div className="max-w-2xl mx-auto rounded-xl border border-accent/20 bg-[var(--panel)]/50 backdrop-blur p-6">
          <h3 className="text-lg font-semibold text-accent-light mb-3">Informacje projektowe</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm text-muted-foreground">
            <div className="flex items-start gap-2">
              <span className="text-accent">•</span>
              <span>Mobile-first (320px min, 390px ideal)</span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-accent">•</span>
              <span>Dark fantasy z złotymi akcentami</span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-accent">•</span>
              <span>Polski UI z angielskimi statystykami</span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-accent">•</span>
              <span>Zakładki w karcie postaci</span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-accent">•</span>
              <span>Zwijany banner walki</span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-accent">•</span>
              <span>Dostosowanie czcionki w ustawieniach</span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-8 text-center">
          <p className="text-xs text-muted-foreground/60">
            Zbudowane w React + Tailwind CSS • Zainspirowane Warhammer Fantasy, D&D, Baldur's Gate
          </p>
        </div>
      </div>
    </div>
  );
}
