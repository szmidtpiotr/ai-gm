/**
 * Login Screen
 *
 * Purpose: Authentication entry point for new and returning users
 * User Actions: Enter username/password, submit login form
 * Related Spec: src/imports/01-screen-inventory.md
 * Stable IDs: #login-screen, #username, #password
 *
 * Note: Currently uses mock auth (no backend validation).
 * See IMPLEMENTATION.md for real API integration guide.
 */

import { useState } from "react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Card } from "../ui/card";
import { Scroll, Sparkles, Flame, Skull } from "lucide-react";

interface LoginScreenProps {
  onLogin: (username: string) => void;
}

export function LoginScreen({ onLogin }: LoginScreenProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (username.trim() && password.trim()) {
      onLogin(username.trim());
    }
  };

  return (
    <div
      id="login-screen"
      className="flex min-h-screen flex-col items-center justify-center p-4 bg-gradient-to-b from-[#0a0806] via-[#12100d] to-[#0a0806]"
    >
      <div className="w-full max-w-sm space-y-8">
        {/* Fantasy Header */}
        <div className="text-center space-y-4">
          <div className="flex justify-center items-center gap-3 mb-2">
            <Skull className="size-8 text-accent/60" />
            <Scroll className="size-16 text-accent" />
            <Flame className="size-8 text-accent/60" />
          </div>
          <div className="space-y-1">
            <h1 className="text-4xl font-bold tracking-wider text-accent-light">
              AI-GM
            </h1>
            <div className="h-px w-32 mx-auto bg-gradient-to-r from-transparent via-accent to-transparent" />
          </div>
          <p className="text-sm text-muted italic">
            Mroczna kraina czeka na bohatera
          </p>
        </div>

        {/* Login Card */}
        <Card className="p-6 bg-[var(--panel)]/80 backdrop-blur border-accent/20 shadow-[0_0_30px_rgba(183,122,43,0.1)]">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username" className="text-accent-light">
                Login
              </Label>
              <Input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Wprowadź login..."
                autoComplete="username"
                autoFocus
                className="bg-[var(--input-background)] border-accent/30 focus:border-accent"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password" className="text-accent-light">
                Hasło
              </Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Wprowadź hasło..."
                autoComplete="current-password"
                className="bg-[var(--input-background)] border-accent/30 focus:border-accent"
              />
            </div>
            <Button
              type="submit"
              disabled={!username.trim() || !password.trim()}
              className="w-full gap-2 bg-accent hover:bg-accent-light text-[var(--bg)] font-semibold disabled:opacity-40 disabled:cursor-not-allowed"
              size="lg"
            >
              <Sparkles className="size-4" />
              Zaloguj się
            </Button>
          </form>
        </Card>

        {/* Atmospheric Footer */}
        <div className="text-center space-y-2">
          <p className="text-xs text-muted-foreground/60 italic">
            "W mroku świec, historie się rodzą..."
          </p>
          <p className="text-xs text-muted-foreground/40">
            v1.0.0
          </p>
        </div>
      </div>

      {/* Background decoration */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden -z-10">
        <div className="absolute top-20 left-10 w-64 h-64 bg-accent/5 rounded-full blur-[100px]" />
        <div className="absolute bottom-20 right-10 w-64 h-64 bg-accent/5 rounded-full blur-[100px]" />
      </div>
    </div>
  );
}
