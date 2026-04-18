import { Sparkles, User, Send } from 'lucide-react';

// Deep Violet Cards - More saturated purple with amber accents
export default function ChatRefinedTwo() {
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
    <div className="size-full flex flex-col" style={{ backgroundColor: '#0f0a1f' }}>
      {/* Header */}
      <div
        className="px-4 py-4 border-b shrink-0"
        style={{
          backgroundColor: '#1a1030',
          borderColor: '#2d1f52',
        }}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: '#3d2866', border: '1px solid #5d4a7a' }}>
              <Sparkles className="w-5 h-5" style={{ color: '#fbbf24' }} />
            </div>
            <div>
              <div className="font-bold" style={{ color: '#f3e8ff', fontSize: '17px' }}>
                The Cursed Vale
              </div>
              <div className="text-xs flex items-center gap-1.5" style={{ color: '#a78bfa' }}>
                <div className="w-1.5 h-1.5 rounded-full bg-green-400"></div>
                Online
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.map((msg, idx) => (
          <div key={idx} className="space-y-1.5">
            <div className="flex items-center gap-2">
              <div
                className="w-6 h-6 rounded-full flex items-center justify-center"
                style={{
                  backgroundColor: msg.type === 'gm' ? '#5b21b6' : '#7c3aed',
                }}
              >
                {msg.type === 'gm' ? (
                  <Sparkles className="w-3 h-3" style={{ color: '#fbbf24' }} />
                ) : (
                  <User className="w-3 h-3" style={{ color: '#fbbf24' }} />
                )}
              </div>
              <div
                className="text-xs font-bold"
                style={{ color: msg.type === 'gm' ? '#c4b5fd' : '#fbbf24' }}
              >
                {msg.type === 'gm' ? 'GAME MASTER' : 'YOU'}
              </div>
            </div>
            <div
              className="px-4 py-3 rounded-xl border ml-8"
              style={{
                backgroundColor: msg.type === 'gm' ? '#1e1537' : '#2d1f52',
                borderColor: msg.type === 'gm' ? '#3d2866' : '#5b21b6',
                color: '#e9d5ff',
                lineHeight: '1.6',
              }}
            >
              <div style={{ fontSize: '14px' }}>{msg.text}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Input */}
      <div
        className="px-4 py-4 border-t shrink-0"
        style={{
          backgroundColor: '#1a1030',
          borderColor: '#2d1f52',
        }}
      >
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Write your action..."
            className="flex-1 px-4 py-3 rounded-xl border focus:outline-none"
            style={{
              backgroundColor: '#0f0a1f',
              borderColor: '#3d2866',
              color: '#e9d5ff',
            }}
          />
          <button
            className="px-6 py-3 rounded-xl font-bold flex items-center gap-2"
            style={{
              backgroundColor: '#fbbf24',
              color: '#0f0a1f',
            }}
          >
            <Send className="w-4 h-4" />
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
