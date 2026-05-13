import { useState, useRef, TouchEvent } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { Card } from "./ui/card";
import { ScrollArea } from "./ui/scroll-area";
import { Backpack, Scroll, User } from "lucide-react";

interface CharacterSheetTabsProps {
  character: {
    name: string;
    level: number;
    hp: number;
    maxHp: number;
    str: number;
    dex: number;
    con: number;
    int: number;
    wis: number;
    cha: number;
    lck: number;
  };
}

const statLabels = {
  str: "Siła",
  dex: "Zręczność",
  con: "Kondycja",
  int: "Intelekt",
  wis: "Mądrość",
  cha: "Charyzma",
  lck: "Szczęście",
};

export function CharacterSheetTabs({ character }: CharacterSheetTabsProps) {
  const [activeTab, setActiveTab] = useState("stats");
  const touchStartX = useRef<number>(0);
  const touchEndX = useRef<number>(0);

  const tabs = ["stats", "skills", "inventory"];

  const handleTouchStart = (e: TouchEvent) => {
    touchStartX.current = e.touches[0].clientX;
  };

  const handleTouchMove = (e: TouchEvent) => {
    touchEndX.current = e.touches[0].clientX;
  };

  const handleTouchEnd = () => {
    const swipeThreshold = 50;
    const diff = touchStartX.current - touchEndX.current;

    if (Math.abs(diff) > swipeThreshold) {
      const currentIndex = tabs.indexOf(activeTab);
      if (diff > 0 && currentIndex < tabs.length - 1) {
        // Swipe left - next tab
        setActiveTab(tabs[currentIndex + 1]);
      } else if (diff < 0 && currentIndex > 0) {
        // Swipe right - previous tab
        setActiveTab(tabs[currentIndex - 1]);
      }
    }
  };

  const getModifier = (stat: number) => {
    return Math.floor((stat - 10) / 2);
  };

  return (
    <div
      id="character-sheet-tabs"
      className="flex h-full flex-col"
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
    >
      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex flex-1 flex-col">
        <TabsList className="grid w-full grid-cols-3 bg-[var(--panel-2)]">
          <TabsTrigger value="stats" className="gap-2">
            <User className="size-4" />
            <span className="hidden sm:inline">Statystyki</span>
          </TabsTrigger>
          <TabsTrigger value="skills" className="gap-2">
            <Scroll className="size-4" />
            <span className="hidden sm:inline">Umiejętności</span>
          </TabsTrigger>
          <TabsTrigger value="inventory" className="gap-2">
            <Backpack className="size-4" />
            <span className="hidden sm:inline">Ekwipunek</span>
          </TabsTrigger>
        </TabsList>

        <ScrollArea className="flex-1">
          <TabsContent value="stats" className="m-0 p-4">
            {/* HP Bar */}
            <Card className="p-3 bg-gradient-to-br from-[var(--panel)] to-[var(--panel-2)] border-accent/20 mb-3">
              <div className="flex justify-between items-baseline mb-2">
                <span className="text-xs text-muted uppercase tracking-wide">Punkty Życia</span>
                <span className="font-bold text-foreground">
                  {character.hp} / {character.maxHp}
                </span>
              </div>
              <div className="h-2.5 w-full bg-[#1a1410] rounded-full overflow-hidden border border-accent/20">
                <div
                  className="h-full bg-gradient-to-r from-[#15803d] to-[#22c55e] transition-all duration-300 rounded-full"
                  style={{ width: `${(character.hp / character.maxHp) * 100}%` }}
                />
              </div>
            </Card>

            {/* Level */}
            <Card className="p-3 bg-[var(--panel)]/60 border-accent/20 mb-3">
              <div className="flex justify-between items-center">
                <span className="text-xs text-muted uppercase">Poziom</span>
                <span className="font-bold text-accent-light">{character.level}</span>
              </div>
            </Card>

            {/* Compact Stats List */}
            <Card className="p-3 bg-[var(--panel)]/60 border-accent/20">
              <div className="space-y-2">
                {Object.entries(character).map(([key, value]) => {
                  if (!['str', 'dex', 'con', 'int', 'wis', 'cha', 'lck'].includes(key)) return null;
                  const modifier = getModifier(value as number);
                  const modifierStr = modifier >= 0 ? `+${modifier}` : `${modifier}`;

                  return (
                    <div key={key} className="flex items-center justify-between text-sm">
                      <span className="text-muted uppercase text-xs">
                        {statLabels[key as keyof typeof statLabels]}
                      </span>
                      <div className="flex items-baseline gap-2">
                        <span className="font-bold text-accent-light">{value}</span>
                        <span className="text-xs text-accent font-medium min-w-[28px] text-right">{modifierStr}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>

            <p className="text-xs text-muted/60 text-center mt-4 italic">
              Przesuń palcem w lewo/prawo, aby zmienić zakładkę
            </p>
          </TabsContent>

          <TabsContent value="skills" className="m-0 p-4">
            <div className="space-y-2">
              <h3 className="font-semibold text-accent-light mb-3">Umiejętności</h3>
              <div className="space-y-2">
                {[
                  { name: "Atletyka", level: 2, max: 5, attr: "STR" },
                  { name: "Skradanie", level: 3, max: 5, attr: "DEX" },
                  { name: "Arkana", level: 1, max: 5, attr: "INT" },
                  { name: "Perswazja", level: 2, max: 5, attr: "CHA" },
                  { name: "Przetrwanie", level: 2, max: 5, attr: "WIS" },
                  { name: "Percepcja", level: 1, max: 5, attr: "WIS" },
                ].map((skill) => (
                  <Card
                    key={skill.name}
                    className="p-3 bg-[var(--panel)]/60 border-accent/20"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="font-medium text-foreground">{skill.name}</div>
                        <div className="text-xs text-muted">Atrybut: {skill.attr}</div>
                      </div>
                      <div className="flex gap-1">
                        {Array.from({ length: skill.max }).map((_, i) => (
                          <div
                            key={i}
                            className={`size-2.5 rounded-full border ${
                              i < skill.level
                                ? "bg-accent border-accent"
                                : "border-muted/30"
                            }`}
                          />
                        ))}
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            </div>

            <p className="text-xs text-muted/60 text-center mt-4 italic">
              Przesuń palcem w lewo/prawo, aby zmienić zakładkę
            </p>
          </TabsContent>

          <TabsContent value="inventory" className="m-0 p-4">
            <div className="space-y-3">
              <h3 className="font-semibold text-accent-light">Ekwipunek</h3>

              {/* Gold */}
              <Card className="p-4 bg-gradient-to-br from-accent/10 to-accent/5 border-accent/30">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted">Złoto</span>
                  <span className="text-xl font-bold text-accent">127 zł</span>
                </div>
              </Card>

              {/* Items */}
              <div className="space-y-2">
                {[
                  { name: "Zardzewiały miecz", type: "Broń", rarity: "common" },
                  { name: "Skórzana zbroja", type: "Zbroja", rarity: "common" },
                  { name: "Eliksir leczenia", type: "Przedmiot", count: 2, rarity: "uncommon" },
                  { name: "Amulet ochrony", type: "Talizman", rarity: "rare" },
                ].map((item, i) => (
                  <Card
                    key={i}
                    className="p-3 bg-[var(--panel)]/60 border-accent/20"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="font-medium text-foreground">{item.name}</div>
                        <div className="text-xs text-muted">{item.type}</div>
                      </div>
                      {item.count && (
                        <div className="text-sm text-muted">x{item.count}</div>
                      )}
                    </div>
                  </Card>
                ))}
              </div>
            </div>

            <p className="text-xs text-muted/60 text-center mt-4 italic">
              Przesuń palcem w lewo/prawo, aby zmienić zakładkę
            </p>
          </TabsContent>
        </ScrollArea>
      </Tabs>
    </div>
  );
}
