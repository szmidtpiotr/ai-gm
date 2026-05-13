import { useState } from "react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Card } from "../ui/card";
import { ArrowLeft, Scroll, Sparkles } from "lucide-react";

interface CampaignCreateProps {
  onBack: () => void;
  onCreate: (campaignName: string) => void;
}

export function CampaignCreate({ onBack, onCreate }: CampaignCreateProps) {
  const [campaignName, setCampaignName] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (campaignName.trim()) {
      onCreate(campaignName.trim());
    }
  };

  return (
    <div
      id="campaign-create-screen"
      className="flex min-h-screen flex-col bg-gradient-to-b from-[#0a0806] via-[#12100d] to-[#0a0806]"
    >
      {/* Header */}
      <div className="sticky top-0 z-10 bg-[var(--top-bar)]/95 backdrop-blur border-b border-accent/20 shadow-[0_2px_16px_rgba(0,0,0,0.4)]">
        <div className="flex items-center gap-3 p-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={onBack}
            className="text-muted hover:text-accent -ml-2"
          >
            <ArrowLeft className="size-5" />
          </Button>
          <Scroll className="size-6 text-accent" />
          <h1 className="text-lg font-semibold text-accent-light">
            Nowa kampania
          </h1>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 flex items-center justify-center p-4">
        <div className="w-full max-w-md space-y-6">
          {/* Info Card */}
          <div className="text-center space-y-3 px-4">
            <div className="inline-flex items-center justify-center size-16 rounded-full bg-accent/10 border border-accent/20 mb-2">
              <Sparkles className="size-8 text-accent" />
            </div>
            <h2 className="text-xl font-semibold text-foreground">
              Nazwa kampanii
            </h2>
            <p className="text-sm text-muted leading-relaxed">
              Nadaj nazwę swojej przygodzie. To będzie tytuł, pod którym zapiszesz swoje epickie historie w mrocznych krainach.
            </p>
          </div>

          {/* Form Card */}
          <Card className="p-6 bg-[var(--panel)]/80 backdrop-blur border-accent/20 shadow-[0_0_30px_rgba(183,122,43,0.1)]">
            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="campaign-name" className="text-accent-light">
                  Nazwa kampanii
                </Label>
                <Input
                  id="campaign-name"
                  type="text"
                  value={campaignName}
                  onChange={(e) => setCampaignName(e.target.value)}
                  placeholder="np. Mroczne Ziemie, Klątwa Starego Lasu..."
                  autoFocus
                  className="bg-[var(--input-background)] border-accent/30 focus:border-accent text-base"
                  maxLength={50}
                />
                <p className="text-xs text-muted/60">
                  {campaignName.length}/50 znaków
                </p>
              </div>

              <Button
                type="submit"
                disabled={!campaignName.trim()}
                className="w-full gap-2 bg-accent hover:bg-accent-light text-[var(--bg)] font-semibold disabled:opacity-40 disabled:cursor-not-allowed"
                size="lg"
              >
                <Sparkles className="size-4" />
                Stwórz kampanię
              </Button>
            </form>
          </Card>

          {/* Examples */}
          <div className="px-4">
            <p className="text-xs text-muted/60 mb-2">
              Przykładowe nazwy:
            </p>
            <div className="flex flex-wrap gap-2">
              {[
                "Cienie Północy",
                "Ostatni Bastion",
                "Ruiny Starego Królestwa",
              ].map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => setCampaignName(example)}
                  className="px-3 py-1.5 text-xs bg-accent/10 border border-accent/20 rounded-md text-accent hover:bg-accent/20 transition-colors"
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Background decoration */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden -z-10">
        <div className="absolute top-1/3 left-10 w-80 h-80 bg-accent/5 rounded-full blur-[100px]" />
        <div className="absolute bottom-1/3 right-10 w-80 h-80 bg-accent/5 rounded-full blur-[100px]" />
      </div>
    </div>
  );
}
