import { useState } from 'react';
import { Scroll, Sword, User, Settings, Plus, X } from 'lucide-react';

export default function MockupFour() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [activePanel, setActivePanel] = useState<'character' | 'settings' | null>(null);

  const messages = [
    { type: 'gm', text: 'You enter the dimly lit tavern. The smell of ale and smoke fills your nostrils. A hooded figure in the corner watches you intently.' },
    { type: 'player', text: 'I approach the hooded figure cautiously, hand on my sword hilt.' },
    { type: 'gm', text: 'The figure raises their head slightly. "You seek the merchant\'s daughter, don\'t you?" Their voice is raspy, barely above a whisper.' },
  ];

  const openPanel = (panel: 'character' | 'settings') => {
    setActivePanel(panel);
    setMenuOpen(false);
  };

  return (
    <div className="size-full bg-stone-900 flex flex-col relative">
      {/* Header */}
      <div className="bg-gradient-to-b from-stone-950 to-stone-900 border-b border-amber-900/30 px-4 py-3 flex items-center justify-center shrink-0">
        <div className="flex items-center gap-2">
          <Scroll className="w-5 h-5 text-amber-600" />
          <span className="text-amber-100 font-semibold">The Cursed Vale</span>
        </div>
      </div>

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.type === 'player' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[85%] px-4 py-3 rounded-lg ${
                msg.type === 'gm'
                  ? 'bg-stone-800 border border-amber-900/30 text-stone-200'
                  : 'bg-amber-900/40 border border-amber-700/50 text-amber-50'
              }`}
            >
              <div className="text-xs text-amber-600 mb-1">{msg.type === 'gm' ? 'Game Master' : 'You'}</div>
              <div className="leading-relaxed">{msg.text}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Input Area */}
      <div className="bg-stone-950 border-t border-stone-800 px-4 py-3 shrink-0">
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Describe your action..."
            className="flex-1 bg-stone-800 border border-stone-700 rounded px-4 py-3 text-stone-200 placeholder:text-stone-500"
          />
          <button className="bg-amber-700 hover:bg-amber-600 px-4 py-3 rounded text-amber-50 font-medium">
            Send
          </button>
        </div>
      </div>

      {/* Floating Action Button */}
      <div className="absolute bottom-24 right-4">
        <button
          onClick={() => setMenuOpen(!menuOpen)}
          className={`bg-amber-700 hover:bg-amber-600 p-4 rounded-full shadow-lg transition-transform ${
            menuOpen ? 'rotate-45' : ''
          }`}
        >
          <Plus className="w-6 h-6 text-amber-50" />
        </button>

        {/* Radial Menu */}
        {menuOpen && (
          <div className="absolute bottom-16 right-0 flex flex-col gap-3">
            <button
              onClick={() => openPanel('character')}
              className="bg-stone-800 hover:bg-stone-700 border border-amber-700 p-3 rounded-full shadow-lg flex items-center gap-2 pr-4"
            >
              <User className="w-5 h-5 text-amber-600" />
              <span className="text-amber-100 text-sm font-medium">Character</span>
            </button>
            <button
              onClick={() => openPanel('settings')}
              className="bg-stone-800 hover:bg-stone-700 border border-amber-700 p-3 rounded-full shadow-lg flex items-center gap-2 pr-4"
            >
              <Settings className="w-5 h-5 text-amber-600" />
              <span className="text-amber-100 text-sm font-medium">Settings</span>
            </button>
          </div>
        )}
      </div>

      {/* Overlay */}
      {activePanel && (
        <div
          className="absolute inset-0 bg-black/60 z-30"
          onClick={() => setActivePanel(null)}
        />
      )}

      {/* Character Panel */}
      {activePanel === 'character' && (
        <div className="absolute inset-x-0 bottom-0 bg-stone-900 border-t-2 border-amber-700 rounded-t-2xl z-40 h-[80vh] flex flex-col">
          {/* Panel Header */}
          <div className="px-4 py-3 border-b border-stone-800 flex items-center justify-between bg-stone-950">
            <h2 className="text-amber-100 font-bold text-lg">Character Sheet</h2>
            <button onClick={() => setActivePanel(null)} className="text-stone-400 hover:text-stone-200">
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Character Content */}
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
            <div className="text-center pb-3 border-b border-stone-800">
              <div className="text-amber-100 text-xl font-bold">Aldric Stormborn</div>
              <div className="text-stone-400 text-sm">Human Warrior • Level 3</div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="bg-red-950/40 border border-red-900/50 rounded-lg p-4 text-center">
                <div className="text-red-400 text-xs font-semibold">HP</div>
                <div className="text-red-100 text-3xl font-bold">28/32</div>
              </div>
              <div className="bg-blue-950/40 border border-blue-900/50 rounded-lg p-4 text-center">
                <div className="text-blue-400 text-xs font-semibold">AC</div>
                <div className="text-blue-100 text-3xl font-bold">16</div>
              </div>
            </div>

            <div className="bg-stone-800 border border-stone-700 rounded-lg p-4">
              <h3 className="text-amber-600 font-semibold mb-3">Stats</h3>
              <div className="grid grid-cols-2 gap-3">
                {[
                  { name: 'STR', value: 16 },
                  { name: 'DEX', value: 12 },
                  { name: 'CON', value: 14 },
                  { name: 'INT', value: 10 },
                  { name: 'WIS', value: 11 },
                  { name: 'CHA', value: 8 },
                ].map((stat) => (
                  <div key={stat.name} className="bg-stone-900 border border-stone-700 rounded p-3 text-center">
                    <div className="text-stone-400 text-xs">{stat.name}</div>
                    <div className="text-amber-100 text-xl font-bold">{stat.value}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-stone-800 border border-stone-700 rounded-lg p-4">
              <h3 className="text-amber-600 font-semibold mb-3 flex items-center gap-2">
                <Sword className="w-4 h-4" />
                Equipment
              </h3>
              <div className="space-y-2">
                {[
                  { name: 'Longsword', stat: '1d8+3' },
                  { name: 'Chain Mail', stat: 'AC 16' },
                ].map((item) => (
                  <div key={item.name} className="flex items-center justify-between bg-stone-900 border border-stone-700 rounded p-3">
                    <span className="text-stone-200">{item.name}</span>
                    <span className="text-amber-600 text-sm font-semibold">{item.stat}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-stone-800 border border-stone-700 rounded-lg p-4">
              <h3 className="text-amber-600 font-semibold mb-3">Inventory</h3>
              <div className="grid grid-cols-2 gap-2">
                {['Health Potion x2', 'Rope (50ft)', 'Torch x5', 'Gold: 47'].map((item) => (
                  <div key={item} className="bg-stone-900 border border-stone-700 rounded p-2 text-stone-200 text-sm">
                    {item}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Settings Panel */}
      {activePanel === 'settings' && (
        <div className="absolute inset-x-0 bottom-0 bg-stone-900 border-t-2 border-amber-700 rounded-t-2xl z-40 h-[80vh] flex flex-col">
          <div className="px-4 py-3 border-b border-stone-800 flex items-center justify-between bg-stone-950">
            <h2 className="text-amber-100 font-bold text-lg">Settings</h2>
            <button onClick={() => setActivePanel(null)} className="text-stone-400 hover:text-stone-200">
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
            <div className="bg-stone-800 border border-stone-700 rounded-lg p-4">
              <h3 className="text-amber-600 font-semibold mb-3">LLM Configuration</h3>
              <div className="space-y-3">
                <div>
                  <label className="text-stone-400 text-sm block mb-1">Provider</label>
                  <select className="w-full bg-stone-900 border border-stone-700 rounded px-3 py-2 text-stone-200">
                    <option>OpenAI</option>
                    <option>Anthropic</option>
                  </select>
                </div>
                <div>
                  <label className="text-stone-400 text-sm block mb-1">Model</label>
                  <select className="w-full bg-stone-900 border border-stone-700 rounded px-3 py-2 text-stone-200">
                    <option>gpt-4o</option>
                  </select>
                </div>
                <div>
                  <label className="text-stone-400 text-sm block mb-1">API Key</label>
                  <input
                    type="password"
                    placeholder="sk-..."
                    className="w-full bg-stone-900 border border-stone-700 rounded px-3 py-2 text-stone-200"
                  />
                </div>
              </div>
            </div>

            <div className="bg-stone-800 border border-stone-700 rounded-lg p-4">
              <h3 className="text-amber-600 font-semibold mb-3">Display Options</h3>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-stone-200">Dark Mode</span>
                  <div className="w-12 h-6 bg-amber-700 rounded-full p-1">
                    <div className="w-4 h-4 bg-amber-50 rounded-full ml-auto"></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
