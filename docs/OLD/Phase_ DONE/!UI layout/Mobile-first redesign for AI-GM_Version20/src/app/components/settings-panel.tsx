import { useState, useEffect } from "react";
import { Label } from "./ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Slider } from "./ui/slider";
import { Card } from "./ui/card";

const FONT_FAMILIES = [
  { value: "system", label: "Domyślna systemowa" },
  { value: "serif", label: "Serif (Garamond-style)" },
  { value: "sans", label: "Sans-serif (Czytelna)" },
  { value: "mono", label: "Monospace (Retro)" },
];

const FONT_SIZES = {
  small: { value: 14, label: "Mała" },
  medium: { value: 16, label: "Średnia" },
  large: { value: 18, label: "Duża" },
  xlarge: { value: 20, label: "Bardzo duża" },
};

interface SettingsPanelProps {
  onSettingsChange?: (settings: { fontFamily: string; fontSize: number }) => void;
}

export function SettingsPanel({ onSettingsChange }: SettingsPanelProps) {
  const [fontFamily, setFontFamily] = useState("system");
  const [fontSize, setFontSize] = useState(16);

  useEffect(() => {
    // Load from localStorage
    const savedFont = localStorage.getItem("aigm-font-family");
    const savedSize = localStorage.getItem("aigm-font-size");

    if (savedFont) setFontFamily(savedFont);
    if (savedSize) setFontSize(parseInt(savedSize));
  }, []);

  useEffect(() => {
    // Save to localStorage and apply
    localStorage.setItem("aigm-font-family", fontFamily);
    localStorage.setItem("aigm-font-size", fontSize.toString());

    // Apply font family
    const fontMap = {
      system: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      serif: 'Georgia, "Times New Roman", serif',
      sans: 'Arial, Helvetica, sans-serif',
      mono: '"Courier New", Courier, monospace',
    };

    document.documentElement.style.setProperty("--font-size", `${fontSize}px`);
    document.body.style.fontFamily = fontMap[fontFamily as keyof typeof fontMap] || fontMap.system;

    onSettingsChange?.({ fontFamily, fontSize });
  }, [fontFamily, fontSize, onSettingsChange]);

  return (
    <div id="settings-panel" className="space-y-6 p-4">
      <Card className="p-4">
        <h3 className="mb-4 font-semibold">Wygląd tekstu</h3>

        <div className="space-y-4">
          {/* Font Family */}
          <div className="space-y-2">
            <Label htmlFor="font-family">Krój czcionki</Label>
            <Select value={fontFamily} onValueChange={setFontFamily}>
              <SelectTrigger id="font-family">
                <SelectValue placeholder="Wybierz czcionkę" />
              </SelectTrigger>
              <SelectContent>
                {FONT_FAMILIES.map((font) => (
                  <SelectItem key={font.value} value={font.value}>
                    {font.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Font Size */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="font-size">Rozmiar czcionki</Label>
              <span className="text-sm text-muted-foreground">{fontSize}px</span>
            </div>
            <Slider
              id="font-size"
              min={14}
              max={22}
              step={1}
              value={[fontSize]}
              onValueChange={(value) => setFontSize(value[0])}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Mała</span>
              <span>Duża</span>
            </div>
          </div>

          {/* Preview */}
          <div className="mt-4 rounded-lg border border-[var(--border)] bg-[var(--panel)] p-3">
            <p className="text-xs text-muted-foreground mb-1">Podgląd:</p>
            <p className="settings-preview-text" style={{ fontSize: `${fontSize}px` }}>
              Przykładowy tekst narracji od Mistrza Gry. Znajdujesz się w ponurej tawernie.
            </p>
          </div>
        </div>
      </Card>

      <Card className="p-4">
        <h3 className="mb-2 font-semibold">Inne ustawienia</h3>
        <p className="text-sm text-muted-foreground">
          Dodatkowe opcje dostosowywania będą dostępne wkrótce.
        </p>
      </Card>
    </div>
  );
}
