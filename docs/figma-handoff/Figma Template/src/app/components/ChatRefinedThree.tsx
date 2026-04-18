import { Crown, User, ArrowRight } from 'lucide-react';

// Midnight Arcane - Dark navy purple with golden highlights
export default function ChatRefinedThree() {
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
    <div className="size-full flex flex-col" style={{ backgroundColor: '#0d0821' }}>
      {/* Header */}
      <div
        className="px-4 py-4 shrink-0"
        style={{
          backgroundColor: '#150f2e',
          borderBottom: '1px solid #2d1f52',
        }}
      >
        <div className="flex items-center justify-between">
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

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-5 space-y-4">
        {messages.map((msg, idx) => (
          <div key={idx} className="flex gap-3">
            {/* Avatar */}
            <div
              className="w-9 h-9 rounded-xl shrink-0 flex items-center justify-center"
              style={{
                backgroundColor: msg.type === 'gm' ? '#2d1f52' : '#3d2866',
                border: `2px solid ${msg.type === 'gm' ? '#5b21b6' : '#6d28d9'}`,
              }}
            >
              {msg.type === 'gm' ? (
                <Crown className="w-4 h-4" style={{ color: '#fcd34d' }} />
              ) : (
                <User className="w-4 h-4" style={{ color: '#fcd34d' }} />
              )}
            </div>

            {/* Message */}
            <div className="flex-1 space-y-1">
              <div
                className="text-[11px] font-bold tracking-wider uppercase"
                style={{ color: msg.type === 'gm' ? '#c4b5fd' : '#fcd34d' }}
              >
                {msg.type === 'gm' ? 'Game Master' : 'Your Action'}
              </div>
              <div
                className="px-4 py-3.5 rounded-2xl"
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
  );
}
