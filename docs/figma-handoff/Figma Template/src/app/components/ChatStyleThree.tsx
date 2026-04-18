import { Crosshair, Send } from 'lucide-react';

// Tactical War Room - Military/operator style, green/gray, terminal-like
export default function ChatStyleThree() {
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
    <div className="size-full flex flex-col" style={{ backgroundColor: '#0a0f0d' }}>
      {/* Header */}
      <div
        className="px-4 py-3 border-b shrink-0"
        style={{
          backgroundColor: '#0f1612',
          borderColor: '#1a3028',
        }}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Crosshair className="w-5 h-5" style={{ color: '#4ade80' }} />
            <div>
              <div className="font-mono font-bold tracking-wide" style={{ color: '#86efac', fontSize: '14px' }}>
                MISSION: THE CURSED VALE
              </div>
              <div className="font-mono text-xs" style={{ color: '#4ade80' }}>
                STATUS: ACTIVE | LOG: 005
              </div>
            </div>
          </div>
          <div className="font-mono text-xs" style={{ color: '#22c55e' }}>
            ●
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {messages.map((msg, idx) => (
          <div key={idx} className="space-y-1">
            <div
              className="font-mono text-[10px] tracking-wider uppercase font-bold"
              style={{ color: msg.type === 'gm' ? '#4ade80' : '#fbbf24' }}
            >
              [{msg.type === 'gm' ? 'GM-RESPONSE' : 'PLAYER-ACTION'}] {new Date().toLocaleTimeString('en-US', { hour12: false })}
            </div>
            <div
              className="px-3 py-2.5 border-l-2"
              style={{
                backgroundColor: msg.type === 'gm' ? '#0f1612' : '#1a1505',
                borderColor: msg.type === 'gm' ? '#22c55e' : '#fbbf24',
                color: '#d1d5db',
                lineHeight: '1.5',
              }}
            >
              <div className="font-sans" style={{ fontSize: '14px' }}>
                {msg.text}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Input */}
      <div
        className="px-4 py-3 border-t shrink-0"
        style={{
          backgroundColor: '#0f1612',
          borderColor: '#1a3028',
        }}
      >
        <div className="flex gap-2">
          <input
            type="text"
            placeholder=">> INPUT ACTION_"
            className="flex-1 px-4 py-2.5 border font-mono"
            style={{
              backgroundColor: '#0a0f0d',
              borderColor: '#1a3028',
              color: '#86efac',
              fontSize: '14px',
            }}
          />
          <button
            className="px-5 py-2.5 font-mono font-bold tracking-wide flex items-center gap-2"
            style={{
              backgroundColor: '#166534',
              color: '#86efac',
              fontSize: '12px',
            }}
          >
            SEND <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
