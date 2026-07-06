import { Link } from "react-router-dom";
import { Play } from "@phosphor-icons/react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ProgressBar } from "@/components/ui/progress-bar";

// F-09 placeholder — typy przygód + Historia w KROKU 3/8 (#1231).
export default function Campaigns() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-serif text-title-lg text-text">Kampanie</h1>

      <Card className="p-4">
        <div className="mb-2 flex items-center gap-2">
          <span className="font-serif text-title text-text">Szept Kresów</span>
          <Badge variant="ember">W toku</Badge>
        </div>
        <p className="mb-3 text-body text-text-2">
          Akt II · Trakt do Wilczburga
        </p>
        <ProgressBar kind="xp" value={62} max={100} showLabel />
        <div className="mt-3 flex justify-end">
          <Button size="sm" asChild>
            <Link to="/gra/1">
              <Play weight="fill" size={16} /> Graj dalej
            </Link>
          </Button>
        </div>
      </Card>
    </div>
  );
}
