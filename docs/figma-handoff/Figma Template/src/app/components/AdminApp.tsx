import { useState } from 'react';
import { Database, Edit2, Trash2, Lock, Plus, Shield, Sword, Target, Users, Flame, Save, X, Gamepad2 } from 'lucide-react';

interface AdminAppProps {
  onNavigateToPlayer: () => void;
}

export default function AdminApp({ onNavigateToPlayer }: AdminAppProps) {
  const [activeTab, setActiveTab] = useState('stats');
  const [editingRow, setEditingRow] = useState<number | null>(null);

  const tabs = [
    { id: 'stats', label: 'Stats', icon: Target },
    { id: 'skills', label: 'Skills', icon: Target },
    { id: 'weapons', label: 'Weapons', icon: Sword },
    { id: 'enemies', label: 'Enemies', icon: Flame },
    { id: 'accounts', label: 'Accounts', icon: Users },
  ];

  const statsData = [
    { id: 1, key: 'STR', label: 'Strength', description: 'Physical power and melee force', sort_order: 1, locked: true },
    { id: 2, key: 'DEX', label: 'Dexterity', description: 'Agility and precision', sort_order: 2, locked: false },
    { id: 3, key: 'CON', label: 'Constitution', description: 'Endurance and vitality', sort_order: 3, locked: false },
    { id: 4, key: 'INT', label: 'Intelligence', description: 'Knowledge and reasoning', sort_order: 4, locked: false },
  ];

  const weaponsData = [
    { id: 1, key: 'longsword', label: 'Longsword', damage_die: '1d8', linked_stat: 'STR', active: true },
    { id: 2, key: 'shortbow', label: 'Shortbow', damage_die: '1d6', linked_stat: 'DEX', active: true },
    { id: 3, key: 'dagger', label: 'Dagger', damage_die: '1d4', linked_stat: 'DEX', active: true },
  ];

  const enemiesData = [
    { id: 1, key: 'goblin', label: 'Goblin', hp_base: 8, ac_base: 11, damage_die: '1d6', active: true },
    { id: 2, key: 'orc', label: 'Orc', hp_base: 15, ac_base: 13, damage_die: '1d8', active: true },
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
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <div className="flex items-center gap-3">
            <div
              className="w-11 h-11 rounded-xl flex items-center justify-center"
              style={{
                background: 'linear-gradient(135deg, #4c1d95 0%, #5b21b6 100%)',
                boxShadow: '0 4px 12px rgba(139, 92, 246, 0.2)',
              }}
            >
              <Shield className="w-6 h-6" style={{ color: '#fcd34d' }} />
            </div>
            <div>
              <div className="font-bold tracking-tight" style={{ color: '#faf5ff', fontSize: '18px' }}>
                Admin Panel
              </div>
              <div className="text-xs" style={{ color: '#a78bfa' }}>
                Game Master Control Center
              </div>
            </div>
          </div>
          <button
            onClick={onNavigateToPlayer}
            className="flex items-center gap-2 px-4 py-2 rounded-lg font-semibold"
            style={{
              background: 'linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%)',
              color: '#0d0821',
            }}
          >
            <Gamepad2 className="w-4 h-4" />
            Back to Game
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div
        className="px-4 py-3 overflow-x-auto shrink-0"
        style={{
          backgroundColor: '#150f2e',
          borderBottom: '1px solid #2d1f52',
        }}
      >
        <div className="flex gap-2 max-w-7xl mx-auto">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors whitespace-nowrap ${
                  activeTab === tab.id ? '' : ''
                }`}
                style={{
                  backgroundColor: activeTab === tab.id ? '#5b21b6' : '#1a1035',
                  color: activeTab === tab.id ? '#fcd34d' : '#a78bfa',
                }}
              >
                <Icon className="w-4 h-4" />
                <span className="font-semibold text-sm">{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto px-4 py-5">
        <div className="max-w-7xl mx-auto">
          {/* Stats Table */}
          {activeTab === 'stats' && (
            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold" style={{ color: '#faf5ff' }}>
                  Primary Stats
                </h2>
                <button
                  className="flex items-center gap-2 px-4 py-2 rounded-lg font-semibold"
                  style={{
                    background: 'linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%)',
                    color: '#0d0821',
                  }}
                >
                  <Plus className="w-4 h-4" />
                  Add Stat
                </button>
              </div>

              <div
                className="rounded-2xl border overflow-hidden"
                style={{
                  backgroundColor: '#1a1035',
                  borderColor: '#3d2866',
                }}
              >
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr style={{ backgroundColor: '#0d0821', borderBottom: '1px solid #3d2866' }}>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Key
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Label
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Description
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Order
                        </th>
                        <th className="px-4 py-3 text-right text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {statsData.map((stat, idx) => (
                        <tr
                          key={stat.id}
                          style={{
                            borderBottom: idx !== statsData.length - 1 ? '1px solid #2d1f52' : 'none',
                          }}
                        >
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <span className="font-mono font-bold" style={{ color: '#fcd34d' }}>
                                {stat.key}
                              </span>
                              {stat.locked && <Lock className="w-3 h-3" style={{ color: '#ef4444' }} />}
                            </div>
                          </td>
                          <td className="px-4 py-3" style={{ color: '#f3e8ff' }}>
                            {stat.label}
                          </td>
                          <td className="px-4 py-3" style={{ color: '#a78bfa' }}>
                            {stat.description}
                          </td>
                          <td className="px-4 py-3" style={{ color: '#f3e8ff' }}>
                            {stat.sort_order}
                          </td>
                          <td className="px-4 py-3 text-right">
                            <div className="flex items-center justify-end gap-2">
                              <button
                                className="p-2 rounded-lg hover:bg-purple-900/30"
                                style={{ color: '#a78bfa' }}
                              >
                                <Edit2 className="w-4 h-4" />
                              </button>
                              <button
                                className="p-2 rounded-lg hover:bg-red-900/30"
                                style={{ color: '#ef4444' }}
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Weapons Table */}
          {activeTab === 'weapons' && (
            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold" style={{ color: '#faf5ff' }}>
                  Weapons
                </h2>
                <button
                  className="flex items-center gap-2 px-4 py-2 rounded-lg font-semibold"
                  style={{
                    background: 'linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%)',
                    color: '#0d0821',
                  }}
                >
                  <Plus className="w-4 h-4" />
                  Add Weapon
                </button>
              </div>

              <div
                className="rounded-2xl border overflow-hidden"
                style={{
                  backgroundColor: '#1a1035',
                  borderColor: '#3d2866',
                }}
              >
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr style={{ backgroundColor: '#0d0821', borderBottom: '1px solid #3d2866' }}>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Key
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Label
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Damage
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Stat
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Status
                        </th>
                        <th className="px-4 py-3 text-right text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {weaponsData.map((weapon, idx) => (
                        <tr
                          key={weapon.id}
                          style={{
                            borderBottom: idx !== weaponsData.length - 1 ? '1px solid #2d1f52' : 'none',
                          }}
                        >
                          <td className="px-4 py-3">
                            <span className="font-mono" style={{ color: '#a78bfa' }}>
                              {weapon.key}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-semibold" style={{ color: '#f3e8ff' }}>
                            {weapon.label}
                          </td>
                          <td className="px-4 py-3">
                            <span className="font-mono font-bold" style={{ color: '#fcd34d' }}>
                              {weapon.damage_die}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="font-mono" style={{ color: '#f3e8ff' }}>
                              {weapon.linked_stat}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className="px-2 py-1 rounded text-xs font-semibold"
                              style={{
                                backgroundColor: weapon.active ? '#166534' : '#7f1d1d',
                                color: weapon.active ? '#86efac' : '#fca5a5',
                              }}
                            >
                              {weapon.active ? 'Active' : 'Inactive'}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-right">
                            <div className="flex items-center justify-end gap-2">
                              <button
                                className="p-2 rounded-lg hover:bg-purple-900/30"
                                style={{ color: '#a78bfa' }}
                              >
                                <Edit2 className="w-4 h-4" />
                              </button>
                              <button
                                className="p-2 rounded-lg hover:bg-red-900/30"
                                style={{ color: '#ef4444' }}
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Enemies Table */}
          {activeTab === 'enemies' && (
            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold" style={{ color: '#faf5ff' }}>
                  Enemies
                </h2>
                <button
                  className="flex items-center gap-2 px-4 py-2 rounded-lg font-semibold"
                  style={{
                    background: 'linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%)',
                    color: '#0d0821',
                  }}
                >
                  <Plus className="w-4 h-4" />
                  Add Enemy
                </button>
              </div>

              <div
                className="rounded-2xl border overflow-hidden"
                style={{
                  backgroundColor: '#1a1035',
                  borderColor: '#3d2866',
                }}
              >
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr style={{ backgroundColor: '#0d0821', borderBottom: '1px solid #3d2866' }}>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Key
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Label
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          HP
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          AC
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Damage
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Status
                        </th>
                        <th className="px-4 py-3 text-right text-xs font-bold uppercase tracking-wider" style={{ color: '#c4b5fd' }}>
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {enemiesData.map((enemy, idx) => (
                        <tr
                          key={enemy.id}
                          style={{
                            borderBottom: idx !== enemiesData.length - 1 ? '1px solid #2d1f52' : 'none',
                          }}
                        >
                          <td className="px-4 py-3">
                            <span className="font-mono" style={{ color: '#a78bfa' }}>
                              {enemy.key}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-semibold" style={{ color: '#f3e8ff' }}>
                            {enemy.label}
                          </td>
                          <td className="px-4 py-3">
                            <span className="font-mono" style={{ color: '#ef4444' }}>
                              {enemy.hp_base}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="font-mono" style={{ color: '#3b82f6' }}>
                              {enemy.ac_base}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="font-mono font-bold" style={{ color: '#fcd34d' }}>
                              {enemy.damage_die}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className="px-2 py-1 rounded text-xs font-semibold"
                              style={{
                                backgroundColor: enemy.active ? '#166534' : '#7f1d1d',
                                color: enemy.active ? '#86efac' : '#fca5a5',
                              }}
                            >
                              {enemy.active ? 'Active' : 'Inactive'}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-right">
                            <div className="flex items-center justify-end gap-2">
                              <button
                                className="p-2 rounded-lg hover:bg-purple-900/30"
                                style={{ color: '#a78bfa' }}
                              >
                                <Edit2 className="w-4 h-4" />
                              </button>
                              <button
                                className="p-2 rounded-lg hover:bg-red-900/30"
                                style={{ color: '#ef4444' }}
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Skills and Accounts tabs - placeholder */}
          {(activeTab === 'skills' || activeTab === 'accounts') && (
            <div className="text-center py-12">
              <Database className="w-16 h-16 mx-auto mb-4" style={{ color: '#5b21b6' }} />
              <h3 className="text-xl font-bold mb-2" style={{ color: '#faf5ff' }}>
                {activeTab === 'skills' ? 'Skills' : 'Accounts'} Management
              </h3>
              <p style={{ color: '#a78bfa' }}>Content coming soon...</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
