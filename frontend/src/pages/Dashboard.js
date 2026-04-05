import React, { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';
import { getDashboard, getSalesSummary, getTopMedicines } from '../services/api';
import { StatCard, Card } from '../components/Card';

export default function Dashboard() {
  const [kpis, setKpis] = useState(null);
  const [sales, setSales] = useState([]);
  const [topMeds, setTopMeds] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getDashboard(),
      getSalesSummary({ start_date: daysAgo(7), end_date: today() }),
      getTopMedicines({ limit: 5 }),
    ]).then(([d, s, t]) => {
      setKpis(d.data);
      setSales(s.data.records || []);
      setTopMeds(t.data.top_medicines || []);
    }).catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spinner />;

  return (
    <div>
      {/* KPI Cards */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 24, flexWrap: 'wrap' }}>
        <StatCard label="Today's Revenue" value={`₹${kpis?.today?.revenue?.toFixed(2) || 0}`}
          icon="💰" color="#27ae60" sub={`${kpis?.today?.invoices || 0} invoices`} />
        <StatCard label="Month Revenue" value={`₹${kpis?.this_month?.revenue?.toFixed(2) || 0}`}
          icon="📅" color="#3498db" sub={`${kpis?.this_month?.invoices || 0} invoices`} />
        <StatCard label="Low Stock Items" value={kpis?.alerts?.low_stock_items || 0}
          icon="⚠️" color="#e74c3c" sub="Need reorder" />
        <StatCard label="Expiring Soon" value={kpis?.alerts?.expiring_soon_batches || 0}
          icon="📦" color="#f39c12" sub="Within 30 days" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        {/* Sales trend */}
        <Card title="Sales Trend (Last 7 Days)">
          {sales.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={sales.slice().reverse()}>
                <XAxis dataKey="sale_date" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={v => `₹${Number(v).toFixed(2)}`} />
                <Line type="monotone" dataKey="revenue" stroke="#4fc3f7" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </Card>

        {/* Top medicines */}
        <Card title="Top 5 Medicines (This Month)">
          {topMeds.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={topMeds} layout="vertical">
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis dataKey="medicine_name" type="category" tick={{ fontSize: 11 }} width={120} />
                <Tooltip />
                <Bar dataKey="total_quantity" fill="#4fc3f7" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </Card>
      </div>

      {/* Quick actions */}
      <Card title="Quick Actions" style={{ marginTop: 0 }}>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          {[
            { label: '+ New Invoice', href: '/billing', color: '#27ae60' },
            { label: '+ Receive Stock', href: '/inventory', color: '#3498db' },
            { label: 'View Expiry Alerts', href: '/inventory?tab=expiry', color: '#f39c12' },
            { label: 'AI Forecast', href: '/ai', color: '#9b59b6' },
          ].map(a => (
            <a key={a.label} href={a.href} style={{
              padding: '10px 20px', background: a.color, color: '#fff',
              borderRadius: 8, textDecoration: 'none', fontSize: 13, fontWeight: 500
            }}>{a.label}</a>
          ))}
        </div>
      </Card>
    </div>
  );
}

const today = () => new Date().toISOString().split('T')[0];
const daysAgo = n => { const d = new Date(); d.setDate(d.getDate() - n); return d.toISOString().split('T')[0]; };
const Spinner = () => <div style={{ textAlign: 'center', padding: 60, color: '#aaa' }}>Loading...</div>;
const Empty = () => <div style={{ textAlign: 'center', padding: 40, color: '#ccc', fontSize: 13 }}>No data yet</div>;
