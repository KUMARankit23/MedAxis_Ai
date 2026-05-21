import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, CartesianGrid } from 'recharts';
import { getDashboard, getSalesSummary, getTopMedicines } from '../services/api';
import { StatCard, Card, SkeletonStatCards, SkeletonCard } from '../components/Card';
import { useToast } from '../components/Toast';
import { getErrorMessage } from '../utils/errors';
import { DollarSign, Calendar, AlertTriangle, Package, Plus, ArrowRight, Brain, BarChart2, RefreshCw } from 'lucide-react';

const today   = () => new Date().toISOString().split('T')[0];
const daysAgo = n => { const d = new Date(); d.setDate(d.getDate() - n); return d.toISOString().split('T')[0]; };

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: '#fff', border: '1px solid var(--border)', borderRadius: 8, padding: '10px 14px', boxShadow: 'var(--shadow-lg)' }}>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>₹{Number(payload[0].value).toFixed(2)}</div>
    </div>
  );
};

export default function Dashboard() {
  const [kpis, setKpis]       = useState(null);
  const [sales, setSales]     = useState([]);
  const [topMeds, setTopMeds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');
  const toast = useToast();

  useEffect(() => {
    setLoading(true);
    Promise.all([
      getDashboard(),
      getSalesSummary({ start_date: daysAgo(7), end_date: today() }),
      getTopMedicines({ limit: 5 }),
    ])
      .then(([d, s, t]) => {
        setKpis(d.data);
        setSales(s.data.records || []);
        setTopMeds(t.data.top_medicines || []);
      })
      .catch(err => { const msg = getErrorMessage(err, 'Failed to load dashboard'); setError(msg); toast.error(msg); })
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line

  if (error) return (
    <div style={{ background: 'var(--danger-50)', color: '#991B1B', border: '1px solid var(--danger-100)', padding: '16px 20px', borderRadius: 'var(--r-lg)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <span>{error}</span>
      <button onClick={() => window.location.reload()} style={{ background: 'none', border: 'none', color: '#991B1B', cursor: 'pointer', textDecoration: 'underline', fontSize: 13 }}>Retry</button>
    </div>
  );

  return (
    <div className="page-enter">
      {/* KPI Cards */}
      {loading ? <SkeletonStatCards /> : (
        <div style={{ display: 'flex', gap: 16, marginBottom: 24, flexWrap: 'wrap' }}>
          <StatCard
            label="Today's Revenue" icon={DollarSign}
            value={`₹${(kpis?.today?.revenue || 0).toFixed(2)}`}
            color="var(--success)" sub={`${kpis?.today?.invoices || 0} invoices today`}
          />
          <StatCard
            label="Month Revenue" icon={Calendar}
            value={`₹${(kpis?.this_month?.revenue || 0).toFixed(2)}`}
            color="var(--primary)" sub={`${kpis?.this_month?.invoices || 0} invoices this month`}
          />
          <StatCard
            label="Low Stock Items" icon={AlertTriangle}
            value={kpis?.alerts?.low_stock_items || 0}
            color="var(--danger)" sub="Items below reorder level"
          />
          <StatCard
            label="Expiring Soon" icon={Package}
            value={kpis?.alerts?.expiring_soon_batches || 0}
            color="var(--warning)" sub="Batches within 30 days"
          />
        </div>
      )}

      {/* Charts row */}
      {loading ? (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>
          <SkeletonCard /><SkeletonCard />
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 20, marginBottom: 20 }}>
          <Card title="Sales Trend — Last 7 Days">
            {sales.length ? (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={[...sales].reverse()} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--slate-100)" />
                  <XAxis dataKey="sale_date" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
                  <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Line type="monotone" dataKey="revenue" stroke="var(--primary)" strokeWidth={2.5} dot={{ r: 3, fill: 'var(--primary)', strokeWidth: 0 }} activeDot={{ r: 5 }} />
                </LineChart>
              </ResponsiveContainer>
            ) : <EmptyChart />}
          </Card>

          <Card title="Top 5 Medicines — This Month">
            {topMeds.length ? (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={topMeds} layout="vertical" margin={{ top: 4, right: 12, left: 4, bottom: 0 }}>
                  <XAxis type="number" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} />
                  <YAxis dataKey="medicine_name" type="category" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} width={110} axisLine={false} tickLine={false} />
                  <Tooltip cursor={{ fill: 'var(--primary-50)' }} />
                  <Bar dataKey="total_quantity" fill="var(--primary)" radius={[0, 5, 5, 0]} barSize={14} />
                </BarChart>
              </ResponsiveContainer>
            ) : <EmptyChart />}
          </Card>
        </div>
      )}

      {/* Quick actions */}
      <Card title="Quick Actions">
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {[
            { label: 'New Invoice',       href: '/billing',       Icon: Plus,      color: 'var(--success)',  bg: 'var(--success-50)',  border: 'var(--success-100)' },
            { label: 'Receive Stock',     href: '/inventory',     Icon: Package,   color: 'var(--primary)',  bg: 'var(--primary-50)',  border: 'var(--primary-100)' },
            { label: 'Expiry Alerts',     href: '/inventory',     Icon: AlertTriangle, color: 'var(--warning)', bg: 'var(--warning-50)', border: 'var(--warning-100)' },
            { label: 'AI Forecast',       href: '/ai',            Icon: Brain,     color: 'var(--violet)',   bg: 'var(--violet-50)',   border: 'var(--violet-100)' },
            { label: 'View Reports',      href: '/reports',       Icon: BarChart2, color: 'var(--indigo)',   bg: 'var(--indigo-50)',   border: '#C7D2FE' },
            { label: 'Replenishment',     href: '/replenishment', Icon: RefreshCw, color: 'var(--danger)',   bg: 'var(--danger-50)',   border: 'var(--danger-100)' },
          ].map(({ label, href, Icon, color, bg, border }) => (
            <Link key={label} to={href} className="quick-action" style={{ background: bg, color, border: `1.5px solid ${border}` }}>
              <Icon size={15} />
              <span>{label}</span>
              <ArrowRight size={13} style={{ opacity: 0.6 }} />
            </Link>
          ))}
        </div>
      </Card>
    </div>
  );
}

const EmptyChart = () => (
  <div className="empty-state" style={{ padding: '40px 24px' }}>
    <div className="empty-state-icon">📊</div>
    No data yet
  </div>
);
