import * as React from "react";
import { CheckCircle, Warning, Info, X } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";

type ToastKind = "info" | "success" | "danger";

interface ToastItem {
  id: number;
  message: string;
  kind: ToastKind;
}

interface ToastCtx {
  toast: (message: string, kind?: ToastKind) => void;
}

const Ctx = React.createContext<ToastCtx | null>(null);

let seq = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = React.useState<ToastItem[]>([]);

  const remove = React.useCallback((id: number) => {
    setItems((xs) => xs.filter((t) => t.id !== id));
  }, []);

  const toast = React.useCallback(
    (message: string, kind: ToastKind = "info") => {
      const id = ++seq;
      setItems((xs) => [...xs, { id, message, kind }]);
      window.setTimeout(() => remove(id), 4000);
    },
    [remove],
  );

  return (
    <Ctx.Provider value={{ toast }}>
      {children}
      <Toaster items={items} onDismiss={remove} />
    </Ctx.Provider>
  );
}

export function useToast() {
  const ctx = React.useContext(Ctx);
  if (!ctx) throw new Error("useToast must be used within <ToastProvider>");
  return ctx;
}

const ICONS: Record<ToastKind, React.ReactNode> = {
  info: <Info weight="fill" className="text-mana" size={18} />,
  success: <CheckCircle weight="fill" className="text-success" size={18} />,
  danger: <Warning weight="fill" className="text-danger" size={18} />,
};

const BORDERS: Record<ToastKind, string> = {
  info: "border-mana/40",
  success: "border-success/40",
  danger: "border-line-danger",
};

function Toaster({
  items,
  onDismiss,
}: {
  items: ToastItem[];
  onDismiss: (id: number) => void;
}) {
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-[100] flex flex-col items-center gap-2 p-4 pb-[calc(var(--sa-bottom)+1rem)] lg:items-end">
      {items.map((t) => (
        <div
          key={t.id}
          className={cn(
            "pointer-events-auto flex w-full max-w-sm items-center gap-2 rounded-md border bg-surface px-3 py-2.5 shadow-float animate-slide-up",
            BORDERS[t.kind],
          )}
        >
          {ICONS[t.kind]}
          <span className="flex-1 text-body text-text">{t.message}</span>
          <button
            onClick={() => onDismiss(t.id)}
            className="text-text-3 hover:text-text"
            aria-label="Zamknij"
          >
            <X size={16} />
          </button>
        </div>
      ))}
    </div>
  );
}
