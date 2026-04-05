import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const NAV = [
  { path: '/',               label: 'Dashboard',      icon: '📊', roles: ['admin','supervisor'] },
  { path: '/inventory',      label: 'Inventory',       icon: '💊', roles: ['admin','supervisor','pharmacist'] },
  { path: '/billing',        label: 'Billing',         icon: '🧾', roles: ['admin','supervisor','pharmacist'] },
  { path: '/replenishment',  label: 'Replenishment',   icon: '🔄', roles: ['admin','supervisor'] },
  { path: '/ai',             label: 'AI Insights',     icon: '🤖', roles: ['admin','supervisor'] },
  { path: '/reports',        label: 'Reports',         icon: '📈', roles: ['admin','supervisor'] },
  { path: '/audit',          label: 'Audit Logs',      icon: '🔒', roles: ['admin'] },
];

const ROLE_COLOR = { admin: '#e74c3c', supervisor: '#f39c12', pharmacist: '#27ae60' };

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);

  const allowed = NAV.filter(n => n.roles.includes(user?.role));

  const handleLogout = () => { logout(); navigate('/login'); };

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: '#f0f4f8' }}>
      {/* Sidebar */}
      <aside style={{
        width: collapsed ? 60 : 220, background: '#1a2332', color: '#fff',
        display: 'flex', flexDirection: 'column', transition: 'width 0.2s',
        flexShrink: 0
      }}>
        {/* Logo */}
        <div style={{ padding: '20px 16px', borderBottom: '1px solid #2d3f55', display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 24 }}>💊</span>
          {!collapsed && <span style={{ fontWeight: 700, fontSize: 16, color: '#4fc3f7' }}>MedAxis</span>}
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: '12px 0' }}>
          {allowed.map(item => {
            const active = location.pathname === item.path;
            return (
              <Link key={item.path} to={item.path} style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '10px 16px', textDecoration: 'none',
                color: active ? '#4fc3f7' : '#b0bec5',
                background: active ? '#2d3f55' : 'transparent',
                borderLeft: active ? '3px solid #4fc3f7' : '3px solid transparent',
                fontSize: 14, transition: 'all 0.15s'
              }}>
                <span style={{ fontSize: 18 }}>{item.icon}</span>
                {!collapsed && item.label}
              </Link>
            );
          })}
        </nav>

        {/* User info */}
        <div style={{ padding: '12px 16px', borderTop: '1px solid #2d3f55' }}>
          {!collapsed && (
            <div style={{ marginBottom: 8 }}>
              <div style={{ fontSize: 13, fontWeight: 600 }}>{user?.username}</div>
              <span style={{
                fontSize: 11, padding: '2px 8px', borderRadius: 10,
                background: ROLE_COLOR[user?.role] || '#555', color: '#fff'
              }}>{user?.role}</span>
            </div>
          )}
          <button onClick={handleLogout} style={{
            width: '100%', padding: '6px', background: '#e74c3c',
            color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 12
          }}>
            {collapsed ? '↩' : 'Logout'}
          </button>
        </div>

        {/* Collapse toggle */}
        <button onClick={() => setCollapsed(!collapsed)} style={{
          background: '#2d3f55', border: 'none', color: '#fff',
          padding: '8px', cursor: 'pointer', fontSize: 16
        }}>
          {collapsed ? '→' : '←'}
        </button>
      </aside>

      {/* Main content */}
      <main style={{ flex: 1, overflow: 'auto' }}>
        {/* Top bar */}
        <div style={{
          background: '#fff', padding: '12px 24px', borderBottom: '1px solid #e0e0e0',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          boxShadow: '0 1px 4px rgba(0,0,0,0.08)'
        }}>
          <h2 style={{ fontSize: 18, color: '#1a2332', fontWeight: 600 }}>
            {allowed.find(n => n.path === location.pathname)?.label || 'MedAxis Platform'}
          </h2>
          <div style={{ fontSize: 13, color: '#666' }}>
            Store: <strong>{user?.store_id || 'All Stores'}</strong>
          </div>
        </div>

        <div style={{ padding: 24 }}>{children}</div>
      </main>
    </div>
  );
}
