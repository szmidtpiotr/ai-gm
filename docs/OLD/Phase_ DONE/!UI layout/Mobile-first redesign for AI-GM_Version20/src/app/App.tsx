/**
 * AI-GM - Polish Fantasy Text RPG
 * Mobile-first dark fantasy game where AI is the Game Master
 *
 * To view design showcase, import and export DemoShowcase instead:
 * import { DemoShowcase } from "./components/demo-showcase";
 * export default DemoShowcase;
 */

import { useState, useEffect } from "react";
import { LoginScreen } from "./components/screens/login-screen";
import { CampaignSelect } from "./components/screens/campaign-select";
import { CampaignCreate } from "./components/screens/campaign-create";
import { CharacterCreation } from "./components/screens/character-creation";
import { GameScreen } from "./components/screens/game-screen";
import { DeathScreen } from "./components/screens/death-screen";
import { MobileViewportIndicator } from "./components/mobile-viewport-indicator";
import {
  rollDice,
  getModifier,
  generateEnemy,
  generateLoot,
  formatTime,
  vibrate,
} from "@/lib/game-utils";

type GamePhase =
  | "login"
  | "campaign-select"
  | "campaign-create"
  | "character-creation"
  | "game"
  | "death";

interface Character {
  name: string;
  class: string;
  background: string;
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
}

interface Message {
  id: string;
  type: "player" | "gm" | "system" | "roll";
  content: string;
  timestamp?: string;
  rollResult?: {
    dice: string;
    result: number;
    modifier?: number;
    total: number;
  };
}

