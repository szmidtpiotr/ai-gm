import { useEffect, useState } from "react";

/**
 * Development helper to show current viewport width
 * Only visible in development mode
 */
export function MobileViewportIndicator() {
  const [width, setWidth] = useState(
    typeof window !== "undefined" ? window.innerWidth : 0
  );

  useEffect(() => {
    const handleResize = () => setWidth(window.innerWidth);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Only show in development
  if (process.env.NODE_ENV !== "development") return null;

  const getWidthColor = () => {
    if (width <= 320) return "bg-destructive";
    if (width <= 375) return "bg-warning";
    if (width <= 390) return "bg-success";
    return "bg-muted";
  };

  return (
    <div
      className={`fixed bottom-2 right-2 z-50 rounded px-2 py-1 text-xs font-mono ${getWidthColor()} text-white opacity-50 pointer-events-none`}
    >
      {width}px
    </div>
  );
}
