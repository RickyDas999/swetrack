import { useTheme } from "next-themes"
import { MoonIcon, SunIcon } from "lucide-react"

import { cn } from "cn"
import { Button } from "@/components/ui/button"

export function ThemeToggle({ className }: { className?: string }) {
  const { resolvedTheme, setTheme } = useTheme()
  // No SSR in this Vite SPA, so there is no hydration mismatch to guard
  // against; resolvedTheme is briefly undefined on first boot, which we
  // treat as "dark" since that is the configured default theme.
  const isDark = resolvedTheme !== "light"

  return (
    <Button
      variant="ghost"
      size="icon"
      className={cn("size-8", className)}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      onClick={() => setTheme(isDark ? "light" : "dark")}
    >
      {isDark ? <SunIcon /> : <MoonIcon />}
    </Button>
  )
}
