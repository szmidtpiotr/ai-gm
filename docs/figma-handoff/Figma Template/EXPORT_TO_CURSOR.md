# AI RPG Game - Export Package for Cursor

## 📋 Overview
This is a complete export of an AI-driven text-based RPG game with Warhammer Fantasy/D&D aesthetic. The app features a player interface for gameplay and an admin panel for game management.

**Design Style**: Midnight Arcane - Dark purple (#0d0821) with golden accents (#fcd34d)

---

## 🎨 Color Palette

```css
/* Main Backgrounds */
#0d0821  - Primary background (darkest)
#150f2e  - Headers/footers
#1a1035  - Card backgrounds
#2d1f52  - Darker elements

/* Purple Accents */
#5b21b6  - Active states, primary purple
#4c1d95  - Purple gradient start
#7c3aed  - Purple gradient end
#3d2866  - Borders
#6d28d9  - Secondary borders

/* Text Colors */
#faf5ff  - Primary text (lightest)
#f3e8ff  - Secondary text
#e9d5ff  - Tertiary text
#c4b5fd  - Labels
#a78bfa  - Muted text

/* Gold Accents */
#fcd34d  - Primary gold
#fbbf24  - Button gold start
#f59e0b  - Button gold end
```

---

## 📦 Installation Steps

### 1. Create React + TypeScript Project
```bash
npm create vite@latest my-rpg-game -- --template react-ts
cd my-rpg-game
```

### 2. Install Dependencies
```bash
npm install lucide-react
npm install -D tailwindcss @tailwindcss/vite
```

### 3. Configure Tailwind CSS

Create `vite.config.ts`:
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
})
```

Create `src/styles/tailwind.css`:
```css
@import "tailwindcss";
```

Update `src/main.tsx`:
```typescript
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './app/App.tsx'
import './styles/tailwind.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

---

## 📁 File Structure

```
src/
├── app/
│   ├── App.tsx
│   └── components/
│       ├── PlayerApp.tsx
│       └── AdminApp.tsx
├── styles/
│   └── tailwind.css
└── main.tsx
```

---

## 💻 Source Code

### `src/app/App.tsx`

```typescript
import { useState } from 'react';
import PlayerApp from './components/PlayerApp';
import AdminApp from './components/AdminApp';

export default function App() {
  const [view, setView] = useState<'player' | 'admin'>('player');

  return (
    <div className="size-full flex flex-col bg-stone-950">
      {/* View Switcher */}
      <div className="bg-stone-900 border-b border-stone-700 p-3 flex gap-2 shrink-0">
        <button
          onClick={() => setView('player')}
          className={`px-6 py-2 rounded transition-colors ${
            view === 'player'
              ? 'bg-purple-700 text-purple-50 font-semibold'
              : 'bg-stone-800 text-stone-400 hover:bg-stone-700'
          }`}
        >
          Player View
        </button>
        <button
          onClick={() => setView('admin')}
          className={`px-6 py-2 rounded transition-colors ${
            view === 'admin'
              ? 'bg-purple-700 text-purple-50 font-semibold'
              : 'bg-stone-800 text-stone-400 hover:bg-stone-700'
          }`}
        >
          Admin Panel
        </button>
      </div>

      {/* View Display */}
      <div className="flex-1 overflow-hidden">
        {view === 'player' ? <PlayerApp onNavigateToAdmin={() => setView('admin')} /> : <AdminApp onNavigateToPlayer={() => setView('player')} />}
      </div>
    </div>
  );
}
```

---

### `src/app/components/PlayerApp.tsx`

