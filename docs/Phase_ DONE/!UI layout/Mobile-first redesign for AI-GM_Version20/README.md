# 🎲 AI-GM

> Polish fantasy text RPG where AI is the Game Master

<div align="center">

**Mobile-First • Dark Fantasy • One-Thumb Gameplay**

[Quick Start](#-quick-start) • [Features](#-features) • [Screens](#-screens) • [Documentation](#-documentation)

</div>

---

## 📱 Overview

AI-GM is a mobile-first text-based RPG with turn-based combat, character creation, and persistent progression. Designed for immersive one-thumb gameplay on phones (320px-390px).

### Design Highlights

- **Dark Fantasy Theme**: Cinematic black backgrounds with gold accents
- **Polish Language**: Full UI in Polish, maintaining cultural immersion
- **Mobile Optimized**: 44px touch targets, sticky bottom controls, smooth animations
- **Preserved Contracts**: HTML IDs maintained for vanilla JS compatibility

---

## 🚀 Quick Start

### For Players

1. Open the app on mobile (or resize browser to 390px)
2. Enter your username
3. Create your character (4-step wizard)
4. Start your adventure!

### For Developers

```bash
# Install dependencies
pnpm install

# Start dev server (auto-running in Figma Make)
# App is at http://localhost:5173

# View design showcase
# Edit App.tsx: export { DemoShowcase as default }
```

---

## ✨ Features

### ✅ Complete Game Loop
- Login with username
- Character creation (name, class, background, stats)
- Text-based adventure gameplay
- Turn-based combat system
- Loot and rewards
- Permadeath and restart

### ✅ Combat System
- D20 dice mechanics (roll + modifier vs armor)
- Attack/Flee tactical choices
- Real-time HP tracking
- Dynamic enemy generation
- Haptic feedback (vibration)
- Victory rewards (gold + items)

### ✅ Mobile Excellence
- One-thumb optimized layout
- Bottom-sticky message composer
- Bottom-sheet character details
- Auto-scrolling chat
- Smooth 60fps animations
- Touch-friendly 44px targets

### ✅ Character System
- 7 core stats (STR, DEX, CON, INT, WIS, CHA, LCK)
- 4 classes (Warrior, Rogue, Mage, Cleric)
- 4 backgrounds (Noble, Soldier, Scholar, Outlaw)
- Stat customization (8-18 range)
- HP tracking with color coding
- LocalStorage persistence

### ✅ UI Polish
- Message types (Player, GM, System, Dice Roll)
- Rarity-coded loot (common → legendary)
- Turn indicators in combat
- Settings dropdown (sound, history, logout)
- Loading states and transitions
- Viewport size indicator (dev mode)

---

## 📱 Screens

### 1. Login Screen
Simple username entry with auto-detect for returning players.

### 2. Character Creation
4-step wizard:
1. Name your character
2. Choose class
3. Choose background
4. Distribute stats (sliders)

### 3. Game Screen
- **Header**: Character name, HP, settings
- **Stats Bar**: Compact view with all stats
- **Chat Area**: Scrolling messages (GM, player, system, rolls)
- **Combat UI**: Shows during encounters (enemy HP, actions)
- **Composer**: Bottom-sticky input with send button

### 4. Death Screen
Permadeath message with restart or main menu options.

---

## 🎨 Design System

### Colors
```css
--primary: #d4af37;           /* Gold - highlights, CTAs */
--background: #0a0a0f;        /* Deep black - main bg */
--card: #14141a;              /* Dark gray - surfaces */
--destructive: #c23b3b;       /* Red - danger, low HP */
--success: #4a9d5f;           /* Green - victory, high HP */
--chat-player: #1e2a3a;       /* Blue tint - player messages */
--chat-gm: #2a1e2a;           /* Purple tint - GM messages */
```

### Typography
- Base: 16px system font stack
- Headings: Medium weight (500)
- Body: Normal weight (400)
- Tabular numbers for stats

### Spacing
- Touch targets: 44px minimum
- Padding: 16px (mobile), responsive
- Border radius: 0.75rem (12px)
- Gap: 8px-16px contextual

---

## 🏗️ Architecture

### Tech Stack
- **React 18** + TypeScript
- **Tailwind CSS v4** (design tokens)
- **Radix UI** (accessible primitives)
- **Vaul** (bottom sheets)
- **Motion** (animations)
- **Lucide React** (icons)
- **Vite 6** (build tool)

### Project Structure
```
src/
├── app/
│   ├── App.tsx                    # Game controller
│   └── components/
│       ├── screens/               # Full-screen views
│       │   ├── login-screen.tsx
│       │   ├── character-creation.tsx
│       │   ├── game-screen.tsx
│       │   └── death-screen.tsx
│       ├── character-stats.tsx    # HP, stats display
│       ├── chat-message.tsx       # Message bubbles
│       ├── combat-ui.tsx          # Combat interface
│       ├── message-composer.tsx   # Input + send
│       ├── loot-card.tsx          # Rewards display
│       └── ui/                    # shadcn components
├── lib/
│   ├── game-utils.ts              # Dice, combat, loot
│   ├── settings.ts                # User preferences
│   └── utils.ts                   # General helpers
└── styles/
    ├── theme.css                  # Design tokens
    ├── animations.css             # Custom keyframes
    └── index.css                  # Main stylesheet
```

### Key Contracts (HTML IDs)

**Critical**: These IDs are preserved for vanilla JS compatibility.

```typescript
// Screens
"#login-screen"
"#character-creation"
"#game-screen"
"#death-screen"

// Components
"#character-stats"
"#chat-messages"
"#combat-ui"
"#message-composer"

// Actions
"#send-button"
"#combat-attack-button"
"#combat-flee-button"
"#message-input"
```

See [AI-GM-README.md](./AI-GM-README.md) for full ID list.

---

## 🎮 Game Mechanics

### Dice System
- D20 for attack rolls (1d20 + modifier)
- D8 for damage (1d8 + STR modifier)
- D6 for enemy damage (1d6 + 2)
- D20 for flee attempts (1d20 + DEX modifier)

### Combat Formula
```typescript
// Player attacks
attackRoll = 1d20 + STR_modifier
if (attackRoll >= enemy.armor) {
  damage = 1d8 + STR_modifier
  enemy.hp -= damage
}

// Enemy attacks  
enemyRoll = 1d20
if (enemyRoll >= 10) {
  damage = 1d6 + 2
  player.hp -= damage
}

// Flee attempt
fleeRoll = 1d20 + DEX_modifier
if (fleeRoll >= 12) escape()
```

### Stat Modifiers
```typescript
modifier = floor((stat - 10) / 2)
// Examples:
// STR 16 → +3
// DEX 12 → +1
// CON 8  → -1
```

---

## 📚 Documentation

- **[AI-GM-README.md](./AI-GM-README.md)** - Complete feature documentation
- **[IMPLEMENTATION.md](./IMPLEMENTATION.md)** - Feature checklist & technical details
- **[QUICKSTART.md](./QUICKSTART.md)** - Developer guide & common tasks

---

## 🔮 Future Roadmap

### v1.1 - AI Integration
- [ ] Connect to Claude/GPT API for dynamic GM responses
- [ ] Context-aware storytelling
- [ ] Adaptive difficulty

### v1.2 - Inventory
- [ ] Item slots (weapon, armor, accessories)
- [ ] Consumables (potions, scrolls)
- [ ] Equipment stats and bonuses

### v1.3 - Progression
- [ ] XP and leveling system
- [ ] Skill trees per class
- [ ] Character portraits

### v1.4 - Content
- [ ] More classes (Ranger, Bard, Paladin)
- [ ] More enemies (Dragons, Liches, Demons)
- [ ] Spell system for casters
- [ ] Crafting system

### v1.5 - Multiplayer
- [ ] Party-based adventures
- [ ] Shared campaigns
- [ ] Co-op combat

---

## 🤝 Contributing

Ideas welcome! Focus areas:
- AI-powered GM responses
- Content (classes, enemies, items, quests)
- Sound design (music, SFX)
- Accessibility improvements
- Localization (English, Spanish, etc.)

---

## 📄 License

Built with ❤️ for Figma Make

---

## 🎯 Screenshots

> Mobile-first design (390px width recommended)

- **Login**: Clean username entry with fantasy branding
- **Creation**: 4-step wizard with progress bar
- **Game**: Scrolling chat, sticky composer, bottom sheet
- **Combat**: Enemy HP, turn indicator, tactical buttons
- **Loot**: Rarity-coded items, gold rewards
- **Death**: Cinematic permadeath screen

---

**Ready to adventure? Start playing now!** 🎲✨
