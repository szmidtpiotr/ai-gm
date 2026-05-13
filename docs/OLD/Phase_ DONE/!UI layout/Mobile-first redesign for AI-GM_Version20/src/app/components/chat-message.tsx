import { Scroll, Sparkles, Info } from "lucide-react";
import { cn } from "@/lib/utils";

export type MessageType = "player" | "gm" | "system" | "roll";

interface ChatMessageProps {
  type: MessageType;
  content: string;
  timestamp?: string;
  rollResult?: {
    dice: string;
    result: number;
    modifier?: number;
    total: number;
  };
}

export function ChatMessage({
  type,
  content,
  timestamp,
  rollResult,
}: ChatMessageProps) {
  if (type === "roll" && rollResult) {
    return (
      <div id="chat-message-roll" className="flex justify-center px-4 py-2">
        <div className="max-w-[280px] rounded-lg border border-primary/30 bg-gradient-to-br from-primary/10 to-accent/10 p-4 text-center">
          <div className="mb-2 flex items-center justify-center gap-2 text-sm text-muted-foreground">
            <Sparkles className="size-4" />
            <span>Rzut kośćmi</span>
          </div>
          <div className="mb-1 text-3xl font-semibold tabular-nums text-primary">
            {rollResult.total}
          </div>
          <div className="text-xs text-muted-foreground">
            {rollResult.dice} = {rollResult.result}
            {rollResult.modifier !== undefined &&
              rollResult.modifier !== 0 &&
              ` ${rollResult.modifier >= 0 ? "+" : ""}${rollResult.modifier}`}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      id={`chat-message-${type}`}
      className={cn("flex gap-2 px-4 py-3", {
        "justify-end": type === "player",
      })}
    >
      {type !== "player" && (
        <div className="mt-1 flex-shrink-0">
          {type === "gm" ? (
            <Scroll className="size-5 text-primary" />
          ) : (
            <Info className="size-4 text-muted-foreground" />
          )}
        </div>
      )}
      <div
        className={cn("max-w-[85%] space-y-1", {
          "text-right": type === "player",
        })}
      >
        <div
          className={cn("rounded-2xl px-4 py-2.5", {
            "bg-[var(--chat-player)] text-foreground": type === "player",
            "bg-[var(--chat-gm)] text-foreground": type === "gm",
            "bg-[var(--chat-system)] text-muted-foreground text-sm":
              type === "system",
          })}
        >
          <p className="message-content whitespace-pre-wrap leading-relaxed">{content}</p>
        </div>
        {timestamp && (
          <div className="px-2 text-xs text-muted-foreground">{timestamp}</div>
        )}
      </div>
    </div>
  );
}
