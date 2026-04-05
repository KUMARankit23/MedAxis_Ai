import React from 'react';

export function Card({ title, children, style = {} }) {
  return (
    <div style={{
      background: '#fff', borderRadius: 10, padding: 20,
      boxShadow: '0 2px 8px rgba(0,0,0,0.07)', marginBottom: 20, ...style
    }}>
      {title && <h3 style={{ marginBottom: 16, fontSize: 15, color: '#1a2332', fontWeight: 600 }}>{title}</h3>}
      {children}
    </div>
  );
}

export function StatCard({ label, value, icon, color = '#4fc3f7', sub }) {
  return (
    <div style={{
      background: '#fff', borderRadius: 10, padding: '20px 24px',
      boxShadow: '0 2px 8px rgba(0,0,0,0.07)',
      borderLeft: `4px solid ${color}`, flex: 1, minWidth: 160
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontSize: 12, color: '#888', marginBottom: 4 }}>{label}</div>
          <div style={{ fontSize: 28, fontWeight: 700, color: '#1a2332' }}>{value ?? '—'}</div>
          {sub && <div style={{ fontSize: 11, color: '#aaa', marginTop: 4 }}>{sub}</div>}
        </div>
        <span style={{ fontSize: 28 }}>{icon}</span>
      </div>
    </div>
  );
}

export function Badge({ text, color = '#4fc3f7' }) {
  const colors = {
    HIGH: '#e74c3c', MEDIUM: '#f39c12', LOW: '#27ae60',
    CRITICAL: '#8e44ad', SUCCESS: '#27ae60', FAILURE: '#e74c3c',
    SUGGESTED: '#3498db', APPROVED: '#27ae60', ORDERED: '#f39c12',
    RECEIVED: '#2ecc71', CONFIRMED: '#27ae60', DRAFT: '#95a5a6',
    CANCELLED: '#e74c3c', REFUNDED: '#9b59b6',
  };
  return (
    <span style={{
      padding: '2px 10px', borderRadius: 12, fontSize: 11, fontWeight: 600,
      background: colors[text] || color, color: '#fff', whiteSpace: 'nowrap'
    }}>{text}</span>
  );
}

export function Table({ columns, data, emptyMsg = 'No data' }) {
  if (!data?.length) return <div style={{ color: '#aaa', padding: 20, textAlign: 'center' }}>{emptyMsg}</div>;
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ background: '#f8fafc' }}>
            {columns.map(c => (
              <th key={c.key} style={{
                padding: '10px 12px', textAlign: 'left', fontWeight: 600,
                color: '#555', borderBottom: '2px solid #e0e0e0', whiteSpace: 'nowrap'
              }}>{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i} style={{ borderBottom: '1px solid #f0f0f0' }}
              onMouseEnter={e => e.currentTarget.style.background = '#f8fafc'}
              onMouseLeave={e => e.currentTarget.style.background = ''}>
              {columns.map(c => (
                <td key={c.key} style={{ padding: '10px 12px', color: '#333' }}>
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

export function Btn({ children, onClick, color = '#4fc3f7', disabled, style = {}, size = 'md' }) {
  const pad = size === 'sm' ? '5px 12px' : '8px 18px';
  return (
    <button onClick={onClick} disabled={disabled} style={{
      padding: pad, background: disabled ? '#ccc' : color,
      color: '#fff', border: 'none', borderRadius: 6,
      cursor: disabled ? 'not-allowed' : 'pointer',
      fontSize: size === 'sm' ? 12 : 13, fontWeight: 500, ...style
    }}>{children}</button>
  );
}
