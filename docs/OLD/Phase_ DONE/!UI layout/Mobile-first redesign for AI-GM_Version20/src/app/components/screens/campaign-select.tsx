/**
 * Campaign Select Screen
 *
 * Purpose: Display list of user's campaigns and allow creation of new ones
 * User Actions: Select existing campaign, create new campaign, logout
 * Related Spec: src/imports/01-screen-inventory.md
 * Stable IDs: #campaign-select-screen
 *
 * Persistence: Loads from localStorage key `campaigns_{username}`
 */

import { useState } from "react";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Plus, Scroll, Sword, Flame, LogOut, ChevronRight } from "lucide-react";

interface Campaign {
  id: string;
  name: string;
  characterName?: string;
  lastPlayed?: string;
  level?: number;
}

interface CampaignSelectProps {
  username: string;
  onSelectCampaign: (campaignId: string) => void;
  onCreateCampaign: () => void;
  onLogout: () => void;
}

export function CampaignSelect({
  username,
  onSelectCampaign,
  onCreateCampaign,
  onLogout,
}: CampaignSelectProps) {
  // Load campaigns from localStorage
  const [campaigns] = useState<Campaign[]>(() => {
    const saved = localStorage.getItem(`campaigns_${username}`);
    return saved ? JSON.parse(saved) : [];
  });

  return (
    <div
      id="campaign-select-screen"
      className="flex min-h-screen flex-col bg-gradient-to-b from-[#0a0806] via-[#12100d] to-[#0a0806]"
    >
      {/* Header */}
      <div className="sticky top-0 z-10 bg-[var(--top-bar)]/95 backdrop-blur border-b border-accent/20 shadow-[0_2px_16px_rgba(0,0,0,0.4)]">
        <div className="flex items-center justify-between p-4">
          <div className="flex items-center gap-3">
            <Scroll className="size-6 text-accent" />
            <div>
              <h1 className="text-lg font-semibold text-accent-light">Kampanie</h1>
              <p className="text-xs text-muted">Witaj, {username}</p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={onLogout}
            className="text-muted hover:text-accent"
          >
            <LogOut className="size-4" />
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 p-4 space-y-4 overflow-y-auto">
        {/* Create New Campaign Button */}
        <Card
          onClick={onCreateCampaign}
          className="p-6 bg-gradient-to-br from-[var(--panel)] to-[var(--panel-2)] border-accent/30 shadow-[0_0_30px_rgba(183,122,43,0.1)] cursor-pointer hover:border-accent/50 hover:shadow-[0_0_40px_rgba(183,122,43,0.15)] transition-all active:scale-[0.98]"
        >
          <div className="flex items-center gap-4">
            <div className="flex-shrink-0 size-14 rounded-full bg-accent/20 flex items-center justify-center">
              <Plus className="size-7 text-accent" strokeWidth={2.5} />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-accent-light mb-1">
                Nowa kampania
              </h3>
              <p className="text-sm text-muted">
                Rozpocznij nową przygodę w mrocznych krainach
              </p>
            </div>
            <ChevronRight className="size-5 text-accent/60 flex-shrink-0" />
          </div>
        </Card>

        {/* Existing Campaigns */}
        {campaigns.length > 0 ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2 px-2">
              <Flame className="size-4 text-accent/60" />
              <h2 className="text-sm font-medium text-muted uppercase tracking-wide">
                Twoje kampanie
              </h2>
            </div>
            {campaigns.map((campaign) => (
              <Card
                key={campaign.id}
                onClick={() => onSelectCampaign(campaign.id)}
                className="p-5 bg-[var(--panel)]/80 border-accent/20 cursor-pointer hover:border-accent/40 hover:bg-[var(--panel-2)]/80 transition-all active:scale-[0.98]"
              >
                <div className="flex items-center gap-4">
                  <div className="flex-shrink-0 size-12 rounded-lg bg-accent/10 flex items-center justify-center border border-accent/20">
                    <Sword className="size-6 text-accent" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-foreground truncate mb-1">
                      {campaign.name}
                    </h3>
                    <div className="flex items-center gap-3 text-xs text-muted">
                      {campaign.characterName && (
                        <span>{campaign.characterName}</span>
                      )}
                      {campaign.level && (
                        <span className="text-accent">Poziom {campaign.level}</span>
                      )}
                      {campaign.lastPlayed && (
                        <span className="text-muted/60">{campaign.lastPlayed}</span>
                      )}
                    </div>
                  </div>
                  <ChevronRight className="size-5 text-accent/40 flex-shrink-0" />
                </div>
              </Card>
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
            <div className="size-20 rounded-full bg-accent/5 flex items-center justify-center mb-4">
              <Scroll className="size-10 text-accent/40" />
            </div>
            <p className="text-muted italic mb-1">
              Nie masz jeszcze żadnych kampanii
            </p>
            <p className="text-sm text-muted/60">
              Stwórz swoją pierwszą przygodę
            </p>
          </div>
        )}
      </div>

      {/* Background decoration */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden -z-10">
        <div className="absolute top-1/4 left-10 w-96 h-96 bg-accent/3 rounded-full blur-[120px]" />
        <div className="absolute bottom-1/4 right-10 w-96 h-96 bg-accent/3 rounded-full blur-[120px]" />
      </div>
    </div>
  );
}
