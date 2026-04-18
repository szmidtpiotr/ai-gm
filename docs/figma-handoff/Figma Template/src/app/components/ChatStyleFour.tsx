import { Sparkles, Send } from 'lucide-react';

// Mystic Codex - Purple/blue magic theme, ethereal and mystical
export default function ChatStyleFour() {
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
    <div className="size-full flex flex-col bg-slate-950">
      {/* Header */}
      <div className="px-4 py-4 border-b border-purple-950/50 shrink-0 bg-gradient-to-b from-slate-950 via-purple-950/20 to-slate-950">
        <div className="flex items-center gap-3">
          <div className="relative">
            <Sparkles className="w-6 h-6 text-purple-400" />
            <div className="absolute inset-0 blur-sm">
              <Sparkles className="w-6 h-6 text-purple-400" />
            </div>
          </div>
          <div>
            <div className="font-serif text-lg" style={{ color: '#e9d5ff', letterSpacing: '0.02em' }}>
              The Cursed Vale
            </div>
            <div className="text-xs italic" style={{ color: '#a78bfa' }}>
              Woven by fate and shadow...
            </div>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-5 space-y-4">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.type === 'player' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[84%] px-4 py-3 rounded-xl backdrop-blur-sm ${
                msg.type === 'gm'
                  ? 'bg-gradient-to-br from-purple-950/40 to-blue-950/30 border border-purple-800/30 shadow-lg shadow-purple-950/50'
                  : 'bg-gradient-to-br from-indigo-950/40 to-purple-950/30 border border-indigo-700/30 shadow-lg shadow-indigo-950/50'
              }`}
            >
              <div
                className={`text-[11px] font-semibold mb-2 tracking-wide uppercase flex items-center gap-1.5 ${
                  msg.type === 'gm' ? 'text-purple-300' : 'text-indigo-300'
                }`}
              >
                <div
                  className="w-1.5 h-1.5 rounded-full"
                  style={{
                    backgroundColor: msg.type === 'gm' ? '#c084fc' : '#818cf8',
                    boxShadow: msg.type === 'gm' ? '0 0 6px #c084fc' : '0 0 6px #818cf8',
                  }}
                />
                {msg.type === 'gm' ? 'The Weaver' : 'Your Tale'}
              </div>
              <div className="text-purple-50 leading-relaxed" style={{ fontSize: '15px' }}>
                {msg.text}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Input */}
      <div className="px-4 py-4 border-t border-purple-950/50 shrink-0 bg-gradient-to-t from-slate-950 via-purple-950/20 to-slate-950">
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Weave your story..."
            className="flex-1 px-4 py-3 rounded-lg border border-purple-900/30 bg-slate-950/50 backdrop-blur-sm text-purple-50 placeholder:text-purple-900/50 focus:border-purple-700/50 focus:outline-none focus:ring-2 focus:ring-purple-800/30"
          />
          <button className="px-5 py-3 rounded-lg bg-gradient-to-r from-purple-700 to-indigo-700 hover:from-purple-600 hover:to-indigo-600 text-purple-50 font-semibold flex items-center gap-2 shadow-lg shadow-purple-950/50">
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
