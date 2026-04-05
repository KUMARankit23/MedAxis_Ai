import React, { useEffect, useState } from 'react';
import { getAuditLogs } from '../services/api';
import { Card, Table, Badge } from '../components/Card';

export default function AuditLogs() {
  const [logs, setLogs] = useState([]);
  const [filter, setFilter] = useState({ action: '', status: '' });

  const load = () => getAuditLogs(filter).then(r => setLogs(r.data.logs || []));
  useEffect(() => { load(); }, []);

  return (
    <div>
      <Card title="Audit Log — Immutable Compliance Trail">
        <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
          <input placeholder="Filter by action (LOGIN, STOCK_DEDUCT...)"
            value={filter.action} onChange={e => setFilter({ ...filter, action: e.target.value })}
            style={{ padding: '8px 12px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13, width: 280 }} />
          <select value={filter.status} onChange={e => setFilter({ ...filter, status: e.target.value })}
            style={{ padding: '8px 12px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13 }}>
            <option value="">All Status</option>
            <option value="SUCCESS">SUCCESS</option>
            <option value="FAILURE">FAILURE</option>
          </select>
          <button onClick={load} style={{
            padding: '8px 16px', background: '#4fc3f7', color: '#fff',
            border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 13
          }}>Search</button>
        </div>

        <Table
          columns={[
            { key: 'timestamp', label: 'Timestamp', render: v => new Date(v).toLocaleString() },
            { key: 'user_id', label: 'User ID', render: v => v?.slice(0, 8) + '...' },
            { key: 'action', label: 'Action', render: v => <Badge text={v} color="#3498db" /> },
            { key: 'resource', label: 'Resource', render: v => v?.slice(0, 20) },
            { key: 'status', label: 'Status', render: v => <Badge text={v} /> },
            { key: 'ip_address', label: 'IP' },
            {
              key: 'details', label: 'Before/After', render: v => {
                if (!v || (!v.before_state && !v.after_state)) return '—';
                return (
                  <button onClick={() => alert(JSON.stringify(v, null, 2))} style={{
                    padding: '2px 8px', background: '#f0f4f8', border: '1px solid #ddd',
                    borderRadius: 4, cursor: 'pointer', fontSize: 11
                  }}>View</button>
                );
              }
            },
          ]}
          data={logs}
          emptyMsg="No audit logs found"
        />
      </Card>
    </div>
  );
}
