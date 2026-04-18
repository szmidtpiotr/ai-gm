import { useState } from 'react';
import { Scroll, Sword, User, Menu } from 'lucide-react';

export default function MockupTwo() {
  const [drawerOpen, setDrawerOpen] = useState(false);

  const messages = [
    { type: 'gm', text: 'You enter the dimly lit tavern. The smell of ale and smoke fills your nostrils. A hooded figure in the corner watches you intently.' },
    { type: 'player', text: 'I approach the hooded figure cautiously, hand on my sword hilt.' },
    { type: 'gm', text: 'The figure raises their head slightly. "You seek the merchant\'s daughter, don\'t you?" Their voice is raspy, barely above a whisper.' },
  ];

  return (
    <div className="size-full bg-stone-900 flex relative">
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="bg-gradient-to-r from-stone-950 to-stone-900 border-b border-amber-900/30 px-4 py-3 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <Scroll className="w-5 h-5 text-amber-600" />
            <span className="text-amber-100 font-semibold">The Cursed Vale</span>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setDrawerOpen(!drawerOpen)}
              className="p-2 hover:bg-stone-800 rounded"
            >
              <User className="w-5 h-5 text-amber-600" />
            </button>
            <button className="p-2 hover:bg-stone-800 rounded">
              <Menu className="w-5 h-5 text-stone-400" />
            </button>
          </div>
        </div>

        {/* Messages */}
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

        {/* Input */}
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
      </div>

      {/* Side Drawer Overlay */}
      {drawerOpen && (
        <div
          className="absolute inset-0 bg-black/50 z-10"
          onClick={() => setDrawerOpen(false)}
        />
      )}

      {/* Side Drawer */}
      <div
        className={`absolute top-0 right-0 h-full w-80 bg-stone-900 border-l-2 border-amber-700 transform transition-transform duration-300 z-20 ${
          drawerOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <div className="flex flex-col h-full">
          {/* Drawer Header */}
          <div className="px-4 py-3 border-b border-stone-800 flex items-center justify-between bg-stone-950">
            <h2 className="text-amber-100 font-bold text-lg">Character</h2>
            <button onClick={() => setDrawerOpen(false)} className="text-stone-400 hover:text-stone-200">
              ✕
            </button>
          </div>

          {/* Character Content */}
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
            {/* Character Name */}
            <div className="text-center pb-3 border-b border-stone-800">
              <div className="text-amber-100 text-xl font-bold">Aldric Stormborn</div>
              <div className="text-stone-400 text-sm">Human Warrior • Level 3</div>
            </div>

            {/* HP/AC */}
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-red-950/40 border border-red-900/50 rounded-lg p-3 text-center">
                <div className="text-red-400 text-xs font-semibold">HP</div>
                <div className="text-red-100 text-2xl font-bold">28/32</div>
              </div>
              <div className="bg-blue-950/40 border border-blue-900/50 rounded-lg p-3 text-center">
                <div className="text-blue-400 text-xs font-semibold">AC</div>
                <div className="text-blue-100 text-2xl font-bold">16</div>
              </div>
            </div>

            {/* Stats */}
            <div className="bg-stone-800 border border-stone-700 rounded-lg p-3">
              <h3 className="text-amber-600 font-semibold text-sm mb-2">Stats</h3>
              <div className="grid grid-cols-3 gap-2">
                {['STR 16', 'DEX 12', 'CON 14', 'INT 10', 'WIS 11', 'CHA 8'].map((stat) => (
                  <div key={stat} className="bg-stone-900 rounded p-2 text-center text-stone-200 text-sm">
                    {stat}
                  </div>
                ))}
              </div>
            </div>

            {/* Equipment */}
            <div className="bg-stone-800 border border-stone-700 rounded-lg p-3">
              <h3 className="text-amber-600 font-semibold text-sm mb-2 flex items-center gap-1">
                <Sword className="w-4 h-4" />
                Equipment
              </h3>
              <div className="space-y-2">
                <div className="bg-stone-900 rounded p-2 text-stone-200 text-sm">
                  Longsword <span className="text-amber-600">1d8+3</span>
                </div>
                <div className="bg-stone-900 rounded p-2 text-stone-200 text-sm">
                  Chain Mail <span className="text-amber-600">AC 16</span>
                </div>
              </div>
            </div>

            {/* Inventory */}
            <div className="bg-stone-800 border border-stone-700 rounded-lg p-3">
              <h3 className="text-amber-600 font-semibold text-sm mb-2">Inventory</h3>
              <div className="space-y-1 text-sm">
                {['Health Potion x2', 'Rope (50ft)', 'Torch x5', 'Gold: 47'].map((item) => (
                  <div key={item} className="bg-stone-900 rounded p-2 text-stone-200">
                    {item}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
