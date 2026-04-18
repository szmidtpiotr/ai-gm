import { useState } from 'react';
import { MessageSquare, User, Settings, Scroll, Sword } from 'lucide-react';

export default function MockupThree() {
  const [activeTab, setActiveTab] = useState('chat');

  const messages = [
    { type: 'gm', text: 'You enter the dimly lit tavern. The smell of ale and smoke fills your nostrils. A hooded figure in the corner watches you intently.' },
    { type: 'player', text: 'I approach the hooded figure cautiously, hand on my sword hilt.' },
    { type: 'gm', text: 'The figure raises their head slightly. "You seek the merchant\'s daughter, don\'t you?" Their voice is raspy, barely above a whisper.' },
  ];

  return (
    <div className="size-full bg-stone-900 flex flex-col">
      {/* Header */}
      <div className="bg-gradient-to-b from-stone-950 to-stone-900 border-b border-amber-900/30 px-4 py-3 flex items-center justify-center shrink-0">
        <div className="flex items-center gap-2">
          <Scroll className="w-5 h-5 text-amber-600" />
          <span className="text-amber-100 font-semibold">The Cursed Vale</span>
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-hidden">
        {/* Chat Tab */}
        {activeTab === 'chat' && (
          <div className="h-full flex flex-col">
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
        )}

        {/* Character Tab */}
        {activeTab === 'character' && (
          <div className="h-full overflow-y-auto px-4 py-4 space-y-4">
            {/* Character Header */}
            <div className="text-center pb-3 border-b border-stone-800">
              <div className="text-amber-100 text-xl font-bold">Aldric Stormborn</div>
              <div className="text-stone-400 text-sm">Human Warrior • Level 3</div>
            </div>

            {/* HP/AC */}
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-red-950/40 border border-red-900/50 rounded-lg p-4 text-center">
                <div className="text-red-400 text-xs font-semibold">HEALTH</div>
                <div className="text-red-100 text-3xl font-bold">28/32</div>
              </div>
              <div className="bg-blue-950/40 border border-blue-900/50 rounded-lg p-4 text-center">
                <div className="text-blue-400 text-xs font-semibold">ARMOR</div>
                <div className="text-blue-100 text-3xl font-bold">16</div>
              </div>
            </div>

            {/* Stats */}
            <div className="bg-stone-800 border border-stone-700 rounded-lg p-4">
              <h3 className="text-amber-600 font-semibold mb-3">Primary Stats</h3>
              <div className="grid grid-cols-2 gap-3">
                {[
                  { name: 'STR', value: 16, mod: '+3' },
                  { name: 'DEX', value: 12, mod: '+1' },
                  { name: 'CON', value: 14, mod: '+2' },
                  { name: 'INT', value: 10, mod: '+0' },
                  { name: 'WIS', value: 11, mod: '+0' },
                  { name: 'CHA', value: 8, mod: '-1' },
                ].map((stat) => (
                  <div key={stat.name} className="bg-stone-900 border border-stone-700 rounded p-3">
                    <div className="text-stone-400 text-xs">{stat.name}</div>
                    <div className="flex items-baseline gap-2">
                      <span className="text-amber-100 text-2xl font-bold">{stat.value}</span>
                      <span className="text-stone-500 text-sm">{stat.mod}</span>
                    </div>
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
                  <span className="text-amber-600 text-sm font-semibold">1d8+3</span>
                </div>
                <div className="flex items-center justify-between bg-stone-900 border border-stone-700 rounded p-3">
                  <span className="text-stone-200">Chain Mail</span>
                  <span className="text-amber-600 text-sm font-semibold">AC 16</span>
                </div>
                <div className="flex items-center justify-between bg-stone-900 border border-stone-700 rounded p-3">
                  <span className="text-stone-200">Steel Shield</span>
                  <span className="text-amber-600 text-sm font-semibold">+2 AC</span>
                </div>
              </div>
            </div>

            {/* Inventory */}
            <div className="bg-stone-800 border border-stone-700 rounded-lg p-4">
              <h3 className="text-amber-600 font-semibold mb-3">Inventory</h3>
              <div className="grid grid-cols-2 gap-2">
                {[
                  'Health Potion x2',
                  'Rope (50ft)',
                  'Torch x5',
                  'Rations x3',
                  'Bedroll',
                  'Gold: 47',
                ].map((item) => (
                  <div key={item} className="bg-stone-900 border border-stone-700 rounded p-2 text-stone-200 text-sm">
                    {item}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Settings Tab */}
        {activeTab === 'settings' && (
          <div className="h-full overflow-y-auto px-4 py-4 space-y-4">
            <h2 className="text-amber-100 text-xl font-bold">Settings</h2>

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
                    <option>gpt-4-turbo</option>
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
              <h3 className="text-amber-600 font-semibold mb-3">Display</h3>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-stone-200">Dark Mode</span>
                  <div className="w-12 h-6 bg-amber-700 rounded-full p-1">
                    <div className="w-4 h-4 bg-amber-50 rounded-full ml-auto"></div>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-stone-200">Dice Roll Animations</span>
                  <div className="w-12 h-6 bg-amber-700 rounded-full p-1">
                    <div className="w-4 h-4 bg-amber-50 rounded-full ml-auto"></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Bottom Tabs */}
      <div className="bg-stone-950 border-t border-stone-800 px-2 py-2 flex gap-1 shrink-0">
        <button
          onClick={() => setActiveTab('chat')}
          className={`flex-1 flex flex-col items-center gap-1 py-2 rounded transition-colors ${
            activeTab === 'chat'
              ? 'bg-amber-700 text-amber-50'
              : 'text-stone-400 hover:bg-stone-800'
          }`}
        >
          <MessageSquare className="w-5 h-5" />
          <span className="text-xs font-medium">Chat</span>
        </button>
        <button
          onClick={() => setActiveTab('character')}
          className={`flex-1 flex flex-col items-center gap-1 py-2 rounded transition-colors ${
            activeTab === 'character'
              ? 'bg-amber-700 text-amber-50'
              : 'text-stone-400 hover:bg-stone-800'
          }`}
        >
          <User className="w-5 h-5" />
          <span className="text-xs font-medium">Character</span>
        </button>
        <button
          onClick={() => setActiveTab('settings')}
          className={`flex-1 flex flex-col items-center gap-1 py-2 rounded transition-colors ${
            activeTab === 'settings'
              ? 'bg-amber-700 text-amber-50'
              : 'text-stone-400 hover:bg-stone-800'
          }`}
        >
          <Settings className="w-5 h-5" />
          <span className="text-xs font-medium">Settings</span>
        </button>
      </div>
    </div>
  );
}
