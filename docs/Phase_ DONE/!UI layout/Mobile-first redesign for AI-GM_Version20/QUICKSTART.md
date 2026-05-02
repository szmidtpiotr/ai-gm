# AI-GM Quick Start Guide

## 🎮 For Players

1. **First Time Playing**
   - Enter your username
   - Create your character (choose class, background, distribute stats)
   - Start your adventure!

2. **Returning Players**
   - Enter your username
   - Your character loads automatically
   - Continue where you left off

3. **Playing the Game**
   - Read GM narration (purple speech bubbles)
   - Type your actions in the bottom composer
   - Tap Attack/Flee during combat
   - View character sheet by tapping the user icon
   - Access settings via the gear icon

4. **Combat Tips**
   - Attack: Roll 1d20 + STR modifier vs enemy armor
   - Flee: Roll 1d20 + DEX modifier (need 12+)
   - Watch your HP - healing items coming soon!
   - Victory = Loot and gold

## 🛠️ For Developers

### Project Structure
```
/workspaces/default/code/
├── src/
│   ├── app/
│   │   ├── App.tsx              # Main game controller
│   │   └── components/
│   │       ├── screens/         # Full screen components
│   │       ├── *.tsx            # Game components
│   │       └── ui/              # shadcn/ui components
│   ├── lib/
│   │   ├── game-utils.ts        # Game mechanics
│   │   ├── settings.ts          # User preferences
│   │   └── utils.ts             # General utilities
│   └── styles/
│       ├── theme.css            # Design tokens
│       ├── animations.css       # Custom animations
│       └── index.css            # Main styles
├── AI-GM-README.md              # Full documentation
├── IMPLEMENTATION.md            # Feature checklist
└── QUICKSTART.md                # This file
```

### Key Files to Understand

1. **App.tsx** - Game state and flow control
   - Phase management (login/creation/game/death)
   - Character state
   - Combat logic
   - Message handling

2. **game-utils.ts** - Core mechanics
   - Dice rolling
   - Damage calculation
   - Enemy generation
   - Loot generation

3. **theme.css** - Design system
   - Color tokens
   - Typography
   - Spacing
   - Dark fantasy palette

### Making Changes

#### Add a New Character Class
1. Edit `character-creation.tsx`
2. Add to `classes` array:
```tsx
{ id: "ranger", name: "Łowca", description: "Mistrz łuku" }
```

#### Add New Enemy Type
1. Edit `game-utils.ts`
2. Add to `enemies` array in `generateEnemy()`:
```tsx
{ name: "Smok", hpMultiplier: 3.0, armorBonus: 5 }
```

#### Add New Loot Item
1. Edit `game-utils.ts`
2. Add to `itemPool` array in `generateLoot()`:
```tsx
{ name: "Magiczny miecz", type: "weapon", rarity: "epic" }
```

#### Change Color Scheme
1. Edit `src/styles/theme.css`
2. Update CSS variables in `:root`:
```css
--primary: #your-color;
--background: #your-bg;
```

#### Add Sound Effects
1. Create sound files in `public/sounds/`
2. Update `playSound()` in `game-utils.ts`
3. Call `playSound("attack")` in combat handlers

### HTML ID Contracts

**CRITICAL: Do not rename these IDs** (used by vanilla JS):

#### Screen IDs
- `#login-screen`
- `#character-creation`
- `#game-screen`
- `#death-screen`

#### Component IDs
- `#character-stats`
- `#character-stats-compact`
- `#chat-messages`
- `#combat-ui`
- `#combat-actions`
- `#message-composer`
- `#loot-card`

#### Interactive IDs
- `#username`
- `#character-name`
- `#message-input`
- `#send-button`
- `#combat-attack-button`
- `#combat-flee-button`
- `#character-sheet-button`
- `#settings-button`

### Testing Different Screens

#### View Design Showcase
```tsx
// In App.tsx, replace export:
import { DemoShowcase } from "./components/demo-showcase";
export default DemoShowcase;
```

#### Force Combat Encounter
```tsx
// In App.tsx, after first GM message:
setTimeout(() => startCombat(), 2000);
```

#### Test Death Screen
```tsx
// In App.tsx, set character HP to 1
// Then trigger combat
```

#### Clear All Data
```javascript
// In browser console:
localStorage.clear();
location.reload();
```

### Mobile Testing

#### Desktop Browser
1. Open DevTools (F12)
2. Toggle device toolbar (Ctrl+Shift+M)
3. Select "iPhone 12 Pro" or similar
4. Test at 390px, 375px, 320px widths

#### Check Viewport Indicator
- Small red dot shows current width in dev mode
- Red = 320px
- Yellow = 375px  
- Green = 390px
- Gray = larger

### Common Tasks

#### Add GM Response Template
```tsx
// In handleSendMessage():
const responses = [
  "Your new response here...",
  // ... existing responses
];
```

#### Adjust Combat Difficulty
```tsx
// In game-utils.ts, generateEnemy():
const baseHp = 15 + level * 8; // More HP
const armor = 12 + level * 2;  // More armor
```

#### Change Starting Stats
```tsx
// In character-creation.tsx:
stats: { str: 12, dex: 12, ... } // New defaults
```

#### Customize Loot Drop Rate
```tsx
// In App.tsx, handleSendMessage():
if (Math.random() > 0.5) { // Was 0.7, now 50% chance
  setTimeout(() => startCombat(), 1000);
}
```

## 🐛 Debugging

### Character Not Saving
- Check browser console for localStorage errors
- Verify username is not empty
- Check `character_${username}` key in DevTools > Application > LocalStorage

### Combat Not Working
- Check `combatState` in React DevTools
- Verify `onAttack` and `onFlee` props passed to CombatUI
- Check console for dice roll logs

### Messages Not Scrolling
- Verify `messagesEndRef` is attached
- Check ScrollArea component rendering
- Test `scrollToBottom()` manually in console

### Styles Not Applying
- Check Tailwind classes are valid
- Verify theme.css variables are defined
- Inspect element to see computed styles
- Clear browser cache

## 📚 Resources

- **Tailwind CSS**: https://tailwindcss.com/docs
- **Radix UI**: https://www.radix-ui.com/
- **Lucide Icons**: https://lucide.dev/
- **React Docs**: https://react.dev/

## 🤝 Contributing Ideas

1. AI Integration - Connect to Claude/GPT API for dynamic GM responses
2. Inventory System - Track items, equipment, consumables
3. Quest Log - Track active quests and completed objectives
4. Character Portraits - Add avatar images
5. Sound Design - Add music and SFX
6. Multiplayer - Allow party-based adventures
7. More Content - Classes, enemies, items, spells
8. Analytics - Track player choices and outcomes

## 💡 Tips

- Keep mobile-first mindset
- Preserve HTML IDs for compatibility
- Test on real devices when possible
- Use haptic feedback thoughtfully
- Polish UI maintains dark fantasy tone
- Combat should feel tactical, not random
- GM narration sets the mood

Happy coding! 🎲
