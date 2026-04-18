import { Scroll, Send } from 'lucide-react';

// Parchment Scholar - Warm, readable, book-like with sepia tones
export default function ChatStyleOne() {
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
    <div className="size-full flex flex-col" style={{ backgroundColor: '#1c1410' }}>
      {/* Header */}
      <div
        className="px-4 py-4 border-b shrink-0"
        style={{
          backgroundColor: '#2a1f1a',
          borderColor: '#3d2e24',
        }}
      >
        <div className="flex items-center gap-3">
          <Scroll className="w-6 h-6" style={{ color: '#d4a574' }} />
          <div>
            <div className="font-semibold" style={{ color: '#e8d5b7', fontSize: '17px' }}>
              The Cursed Vale
            </div>
            <div className="text-xs" style={{ color: '#8b7355' }}>
              Chapter III: The Hooded Stranger
            </div>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-5 space-y-4">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.type === 'player' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[82%] px-4 py-3 rounded-lg border ${
                msg.type === 'gm' ? 'rounded-tl-none' : 'rounded-tr-none'
              }`}
              style={{
                backgroundColor: msg.type === 'gm' ? '#2a1f1a' : '#3d2c1f',
                borderColor: msg.type === 'gm' ? '#3d2e24' : '#5a432e',
                color: '#e8d5b7',
                lineHeight: '1.6',
              }}
            >
              <div
                className="text-xs font-semibold mb-1.5 tracking-wide uppercase"
                style={{ color: msg.type === 'gm' ? '#d4a574' : '#c9985a' }}
              >
                {msg.type === 'gm' ? 'Game Master' : 'You'}
              </div>
              <div style={{ fontSize: '15px' }}>{msg.text}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Input */}
      <div
        className="px-4 py-4 border-t shrink-0"
        style={{
          backgroundColor: '#2a1f1a',
          borderColor: '#3d2e24',
        }}
      >
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Describe your action..."
            className="flex-1 px-4 py-3 rounded border"
            style={{
              backgroundColor: '#1c1410',
              borderColor: '#3d2e24',
              color: '#e8d5b7',
            }}
          />
          <button
            className="px-5 py-3 rounded font-medium flex items-center gap-2"
            style={{
              backgroundColor: '#8b5a2b',
              color: '#fef3e2',
            }}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
