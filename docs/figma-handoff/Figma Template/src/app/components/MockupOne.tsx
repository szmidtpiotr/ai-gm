import { useState } from 'react';
import { Scroll, Sword, Shield, Menu } from 'lucide-react';

export default function MockupOne() {
  const [sheetOpen, setSheetOpen] = useState(false);

  const messages = [
    { type: 'gm', text: 'You enter the dimly lit tavern. The smell of ale and smoke fills your nostrils. A hooded figure in the corner watches you intently.' },
    { type: 'player', text: 'I approach the hooded figure cautiously, hand on my sword hilt.' },
    { type: 'gm', text: 'The figure raises their head slightly. "You seek the merchant\'s daughter, don\'t you?" Their voice is raspy, barely above a whisper.' },
  ];

  return (
    <div className="size-full bg-stone-900 flex flex-col relative">
      {/* Header */}
      <div className="bg-gradient-to-b from-stone-950 to-stone-900 border-b border-amber-900/30 px-4 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <Scroll className="w-5 h-5 text-amber-600" />
          <span className="text-amber-100 font-semibold">The Cursed Vale</span>
        </div>
        <button className="p-2 hover:bg-stone-800 rounded">
          <Menu className="w-5 h-5 text-stone-400" />
        </button>
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

      {/* Character Sheet Button */}
      <button
        onClick={() => setSheetOpen(!sheetOpen)}
        className="absolute bottom-24 right-4 bg-amber-700 hover:bg-amber-600 p-4 rounded-full shadow-lg"
      >
        <Scroll className="w-6 h-6 text-amber-50" />
      </button>

      {/* Bottom Sheet */}
      <div
        className={`absolute inset-x-0 bottom-0 bg-stone-900 border-t-2 border-amber-700 rounded-t-2xl transition-transform duration-300 ${
          sheetOpen ? 'translate-y-0' : 'translate-y-full'
        }`}
        style={{ height: '75vh' }}
      >
        <div className="flex flex-col h-full">
          {/* Sheet Header */}
          <div className="px-4 py-3 border-b border-stone-800 flex items-center justify-between">
            <h2 className="text-amber-100 font-bold text-lg">Character Sheet</h2>
            <button onClick={() => setSheetOpen(false)} className="text-stone-400 hover:text-stone-200">
              ✕
            </button>
          </div>

          {/* Character Info */}
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
            {/* Stats */}
            <div className="bg-stone-800 border border-stone-700 rounded-lg p-4">
              <h3 className="text-amber-600 font-semibold mb-3">Primary Stats</h3>
              <div className="grid grid-cols-2 gap-3">
                {['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'].map((stat) => (
                  <div key={stat} className="bg-stone-900 border border-stone-700 rounded p-3">
                    <div className="text-stone-400 text-xs">{stat}</div>
                    <div className="text-amber-100 text-xl font-bold">14</div>
                    <div className="text-stone-500 text-xs">+2</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Equipment */}
            <div className="bg-stone-800 border border-stone-700 rounded-lg p-4">
              <h3 className="text-amber-600 font-semibold mb-3 flex items-center gap-2">
                <Sword className="w-4 h-4" />
                Equipment
              </h3>
              <div className="space-y-2">
                <div className="flex items-center justify-between bg-stone-900 border border-stone-700 rounded p-3">
                  <span className="text-stone-200">Longsword</span>
                  <span className="text-amber-600 text-sm">1d8+2</span>
                </div>
                <div className="flex items-center justify-between bg-stone-900 border border-stone-700 rounded p-3">
                  <span className="text-stone-200">Chain Mail</span>
                  <span className="text-amber-600 text-sm">AC 16</span>
                </div>
              </div>
            </div>

            {/* Inventory */}
            <div className="bg-stone-800 border border-stone-700 rounded-lg p-4">
              <h3 className="text-amber-600 font-semibold mb-3">Inventory</h3>
              <div className="space-y-2">
                {['Health Potion x2', 'Rope (50ft)', 'Torch x5', 'Gold: 47'].map((item) => (
                  <div key={item} className="bg-stone-900 border border-stone-700 rounded p-2 text-stone-200 text-sm">
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
