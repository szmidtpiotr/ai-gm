import * as React from "react";
import { Eye, EyeSlash, type Icon } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";

// Pole formularza z ikoną z lewej (makieta zar8): koperta / kłódka.
// Hasło dostaje opcjonalny przełącznik podglądu (oko).
interface FieldProps extends React.InputHTMLAttributes<HTMLInputElement> {
  icon: Icon;
  /** Toggle „pokaż hasło" — tylko dla type=password. */
  revealable?: boolean;
}

export const Field = React.forwardRef<HTMLInputElement, FieldProps>(
  ({ icon: LeftIcon, revealable, type = "text", className, ...props }, ref) => {
    const [show, setShow] = React.useState(false);
    const effectiveType = revealable && show ? "text" : type;
    return (
      <div
        className={cn(
          "flex items-center gap-2.5 rounded-md border border-line bg-surface px-3.5",
          "focus-within:border-line-ember focus-within:ring-2 focus-within:ring-ember/10",
          className,
        )}
      >
        <LeftIcon size={18} className="shrink-0 text-text-3" />
        <input
          ref={ref}
          type={effectiveType}
          className="flex-1 bg-transparent py-3.5 font-ui text-body text-text outline-none placeholder:text-text-3"
          {...props}
        />
        {revealable && (
          <button
            type="button"
            aria-label={show ? "Ukryj hasło" : "Pokaż hasło"}
            onClick={() => setShow((v) => !v)}
            className="shrink-0 text-text-3 transition-colors hover:text-ember-glow"
          >
            {show ? <EyeSlash size={18} /> : <Eye size={18} />}
          </button>
        )}
      </div>
    );
  },
);
Field.displayName = "Field";

// Komunikat błędu / info pod formularzem.
export function FormNotice({
  kind = "error",
  children,
}: {
  kind?: "error" | "info" | "success";
  children: React.ReactNode;
}) {
  const styles = {
    error: "border-line-danger bg-danger/10 text-danger-glow",
    info: "border-line bg-surface text-text-2",
    success: "border-success/30 bg-success/10 text-success",
  }[kind];
  return (
    <div
      role={kind === "error" ? "alert" : "status"}
      className={cn(
        "rounded-md border px-3.5 py-2.5 font-ui text-label",
        styles,
      )}
    >
      {children}
    </div>
  );
}
