import React from 'react';

/* ── Card ──────────────────────────────────────────────────────────────────── */
export function Card({ title, children, style = {}, action }) {
  return (
    <div className="card" style={{ marginBottom: 20, ...style }}>
      {title && (
        <div className="card-header">
          <span className="card-title">{title}</span>
          {action && <div>{action}</div>}
        </div>
      )}
      <div className="card-body" style={{ paddingTop: title ? 18 : 24 }}>
        {children}
      </div>
    </div>
  );
}

/* ── StatCard ──────────────────────────────────────────────────────────────── */
export function StatCard({ label, value, icon: Icon, color = 'var(--primary)', iconBg, sub, trend }) {
  const bg = iconBg || color + '18';
  return (
    <div className="stat-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="stat-label">{label}</div>
          <div className="stat-value">{value ?? '—'}</div>
          {sub && <div className="stat-sub">{sub}</div>}
          {trend !== undefined && (
            <div style={{ marginTop: 6, fontSize: 11, fontWeight: 600, color: trend >= 0 ? 'var(--success)' : 'var(--danger)' }}>
              {trend >= 0 ? '↑' : '↓'} {Math.abs(trend)}% vs last period
            </div>
          )}
        </div>
        {Icon && (
          <div className="stat-icon" style={{ background: bg }}>
            <Icon size={20} style={{ color }} />
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Badge ─────────────────────────────────────────────────────────────────── */
const BADGE_STYLES = {
  HIGH:      { bg: '#FEE2E2', color: '#991B1B' },
  MEDIUM:    { bg: '#FEF3C7', color: '#92400E' },
  LOW:       { bg: '#D1FAE5', color: '#065F46' },
  CRITICAL:  { bg: '#F5F3FF', color: '#5B21B6' },
  SUCCESS:   { bg: '#D1FAE5', color: '#065F46' },
  FAILURE:   { bg: '#FEE2E2', color: '#991B1B' },
  SUGGESTED: { bg: '#DBEAFE', color: '#1E40AF' },
  APPROVED:  { bg: '#D1FAE5', color: '#065F46' },
  ORDERED:   { bg: '#FEF3C7', color: '#92400E' },
  RECEIVED:  { bg: '#ECFDF5', color: '#047857' },
  CONFIRMED: { bg: '#D1FAE5', color: '#065F46' },
  DRAFT:     { bg: '#F1F5F9', color: '#475569' },
  CANCELLED: { bg: '#FEE2E2', color: '#991B1B' },
  REFUNDED:  { bg: '#F5F3FF', color: '#5B21B6' },
  OTC:       { bg: '#DBEAFE', color: '#1E40AF' },
  PRESCRIPTION: { bg: '#EDE9FE', color: '#5B21B6' },
  CONTROLLED:   { bg: '#FEE2E2', color: '#991B1B' },
};

export function Badge({ text, color }) {
  const s = BADGE_STYLES[String(text).toUpperCase()] || { bg: color ? color + '20' : '#F1F5F9', color: color || 'var(--text-secondary)' };
  return (
    <span className="badge" style={{ background: s.bg, color: s.color }}>
      {text}
    </span>
  );
}

/* ── Table ─────────────────────────────────────────────────────────────────── */
export function Table({ columns, data, emptyMsg = 'No data' }) {
  if (!data?.length) return (
    <div className="empty-state">
      <div className="empty-state-icon">○</div>
      <div>{emptyMsg}</div>
    </div>
  );
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map(c => <th key={c.key}>{c.label}</th>)}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i}>
              {columns.map(c => (
                <td key={c.key}>
                  {c.render ? c.render(row[c.key], row) : (row[c.key] ?? '—')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ── Btn ────────────────────────────────────────────────────────────────────── */
const BTN_VARIANT = {
  '#27ae60': 'btn-success',
  '#10B981': 'btn-success',
  '#e74c3c': 'btn-danger',
  '#EF4444': 'btn-danger',
  '#f39c12': 'btn-warning',
  '#F59E0B': 'btn-warning',
  '#3498db': 'btn-primary',
  '#0EA5E9': 'btn-primary',
  '#4fc3f7': 'btn-primary',
  '#9b59b6': 'btn-violet',
  '#8B5CF6': 'btn-violet',
  '#95a5a6': 'btn-ghost',
};

export function Btn({ children, onClick, color = '#0EA5E9', disabled, style = {}, size = 'md' }) {
  const variant = BTN_VARIANT[color] || 'btn-primary';
  const sizeClass = size === 'sm' ? 'btn-sm' : 'btn-md';
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`btn ${variant} ${sizeClass}`}
      style={style}
    >
      {children}
    </button>
  );
}

/* ── Skeleton ───────────────────────────────────────────────────────────────── */
export function Skeleton({ width = '100%', height = 16, radius = 6, style = {} }) {
  return (
    <div className="skeleton" style={{ width, height, borderRadius: radius, ...style }} />
  );
}

export function SkeletonCard() {
  return (
    <div className="card" style={{ padding: 24, marginBottom: 20 }}>
      <Skeleton width="40%" height={14} style={{ marginBottom: 16 }} />
      <Skeleton height={12} style={{ marginBottom: 8 }} />
      <Skeleton width="80%" height={12} style={{ marginBottom: 8 }} />
      <Skeleton width="60%" height={12} />
    </div>
  );
}

export function SkeletonStatCards() {
  return (
    <div style={{ display: 'flex', gap: 16, marginBottom: 24, flexWrap: 'wrap' }}>
      {[1,2,3,4].map(i => (
        <div key={i} className="stat-card" style={{ flex: 1, minWidth: 160 }}>
          <Skeleton width="60%" height={11} style={{ marginBottom: 12 }} />
          <Skeleton width="50%" height={28} style={{ marginBottom: 8 }} />
          <Skeleton width="40%" height={10} />
        </div>
      ))}
    </div>
  );
}
