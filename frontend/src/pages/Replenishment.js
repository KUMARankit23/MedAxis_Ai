import React, { useEffect, useState, useCallback } from 'react';
import { getOrders, approveOrder, markOrdered, receiveOrder } from '../services/api';
import { Card, Table, Badge, Btn } from '../components/Card';
import { useToast } from '../components/Toast';
import { ClipboardList, CheckCircle, Truck } from 'lucide-react';

export default function Replenishment() {
  const [orders, setOrders]   = useState([]);
  const [filter, setFilter]   = useState('');
  const [loading, setLoading] = useState(true);
  const toast = useToast();

  const load = useCallback(() => {
    setLoading(true);
    getOrders(filter ? { status: filter } : {})
      .then(r => setOrders(r.data.orders || []))
      .catch(err => toast.error(err.response?.data?.detail || 'Failed to load orders'))
      .finally(() => setLoading(false));
  }, [filter]); // eslint-disable-line

  useEffect(() => { load(); }, [load]);

  const action = async (fn, id, label, extra) => {
    try { await fn(id, extra); toast.success(`${label} successful`); load(); }
    catch (e) { toast.error(e.response?.data?.detail || `${label} failed`); }
  };

  const counts = {
    SUGGESTED: orders.filter(o => o.status === 'SUGGESTED').length,
    APPROVED:  orders.filter(o => o.status === 'APPROVED').length,
    ORDERED:   orders.filter(o => o.status === 'ORDERED').length,
  };

  const SUMMARY = [
    { label: 'Pending Approval', val: counts.SUGGESTED, color: 'var(--primary)',  Icon: ClipboardList },
    { label: 'Approved',         val: counts.APPROVED,  color: 'var(--success)',  Icon: CheckCircle },
    { label: 'Ordered',          val: counts.ORDERED,   color: 'var(--warning)',  Icon: Truck },
  ];

  return (
    <div className="page-enter">
      {/* Summary */}
      <div className="summary-strip">
        {SUMMARY.map(({ label, val, color, Icon }) => (
          <div key={label} className="summary-chip" style={{ position: 'relative', paddingLeft: 24, overflow: 'hidden' }}>
            <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 4, background: color, borderRadius: '12px 0 0 12px' }} />
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <div className="summary-chip-val">{val}</div>
                <div className="summary-chip-label">{label}</div>
              </div>
              <Icon size={22} style={{ color, opacity: 0.35 }} />
            </div>
          </div>
        ))}
      </div>

      {/* Filter */}
      <div className="filter-bar">
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginRight: 4 }}>Status:</span>
        {['', 'SUGGESTED', 'APPROVED', 'ORDERED', 'RECEIVED', 'CANCELLED'].map(s => (
          <button key={s} onClick={() => setFilter(s)} className={`filter-btn ${filter === s ? 'active' : ''}`}>
            {s || 'All'}
          </button>
        ))}
      </div>

      <Card title={`Replenishment Orders  ·  ${orders.length}`}>
        {loading ? (
          <div style={{ padding: '40px 0', textAlign: 'center' }}>
            <div className="spinner spinner-dark" style={{ width: 24, height: 24, margin: '0 auto 12px' }} />
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Loading orders…</div>
          </div>
        ) : (
          <Table
            columns={[
              { key: 'po_number',           label: 'PO #',            render: v => v || <span style={{ color: 'var(--text-muted)' }}>—</span> },
              { key: 'medicine_name',        label: 'Medicine' },
              { key: 'outlet_id',            label: 'Outlet' },
              { key: 'trigger_reason',       label: 'Trigger',        render: v => <Badge text={v} color="var(--violet)" /> },
              { key: 'suggested_quantity',   label: 'Suggested' },
              { key: 'approved_quantity',    label: 'Approved',       render: v => v ?? '—' },
              { key: 'current_stock',        label: 'Stock',          render: v => v ?? '—' },
              { key: 'ai_confidence',        label: 'AI Confidence',  render: v => v ? (
                <span style={{ fontWeight: 600, color: v > 0.7 ? 'var(--success)' : 'var(--warning)' }}>{(v*100).toFixed(0)}%</span>
              ) : '—' },
              { key: 'status',              label: 'Status',         render: v => <Badge text={v} /> },
              {
                key: 'id', label: 'Action', render: (id, row) => (
                  <div style={{ display: 'flex', gap: 6 }}>
                    {row.status === 'SUGGESTED' && <Btn size="sm" color="#10B981" onClick={() => action(approveOrder, id, 'Approve', {})}>Approve</Btn>}
                    {row.status === 'APPROVED'  && <Btn size="sm" color="#F59E0B" onClick={() => action(markOrdered, id, 'Mark Ordered')}>Mark Ordered</Btn>}
                    {row.status === 'ORDERED'   && <Btn size="sm" color="#0EA5E9" onClick={() => action(receiveOrder, id, 'Receive')}>Receive</Btn>}
                  </div>
                ),
              },
            ]}
            data={orders}
            emptyMsg="No replenishment orders"
          />
        )}
      </Card>
    </div>
  );
}
