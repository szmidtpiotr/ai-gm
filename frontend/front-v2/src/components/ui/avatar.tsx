import * as React from "react";
import * as AvatarPrimitive from "@radix-ui/react-avatar";
import { UserCircle } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";

// Portret = sylwetka-placeholder (Phosphor). Art generowany później (parasol #1240 §6).
export const Avatar = React.forwardRef<
  React.ElementRef<typeof AvatarPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof AvatarPrimitive.Root>
>(({ className, ...props }, ref) => (
  <AvatarPrimitive.Root
    ref={ref}
    className={cn(
      "relative flex h-11 w-11 shrink-0 overflow-hidden rounded-pill border border-line bg-mech-card",
      className,
    )}
    {...props}
  />
));
Avatar.displayName = "Avatar";

export const AvatarImage = React.forwardRef<
  React.ElementRef<typeof AvatarPrimitive.Image>,
  React.ComponentPropsWithoutRef<typeof AvatarPrimitive.Image>
>(({ className, ...props }, ref) => (
  <AvatarPrimitive.Image
    ref={ref}
    className={cn("h-full w-full object-cover", className)}
    {...props}
  />
));
AvatarImage.displayName = "AvatarImage";

export const AvatarFallback = React.forwardRef<
  React.ElementRef<typeof AvatarPrimitive.Fallback>,
  React.ComponentPropsWithoutRef<typeof AvatarPrimitive.Fallback>
>(({ className, children, ...props }, ref) => (
  <AvatarPrimitive.Fallback
    ref={ref}
    className={cn(
      "flex h-full w-full items-center justify-center text-text-3",
      className,
    )}
    {...props}
  >
    {children ?? <UserCircle weight="fill" className="h-3/4 w-3/4" />}
  </AvatarPrimitive.Fallback>
));
AvatarFallback.displayName = "AvatarFallback";
