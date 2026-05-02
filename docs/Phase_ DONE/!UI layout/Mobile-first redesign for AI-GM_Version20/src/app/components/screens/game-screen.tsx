/**
 * Game Screen
 *
 * Purpose: Main play area with chat, combat, and character management
 * User Actions: Send messages, engage in combat, view character sheet, adjust settings
 * Related Spec: src/imports/01-screen-inventory.md, src/imports/07-combat-panel-spec.md
 * Stable IDs: #game-screen, #chat-messages, #combat-ui, #character-sheet-button
 *
 * Layout:
 * - Header: Character name/HP, settings dropdown, character sheet trigger (user icon)
 * - Chat area: Scrollable messages with combat UI and loot inline
 * - Bottom composer: Sticky input bar (always reachable)
 * - Drawer: Character sheet with swipeable tabs (Stats/Skills/Inventory)
 */

import { useState, useRef, useEffect } from "react";
import { Button } from "../ui/button";
import { ScrollArea } from "../ui/scroll-area";
import { Drawer, DrawerContent, DrawerTrigger, DrawerTitle, DrawerDescription } from "../ui/drawer";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";
import { ChatMessage, MessageType } from "../chat-message";
import { MessageComposer } from "../message-composer";
import { CharacterStats } from "../character-stats";
import { CharacterSheetTabs } from "../character-sheet-tabs";
import { SettingsPanel } from "../settings-panel";
import { CombatUI } from "../combat-ui";
import { LootCard, LootItem } from "../loot-card";
import {
  User,
  Settings,
  History,
  LogOut,
  Volume2,
  VolumeX,
  Shield as ShieldIcon,
} from "lucide-react";

