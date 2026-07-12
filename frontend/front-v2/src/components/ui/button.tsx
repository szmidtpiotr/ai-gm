import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

// ŻAR: CTA = ember gradient; sekundarne = obrys ciepły; ghost = bez tła.
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md font-ui font-medium " +
    "transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-line-ember " +
    "disabled:pointer-events-none disabled:opacity-50 select-none",
  {
    variants: {
      variant: {
        primary:
          "bg-gradient-to-b from-ember to-[#e8632c] text-[#1a0f08] shadow-float " +
          "hover:from-ember-glow hover:to-ember active:translate-y-px",
        secondary:
          "bg-surface text-text border border-line hover:border-line-ember hover:text-ember-glow",
        ghost: "bg-transparent text-text-2 hover:text-text hover:bg-surface/60",
        danger:
          "bg-transparent text-danger border border-line-danger hover:bg-danger/10",
        gold: "bg-transparent text-gold border border-line-mech hover:bg-gold/10",
      },
      size: {
        sm: "h-9 px-3 text-label",
        md: "h-11 px-4 text-body",
        lg: "h-12 px-5 text-body",
        icon: "h-11 w-11 p-0",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { buttonVariants };