export default function App() {
  const [phase, setPhase] = useState<GamePhase>("login");
  const [username, setUsername] = useState("");
  const [currentCampaignId, setCurrentCampaignId] = useState<string | null>(
    null
  );
  const [currentCampaignName, setCurrentCampaignName] = useState("");
  const [character, setCharacter] = useState<Character | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [combatState, setCombatState] = useState<{
    enemy: {
      name: string;
      hp: number;
      maxHp: number;
      level: number;
      armor?: number;
    };
    playerTurn: boolean;
  } | null>(null);
  const [lootState, setLootState] = useState<{
    items: Array<{
      id: string;
      name: string;
      type: "weapon" | "armor" | "item" | "gold";
      rarity?: "common" | "uncommon" | "rare" | "epic" | "legendary";
      amount?: number;
    }>;
    gold: number;
  } | null>(null);

  const handleLogin = (name: string) => {
    setUsername(name);
    setPhase("campaign-select");
  };

  const handleSelectCampaign = (campaignId: string) => {
    setCurrentCampaignId(campaignId);
    // Load campaign data
    const savedCampaign = localStorage.getItem(
      `campaign_${username}_${campaignId}`
    );
    if (savedCampaign) {
      const campaign = JSON.parse(savedCampaign);
      setCurrentCampaignName(campaign.name);
      if (campaign.character) {
        setCharacter(campaign.character);
        setMessages(campaign.messages || []);
        setPhase("game");
        addMessage("system", "Witaj ponownie, " + campaign.character.name + "!");
        addMessage(
          "gm",
          "Kontynuujesz swoją przygodę w mrocznych krainach fantasy..."
        );
      } else {
        setPhase("character-creation");
      }
    }
  };

  const handleCreateCampaign = (campaignName: string) => {
    const campaignId = Date.now().toString();
    setCurrentCampaignId(campaignId);
    setCurrentCampaignName(campaignName);

    // Save campaign to campaigns list
    const campaignsKey = `campaigns_${username}`;
    const existingCampaigns = localStorage.getItem(campaignsKey);
    const campaigns = existingCampaigns ? JSON.parse(existingCampaigns) : [];
    campaigns.push({
      id: campaignId,
      name: campaignName,
      createdAt: new Date().toISOString(),
    });
    localStorage.setItem(campaignsKey, JSON.stringify(campaigns));

    // Create empty campaign data
    const campaignData = {
      name: campaignName,
      character: null,
      messages: [],
    };
    localStorage.setItem(
      `campaign_${username}_${campaignId}`,
      JSON.stringify(campaignData)
    );

    setPhase("character-creation");
  };

  const handleCharacterCreated = (characterData: any) => {
    const newCharacter: Character = {
      name: characterData.name,
      class: characterData.class,
      background: characterData.background,
      level: 1,
      hp: 20 + characterData.stats.con,
      maxHp: 20 + characterData.stats.con,
      str: characterData.stats.str,
      dex: characterData.stats.dex,
      con: characterData.stats.con,
      int: characterData.stats.int,
      wis: characterData.stats.wis,
      cha: characterData.stats.cha,
      lck: characterData.stats.lck,
    };
    setCharacter(newCharacter);

    // Save character to campaign
    if (currentCampaignId) {
      const campaignKey = `campaign_${username}_${currentCampaignId}`;
      const savedCampaign = localStorage.getItem(campaignKey);
      const campaign = savedCampaign ? JSON.parse(savedCampaign) : {};
      campaign.character = newCharacter;
      localStorage.setItem(campaignKey, JSON.stringify(campaign));

      // Update campaigns list with character info
      const campaignsKey = `campaigns_${username}`;
      const existingCampaigns = localStorage.getItem(campaignsKey);
      const campaigns = existingCampaigns ? JSON.parse(existingCampaigns) : [];
      const campaignIndex = campaigns.findIndex(
        (c: any) => c.id === currentCampaignId
      );
      if (campaignIndex !== -1) {
        campaigns[campaignIndex].characterName = newCharacter.name;
        campaigns[campaignIndex].level = newCharacter.level;
        localStorage.setItem(campaignsKey, JSON.stringify(campaigns));
      }
    }

    setPhase("game");
    addMessage("system", "Postać utworzona!");
    addMessage(
      "gm",
      `Witaj, ${newCharacter.name}! Twoja przygoda w mrocznym świecie fantasy właśnie się rozpoczyna. Znajdujesz się w ponurej tawernie "Srebrny Smok", gdzie gwar rozmów miesza się z zapachem starego piwa i dymu z kominka.`
    );
  };

  const addMessage = (
    type: Message["type"],
    content: string,
    rollResult?: Message["rollResult"]
  ) => {
    const newMessage: Message = {
      id: Date.now().toString() + Math.random(),
      type,
      content,
      timestamp: formatTime(),
      rollResult,
    };
    setMessages((prev) => [...prev, newMessage]);
  };

  const handleSendMessage = (message: string) => {
    addMessage("player", message);

    setTimeout(() => {
      const responses = [
        "Zaciekawiony, podchodzisz bliżej. W mroku dostrzegasz tajemnicze symbole na starym kamieniu...",
        "Twoje kroki odbijają się echem w ciemności. Coś się rusza w cieniach...",
        "Stary mag kiwa głową i mówi: 'Szukasz przygód? Mam dla ciebie zadanie...'",
        "Rozglądasz się wokół. Na ścianie wisi mapa prowincji z zaznaczonymi niebezpiecznymi obszarami.",
        "Czujesz, że to początek czegoś wielkiego. Czy jesteś gotowy na wyzwanie?",
      ];
      const randomResponse =
        responses[Math.floor(Math.random() * responses.length)];
      addMessage("gm", randomResponse);

      if (Math.random() > 0.7 && !combatState) {
        setTimeout(() => startCombat(), 1000);
      }
    }, 1000);
  };

  const startCombat = () => {
    const enemy = generateEnemy(character?.level || 1);
    vibrate(30);

    setCombatState({
      enemy: { ...enemy, hp: enemy.maxHp },
      playerTurn: true,
    });
    addMessage("system", `Walka rozpoczęta! ${enemy.name} atakuje!`);
  };

  const handleAttack = () => {
    if (!combatState || !character) return;

    const attackRoll = rollDice("1d20");
    const modifier = getModifier(character.str);
    const total = attackRoll + modifier;

    addMessage("roll", `Rzut na atak`, {
      dice: "1d20",
      result: attackRoll,
      modifier,
      total,
    });

    if (total >= (combatState.enemy.armor || 10)) {
      const damageRoll = rollDice("1d8");
      const damage = damageRoll + modifier;
      const newEnemyHp = Math.max(0, combatState.enemy.hp - damage);

      vibrate([10, 50, 10]);
      addMessage("gm", `Trafiłeś! Zadajesz ${damage} obrażeń.`);

      if (newEnemyHp <= 0) {
        vibrate([30, 100, 30]);
        addMessage("system", `Pokonałeś ${combatState.enemy.name}!`);
        setCombatState(null);
        setTimeout(() => {
          const loot = generateLoot(combatState.enemy.level);
          setLootState(loot);
          addMessage("gm", "Przeszukujesz ciało pokonanego wroga...");
        }, 1000);
      } else {
        setCombatState({
          ...combatState,
          enemy: { ...combatState.enemy, hp: newEnemyHp },
          playerTurn: false,
        });
        setTimeout(handleEnemyTurn, 1500);
      }
    } else {
      vibrate(20);
      addMessage("gm", "Chybiłeś!");
      setCombatState({ ...combatState, playerTurn: false });
      setTimeout(handleEnemyTurn, 1500);
    }
  };

  const handleEnemyTurn = () => {
    if (!combatState || !character) return;

    const enemyRoll = rollDice("1d20");
    const enemyHits = enemyRoll >= 10;

    if (enemyHits) {
      const damage = rollDice("1d6") + 2;
      const newHp = Math.max(0, character.hp - damage);

      vibrate([50, 100, 50]);
      addMessage("gm", `${combatState.enemy.name} trafia! Otrzymujesz ${damage} obrażeń.`);

      setCharacter({ ...character, hp: newHp });
      localStorage.setItem(
        `character_${username}`,
        JSON.stringify({ ...character, hp: newHp })
      );

      if (newHp <= 0) {
        vibrate([100, 200, 100]);
        setCombatState(null);
        setTimeout(() => {
          setPhase("death");
        }, 1000);
        return;
      }
    } else {
      addMessage("gm", `${combatState.enemy.name} chybił!`);
    }

    setCombatState({ ...combatState, playerTurn: true });
  };

  const handleFlee = () => {
    const fleeRoll = rollDice("1d20");
    const dexModifier = character ? getModifier(character.dex) : 0;
    const total = fleeRoll + dexModifier;

    if (total >= 12) {
      vibrate(20);
      addMessage("system", "Udało ci się uciec!");
      setCombatState(null);
    } else {
      vibrate([30, 50]);
      addMessage("gm", "Nie udało się uciec! Przeciwnik cię dogonił.");
      setCombatState({ ...combatState!, playerTurn: false });
      setTimeout(handleEnemyTurn, 1000);
    }
  };

  // Auto-save campaign progress
  useEffect(() => {
    if (currentCampaignId && username && phase === "game") {
      const campaignKey = `campaign_${username}_${currentCampaignId}`;
      const savedCampaign = localStorage.getItem(campaignKey);
      const campaign = savedCampaign ? JSON.parse(savedCampaign) : {};
      campaign.character = character;
      campaign.messages = messages;
      localStorage.setItem(campaignKey, JSON.stringify(campaign));
    }
  }, [character, messages, currentCampaignId, username, phase]);

  const handleRestart = () => {
    // Clear current campaign character and start fresh
    if (currentCampaignId) {
      const campaignKey = `campaign_${username}_${currentCampaignId}`;
      const savedCampaign = localStorage.getItem(campaignKey);
      const campaign = savedCampaign ? JSON.parse(savedCampaign) : {};
      campaign.character = null;
      campaign.messages = [];
      localStorage.setItem(campaignKey, JSON.stringify(campaign));
    }

    setPhase("character-creation");
    setCharacter(null);
    setMessages([]);
    setCombatState(null);
    setLootState(null);
  };

  const handleLogout = () => {
    // Save current state before logout
    if (currentCampaignId && character) {
      const campaignKey = `campaign_${username}_${currentCampaignId}`;
      const savedCampaign = localStorage.getItem(campaignKey);
      const campaign = savedCampaign ? JSON.parse(savedCampaign) : {};
      campaign.character = character;
      campaign.messages = messages;
      localStorage.setItem(campaignKey, JSON.stringify(campaign));

      // Update last played
      const campaignsKey = `campaigns_${username}`;
      const existingCampaigns = localStorage.getItem(campaignsKey);
      const campaigns = existingCampaigns ? JSON.parse(existingCampaigns) : [];
      const campaignIndex = campaigns.findIndex(
        (c: any) => c.id === currentCampaignId
      );
      if (campaignIndex !== -1) {
        campaigns[campaignIndex].lastPlayed = new Date().toLocaleDateString(
          "pl-PL"
        );
        localStorage.setItem(campaignsKey, JSON.stringify(campaigns));
      }
    }

    setPhase("campaign-select");
    setCurrentCampaignId(null);
    setCurrentCampaignName("");
    setCharacter(null);
    setMessages([]);
    setCombatState(null);
    setLootState(null);
  };

  return (
    <>
      <MobileViewportIndicator />
      {phase === "login" && <LoginScreen onLogin={handleLogin} />}
      {phase === "campaign-select" && (
        <CampaignSelect
          username={username}
          onSelectCampaign={handleSelectCampaign}
          onCreateCampaign={() => setPhase("campaign-create")}
          onLogout={() => {
            setPhase("login");
            setUsername("");
          }}
        />
      )}
      {phase === "campaign-create" && (
        <CampaignCreate
          onBack={() => setPhase("campaign-select")}
          onCreate={handleCreateCampaign}
        />
      )}
      {phase === "character-creation" && (
        <CharacterCreation onComplete={handleCharacterCreated} />
      )}
      {phase === "death" && (
        <DeathScreen
          causeOfDeath="Uległeś swoim ranom w walce..."
          onRestart={handleRestart}
          onMainMenu={handleLogout}
        />
      )}
      {phase === "game" && character && (
        <GameScreen
          gameState={{
            character,
            combat: combatState || undefined,
            loot: lootState || undefined,
          }}
          messages={messages}
          onSendMessage={handleSendMessage}
          onAttack={handleAttack}
          onFlee={handleFlee}
          onLogout={handleLogout}
        />
      )}
    </>
  );
}
