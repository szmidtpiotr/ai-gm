import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { cva, type VariantProps } from "class-variance-authority";
import { X } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";

// Sheet = bottom-sheet na mobile / side-panel na desktop (frontend_design.md §4,10).
// Domyślnie: side="responsive" → dół na <lg, prawa krawędź na lg+.
export const Sheet = DialogPrimitive.Root;
export const SheetTrigger = DialogPrimitive.Trigger;
export const SheetClose = DialogPrimitive.Close;

const SheetOverlay = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      "fixed inset-0 z-50 bg-black/70 backdrop-blur-sm animate-fade-in",
      className,
    )}
    {...props}
  />
));
SheetOverlay.displayName = "SheetOverlay";

const sheetVariants = cva(
  "fixed z-50 border-line bg-surface shadow-modal flex flex-col",
  {
    variants: {
      side: {
        bottom:
          "inset-x-0 bottom-0 max-h-[90dvh] rounded-t-xl border-t animate-slide-up " +
          "pb-[var(--sa-bottom)]",
        right:
          "inset-y-0 right-0 h-full w-full max-w-md border-l animate-slide-in-right",
        // Mobile = bottom-sheet; desktop (lg+) = prawy side-panel.
        responsive:
          "inset-x-0 bottom-0 max-h-[90dvh] rounded-t-xl border-t animate-slide-up pb-[var(--sa-bottom)] " +
          "lg:inset-y-0 lg:right-0 lg:left-auto lg:h-full lg:max-h-full lg:w-full lg:max-w-md " +
          "lg:rounded-none lg:border-l lg:border-t-0 lg:animate-slide-in-right",
      },
    },
    defaultVariants: { side: "responsive" },
  },
);

export interface SheetContentProps
  extends React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>,
    VariantProps<typeof sheetVariants> {
  title?: string;
  hideClose?: boolean;
}

export const SheetContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  SheetContentProps
>(({ className, children, side, title, hideClose, ...props }, ref) => (
  <DialogPrimitive.Portal>
    <SheetOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(sheetVariants({ side }), className)}
      {...props}
    >
      {/* Grip (mobile bottom-sheet affordance) */}
      <div className="mx-auto mt-2 h-1 w-10 rounded-pill bg-line lg:hidden" />
      {(title || !hideClose) && (
        <div className="flex items-center justify-between px-4 py-3">
          <DialogPrimitive.Title className="font-serif text-title text-text">
            {title}
          </DialogPrimitive.Title>
          {!hideClose && (
            <DialogPrimitive.Close
              className="text-text-3 hover:text-text focus:outline-none"
              aria-label="Zamknij"
            >
              <X size={20} />
            </DialogPrimitive.Close>
          )}
        </div>
      )}
      <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-4 [overscroll-behavior:contain]">
        {children}
      </div>
    </DialogPrimitive.Content>
  </DialogPrimitive.Portal>
));
SheetContent.displayName = "SheetContent";
