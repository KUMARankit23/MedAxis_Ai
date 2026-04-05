import React, { useEffect, useState } from 'react';
import { getOrders, approveOrder, markOrdered, receiveOrder } from '../services/api';
import { Card, Table, Badge, Btn } from '../components/Card';

export default function Replenishment() {
  const [orders, setOrders] = useState([]);
  const [filter, setFilter] = useState('');
  const [msg, setMsg] = useState('');

  const load = () => getOrders(filter ? { status: filter } : {}).then(r => setOrders(r.data.orders || []));
  useEffect(() => { load(); }, [filter]);

  const flash = m => { setMsg(m); setTimeout(() => setMsg(''), 3000); };

  const action = async (fn, id, label) => {
    try { await fn(id); flash(`${label} successful`); load(); }
    catch (e) { flash(e.response?.data?.error || `${label} failed`); }
  };

  const counts = {
    SUGGESTED: orders.filter(o => o.status === 'SUGGESTED').length,
    APPROVED:  orders.filter(o => o.status === 'APPROVED').length,
    ORDERED:   orders.filter(o => o.status === 'ORDERED').length,
  };

  return (
    <div>
      {msg && <div style={{ background: '#d4edda', color: '#155724', padding: '10px 16px', borderRadius: 8, marginBottom: 16 }}>{msg}</div>}

      {/* Summary */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
        {[
          { label: 'Pending Approval', count: counts.SUGGESTED, color: '#3498db' },
          { label: 'Approved', count: counts.APPROVED, color: '#27ae60' },
          { label: 'Ordered', count: counts.ORDERED, color: '#f39c12' },
        ].map(s => (
          <div key={s.label} style={{
            background: '#fff', borderRadius: 10, padding: '16px 20px',
            borderLeft: `4px solid ${s.color}`, flex: 1,
            boxShadow: '0 2px 8px rgba(0,0,0,0.07)'
          }}>
            <div style={{ fontSize: 24, fontWeight: 700, color: '#1a2332' }}>{s.count}</div>
            <div style={{ fontSize: 12, color: '#888' }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Filter */}
      <div style={{ marginBottom: 16, display: 'flex', gap: 8 }}>
        {['', 'SUGGESTED', 'APPROVED', 'ORDERED', 'RECEIVED'].map(s => (
          <button key={s} onClick={() => setFilter(s)} style={{
            padding: '6px 14px', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 12,
            background: filter === s ? '#4fc3f7' : '#e0e0e0',
            color: filter === s ? '#fff' : '#555'
          }}>{s || 'All'}</button>
        ))}
      </div>

      <Card title={`Replenishment Orders (${orders.length})`}>
        <Table
          columns={[
            { key: 'medicine_name', label: 'Medicine' },
            { key: 'store_id', label: 'Store' },
            { key: 'trigger_reason', label: 'Trigger', render: v => <Badge text={v} color="#9b59b6" /> },
            { key: 'suggested_quantity', label: 'Suggested Qty' },
            { key: 'current_stock', label: 'Current Stock' },
            { key: 'ai_confidence', label: 'AI Confidence', render: v => v ? `${(v * 100).toFixed(0)}%` : '—' },
            { key: 'status', label: 'Status', render: v => <Badge text={v} /> },
            { key: 'created_by', label: 'Created By' },
            {
              key: 'id', label: 'Actions', render: (id, row) => (
                <div style={{ display: 'flex', gap: 6 }}>
                  {row.status === 'SUGGESTED' && (
                    <Btn size="sm" color="#27ae60" onClick={() => action(approveOrder, id, 'Approve')}>Approve</Btn>
                  )}
                  {row.status === 'APPROVED' && (
                    <Btn size="sm" color="#f39c12" onClick={() => action(markOrdered, id, 'Mark Ordered')}>Mark Ordered</Btn>
                  )}
                  {row.status === 'ORDERED' && (
                    <Btn size="sm" color="#3498db" onClick={() => action(receiveOrder, id, 'Receive')}>Receive</Btn>
                  )}
                </div>
              )
            },
          ]}
          data={orders}
          emptyMsg="No replenishment orders"
        />
      </Card>
    </div>
  );
}