interface Message {
  id: string;
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

interface GameState {
  character: {
    name: string;
    level: number;
    hp: number;
    maxHp: number;
    str: number;
    dex: number;
    con: number;
    int: number;
    wis: number;
    cha: number;
    lck: number;
  };
  combat?: {
    enemy: {
      name: string;
      hp: number;
      maxHp: number;
      level: number;
      armor?: number;
    };
    playerTurn: boolean;
  };
  loot?: {
    items: LootItem[];
    gold: number;
  };
}

interface GameScreenProps {
  gameState: GameState;
  messages: Message[];
  onSendMessage: (message: string) => void;
  onAttack?: () => void;
  onFlee?: () => void;
  onLogout: () => void;
}

export function GameScreen({
  gameState,
  messages,
  onSendMessage,
  onAttack,
  onFlee,
  onLogout,
}: GameScreenProps) {
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [showSettingsPanel, setShowSettingsPanel] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  return (
    <div id="game-screen" className="flex h-[100dvh] flex-col overflow-hidden bg-background">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-[var(--border-strong)] bg-[var(--top-bar)] px-4 py-3 shadow-[var(--shadow-strong)] flex-none z-10">
        <Drawer>
          <DrawerTrigger asChild>
            <Button id="character-sheet-button" variant="ghost" size="icon">
              <User className="size-5" />
            </Button>
          </DrawerTrigger>
          <DrawerContent className="h-[80vh]">
            <div className="mx-auto w-full max-w-sm h-full flex flex-col">
              <DrawerTitle className="px-4 pt-4 pb-2 text-xl font-semibold">
                {gameState.character.name}
              </DrawerTitle>
              <DrawerDescription className="sr-only">
                Karta postaci z zakładkami statystyk, umiejętności i ekwipunku
              </DrawerDescription>
              <CharacterSheetTabs character={gameState.character} />
            </div>
          </DrawerContent>
        </Drawer>

        <div className="flex-1 text-center">
          <h1 className="text-sm font-medium">{gameState.character.name}</h1>
          <div className="text-xs text-muted-foreground">
            Poziom {gameState.character.level} •{" "}
            {gameState.character.hp}/{gameState.character.maxHp} HP
          </div>
        </div>

        <DropdownMenu open={showSettings} onOpenChange={setShowSettings}>
          <DropdownMenuTrigger asChild>
            <Button id="settings-button" variant="ghost" size="icon">
              <Settings className="size-5" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem
              id="toggle-sound"
              onClick={() => setSoundEnabled(!soundEnabled)}
            >
              {soundEnabled ? (
                <Volume2 className="mr-2 size-4" />
              ) : (
                <VolumeX className="mr-2 size-4" />
              )}
              {soundEnabled ? "Wycisz dźwięk" : "Włącz dźwięk"}
            </DropdownMenuItem>
            <DropdownMenuItem
              id="open-settings"
              onClick={() => {
                setShowSettings(false);
                setShowSettingsPanel(true);
              }}
            >
              <Settings className="mr-2 size-4" />
              Ustawienia
            </DropdownMenuItem>
            <DropdownMenuItem id="view-history">
              <History className="mr-2 size-4" />
              Historia
            </DropdownMenuItem>
            <DropdownMenuItem id="logout" onClick={onLogout}>
              <LogOut className="mr-2 size-4" />
              Wyloguj
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </header>

      {/* Main Content Area */}
      <div className="flex flex-1 overflow-hidden">
        <div className="flex-1 flex flex-col min-w-0">
          {/* Messages */}
          <ScrollArea id="chat-messages" className="flex-1 min-h-0">
            <div className="py-4">
              {messages.map((msg) => (
                <ChatMessage
                  key={msg.id}
                  type={msg.type}
                  content={msg.content}
                  timestamp={msg.timestamp}
                  rollResult={msg.rollResult}
                />
              ))}

              {/* Combat UI (Mobile Inline) */}
              {gameState.combat && (
                <div className="px-4 py-3 lg:hidden">
                  <CombatUI
                    character={gameState.character}
                    enemy={gameState.combat.enemy}
                    playerTurn={gameState.combat.playerTurn}
                    onAttack={onAttack || (() => {})}
                    onFlee={onFlee || (() => {})}
                    combatLogs={messages.filter(m => m.type === "roll" || m.content.includes("trafia") || m.content.includes("obrażeń") || m.content.includes("Trafiłeś") || m.content.includes("Chybił")).slice(-3)}
                  />
                </div>
              )}

              {/* Loot */}
              {gameState.loot && (
                <div className="px-4 py-3">
                  <LootCard items={gameState.loot.items} gold={gameState.loot.gold} />
                </div>
              )}

              {/* Scroll anchor */}
              <div ref={messagesEndRef} />
            </div>
          </ScrollArea>

          {/* Composer */}
          <MessageComposer
            onSend={onSendMessage}
            disabled={!!gameState.combat && !gameState.combat.playerTurn}
          />
        </div>

        {/* Desktop Sidebar */}
        <aside className="hidden lg:flex w-80 xl:w-96 flex-col border-l border-[var(--border-strong)] bg-[var(--panel)] shadow-inner">
          <div className="p-4 border-b border-[var(--border)] bg-[#efeae1]">
            <h2 className="font-bold text-lg text-[#3d2b1f]">Panel Boczny</h2>
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            {gameState.combat ? (
              <CombatUI
                character={gameState.character}
                enemy={gameState.combat.enemy}
                playerTurn={gameState.combat.playerTurn}
                onAttack={onAttack || (() => {})}
                onFlee={onFlee || (() => {})}
                combatLogs={messages.filter(m => m.type === "roll" || m.content.includes("trafia") || m.content.includes("obrażeń") || m.content.includes("Trafiłeś") || m.content.includes("Chybił")).slice(-3)}
              />
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-[#8c745c] space-y-2 opacity-70">
                <ShieldIcon className="size-12" />
                <p>Brak aktywnej walki</p>
              </div>
            )}
          </div>
        </aside>
      </div>

      {/* Settings Drawer */}
      <Drawer open={showSettingsPanel} onOpenChange={setShowSettingsPanel}>
        <DrawerContent className="h-[80vh]">
          <div className="mx-auto w-full max-w-sm h-full flex flex-col">
            <DrawerTitle className="px-4 pt-4 pb-2 text-xl font-semibold">
              Ustawienia
            </DrawerTitle>
            <DrawerDescription className="sr-only">
              Panel ustawień z opcjami dostosowania czcionki i wyglądu
            </DrawerDescription>
            <ScrollArea className="flex-1">
              <SettingsPanel />
            </ScrollArea>
          </div>
        </DrawerContent>
      </Drawer>
    </div>
  );
}
