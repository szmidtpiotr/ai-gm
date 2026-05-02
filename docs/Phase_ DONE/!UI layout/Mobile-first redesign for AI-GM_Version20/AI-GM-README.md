# AI-GM - Polish Fantasy Text RPG

A mobile-first dark fantasy text RPG where AI acts as the Game Master.

## Design System

### Colors
- **Primary**: Gold (`#d4af37`) - Used for highlights, important UI elements
- **Background**: Very dark blue-black (`#0a0a0f`)
- **Cards**: Slightly lighter dark (`#14141a`)
- **Combat danger**: Deep red tones
- **HP colors**: Green (high) → Gold (mid) → Red (low)

### Typography
- System font stack
- Base size: 16px
- Polish UI language
- English stat abbreviations (STR, DEX, CON, INT, WIS, CHA, LCK)

### Spacing & Layout
- Mobile-first (primary: 390px, also 375px, 320px)
- 44px minimum touch targets
- Bottom-sticky composer
- One-thumb optimized navigation

## Screens

### 1. Login Screen (`login-screen.tsx`)
- Username input
- First visit → Character Creation
- Return visit → Load saved character

### 2. Character Creation (`character-creation.tsx`)
- 4-step wizard with progress bar
- Steps: Name → Class → Background → Stats
- Stat distribution with sliders
- Classes: Warrior, Rogue, Mage, Cleric
- Backgrounds: Noble, Soldier, Scholar, Outlaw

### 3. Game Screen (`game-screen.tsx`)
- Header with character info
- Compact stats bar
- Scrollable chat messages
- Combat UI (when in combat)
- Loot display (after victory)
- Bottom-sheet character details
- Sticky message composer
- Settings dropdown (sound, history, logout)

### 4. Death Screen (`death-screen.tsx`)
- Cause of death display
- Restart option
- Return to main menu

## Components

### Chat System
- **ChatMessage**: Player, GM, system, and dice roll messages
- Different styling per message type
- Timestamps
- Special dice roll card with result display

### Combat System
- **CombatUI**: Enemy health, turn indicator, action buttons
- Attack and Flee buttons
- Real-time HP tracking
- Visual turn indication

### Character System
- **CharacterStats**: Full and compact views
- HP bar with color coding
- Stat blocks with modifiers
- Expandable character sheet (drawer)

### Loot System
- **LootCard**: Post-combat rewards
- Item rarity color coding
- Gold display
- Item type icons

### Input
- **MessageComposer**: Sticky bottom input
- Auto-growing textarea
- Send button
- Disabled during enemy turn

## HTML ID Contracts

Critical IDs that must not be renamed (for JS compatibility):

### Screens
- `#login-screen`
- `#character-creation`
- `#game-screen`
- `#death-screen`

### Game Elements
- `#character-stats`
- `#character-stats-compact`
- `#chat-messages`
- `#combat-ui`
- `#message-composer`
- `#loot-card`

### Buttons
- `#character-sheet-button`
- `#settings-button`
- `#send-button`
- `#combat-attack-button`
- `#combat-flee-button`
- `#character-creation-next`
- `#character-creation-back`

### Inputs
- `#username`
- `#character-name`
- `#message-input`

### Actions
- `#logout`
- `#toggle-sound`
- `#view-history`
- `#death-restart`
- `#death-main-menu`

## Game Flow

### First Visit
1. Login screen → enter username
2. Character creation wizard
3. Game screen with welcome message
4. LocalStorage saves character

### Return Visit
1. Login screen → enter username
2. Load character from LocalStorage
3. Game screen continues adventure

### Combat Flow
1. Random encounter triggers
2. Combat UI appears
3. Player turn → Attack/Flee
4. Enemy turn (automated)
5. Victory → Loot display
6. Defeat → Death screen

### Death Flow
1. HP reaches 0
2. Death screen displays
3. Options: Restart (new character) or Main Menu

## Technical Notes

- React 18 + TypeScript
- Tailwind CSS v4
- Radix UI components
- Vaul for bottom sheets
- LocalStorage for persistence
- No backend required (pure frontend)
- Mobile viewport optimized
- 60fps smooth animations

## Development

To view design showcase:
```tsx
// In App.tsx, temporarily replace default export:
import { DemoShowcase } from "./components/demo-showcase";
export default DemoShowcase;
```

## Future Enhancements

- Inventory system
- Quest log
- Multiple save slots
- Character portraits
- Sound effects
- Background music
- AI-powered GM responses
- More character classes
- Equipment system
- Leveling up mechanics
