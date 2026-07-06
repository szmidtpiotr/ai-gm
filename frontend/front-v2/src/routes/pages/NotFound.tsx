import { Link } from "react-router-dom";
import { Compass } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center gap-4 py-16 text-center">
      <Compass className="text-text-3" size={48} />
      <h1 className="font-serif text-title-lg text-text">Zbłądziłeś</h1>
      <p className="text-body text-text-3">Ta ścieżka nie istnieje na mapie.</p>
      <Button asChild variant="secondary">
        <Link to="/bohaterowie">Wróć do bohaterów</Link>
      </Button>
    </div>
  );
}
