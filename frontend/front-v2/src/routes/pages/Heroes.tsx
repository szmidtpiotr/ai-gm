import { Link } from "react-router-dom";
import { Plus, Play } from "@phosphor-icons/react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { useToast } from "@/components/ui/toast";

// F-08 hub placeholder — właściwe karty bohaterów w KROKU 2/8 (#1230).
export default function Heroes() {
  const { toast } = useToast();
  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-serif text-title-lg text-text">Twoi bohaterowie</h1>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Card className="flex items-center gap-3 p-4">
          <Avatar className="h-14 w-14">
            <AvatarFallback />
          </Avatar>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="truncate font-serif text-title text-text">Wiga</span>
              <Badge variant="ember">Aktywna</Badge>
            </div>
            <p className="font-mono text-micro text-text-3">
              Wojowniczka · poz. 3 · HP 24/30
            </p>
          </div>
          <Button size="sm" asChild>
            <Link to="/bohaterowie/1/kampanie">
              <Play weight="fill" size={16} /> Graj
            </Link>
          </Button>
        </Card>

        <button
          onClick={() => toast("Kreator postaci — KROK 3/8", "info")}
          className="flex min-h-[84px] items-center justify-center gap-2 rounded-lg border border-dashed border-line text-text-3 transition-colors hover:border-line-ember hover:text-ember-glow"
        >
          <Plus size={20} />
          <span className="font-ui text-body">Nowy bohater</span>
        </button>
      </div>
    </div>
  );
}
