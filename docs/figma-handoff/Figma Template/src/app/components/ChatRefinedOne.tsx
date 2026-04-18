import { Sparkles, User, Send } from 'lucide-react';

// Royal Purple & Gold - Closest to reference image
export default function ChatRefinedOne() {
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
    <div className="size-full flex flex-col" style={{ backgroundColor: '#1a0f2e' }}>
      {/* Header */}
      <div
        className="px-4 py-4 border-b shrink-0"
        style={{
          backgroundColor: '#231640',
          borderColor: '#3d2866',
        }}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full flex items-center justify-center" style={{ backgroundColor: '#4c2f7a' }}>
              <Sparkles className="w-5 h-5" style={{ color: '#d4a574' }} />
            </div>
            <div>
              <div className="font-semibold" style={{ color: '#e5d4f7', fontSize: '16px' }}>
                The Cursed Vale
              </div>
              <div className="text-xs" style={{ color: '#8b7ba8' }}>
                Active Session
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {messages.map((msg, idx) => (
          <div key={idx} className="flex gap-3">
            {/* Avatar */}
            <div
              className="w-8 h-8 rounded-full shrink-0 flex items-center justify-center"
              style={{
                backgroundColor: msg.type === 'gm' ? '#4c2f7a' : '#5d4a7a',
              }}
            >
              {msg.type === 'gm' ? (
                <Sparkles className="w-4 h-4" style={{ color: '#d4a574' }} />
              ) : (
                <User className="w-4 h-4" style={{ color: '#d4a574' }} />
              )}
            </div>

            {/* Message Card */}
            <div className="flex-1">
              <div
                className="text-xs font-semibold mb-1"
                style={{ color: msg.type === 'gm' ? '#b794f6' : '#d4a574' }}
              >
                {msg.type === 'gm' ? 'Game Master' : 'You'}
              </div>
              <div
                className="px-4 py-3 rounded-lg border"
                style={{
                  backgroundColor: msg.type === 'gm' ? '#2a1a47' : '#3d2866',
                  borderColor: msg.type === 'gm' ? '#4c2f7a' : '#5d4a7a',
                  color: '#e5d4f7',
                  lineHeight: '1.6',
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
        className="px-4 py-4 border-t shrink-0"
        style={{
          backgroundColor: '#231640',
          borderColor: '#3d2866',
        }}
      >
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Describe your action..."
            className="flex-1 px-4 py-3 rounded-lg border"
            style={{
              backgroundColor: '#1a0f2e',
              borderColor: '#4c2f7a',
              color: '#e5d4f7',
            }}
          />
          <button
            className="px-6 py-3 rounded-lg font-semibold flex items-center gap-2"
            style={{
              backgroundColor: '#d4a574',
              color: '#1a0f2e',
            }}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
