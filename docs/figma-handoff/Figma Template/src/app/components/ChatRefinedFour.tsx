import { Wand2, User, Send } from 'lucide-react';

// Dark Enchantment - Very dark with subtle purple glow
export default function ChatRefinedFour() {
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
    <div className="size-full flex flex-col" style={{ backgroundColor: '#0a0514' }}>
      {/* Header */}
      <div
        className="px-4 py-4 border-b shrink-0"
        style={{
          backgroundColor: '#110a1f',
          borderColor: '#1f1533',
        }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-full flex items-center justify-center relative"
            style={{
              backgroundColor: '#2d1f52',
              boxShadow: '0 0 20px rgba(139, 92, 246, 0.3)',
            }}
          >
            <Wand2 className="w-5 h-5" style={{ color: '#e5b35d' }} />
            <div
              className="absolute inset-0 rounded-full animate-pulse"
              style={{
                backgroundColor: '#8b5cf6',
                opacity: 0.2,
              }}
            ></div>
          </div>
          <div>
            <div className="font-semibold" style={{ color: '#f5f3ff', fontSize: '17px' }}>
              The Cursed Vale
            </div>
            <div className="text-xs" style={{ color: '#7c3aed' }}>
              Chapter III
            </div>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-3">
        {messages.map((msg, idx) => (
          <div key={idx} className="flex gap-2.5">
            {/* Avatar */}
            <div
              className="w-8 h-8 rounded-lg shrink-0 flex items-center justify-center"
              style={{
                backgroundColor: msg.type === 'gm' ? '#1f1533' : '#2d1f52',
                border: `1.5px solid ${msg.type === 'gm' ? '#4c1d95' : '#5b21b6'}`,
                boxShadow: msg.type === 'gm' ? '0 0 12px rgba(76, 29, 149, 0.4)' : '0 0 12px rgba(91, 33, 182, 0.4)',
              }}
            >
              {msg.type === 'gm' ? (
                <Wand2 className="w-4 h-4" style={{ color: '#e5b35d' }} />
              ) : (
                <User className="w-4 h-4" style={{ color: '#e5b35d' }} />
              )}
            </div>

            {/* Message */}
            <div className="flex-1 min-w-0">
              <div
                className="text-[10px] font-bold tracking-widest uppercase mb-1.5"
                style={{ color: msg.type === 'gm' ? '#a78bfa' : '#e5b35d' }}
              >
                {msg.type === 'gm' ? 'GM' : 'YOU'}
              </div>
              <div
                className="px-3.5 py-3 rounded-xl"
                style={{
                  backgroundColor: msg.type === 'gm' ? '#110a1f' : '#1f1533',
                  border: `1px solid ${msg.type === 'gm' ? '#2d1f52' : '#4c1d95'}`,
                  color: '#ede9fe',
                  lineHeight: '1.6',
                  boxShadow: msg.type === 'gm'
                    ? '0 2px 8px rgba(0, 0, 0, 0.3)'
                    : '0 2px 8px rgba(91, 33, 182, 0.15)',
                }}
              >
                <div style={{ fontSize: '14px' }}>{msg.text}</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Input */}
      <div
        className="px-4 py-3.5 border-t shrink-0"
        style={{
          backgroundColor: '#110a1f',
          borderColor: '#1f1533',
        }}
      >
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Your action..."
            className="flex-1 px-4 py-3 rounded-xl border focus:outline-none"
            style={{
              backgroundColor: '#0a0514',
              borderColor: '#2d1f52',
              color: '#ede9fe',
              fontSize: '14px',
            }}
          />
          <button
            className="px-5 py-3 rounded-xl font-bold flex items-center gap-2"
            style={{
              backgroundColor: '#e5b35d',
              color: '#0a0514',
              boxShadow: '0 4px 12px rgba(229, 179, 93, 0.25)',
            }}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
