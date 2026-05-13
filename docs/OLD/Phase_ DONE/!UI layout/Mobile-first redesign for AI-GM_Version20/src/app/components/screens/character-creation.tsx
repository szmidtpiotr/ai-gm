/**
 * Character Creation Screen
 *
 * Purpose: 4-step wizard for creating new characters in a campaign
 * User Actions: Name/archetype → stat allocation → skill selection → backstory editing
 * Related Spec: src/imports/09-character-wizard-spec.md
 * Stable IDs: #character-creation, #character-name, #class-warrior, #class-scholar
 *
 * Steps:
 * 1. Name, archetype (Wojownik/Uczony), background text
 * 2. Stat adjustment (+/- buttons, 8-18 range)
 * 3. Skill selection with exchange drawer (18 skills available)
 * 4. Appearance/personality editing (AI-generated defaults)
 */

import { useState } from "react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Card } from "../ui/card";
import { Drawer, DrawerContent, DrawerTitle, DrawerDescription, DrawerClose } from "../ui/drawer";
import { ScrollArea } from "../ui/scroll-area";
import { Minus, Plus, Lock, Scroll, RefreshCw, Sparkles, Sword, BookOpen, ChevronRight, ArrowRightLeft, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface CharacterData {
  name: string;
  class: string;
  background: string;
  stats: {
    str: number;
    dex: number;
    con: number;
    int: number;
    wis: number;
    cha: number;
    lck: number;
  };
  skills: Record<string, { level: number; name: string }>;
  appearance: string;
  personality: string;
  flaw: string;
  bond: string;
}

interface CharacterCreationProps {
  onComplete: (character: CharacterData) => void;
}

const archetypes = [
  {
    id: "warrior",
    name: "Wojownik",
    icon: Sword,
    description: "Mistrz walki wręcz, odporny na ból, siła i wytrzymałość to jego największe atuty."
  },
  {
    id: "scholar",
    name: "Uczony",
    icon: BookOpen,
    description: "Tkacz arkanów i strażnik wiedzy, kruchy ciałem lecz potężny umysłem."
  },
];

const initialSkills = [
  { id: "endurance", name: "Wytrzymałość", attr: "CON", level: 2, label: "Wprawny" },
  { id: "athletics", name: "Atletyka", attr: "STR", level: 1, label: "Trenowany" },
  { id: "investigation", name: "Śledztwo", attr: "INT", level: 1, label: "Trenowany" },
  { id: "lore", name: "Wiedza", attr: "INT", level: 1, label: "Trenowany" },
  { id: "melee", name: "Walka Wręcz", attr: "STR", level: 1, label: "Trenowany" },
  { id: "sleight", name: "Zręczne Dłonie", attr: "DEX", level: 1, label: "Trenowany" },
  { id: "survival", name: "Przetrwanie", attr: "WIS", level: 1, label: "Trenowany" },
];

const allAvailableSkills = [
  { id: "athletics", name: "Atletyka", attr: "STR", description: "Wspinaczka, pływanie, skoki" },
  { id: "endurance", name: "Wytrzymałość", attr: "CON", description: "Odporność na trudy i zmęczenie" },
  { id: "melee", name: "Walka Wręcz", attr: "STR", description: "Walka mieczem, toporem, włócznią" },
  { id: "ranged", name: "Walka Dystansowa", attr: "DEX", description: "Łuki, kusze, broń miotana" },
  { id: "stealth", name: "Skradanie", attr: "DEX", description: "Ciche poruszanie się, ukrywanie" },
  { id: "sleight", name: "Zręczne Dłonie", attr: "DEX", description: "Kradzież kieszonkowa, sztuczki" },
  { id: "acrobatics", name: "Akrobatyka", attr: "DEX", description: "Uniki, przewroty, równowaga" },
  { id: "investigation", name: "Śledztwo", attr: "INT", description: "Analiza śladów, tropienie" },
  { id: "lore", name: "Wiedza", attr: "INT", description: "Historia, kultura, legendy" },
  { id: "arcana", name: "Arkana", attr: "INT", description: "Magia, zaklęcia, artefakty" },
  { id: "medicine", name: "Medycyna", attr: "WIS", description: "Leczenie ran, ziołolecznictwo" },
  { id: "perception", name: "Percepcja", attr: "WIS", description: "Wyostrzenie zmysłów, obserwacja" },
  { id: "survival", name: "Przetrwanie", attr: "WIS", description: "Orientacja w terenie, tropienie" },
  { id: "insight", name: "Wnikliwość", attr: "WIS", description: "Odczytywanie intencji, kłamstwa" },
  { id: "persuasion", name: "Perswazja", attr: "CHA", description: "Przekonywanie, negocjacje" },
  { id: "deception", name: "Oszustwo", attr: "CHA", description: "Kłamstwo, manipulacja" },
  { id: "intimidation", name: "Zastraszanie", attr: "CHA", description: "Groźby, dominacja" },
  { id: "performance", name: "Występy", attr: "CHA", description: "Muzyka, taniec, aktorstwo" },
];

const statLabels = {
  str: "Siła",
  dex: "Zręczność",
  con: "Kondycja",
  int: "Intelekt",
  wis: "Mądrość",
  cha: "Charyzma",
  lck: "Szczęście",
};

export function CharacterCreation({ onComplete }: CharacterCreationProps) {
  const [step, setStep] = useState(0);

  const [character, setCharacter] = useState<CharacterData>({
    name: "",
    class: "",
    background: "",
    stats: { str: 16, dex: 8, con: 9, int: 18, wis: 13, cha: 11, lck: 10 },
    skills: initialSkills.reduce((acc, skill) => ({ ...acc, [skill.id]: { level: skill.level, name: skill.name } }), {}),
    appearance: "Jest potężnie zbudowany, z szerokimi ramionami i licznymi bliznami na przedramionach. Ma krótkie, ciemne włosy oraz surowe, stalowoniebieskie oczy, które rzadko okazują emocje.",
    personality: "Jest stanowczy i nieustępliwy, zawsze dąży do celu bez względu na przeciwności. Często działa impulsywnie, ufając własnej sile.",
    flaw: "Często popada w gniew, co prowadzi do pochopnych decyzji w walce. Ma trudności z okazywaniem słabości.",
    bond: "Przysiągł bronić swojej rodzinnej wioski przed wszelkim zagrożeniem.",
  });

  const [unassignedPoints, setUnassignedPoints] = useState(0);
  const [skillsChanged, setSkillsChanged] = useState(0);
  const [skillExchangeOpen, setSkillExchangeOpen] = useState(false);
  const [skillToExchange, setSkillToExchange] = useState<{ id: string; level: number; name: string } | null>(null);

  const totalSteps = 4;

  const handleNext = () => {
    if (step < totalSteps - 1) {
      setStep(step + 1);
    } else {
      onComplete(character);
    }
  };

  const handleBack = () => {
    if (step > 0) setStep(step - 1);
  };

  const canProceed = () => {
    switch (step) {
      case 0:
        return character.name.trim().length > 0 && character.class.length > 0;
      case 1:
        return unassignedPoints >= 0;
      case 2:
        return skillsChanged <= 4;
      case 3:
        return true;
      default:
        return false;
    }
  };

  const adjustStat = (stat: keyof CharacterData["stats"], delta: number) => {
    const currentVal = character.stats[stat];
    if (delta > 0 && unassignedPoints > 0 && currentVal < 18) {
      setCharacter({ ...character, stats: { ...character.stats, [stat]: currentVal + 1 } });
      setUnassignedPoints(prev => prev - 1);
    } else if (delta < 0 && currentVal > 8) {
      setCharacter({ ...character, stats: { ...character.stats, [stat]: currentVal - 1 } });
      setUnassignedPoints(prev => prev + 1);
    }
  };

  const adjustSkill = (skillId: string, delta: number) => {
    const currentLevel = character.skills[skillId].level;
    if (delta > 0 && skillsChanged < 4 && currentLevel < 3) {
      setCharacter(prev => ({
        ...prev,
        skills: { ...prev.skills, [skillId]: { ...prev.skills[skillId], level: currentLevel + 1 } }
      }));
      setSkillsChanged(prev => prev + 1);
    } else if (delta < 0 && currentLevel > 0) {
      setCharacter(prev => ({
        ...prev,
        skills: { ...prev.skills, [skillId]: { ...prev.skills[skillId], level: currentLevel - 1 } }
      }));
      setSkillsChanged(prev => prev + 1);
    }
  };

  const handleResetStats = () => {
    setCharacter({
      ...character,
      stats: { str: 16, dex: 8, con: 9, int: 18, wis: 13, cha: 11, lck: 10 }
    });
    setUnassignedPoints(0);
  };

  const handleResetSkills = () => {
    setCharacter({
      ...character,
      skills: initialSkills.reduce((acc, skill) => ({ ...acc, [skill.id]: { level: skill.level, name: skill.name } }), {})
    });
    setSkillsChanged(0);
  };

  const handleOpenSkillExchange = (skillId: string) => {
    const skill = character.skills[skillId];
    if (skill) {
      setSkillToExchange({ id: skillId, level: skill.level, name: skill.name });
      setSkillExchangeOpen(true);
    }
  };

  const handleExchangeSkill = (newSkillId: string) => {
    if (!skillToExchange) return;

    const newSkill = allAvailableSkills.find(s => s.id === newSkillId);
    if (!newSkill) return;

    // Remove old skill and add new skill with same level
    const updatedSkills = { ...character.skills };
    delete updatedSkills[skillToExchange.id];
    updatedSkills[newSkillId] = { level: skillToExchange.level, name: newSkill.name };

    setCharacter({ ...character, skills: updatedSkills });
    setSkillExchangeOpen(false);
    setSkillToExchange(null);
  };

  const stepTitles = [
    "Tożsamość bohatera",
    "Atrybuty",
    "Umiejętności",
    "Historia postaci"
  ];

  return (
    <div
      id="character-creation"
      className="flex min-h-screen flex-col bg-gradient-to-b from-[#0a0806] via-[#12100d] to-[#0a0806]"
    >
      {/* Header */}
      <div className="sticky top-0 z-10 bg-[var(--top-bar)]/95 backdrop-blur border-b border-accent/20 shadow-[0_2px_16px_rgba(0,0,0,0.4)]">
        <div className="flex items-center gap-3 p-4">
          <Scroll className="size-6 text-accent" />
          <div className="flex-1">
            <h1 className="text-lg font-semibold text-accent-light">{stepTitles[step]}</h1>
            <p className="text-xs text-muted">Krok {step + 1} z {totalSteps}</p>
          </div>
        </div>
        {/* Progress bar */}
        <div className="h-1 bg-[var(--panel)]">
          <div
            className="h-full bg-gradient-to-r from-accent-dark via-accent to-accent-light transition-all duration-500"
            style={{ width: `${((step + 1) / totalSteps) * 100}%` }}
          />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="max-w-2xl mx-auto space-y-4">
          {/* Step 0: Name & Archetype */}
          {step === 0 && (
            <div className="space-y-4">
              <Card className="p-5 bg-[var(--panel)]/80 border-accent/20">
                <p className="text-sm text-muted leading-relaxed">
                  Nie masz jeszcze bohatera w tej kampanii. Przygotuj kartę i zacznij przygodę.
                </p>
              </Card>

              <Card className="p-5 bg-[var(--panel)]/80 border-accent/20 space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="character-name" className="text-accent-light">
                    Imię postaci
                  </Label>
                  <Input
                    id="character-name"
                    value={character.name}
                    onChange={(e) => setCharacter({ ...character, name: e.target.value })}
                    placeholder="np. Aldric z Północy"
                    className="bg-[var(--input-background)] border-accent/30 focus:border-accent"
                    autoFocus
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="character-background" className="text-accent-light">
                    Historia / Tło Postaci
                  </Label>
                  <textarea
                    id="character-background"
                    value={character.background}
                    onChange={(e) => setCharacter({ ...character, background: e.target.value })}
                    placeholder="Kim był twój bohater przed początkiem kampanii?"
                    className="w-full min-h-[100px] rounded-md border border-accent/30 bg-[var(--input-background)] px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:border-accent resize-none"
                  />
                </div>
              </Card>

              <div className="space-y-3">
                <Label className="text-accent-light px-1">Archetyp</Label>
                {archetypes.map((arch) => {
                  const Icon = arch.icon;
                  return (
                    <Card
                      key={arch.id}
                      id={`class-${arch.id}`}
                      onClick={() => setCharacter({ ...character, class: arch.id })}
                      className={cn(
                        "p-5 cursor-pointer transition-all active:scale-[0.98]",
                        character.class === arch.id
                          ? "bg-gradient-to-br from-accent/20 to-accent/10 border-accent shadow-[0_0_20px_rgba(183,122,43,0.15)]"
                          : "bg-[var(--panel)]/60 border-accent/20 hover:border-accent/40 hover:bg-[var(--panel-2)]/60"
                      )}
                    >
                      <div className="flex items-start gap-4">
                        <div className={cn(
                          "flex-shrink-0 size-12 rounded-lg flex items-center justify-center",
                          character.class === arch.id
                            ? "bg-accent/30 border border-accent/40"
                            : "bg-accent/10 border border-accent/20"
                        )}>
                          <Icon className="size-6 text-accent" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <h3 className="font-semibold text-foreground mb-1">{arch.name}</h3>
                          <p className="text-sm text-muted leading-relaxed">{arch.description}</p>
                        </div>
                        {character.class === arch.id && (
                          <div className="flex-shrink-0 size-5 rounded-full bg-accent flex items-center justify-center">
                            <Sparkles className="size-3 text-[var(--bg)]" />
                          </div>
                        )}
                      </div>
                    </Card>
                  );
                })}
              </div>
            </div>
          )}

          {/* Step 1: Stats */}
          {step === 1 && (
            <div className="space-y-4">
              <Card className="p-5 bg-[var(--panel)]/80 border-accent/20">
                <h2 className="font-semibold text-foreground mb-2">Dostosuj atrybuty</h2>
                <p className="text-sm text-muted leading-relaxed">
                  Przenieś punkty do puli nieprzypisanej (minimum 8) lub wydaj punkty z puli (maksimum 18). Bonusy klasowe zostaną dodane automatycznie.
                </p>
              </Card>

              <Card className="p-4 bg-gradient-to-br from-accent/10 to-accent/5 border-accent/30">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted">Nieprzypisane punkty:</span>
                  <span className="text-xl font-bold text-accent">{unassignedPoints}</span>
                </div>
                <p className="text-xs text-muted/60 mt-2">
                  Suma bazowa: 75 (wylosowano 75) • +2 STR, +1 CON po zatwierdzeniu
                </p>
              </Card>

              <div className="space-y-2">
                {Object.entries(character.stats).map(([key, value]) => {
                  if (key === 'lck') return null;
                  const modifier = value >= 14 ? '+3' : value >= 12 ? '+1' : value <= 9 ? '-1' : '0';
                  return (
                    <Card key={key} className="p-4 bg-[var(--panel)]/80 border-accent/20">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <span className="font-semibold text-foreground uppercase w-24">
                            {statLabels[key as keyof typeof statLabels]}
                          </span>
                          <span className="text-sm text-accent font-medium min-w-[32px] text-center">
                            {modifier}
                          </span>
                        </div>
                        <div className="flex items-center gap-3">
                          <button
                            onClick={() => adjustStat(key as keyof CharacterData["stats"], -1)}
                            disabled={value <= 8}
                            className="size-9 rounded-md border border-accent/30 bg-[var(--input-background)] flex items-center justify-center text-accent hover:bg-accent/10 hover:border-accent disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                          >
                            <Minus className="size-4" />
                          </button>
                          <span className="min-w-[40px] text-center font-bold text-accent-light text-lg">
                            {value}
                          </span>
                          <button
                            onClick={() => adjustStat(key as keyof CharacterData["stats"], 1)}
                            disabled={unassignedPoints === 0 || value >= 18}
                            className="size-9 rounded-md border border-accent/30 bg-[var(--input-background)] flex items-center justify-center text-accent hover:bg-accent/10 hover:border-accent disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                          >
                            <Plus className="size-4" />
                          </button>
                        </div>
                      </div>
                    </Card>
                  );
                })}
              </div>

              <Button
                onClick={handleResetStats}
                variant="outline"
                className="w-full gap-2 border-accent/30 text-muted hover:text-accent hover:border-accent"
              >
                <RefreshCw className="size-4" />
                Zresetuj do wartości bazowych
              </Button>
            </div>
          )}

          {/* Step 2: Skills */}
          {step === 2 && (
            <div className="space-y-4">
              <Card className="p-5 bg-[var(--panel)]/80 border-accent/20">
                <h2 className="font-semibold text-foreground mb-2">Dostosuj umiejętności</h2>
                <p className="text-sm text-muted leading-relaxed">
                  Wylosowane umiejętności. Zmiana poziomu (± 1) kosztuje 1 punkt — maksymalnie 4 zmiany łącznie.
                </p>
              </Card>

              <Card className="p-4 bg-gradient-to-br from-accent/10 to-accent/5 border-accent/30">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted">Wykorzystane zmiany:</span>
                  <span className="text-xl font-bold text-accent">{skillsChanged} / 4</span>
                </div>
              </Card>

              <div className="space-y-2">
                {Object.keys(character.skills).map((skillId) => {
                  const skillData = character.skills[skillId];
                  const currentLevel = skillData.level;
                  const levelLabel = currentLevel === 2 ? 'Wprawny' : currentLevel === 1 ? 'Trenowany' : 'Niewykwalifikowany';
                  const skillInfo = allAvailableSkills.find(s => s.id === skillId);

                  return (
                    <Card key={skillId} className="p-4 bg-[var(--panel)]/80 border-accent/20">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex-1 min-w-0">
                          <div className="font-semibold text-foreground">{skillData.name}</div>
                          <div className="text-xs text-muted">Atrybut: {skillInfo?.attr || 'N/A'}</div>
                        </div>
                        <div className="flex items-center gap-3">
                          <button
                            onClick={() => adjustSkill(skillId, -1)}
                            disabled={currentLevel <= 0}
                            className="size-8 rounded border border-accent/30 bg-[var(--input-background)] flex items-center justify-center text-accent hover:bg-accent/10 hover:border-accent disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                          >
                            <Minus className="size-3.5" />
                          </button>
                          <div className="min-w-[90px] text-center">
                            <div className="text-lg font-bold text-accent-light">{currentLevel}</div>
                            <div className="text-xs text-muted">{levelLabel}</div>
                          </div>
                          <button
                            onClick={() => adjustSkill(skillId, 1)}
                            disabled={skillsChanged >= 4 || currentLevel >= 3}
                            className="size-8 rounded border border-accent/30 bg-[var(--input-background)] flex items-center justify-center text-accent hover:bg-accent/10 hover:border-accent disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                          >
                            <Plus className="size-3.5" />
                          </button>
                        </div>
                      </div>
                      <Button
                        onClick={() => handleOpenSkillExchange(skillId)}
                        variant="outline"
                        size="sm"
                        className="w-full gap-2 border-accent/30 text-muted hover:text-accent hover:border-accent"
                      >
                        <ArrowRightLeft className="size-3.5" />
                        Wymień umiejętność
                      </Button>
                    </Card>
                  );
                })}
              </div>

              <Button
                onClick={handleResetSkills}
                variant="outline"
                className="w-full gap-2 border-accent/30 text-muted hover:text-accent hover:border-accent"
              >
                <RefreshCw className="size-4" />
                Zresetuj do wartości bazowych
              </Button>
            </div>
          )}

          {/* Step 3: Backstory */}
          {step === 3 && (
            <div className="space-y-4">
              <Card className="p-5 bg-[var(--panel)]/80 border-accent/20">
                <h2 className="font-semibold text-foreground mb-2">Twoja postać</h2>
                <p className="text-sm text-muted leading-relaxed">
                  Poniżej wygenerowano historię postaci. Możesz edytować wygląd i osobowość według własnych preferencji.
                </p>
              </Card>

              <div className="space-y-3">
                <div className="space-y-2">
                  <Label htmlFor="appearance" className="text-accent-light">
                    Wygląd
                  </Label>
                  <textarea
                    id="appearance"
                    value={character.appearance}
                    onChange={(e) => setCharacter({ ...character, appearance: e.target.value })}
                    className="w-full min-h-[100px] rounded-md border border-accent/30 bg-[var(--input-background)] px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:border-accent resize-none"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="personality" className="text-accent-light">
                    Osobowość
                  </Label>
                  <textarea
                    id="personality"
                    value={character.personality}
                    onChange={(e) => setCharacter({ ...character, personality: e.target.value })}
                    className="w-full min-h-[100px] rounded-md border border-accent/30 bg-[var(--input-background)] px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:border-accent resize-none"
                  />
                </div>

                <div className="space-y-2">
                  <Label className="text-accent-light flex items-center gap-2">
                    <Lock className="size-3.5" />
                    Wada (Zablokowane)
                  </Label>
                  <Input
                    readOnly
                    value={character.flaw}
                    className="bg-[var(--panel-2)] border-accent/10 text-muted cursor-not-allowed"
                  />
                </div>

                <div className="space-y-2">
                  <Label className="text-accent-light flex items-center gap-2">
                    <Lock className="size-3.5" />
                    Więź (Zablokowane)
                  </Label>
                  <Input
                    readOnly
                    value={character.bond}
                    className="bg-[var(--panel-2)] border-accent/10 text-muted cursor-not-allowed"
                  />
                </div>

                <Card className="p-4 bg-accent/5 border-accent/20">
                  <div className="flex items-start gap-3">
                    <Lock className="size-5 text-accent flex-shrink-0 mt-0.5" />
                    <p className="text-xs text-muted leading-relaxed">
                      Twój sekret zostanie ujawniony, gdy historia tego zażąda. Niektóre elementy przeszłości bohatera pozostają ukryte do odpowiedniego momentu.
                    </p>
                  </div>
                </Card>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Footer Actions */}
      <div className="sticky bottom-0 bg-[var(--bottom-bar)]/95 backdrop-blur border-t border-accent/20 p-4 space-y-2 shadow-[0_-2px_16px_rgba(0,0,0,0.4)]">
        <Button
          id="character-creation-next"
          onClick={handleNext}
          disabled={!canProceed()}
          className="w-full gap-2 bg-accent hover:bg-accent-light text-[var(--bg)] font-semibold disabled:opacity-40 disabled:cursor-not-allowed"
          size="lg"
        >
          {step === totalSteps - 1 ? "Rozpocznij przygodę" : "Dalej"}
          <ChevronRight className="size-5" />
        </Button>
        {step > 0 && (
          <Button
            id="character-creation-back"
            onClick={handleBack}
            variant="outline"
            className="w-full border-accent/30 text-muted hover:text-accent hover:border-accent"
          >
            Wstecz
          </Button>
        )}
      </div>

      {/* Background decoration */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden -z-10">
        <div className="absolute top-1/4 left-10 w-96 h-96 bg-accent/3 rounded-full blur-[120px]" />
        <div className="absolute bottom-1/4 right-10 w-96 h-96 bg-accent/3 rounded-full blur-[120px]" />
      </div>

      {/* Skill Exchange Drawer */}
      <Drawer open={skillExchangeOpen} onOpenChange={setSkillExchangeOpen}>
        <DrawerContent className="h-[85vh]">
          <div className="mx-auto w-full max-w-md h-full flex flex-col">
            <div className="px-4 pt-4 pb-2 border-b border-accent/20 flex items-center justify-between">
              <div>
                <DrawerTitle className="text-xl font-semibold text-accent-light">
                  Wymień umiejętność
                </DrawerTitle>
                <DrawerDescription className="text-sm text-muted mt-1">
                  {skillToExchange && `Zamień "${skillToExchange.name}" na inną umiejętność`}
                </DrawerDescription>
              </div>
              <DrawerClose asChild>
                <Button variant="ghost" size="icon" className="text-muted hover:text-accent">
                  <X className="size-5" />
                </Button>
              </DrawerClose>
            </div>

            <ScrollArea className="flex-1">
              <div className="p-4 space-y-2">
                {allAvailableSkills
                  .filter(skill => !character.skills[skill.id]) // Only show skills not already selected
                  .map((skill) => (
                    <Card
                      key={skill.id}
                      onClick={() => handleExchangeSkill(skill.id)}
                      className="p-4 bg-[var(--panel)]/60 border-accent/20 cursor-pointer hover:border-accent/40 hover:bg-[var(--panel-2)]/60 transition-all active:scale-[0.98]"
                    >
                      <div className="flex items-start gap-3">
                        <div className="flex-shrink-0 size-10 rounded-lg bg-accent/10 border border-accent/20 flex items-center justify-center">
                          <span className="text-xs font-bold text-accent">{skill.attr}</span>
                        </div>
                        <div className="flex-1 min-w-0">
                          <h4 className="font-semibold text-foreground mb-1">{skill.name}</h4>
                          <p className="text-xs text-muted leading-relaxed">{skill.description}</p>
                        </div>
                        <ChevronRight className="size-5 text-accent/40 flex-shrink-0 mt-1" />
                      </div>
                    </Card>
                  ))}
              </div>
            </ScrollArea>
          </div>
        </DrawerContent>
      </Drawer>
    </div>
  );
}
