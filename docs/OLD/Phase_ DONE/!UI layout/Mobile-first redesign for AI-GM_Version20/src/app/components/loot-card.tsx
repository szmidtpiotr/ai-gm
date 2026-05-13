import { Card } from "./ui/card";
import { Sparkles, Coins, Sword, Shield, ScrollText } from "lucide-react";

export interface LootItem {
  id: string;
  name: string;
  type: "weapon" | "armor" | "item" | "gold";
  rarity?: "common" | "uncommon" | "rare" | "epic" | "legendary";
  amount?: number;
}

interface LootCardProps {
  items: LootItem[];
  gold: number;
}

export function LootCard({ items, gold }: LootCardProps) {
  const rarityColors = {
    common: "text-muted-foreground",
    uncommon: "text-green-400",
    rare: "text-blue-400",
    epic: "text-purple-400",
    legendary: "text-primary",
  };

  const typeIcons = {
    weapon: Sword,
    armor: Shield,
    item: ScrollText,
    gold: Coins,
  };

  return (
    <Card
      id="loot-card"
      className="border-primary/30 bg-gradient-to-br from-primary/10 to-accent/10 p-4"
    >
      <div className="mb-3 flex items-center gap-2">
        <Sparkles className="size-5 text-primary" />
        <h3 className="font-medium">Zdobycz</h3>
      </div>

      <div className="space-y-2">
        {gold > 0 && (
          <div className="flex items-center gap-2 rounded-lg bg-background/50 p-2">
            <Coins className="size-4 text-primary" />
            <span className="flex-1">{gold} złota</span>
          </div>
        )}

        {items.map((item) => {
          const Icon = typeIcons[item.type];
          return (
            <div
              key={item.id}
              className="flex items-center gap-2 rounded-lg bg-background/50 p-2"
            >
              <Icon className="size-4 text-muted-foreground" />
              <span
                className={
                  item.rarity
                    ? rarityColors[item.rarity]
                    : "text-foreground"
                }
              >
                {item.name}
                {item.amount && item.amount > 1 && ` x${item.amount}`}
              </span>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
