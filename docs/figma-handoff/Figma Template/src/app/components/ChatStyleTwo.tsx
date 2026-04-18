import { Skull, Send } from 'lucide-react';

// Dark Grimoire - Pure black, blood red accents, gothic horror
export default function ChatStyleTwo() {
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
    <div className="size-full flex flex-col bg-black">
      {/* Header */}
      <div className="px-4 py-4 border-b border-red-950/50 shrink-0 bg-gradient-to-b from-zinc-950 to-black">
        <div className="flex items-center gap-3">
          <Skull className="w-6 h-6 text-red-700" />
          <div>
            <div className="font-bold text-red-100 text-lg tracking-tight">The Cursed Vale</div>
            <div className="text-xs text-red-900">A tale of darkness and despair</div>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3 py-5 space-y-3">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.type === 'player' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[85%] ${
                msg.type === 'gm'
                  ? 'bg-zinc-950 border-l-2 border-red-900/60 pl-3 pr-4 py-3'
                  : 'bg-red-950/20 border-r-2 border-red-800/60 pr-3 pl-4 py-3'
              }`}
            >
              <div
                className={`text-[10px] font-bold mb-2 tracking-widest uppercase ${
                  msg.type === 'gm' ? 'text-red-700' : 'text-red-600'
                }`}
              >
                {msg.type === 'gm' ? '⚔ Game Master' : '⚔ You'}
              </div>
              <div className="text-red-50 leading-relaxed" style={{ fontSize: '15px' }}>
                {msg.text}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Input */}
      <div className="px-4 py-4 border-t border-red-950/50 shrink-0 bg-zinc-950">
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Speak your intent..."
            className="flex-1 px-4 py-3 bg-black border border-red-950 text-red-50 placeholder:text-red-950 focus:border-red-900 focus:outline-none"
          />
          <button className="px-5 py-3 bg-red-900 hover:bg-red-800 text-red-50 font-bold flex items-center gap-2">
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
