import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-pill px-2.5 py-0.5 text-micro font-ui font-medium border",
  {
    variants: {
      variant: {
        neutral: "bg-surface text-text-2 border-line",
        ember: "bg-ember/10 text-ember-glow border-line-ember",
        gold: "bg-gold/10 text-gold border-line-mech",
        danger: "bg-danger/10 text-danger-glow border-line-danger",
        success: "bg-success/10 text-success border-success/30",
        mana: "bg-mana/10 text-mana border-mana/30",
        rare: "bg-rare/10 text-rare border-rare/30",
        epic: "bg-epic/10 text-epic border-epic/30",
      },
    },
    defaultVariants: { variant: "neutral" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}
