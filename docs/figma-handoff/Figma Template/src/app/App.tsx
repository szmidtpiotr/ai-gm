import { useState } from 'react';
import PlayerApp from './components/PlayerApp';
import AdminApp from './components/AdminApp';

export default function App() {
  const [view, setView] = useState<'player' | 'admin'>('player');

  return (
    <div className="size-full flex flex-col bg-stone-950">
      {/* View Switcher */}
      <div className="bg-stone-900 border-b border-stone-700 p-3 flex gap-2 shrink-0">
        <button
          onClick={() => setView('player')}
          className={`px-6 py-2 rounded transition-colors ${
            view === 'player'
              ? 'bg-purple-700 text-purple-50 font-semibold'
              : 'bg-stone-800 text-stone-400 hover:bg-stone-700'
          }`}
        >
          Player View
        </button>
        <button
          onClick={() => setView('admin')}
          className={`px-6 py-2 rounded transition-colors ${
            view === 'admin'
              ? 'bg-purple-700 text-purple-50 font-semibold'
              : 'bg-stone-800 text-stone-400 hover:bg-stone-700'
          }`}
        >
          Admin Panel
        </button>
      </div>

      {/* View Display */}
      <div className="flex-1 overflow-hidden">
        {view === 'player' ? <PlayerApp onNavigateToAdmin={() => setView('admin')} /> : <AdminApp onNavigateToPlayer={() => setView('player')} />}
      </div>
    </div>
  );
}
