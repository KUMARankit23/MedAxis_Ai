import React, { useEffect, useState, useCallback } from 'react';
import { getAuditLogs } from '../services/api';
import { Card, Table, Badge } from '../components/Card';
import { useToast } from '../components/Toast';
import { Activity, CheckCircle, XCircle, Search, X } from 'lucide-react';

export default function AuditLogs() {
  const [logs, setLogs]       = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter]   = useState({ action: '', status: '' });
  const toast = useToast();

  const load = useCallback(() => {
    setLoading(true);
    const params = {};
    if (filter.action) params.action = filter.action;
    if (filter.status) params.status = filter.status;
    getAuditLogs(params)
      .then(r => setLogs(r.data || []))
      .catch(err => toast.error(err.response?.data?.detail || 'Failed to load audit logs'))
      .finally(() => setLoading(false));
  }, [filter]); // eslint-disable-line

  useEffect(() => { load(); }, [load]);

  const successCount = logs.filter(l => l.status === 'SUCCESS').length;
  const failureCount = logs.filter(l => l.status === 'FAILURE').length;

  const SUMMARY = [
    { label: 'Total Events',    val: logs.length,   color: 'var(--primary)', Icon: Activity },
    { label: 'Successful',      val: successCount,  color: 'var(--success)', Icon: CheckCircle },
    { label: 'Failed Attempts', val: failureCount,  color: 'var(--danger)',  Icon: XCircle },
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

      <Card title="Audit Log — Immutable Compliance Trail">
        {/* Filters */}
        <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap', alignItems: 'center' }}>
          <div style={{ position: 'relative', flex: '1 1 260px', minWidth: 200 }}>
            <Search size={13} style={{ position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', pointerEvents: 'none' }} />
            <input
              placeholder="Filter by action (LOGIN, USER_CREATE…)"
              value={filter.action}
              onChange={e => setFilter(f => ({ ...f, action: e.target.value }))}
              onKeyDown={e => e.key === 'Enter' && load()}
              className="form-input"
              style={{ paddingLeft: 32 }}
            />
          </div>
          <select
            value={filter.status}
            onChange={e => setFilter(f => ({ ...f, status: e.target.value }))}
            className="form-select"
            style={{ width: 'auto', flex: '0 0 auto' }}
          >
            <option value="">All Status</option>
            <option value="SUCCESS">SUCCESS</option>
            <option value="FAILURE">FAILURE</option>
          </select>
          <button onClick={load} className="btn btn-primary btn-md" style={{ flexShrink: 0 }}>
            <Search size={13} /> Search
          </button>
          <button onClick={() => setFilter({ action: '', status: '' })} className="btn btn-ghost btn-md" style={{ flexShrink: 0 }}>
            <X size={13} /> Clear
          </button>
        </div>

        {loading ? (
          <div style={{ padding: '40px 0', textAlign: 'center' }}>
            <div className="spinner spinner-dark" style={{ width: 24, height: 24, margin: '0 auto 12px' }} />
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Loading audit logs…</div>
          </div>
        ) : (
          <Table
            columns={[
              { key: 'timestamp',  label: 'Timestamp',  render: v => <span style={{ fontSize: 11, fontFamily: 'monospace' }}>{new Date(v).toLocaleString()}</span> },
              { key: 'user_id',    label: 'User',       render: v => v ? <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{v.slice(0,8)}…</span> : <span style={{ color: 'var(--text-muted)' }}>System</span> },
              { key: 'action',     label: 'Action',     render: v => <Badge text={v} color="var(--primary)" /> },
              { key: 'resource',   label: 'Resource',   render: v => v ? <span style={{ fontSize: 12 }}>{v.slice(0,24)}</span> : '—' },
              { key: 'status',     label: 'Status',     render: v => <Badge text={v} /> },
              { key: 'ip_address', label: 'IP Address', render: v => <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{v || '—'}</span> },
              {
                key: 'id', label: 'Details', render: (_, row) => {
                  const hasData = row.before_state || row.after_state;
                  if (!hasData) return <span style={{ color: 'var(--text-muted)' }}>—</span>;
                  return (
                    <button
                      onClick={() => {
                        const detail = {
                          before: row.before_state ? JSON.parse(row.before_state) : null,
                          after:  row.after_state  ? JSON.parse(row.after_state)  : null,
                        };
                        alert(JSON.stringify(detail, null, 2));
                      }}
                      className="btn btn-ghost btn-sm"
                    >View</button>
                  );
                },
              },
            ]}
            data={logs}
            emptyMsg="No audit logs found"
          />
        )}
      </Card>
    </div>
  );
}