```typescript
import { useState } from 'react';
import { MessageSquare, User, Settings, Crown, Send, Sword, Shield, Heart, ArrowRight, ShieldAlert } from 'lucide-react';

interface PlayerAppProps {
  onNavigateToAdmin: () => void;
}

export default function PlayerApp({ onNavigateToAdmin }: PlayerAppProps) {
  const [activeTab, setActiveTab] = useState('chat');

  const messages = [
    {
      type: 'gm',
      text: 'You enter the dimly lit tavern. The smell of ale and smoke fills your nostrils. A hooded figure in the corner watches you intently, their gloved hand resting on a worn leather satchel.',
    },
    {
      type: 'player',
      text: 'I approach the hooded figure cautiously, hand on my sword hilt.',
    },
    {
      type: 'gm',
      text: 'The figure raises their head slightly. "You seek the merchant\'s daughter, don\'t you?" Their voice is raspy, barely above a whisper. The figure\'s eyes gleam in the candlelight—one blue, one milky white.',
    },
    {
      type: 'player',
      text: 'I nod slowly. "What do you know about her disappearance?"',
    },
    {
      type: 'gm',
      text: '"More than you\'d like to hear, sellsword." The figure slides a tarnished silver coin across the table. Strange runes are carved into its surface. "The girl walked into the Blackwood willingly. No one forced her hand."',
    },
  ];

  return (
    <div className="size-full flex flex-col md:flex-row" style={{ backgroundColor: '#0d0821' }}>
      {/* Main Content */}
      <div className="flex-1 flex flex-col min-h-0">
        {/* Header */}
        <div
          className="px-4 py-4 shrink-0"
          style={{
            backgroundColor: '#150f2e',
            borderBottom: '1px solid #2d1f52',
          }}
        >
          <div className="flex items-center justify-between max-w-5xl mx-auto">
            <div className="flex items-center gap-3">
              <div
                className="w-11 h-11 rounded-xl flex items-center justify-center"
                style={{
                  background: 'linear-gradient(135deg, #4c1d95 0%, #5b21b6 100%)',
                  boxShadow: '0 4px 12px rgba(139, 92, 246, 0.2)',
                }}
              >
                <Crown className="w-6 h-6" style={{ color: '#fcd34d' }} />
              </div>
              <div>
                <div className="font-bold tracking-tight" style={{ color: '#faf5ff', fontSize: '18px' }}>
                  The Cursed Vale
                </div>
                <div className="text-xs" style={{ color: '#a78bfa' }}>
                  Session in progress
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-hidden">
          {/* Chat Tab */}
          {activeTab === 'chat' && (
            <div className="h-full flex flex-col max-w-5xl mx-auto w-full">
              <div className="flex-1 overflow-y-auto px-4 py-5 space-y-4">
                {messages.map((msg, idx) => (
                  <div key={idx} className={`flex gap-3 ${msg.type === 'player' ? 'justify-end' : 'justify-start'}`}>
                    {/* Avatar - left for GM */}
                    {msg.type === 'gm' && (
                      <div
                        className="w-9 h-9 rounded-xl shrink-0 flex items-center justify-center"
                        style={{
                          backgroundColor: '#2d1f52',
                          border: '2px solid #5b21b6',
                        }}
                      >
                        <Crown className="w-4 h-4" style={{ color: '#fcd34d' }} />
                      </div>
                    )}

                    {/* Message */}
                    <div className="space-y-1" style={{ maxWidth: '80%' }}>
                      <div
                        className={`text-[11px] font-bold tracking-wider uppercase ${msg.type === 'player' ? 'text-right' : ''}`}
                        style={{ color: msg.type === 'gm' ? '#c4b5fd' : '#fcd34d' }}
                      >
                        {msg.type === 'gm' ? 'Game Master' : 'Your Action'}
                      </div>
                      <div
                        className="px-4 py-3.5 rounded-2xl inline-block"
                        style={{
                          backgroundColor: msg.type === 'gm' ? '#1a1035' : '#2d1f52',
                          border: `1px solid ${msg.type === 'gm' ? '#3d2866' : '#5b21b6'}`,
                          color: '#f3e8ff',
                          lineHeight: '1.65',
                        }}
                      >
                        <div style={{ fontSize: '14px' }}>{msg.text}</div>
                      </div>
                    </div>

                    {/* Avatar - right for Player */}
                    {msg.type === 'player' && (
                      <div
                        className="w-9 h-9 rounded-xl shrink-0 flex items-center justify-center"
                        style={{
                          backgroundColor: '#3d2866',
                          border: '2px solid #6d28d9',
                        }}
                      >
                        <User className="w-4 h-4" style={{ color: '#fcd34d' }} />
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* Input */}
              <div
                className="px-4 py-4 shrink-0"
                style={{
                  backgroundColor: '#150f2e',
                  borderTop: '1px solid #2d1f52',
                }}
              >
                <div className="flex gap-3">
                  <input
                    type="text"
                    placeholder="What do you do..."
                    className="flex-1 px-4 py-3.5 rounded-xl border focus:outline-none focus:ring-2"
                    style={{
                      backgroundColor: '#0d0821',
                      borderColor: '#3d2866',
                      color: '#f3e8ff',
                      fontSize: '15px',
                    }}
                  />
                  <button
                    className="px-7 py-3.5 rounded-xl font-bold flex items-center gap-2 shadow-lg"
                    style={{
                      background: 'linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%)',
                      color: '#0d0821',
                      boxShadow: '0 4px 16px rgba(251, 191, 36, 0.3)',
                    }}
                  >
                    <ArrowRight className="w-5 h-5" />
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Character Tab */}
          {activeTab === 'character' && (
            <div className="h-full overflow-y-auto px-4 py-5 max-w-5xl mx-auto w-full">
              <div className="grid md:grid-cols-2 gap-4">
                {/* Character Header */}
                <div className="md:col-span-2 text-center pb-4 border-b border-purple-900/30">
                  <div className="text-2xl font-bold" style={{ color: '#faf5ff' }}>
                    Aldric Stormborn
                  </div>
                  <div className="text-sm mt-1" style={{ color: '#a78bfa' }}>
                    Human Warrior • Level 3
                  </div>
                </div>

                {/* HP/AC */}
                <div
                  className="p-5 rounded-2xl text-center border"
                  style={{
                    backgroundColor: '#1a1035',
                    borderColor: '#dc2626',
                  }}
                >
                  <div className="flex items-center justify-center gap-2 mb-2">
                    <Heart className="w-5 h-5 text-red-400" />
                    <div className="text-red-400 text-xs font-bold tracking-wider uppercase">Health</div>
                  </div>
                  <div className="text-red-100 text-4xl font-bold">28/32</div>
                </div>

                <div
                  className="p-5 rounded-2xl text-center border"
                  style={{
                    backgroundColor: '#1a1035',
                    borderColor: '#2563eb',
                  }}
                >
                  <div className="flex items-center justify-center gap-2 mb-2">
                    <Shield className="w-5 h-5 text-blue-400" />
                    <div className="text-blue-400 text-xs font-bold tracking-wider uppercase">Armor</div>
                  </div>
                  <div className="text-blue-100 text-4xl font-bold">16</div>
                </div>

                {/* Stats */}
                <div
                  className="md:col-span-2 p-5 rounded-2xl border"
                  style={{
                    backgroundColor: '#1a1035',
                    borderColor: '#3d2866',
                  }}
                >
                  <h3 className="font-bold mb-4 tracking-wider uppercase text-sm" style={{ color: '#c4b5fd' }}>
                    Primary Stats
                  </h3>
                  <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
                    {[
                      { name: 'STR', value: 16, mod: '+3' },
                      { name: 'DEX', value: 12, mod: '+1' },
                      { name: 'CON', value: 14, mod: '+2' },
                      { name: 'INT', value: 10, mod: '+0' },
                      { name: 'WIS', value: 11, mod: '+0' },
                      { name: 'CHA', value: 8, mod: '-1' },
                    ].map((stat) => (
                      <div
                        key={stat.name}
                        className="p-4 rounded-xl border text-center"
                        style={{
                          backgroundColor: '#0d0821',
                          borderColor: '#5b21b6',
                        }}
                      >
                        <div className="text-xs font-bold mb-1" style={{ color: '#a78bfa' }}>
                          {stat.name}
                        </div>
                        <div className="text-2xl font-bold" style={{ color: '#fcd34d' }}>
                          {stat.value}
                        </div>
                        <div className="text-xs" style={{ color: '#c4b5fd' }}>
                          {stat.mod}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Equipment */}
                <div
                  className="p-5 rounded-2xl border"
                  style={{
                    backgroundColor: '#1a1035',
                    borderColor: '#3d2866',
                  }}
                >
                  <h3 className="font-bold mb-4 flex items-center gap-2 tracking-wider uppercase text-sm" style={{ color: '#c4b5fd' }}>
                    <Sword className="w-4 h-4" style={{ color: '#fcd34d' }} />
                    Equipment
                  </h3>
                  <div className="space-y-3">
                    {[
                      { name: 'Longsword', stat: '1d8+3' },
                      { name: 'Chain Mail', stat: 'AC 16' },
                      { name: 'Steel Shield', stat: '+2 AC' },
                    ].map((item) => (
                      <div
                        key={item.name}
                        className="flex items-center justify-between p-3 rounded-xl border"
                        style={{
                          backgroundColor: '#0d0821',
                          borderColor: '#5b21b6',
                        }}
                      >
                        <span style={{ color: '#f3e8ff' }}>{item.name}</span>
                        <span className="font-bold" style={{ color: '#fcd34d' }}>
                          {item.stat}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Inventory */}
                <div
                  className="p-5 rounded-2xl border"
                  style={{
                    backgroundColor: '#1a1035',
                    borderColor: '#3d2866',
                  }}
                >
                  <h3 className="font-bold mb-4 tracking-wider uppercase text-sm" style={{ color: '#c4b5fd' }}>
                    Inventory
                  </h3>
                  <div className="grid grid-cols-2 gap-2">
                    {['Health Potion x2', 'Rope (50ft)', 'Torch x5', 'Rations x3', 'Bedroll', 'Gold: 47'].map(
                      (item) => (
                        <div
                          key={item}
                          className="p-2 rounded-lg border text-sm"
                          style={{
                            backgroundColor: '#0d0821',
                            borderColor: '#5b21b6',
                            color: '#f3e8ff',
                          }}
                        >
                          {item}
                        </div>
                      )
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Settings Tab */}
          {activeTab === 'settings' && (
            <div className="h-full overflow-y-auto px-4 py-5 max-w-3xl mx-auto w-full space-y-4">
              <h2 className="text-2xl font-bold mb-6" style={{ color: '#faf5ff' }}>
                Settings
              </h2>

              <div
                className="p-5 rounded-2xl border"
                style={{
                  backgroundColor: '#1a1035',
                  borderColor: '#3d2866',
                }}
              >
                <h3 className="font-bold mb-4 tracking-wider uppercase text-sm" style={{ color: '#c4b5fd' }}>
                  LLM Configuration
                </h3>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-semibold mb-2" style={{ color: '#a78bfa' }}>
                      Provider
                    </label>
                    <select
                      className="w-full px-4 py-3 rounded-xl border focus:outline-none focus:ring-2"
                      style={{
                        backgroundColor: '#0d0821',
                        borderColor: '#5b21b6',
                        color: '#f3e8ff',
                      }}
                    >
                      <option>OpenAI</option>
                      <option>Anthropic</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-semibold mb-2" style={{ color: '#a78bfa' }}>
                      Model
                    </label>
                    <select
                      className="w-full px-4 py-3 rounded-xl border focus:outline-none focus:ring-2"
                      style={{
                        backgroundColor: '#0d0821',
                        borderColor: '#5b21b6',
                        color: '#f3e8ff',
                      }}
                    >
                      <option>gpt-4o</option>
                      <option>gpt-4-turbo</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-semibold mb-2" style={{ color: '#a78bfa' }}>
                      API Key
                    </label>
                    <input
                      type="password"
                      placeholder="sk-..."
                      className="w-full px-4 py-3 rounded-xl border focus:outline-none focus:ring-2"
                      style={{
                        backgroundColor: '#0d0821',
                        borderColor: '#5b21b6',
                        color: '#f3e8ff',
                      }}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-semibold mb-2" style={{ color: '#a78bfa' }}>
                      Base URL (optional)
                    </label>
                    <input
                      type="text"
                      placeholder="https://api.openai.com/v1"
                      className="w-full px-4 py-3 rounded-xl border focus:outline-none focus:ring-2"
                      style={{
                        backgroundColor: '#0d0821',
                        borderColor: '#5b21b6',
                        color: '#f3e8ff',
                      }}
                    />
                  </div>
                </div>
              </div>

              <div
                className="p-5 rounded-2xl border"
                style={{
                  backgroundColor: '#1a1035',
                  borderColor: '#3d2866',
                }}
              >
                <h3 className="font-bold mb-4 tracking-wider uppercase text-sm" style={{ color: '#c4b5fd' }}>
                  Display Options
                </h3>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span style={{ color: '#f3e8ff' }}>Dark Mode</span>
                    <div
                      className="w-14 h-7 rounded-full p-1 cursor-pointer"
                      style={{ backgroundColor: '#5b21b6' }}
                    >
                      <div
                        className="w-5 h-5 rounded-full ml-auto"
                        style={{ backgroundColor: '#fcd34d' }}
                      ></div>
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <span style={{ color: '#f3e8ff' }}>Dice Roll Animations</span>
                    <div
                      className="w-14 h-7 rounded-full p-1 cursor-pointer"
                      style={{ backgroundColor: '#5b21b6' }}
                    >
                      <div
                        className="w-5 h-5 rounded-full ml-auto"
                        style={{ backgroundColor: '#fcd34d' }}
                      ></div>
                    </div>
                  </div>
                </div>
              </div>

              <div
                className="p-5 rounded-2xl border"
                style={{
                  backgroundColor: '#1a1035',
                  borderColor: '#3d2866',
                }}
              >
                <h3 className="font-bold mb-4 tracking-wider uppercase text-sm" style={{ color: '#c4b5fd' }}>
                  Administration
                </h3>
                <button
                  onClick={onNavigateToAdmin}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl font-semibold"
                  style={{
                    background: 'linear-gradient(135deg, #5b21b6 0%, #7c3aed 100%)',
                    color: '#fcd34d',
                  }}
                >
                  <ShieldAlert className="w-5 h-5" />
                  Open Admin Panel
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Bottom Tabs - Mobile Only */}
        <div
          className="md:hidden px-2 py-2 flex gap-1 shrink-0"
          style={{
            backgroundColor: '#150f2e',
            borderTop: '1px solid #2d1f52',
          }}
        >
          <button
            onClick={() => setActiveTab('chat')}
            className={`flex-1 flex flex-col items-center gap-1 py-2 rounded-lg transition-colors ${
              activeTab === 'chat' ? '' : ''
            }`}
            style={{
              backgroundColor: activeTab === 'chat' ? '#5b21b6' : 'transparent',
              color: activeTab === 'chat' ? '#fcd34d' : '#7c3aed',
            }}
          >
            <MessageSquare className="w-5 h-5" />
            <span className="text-xs font-semibold">Chat</span>
          </button>
          <button
            onClick={() => setActiveTab('character')}
            className={`flex-1 flex flex-col items-center gap-1 py-2 rounded-lg transition-colors ${
              activeTab === 'character' ? '' : ''
            }`}
            style={{
              backgroundColor: activeTab === 'character' ? '#5b21b6' : 'transparent',
              color: activeTab === 'character' ? '#fcd34d' : '#7c3aed',
            }}
          >
            <User className="w-5 h-5" />
            <span className="text-xs font-semibold">Character</span>
          </button>
          <button
            onClick={() => setActiveTab('settings')}
            className={`flex-1 flex flex-col items-center gap-1 py-2 rounded-lg transition-colors ${
              activeTab === 'settings' ? '' : ''
            }`}
            style={{
              backgroundColor: activeTab === 'settings' ? '#5b21b6' : 'transparent',
              color: activeTab === 'settings' ? '#fcd34d' : '#7c3aed',
            }}
          >
            <Settings className="w-5 h-5" />
            <span className="text-xs font-semibold">Settings</span>
          </button>
        </div>
      </div>

      {/* Desktop Sidebar */}
      <div
        className="hidden md:block w-80 border-l shrink-0"
        style={{
          backgroundColor: '#150f2e',
          borderColor: '#2d1f52',
        }}
      >
        <div className="p-4 space-y-2">
          <button
            onClick={() => setActiveTab('chat')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-colors ${
              activeTab === 'chat' ? '' : ''
            }`}
            style={{
              backgroundColor: activeTab === 'chat' ? '#5b21b6' : '#1a1035',
              color: activeTab === 'chat' ? '#fcd34d' : '#a78bfa',
            }}
          >
            <MessageSquare className="w-5 h-5" />
            <span className="font-semibold">Chat</span>
          </button>
          <button
            onClick={() => setActiveTab('character')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-colors ${
              activeTab === 'character' ? '' : ''
            }`}
            style={{
              backgroundColor: activeTab === 'character' ? '#5b21b6' : '#1a1035',
              color: activeTab === 'character' ? '#fcd34d' : '#a78bfa',
            }}
          >
            <User className="w-5 h-5" />
            <span className="font-semibold">Character</span>
          </button>
          <button
            onClick={() => setActiveTab('settings')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-colors ${
              activeTab === 'settings' ? '' : ''
            }`}
            style={{
              backgroundColor: activeTab === 'settings' ? '#5b21b6' : '#1a1035',
              color: activeTab === 'settings' ? '#fcd34d' : '#a78bfa',
            }}
          >
            <Settings className="w-5 h-5" />
            <span className="font-semibold">Settings</span>
          </button>
        </div>

        {/* Quick Character Info */}
        {activeTab === 'chat' && (
          <div className="p-4 mt-4">
            <div
              className="p-4 rounded-2xl border"
              style={{
                backgroundColor: '#1a1035',
                borderColor: '#3d2866',
              }}
            >
              <div className="text-center mb-3">
                <div className="font-bold" style={{ color: '#faf5ff' }}>
                  Aldric Stormborn
                </div>
                <div className="text-xs" style={{ color: '#a78bfa' }}>
                  Level 3 Warrior
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="text-center p-2 rounded-lg" style={{ backgroundColor: '#0d0821' }}>
                  <div className="text-xs" style={{ color: '#a78bfa' }}>HP</div>
                  <div className="font-bold text-red-400">28/32</div>
                </div>
                <div className="text-center p-2 rounded-lg" style={{ backgroundColor: '#0d0821' }}>
                  <div className="text-xs" style={{ color: '#a78bfa' }}>AC</div>
                  <div className="font-bold text-blue-400">16</div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
```

---

### `src/app/components/AdminApp.tsx`

```typescript
import { useState } from 'react';
import { Database, Edit2, Trash2, Lock, Plus, Shield, Sword, Target, Users, Flame, Gamepad2 } from 'lucide-react';

interface AdminAppProps {
  onNavigateToPlayer: () => void;
}

export default function AdminApp({ onNavigateToPlayer }: AdminAppProps) {
  const [activeTab, setActiveTab] = useState('stats');

  const tabs = [
    { id: 'stats', label: 'Stats', icon: Target },
    { id: 'skills', label: 'Skills', icon: Target },
    { id: 'weapons', label: 'Weapons', icon: Sword },
    { id: 'enemies', label: 'Enemies', icon: Flame },
    { id: 'accounts', label: 'Accounts', icon: Users },
  ];

  const statsData = [
    { id: 1, key: 'STR', label: 'Strength', description: 'Physical power and melee force', sort_order: 1, locked: true },
    { id: 2, key: 'DEX', label: 'Dexterity', description: 'Agility and precision', sort_order: 2, locked: false },
    { id: 3, key: 'CON', label: 'Constitution', description: 'Endurance and vitality', sort_order: 3, locked: false },
    { id: 4, key: 'INT', label: 'Intelligence', description: 'Knowledge and reasoning', sort_order: 4, locked: false },
  ];

  const weaponsData = [
    { id: 1, key: 'longsword', label: 'Longsword', damage_die: '1d8', linked_stat: 'STR', active: true },
    { id: 2, key: 'shortbow', label: 'Shortbow', damage_die: '1d6', linked_stat: 'DEX', active: true },
    { id: 3, key: 'dagger', label: 'Dagger', damage_die: '1d4', linked_stat: 'DEX', active: true },
  ];

  const enemiesData = [
    { id: 1, key: 'goblin', label: 'Goblin', hp_base: 8, ac_base: 11, damage_die: '1d6', active: true },
    { id: 2, key: 'orc', label: 'Orc', hp_base: 15, ac_base: 13, damage_die: '1d8', active: true },
  ];

  return (
    <div className="size-full flex flex-col" style={{ backgroundColor: '#0d0821' }}>
      {/* Header */}
      <div
        className="px-4 py-4 shrink-0"
        style={{
          backgroundColor: '#150f2e',
          borderBottom: '1px solid #2d1f52',
        }}
      >
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <div className="flex items-center gap-3">
            <div
              className="w-11 h-11 rounded-xl flex items-center justify-center"
              style={{
                background: 'linear-gradient(135deg, #4c1d95 0%, #5b21b6 100%)',
                boxShadow: '0 4px 12px rgba(139, 92, 246, 0.2)',
              }}
            >
              <Shield className="w-6 h-6" style={{ color: '#fcd34d' }} />
            </div>
            <div>
              <div className="font-bold tracking-tight" style={{ color: '#faf5ff', fontSize: '18px' }}>
                Admin Panel
              </div>
              <div className="text-xs" style={{ color: '#a78bfa' }}>
                Game Master Control Center
              </div>
            </div>
          </div>
          <button
            onClick={onNavigateToPlayer}
            className="flex items-center gap-2 px-4 py-2 rounded-lg font-semibold"
            style={{
              background: 'linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%)',
              color: '#0d0821',
            }}
          >
            <Gamepad2 className="w-4 h-4" />
            Back to Game
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div
        className="px-4 py-3 overflow-x-auto shrink-0"
        style={{
          backgroundColor: '#150f2e',
          borderBottom: '1px solid #2d1f52',
        }}
      >
        <div className="flex gap-2 max-w-7xl mx-auto">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors whitespace-nowrap ${
                  activeTab === tab.id ? '' : ''
                }`}
                style={{
                  backgroundColor: activeTab === tab.id ? '#5b21b6' : '#1a1035',
                  color: activeTab === tab.id ? '#fcd34d' : '#a78bfa',
                }}
              >
                <Icon className="w-4 h-4" />
                <span className="font-semibold text-sm">{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto px-4 py-5">
        <div className="max-w-7xl mx-auto">
          {/* Stats Table */}
          {activeTab === 'stats' && (
            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold" style={{ color: '#faf5ff' }}>
                  Primary Stats
                </h2>
                <button
                  className="flex items-center gap-2 px-4 py-2 rounded-lg font-semibold"
                  style={{
                    background: 'linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%)',
                    color: '#0d0821',
                  }}
                >
                  <Plus className="w-4 h-4" />
                  Add Stat
                </button>
              </div>

              <div
                className="rounded-2xl border overflow-hidden"
                style={{
                  backgroundColor: '#1a1035',
                  borderColor: '#3d2866',
                }}
              >
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr style={{ backgroundColor: '#0d0821', borderBottom: '1px solid #3d2866' }}>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Key
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Label
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Description
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Order
                        </th>
                        <th className="px-4 py-3 text-right text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {statsData.map((stat, idx) => (
                        <tr
                          key={stat.id}
                          style={{
                            borderBottom: idx !== statsData.length - 1 ? '1px solid #2d1f52' : 'none',
                          }}
                        >
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <span className="font-mono font-bold" style={{ color: '#fcd34d' }}>
                                {stat.key}
                              </span>
                              {stat.locked && <Lock className="w-3 h-3" style={{ color: '#ef4444' }} />}
                            </div>
                          </td>
                          <td className="px-4 py-3" style={{ color: '#f3e8ff' }}>
                            {stat.label}
                          </td>
                          <td className="px-4 py-3" style={{ color: '#a78bfa' }}>
                            {stat.description}
                          </td>
                          <td className="px-4 py-3" style={{ color: '#f3e8ff' }}>
                            {stat.sort_order}
                          </td>
                          <td className="px-4 py-3 text-right">
                            <div className="flex items-center justify-end gap-2">
                              <button
                                className="p-2 rounded-lg hover:bg-purple-900/30"
                                style={{ color: '#a78bfa' }}
                              >
                                <Edit2 className="w-4 h-4" />
                              </button>
                              <button
                                className="p-2 rounded-lg hover:bg-red-900/30"
                                style={{ color: '#ef4444' }}
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Weapons Table */}
          {activeTab === 'weapons' && (
            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold" style={{ color: '#faf5ff' }}>
                  Weapons
                </h2>
                <button
                  className="flex items-center gap-2 px-4 py-2 rounded-lg font-semibold"
                  style={{
                    background: 'linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%)',
                    color: '#0d0821',
                  }}
                >
                  <Plus className="w-4 h-4" />
                  Add Weapon
                </button>
              </div>

              <div
                className="rounded-2xl border overflow-hidden"
                style={{
                  backgroundColor: '#1a1035',
                  borderColor: '#3d2866',
                }}
              >
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr style={{ backgroundColor: '#0d0821', borderBottom: '1px solid #3d2866' }}>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Key
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Label
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Damage
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Stat
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Status
                        </th>
                        <th className="px-4 py-3 text-right text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {weaponsData.map((weapon, idx) => (
                        <tr
                          key={weapon.id}
                          style={{
                            borderBottom: idx !== weaponsData.length - 1 ? '1px solid #2d1f52' : 'none',
                          }}
                        >
                          <td className="px-4 py-3">
                            <span className="font-mono" style={{ color: '#a78bfa' }}>
                              {weapon.key}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-semibold" style={{ color: '#f3e8ff' }}>
                            {weapon.label}
                          </td>
                          <td className="px-4 py-3">
                            <span className="font-mono font-bold" style={{ color: '#fcd34d' }}>
                              {weapon.damage_die}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="font-mono" style={{ color: '#f3e8ff' }}>
                              {weapon.linked_stat}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className="px-2 py-1 rounded text-xs font-semibold"
                              style={{
                                backgroundColor: weapon.active ? '#166534' : '#7f1d1d',
                                color: weapon.active ? '#86efac' : '#fca5a5',
                              }}
                            >
                              {weapon.active ? 'Active' : 'Inactive'}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-right">
                            <div className="flex items-center justify-end gap-2">
                              <button
                                className="p-2 rounded-lg hover:bg-purple-900/30"
                                style={{ color: '#a78bfa' }}
                              >
                                <Edit2 className="w-4 h-4" />
                              </button>
                              <button
                                className="p-2 rounded-lg hover:bg-red-900/30"
                                style={{ color: '#ef4444' }}
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Enemies Table */}
          {activeTab === 'enemies' && (
            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold" style={{ color: '#faf5ff' }}>
                  Enemies
                </h2>
                <button
                  className="flex items-center gap-2 px-4 py-2 rounded-lg font-semibold"
                  style={{
                    background: 'linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%)',
                    color: '#0d0821',
                  }}
                >
                  <Plus className="w-4 h-4" />
                  Add Enemy
                </button>
              </div>

              <div
                className="rounded-2xl border overflow-hidden"
                style={{
                  backgroundColor: '#1a1035',
                  borderColor: '#3d2866',
                }}
              >
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr style={{ backgroundColor: '#0d0821', borderBottom: '1px solid #3d2866' }}>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Key
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Label
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          HP
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          AC
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Damage
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Status
                        </th>
                        <th className="px-4 py-3 text-right text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {enemiesData.map((enemy, idx) => (
                        <tr
                          key={enemy.id}
                          style={{
                            borderBottom: idx !== enemiesData.length - 1 ? '1px solid #2d1f52' : 'none',
                          }}
                        >
                          <td className="px-4 py-3">
                            <span className="font-mono" style={{ color: '#a78bfa' }}>
                              {enemy.key}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-semibold" style={{ color: '#f3e8ff' }}>
                            {enemy.label}
                          </td>
                          <td className="px-4 py-3">
                            <span className="font-mono" style={{ color: '#ef4444' }}>
                              {enemy.hp_base}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="font-mono" style={{ color: '#3b82f6' }}>
                              {enemy.ac_base}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="font-mono font-bold" style={{ color: '#fcd34d' }}>
                              {enemy.damage_die}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className="px-2 py-1 rounded text-xs font-semibold"
                              style={{
                                backgroundColor: enemy.active ? '#166534' : '#7f1d1d',
                                color: enemy.active ? '#86efac' : '#fca5a5',
                              }}
                            >
                              {enemy.active ? 'Active' : 'Inactive'}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-right">
                            <div className="flex items-center justify-end gap-2">
                              <button
                                className="p-2 rounded-lg hover:bg-purple-900/30"
                                style={{ color: '#a78bfa' }}
                              >
                                <Edit2 className="w-4 h-4" />
                              </button>
                              <button
                                className="p-2 rounded-lg hover:bg-red-900/30"
                                style={{ color: '#ef4444' }}
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Skills and Accounts tabs - placeholder */}
          {(activeTab === 'skills' || activeTab === 'accounts') && (
            <div className="text-center py-12">
              <Database className="w-16 h-16 mx-auto mb-4" style={{ color: '#5b21b6' }} />
              <h3 className="text-xl font-bold mb-2" style={{ color: '#faf5ff' }}>
                {activeTab === 'skills' ? 'Skills' : 'Accounts'} Management
              </h3>
              <p style={{ color: '#a78bfa' }}>Content coming soon...</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

---

## ✨ Features

### Player Interface
- **Chat**: AI-driven conversation with Game Master
  - Messages scale to content (max 80% width)
  - Clear visual distinction between GM and Player
  - Avatar icons for both sides
- **Character Sheet**: Full RPG stats, equipment, inventory
- **Settings**: LLM configuration, display options
- **Navigation**: Bottom tabs on mobile, sidebar on desktop
- **Admin Access**: Button to switch to admin panel

### Admin Panel
- **Tabbed Interface**: Stats, Skills, Weapons, Enemies, Accounts
- **Data Tables**: CRUD operations with inline editing
- **Lock System**: Visual indicators for protected data
- **Status Badges**: Active/Inactive states
- **Responsive**: Full-width tables optimized for data entry

### Responsive Design
- **Mobile First**: Tab navigation at bottom
- **Desktop Enhanced**: Sidebar navigation with quick character stats
- **Flexible Layout**: Adapts seamlessly from 320px to 4K

---

## 🚀 Next Steps

1. **Add Backend**: Connect to database (SQLite, PostgreSQL)
2. **Implement LLM**: Integrate OpenAI/Anthropic API
3. **State Management**: Add React Context or Zustand
4. **Real-time Updates**: WebSockets for multiplayer
5. **Dice Rolling**: Add interactive dice mechanics
6. **Save System**: Character persistence
7. **Authentication**: User login/registration

---

## 📝 Notes

- Uses **inline styles** for easy color customization
- **No backend required** to run - perfect for prototyping
- All data is currently **mock data**
- Built with **TypeScript** for type safety
- **Tailwind CSS v4** for utility classes

---

**Created with Claude Code** 🤖
