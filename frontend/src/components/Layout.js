import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  LayoutDashboard, Package, Receipt, RefreshCw, Brain,
  BarChart2, Shield, LogOut, ChevronLeft, ChevronRight,
  MapPin,
} from 'lucide-react';

const NAV = [
  { path: '/',              label: 'Dashboard',     Icon: LayoutDashboard, roles: ['admin', 'supervisor'] },
  { path: '/inventory',     label: 'Inventory',     Icon: Package,         roles: ['admin', 'supervisor', 'pharmacist', 'inventory_planner'] },
  { path: '/billing',       label: 'Billing',       Icon: Receipt,         roles: ['admin', 'supervisor', 'pharmacist'] },
  { path: '/replenishment', label: 'Replenishment', Icon: RefreshCw,       roles: ['admin', 'supervisor', 'inventory_planner'] },
  { path: '/ai',            label: 'AI Insights',   Icon: Brain,           roles: ['admin', 'supervisor'] },
  { path: '/reports',       label: 'Reports',       Icon: BarChart2,       roles: ['admin', 'supervisor'] },
  { path: '/audit',         label: 'Audit Logs',    Icon: Shield,          roles: ['admin'] },
];

const ROLE_COLORS = {
  admin:             { bg: '#FEE2E2', color: '#991B1B' },
  supervisor:        { bg: '#FEF3C7', color: '#92400E' },
  pharmacist:        { bg: '#D1FAE5', color: '#065F46' },
  inventory_planner: { bg: '#DBEAFE', color: '#1E40AF' },
};

function initials(name = '') {
  return name.slice(0, 2).toUpperCase() || 'U';
}

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const location  = useLocation();
  const navigate  = useNavigate();
  const [collapsed, setCollapsed] = useState(false);

  const allowed = NAV.filter(n => n.roles.includes(user?.role));
  const currentPage = allowed.find(n => n.path === location.pathname);
  const roleColor = ROLE_COLORS[user?.role] || { bg: '#F1F5F9', color: '#475569' };

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg-base)' }}>

      {/* ── Sidebar ── */}
      <aside
        className="sidebar"
        style={{
          width: collapsed ? 62 : 240,
          display: 'flex', flexDirection: 'column',
          transition: 'width 0.22s cubic-bezier(0.4,0,0.2,1)',
          flexShrink: 0, position: 'sticky', top: 0, height: '100vh',
          overflow: 'hidden',
        }}
      >
        {/* Logo */}
        <div className="sidebar-logo-wrap" style={{ overflow: 'hidden' }}>
          <div className="sidebar-logo-mark">M</div>
          {!collapsed && (
            <div style={{ overflow: 'hidden' }}>
              <div className="sidebar-logo-text">MedAxis</div>
              <div className="sidebar-logo-sub">Platform</div>
            </div>
          )}
        </div>

        {/* Nav */}
        <nav className="sidebar-nav">
          {allowed.map(({ path, label, Icon }) => {
            const active = location.pathname === path;
            return (
              <Link
                key={path}
                to={path}
                title={collapsed ? label : undefined}
                className={`nav-item ${active ? 'active' : ''}`}
              >
                <Icon size={17} className="nav-icon" />
                {!collapsed && <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* User + logout */}
        <div className="sidebar-footer">
          {!collapsed ? (
            <div style={{ marginBottom: 10, display: 'flex', alignItems: 'center', gap: 10 }}>
              <div className="user-avatar" style={{ flexShrink: 0 }}>{initials(user?.username)}</div>
              <div style={{ overflow: 'hidden', flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: '#F1F5F9', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {user?.username}
                </div>
                <div style={{ marginTop: 3 }}>
                  <span className="role-badge" style={{ background: roleColor.bg, color: roleColor.color, fontSize: 9 }}>
                    {user?.role?.replace('_', ' ')}
                  </span>
                </div>
                {user?.outlet_id && (
                  <div style={{ fontSize: 10, color: 'var(--slate-500)', marginTop: 3, display: 'flex', alignItems: 'center', gap: 3 }}>
                    <MapPin size={9} /> {user.outlet_id}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 8 }}>
              <div className="user-avatar">{initials(user?.username)}</div>
            </div>
          )}
          <button
            onClick={handleLogout}
            title={collapsed ? 'Logout' : undefined}
            style={{
              width: '100%', padding: collapsed ? '8px' : '8px 12px',
              background: 'rgba(239,68,68,0.1)', color: '#F87171',
              border: '1px solid rgba(239,68,68,0.2)', borderRadius: 'var(--r-sm)',
              cursor: 'pointer', fontSize: 12, fontWeight: 600,
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
              transition: 'all var(--t-fast)',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(239,68,68,0.18)'; e.currentTarget.style.color = '#FCA5A5'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'rgba(239,68,68,0.1)';  e.currentTarget.style.color = '#F87171'; }}
          >
            <LogOut size={13} />
            {!collapsed && 'Logout'}
          </button>
        </div>

        {/* Collapse toggle */}
        <button className="sidebar-collapse-btn" onClick={() => setCollapsed(c => !c)}>
          {collapsed ? <ChevronRight size={15} /> : <ChevronLeft size={15} />}
        </button>
      </aside>

      {/* ── Main ── */}
      <main style={{ flex: 1, overflow: 'auto', minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        {/* Topbar */}
        <div className="topbar">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {currentPage && <currentPage.Icon size={18} style={{ color: 'var(--primary)', flexShrink: 0 }} />}
            <span className="topbar-title">{currentPage?.label || 'MedAxis'}</span>
          </div>
          <div className="topbar-right">
            {user?.outlet_id && (
              <div className="topbar-chip">
                <MapPin size={11} style={{ color: 'var(--text-muted)' }} />
                {user.outlet_id}
              </div>
            )}
            <span className="role-badge" style={{ background: roleColor.bg, color: roleColor.color }}>
              {user?.role?.replace('_', ' ')}
            </span>
            <div className="topbar-avatar">{initials(user?.username)}</div>
          </div>
        </div>

        {/* Content */}
        <div style={{ padding: 24, flex: 1 }} className="page-enter">
          {children}
        </div>
      </main>
    </div>
  );
}
