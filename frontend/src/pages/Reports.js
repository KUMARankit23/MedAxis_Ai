import React, { useEffect, useState, useCallback } from 'react';
import { getSalesSummary, getTopMedicines, getStorePerformance, getExpiryReport } from '../services/api';
import { Card, Table } from '../components/Card';
import { useToast } from '../components/Toast';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend, CartesianGrid } from 'recharts';

const COLORS = ['#0EA5E9','#10B981','#F59E0B','#EF4444','#8B5CF6','#06B6D4','#F97316'];
const today   = () => new Date().toISOString().split('T')[0];
const daysAgo = n => { const d = new Date(); d.setDate(d.getDate()-n); return d.toISOString().split('T')[0]; };
const TABS    = ['Sales Summary', 'Top Medicines', 'Store Performance', 'Expiry Report'];

export default function Reports() {
  const [tab, setTab]           = useState(0);
  const [sales, setSales]       = useState([]);
  const [topMeds, setTopMeds]   = useState([]);
  const [storePerf, setStorePerf] = useState([]);
  const [expiry, setExpiry]     = useState([]);
  const [start, setStart]       = useState(daysAgo(30));
  const [end, setEnd]           = useState(today());
  const [loading, setLoading]   = useState(true);
  const toast = useToast();

  const loadAll = useCallback(() => {
    setLoading(true);
    Promise.all([
      getSalesSummary({ start_date: start, end_date: end }),
      getTopMedicines({ start_date: start, end_date: end, limit: 10 }),
      getStorePerformance({ start_date: start, end_date: end }),
      getExpiryReport({ days: 90 }),
    ])
      .then(([s,t,p,e]) => {
        setSales(s.data.records||[]);
        setTopMeds(t.data.top_medicines||[]);
        setStorePerf(p.data.store_performance||[]);
        setExpiry(e.data.expiring_batches||[]);
      })
      .catch(err => toast.error(err.response?.data?.detail || 'Failed to load reports'))
      .finally(() => setLoading(false));
  }, [start, end]); // eslint-disable-line

  useEffect(() => { loadAll(); }, [loadAll]);

  const totalRevenue = sales.reduce((s,r) => s + (r.revenue||0), 0);

  const BarTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
      <div style={{ background: '#fff', border: '1px solid var(--border)', borderRadius: 8, padding: '10px 14px', boxShadow: 'var(--shadow-lg)' }}>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>{label}</div>
        <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>₹{Number(payload[0].value).toFixed(2)}</div>
      </div>
    );
  };

  return (
    <div className="page-enter">
      {/* Date range */}
      <div className="filter-bar">
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)' }}>Date Range</span>
        <input type="date" value={start} onChange={e => setStart(e.target.value)}
          className="form-input" style={{ width: 'auto', padding: '6px 10px' }} />
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>to</span>
        <input type="date" value={end} onChange={e => setEnd(e.target.value)}
          className="form-input" style={{ width: 'auto', padding: '6px 10px' }} />
        {[7,30,90].map(d => (
          <button key={d} onClick={() => { setStart(daysAgo(d)); setEnd(today()); }} className="filter-btn">
            Last {d}d
          </button>
        ))}
        {!loading && (
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600 }}>TOTAL REVENUE</span>
            <span style={{ fontSize: 15, fontWeight: 800, color: 'var(--success)' }}>₹{totalRevenue.toFixed(2)}</span>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="tab-bar">
        {TABS.map((t,i) => (
          <button key={t} onClick={() => setTab(i)} className={`tab-btn ${tab===i?'active':''}`}>{t}</button>
        ))}
      </div>

      {loading && (
        <div style={{ padding: '60px 0', textAlign: 'center' }}>
          <div className="spinner spinner-dark" style={{ width: 28, height: 28, margin: '0 auto 14px' }} />
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Loading reports…</div>
        </div>
      )}

      {!loading && tab === 0 && (
        <Card title={`Daily Sales Summary  ·  ${sales.length} records`}>
          {sales.length ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={[...sales].reverse()} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--slate-100)" />
                <XAxis dataKey="sale_date" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
                <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
                <Tooltip content={<BarTooltip />} />
                <Bar dataKey="revenue" fill="var(--primary)" radius={[5,5,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty />}
          <div style={{ marginTop: 20 }}>
            <Table
              columns={[
                { key: 'outlet_id',         label: 'Store' },
                { key: 'sale_date',         label: 'Date' },
                { key: 'invoice_count',     label: 'Invoices' },
                { key: 'revenue',           label: 'Revenue',   render: v => `₹${Number(v).toFixed(2)}` },
                { key: 'avg_invoice_value', label: 'Avg Value', render: v => `₹${Number(v).toFixed(2)}` },
              ]}
              data={sales}
              emptyMsg="No sales data for this period"
            />
          </div>
        </Card>
      )}

      {!loading && tab === 1 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 20 }}>
          <Card title="Top Medicines by Quantity">
            {topMeds.length ? (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={topMeds} layout="vertical" margin={{ top: 4, right: 12, left: 4, bottom: 0 }}>
                  <XAxis type="number" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} />
                  <YAxis dataKey="medicine_name" type="category" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} width={130} axisLine={false} tickLine={false} />
                  <Tooltip />
                  <Bar dataKey="total_quantity" fill="var(--success)" radius={[0,5,5,0]} barSize={14} />
                </BarChart>
              </ResponsiveContainer>
            ) : <Empty />}
          </Card>
          <Card title="Revenue Share">
            {topMeds.length ? (
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie data={topMeds} dataKey="total_revenue" nameKey="medicine_name" cx="50%" cy="45%" outerRadius={95} innerRadius={45}>
                    {topMeds.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip formatter={v => `₹${Number(v).toFixed(2)}`} />
                  <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer>
            ) : <Empty />}
          </Card>
          <Card title="Top Medicines — Detail" style={{ gridColumn: '1 / -1' }}>
            <Table
              columns={[
                { key: 'medicine_name',  label: 'Medicine' },
                { key: 'total_quantity', label: 'Units Sold' },
                { key: 'total_revenue',  label: 'Revenue', render: v => `₹${Number(v).toFixed(2)}` },
              ]}
              data={topMeds}
              emptyMsg="No sales data for this period"
            />
          </Card>
        </div>
      )}

      {!loading && tab === 2 && (
        <Card title="Store Performance Comparison">
          {storePerf.length ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={storePerf} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--slate-100)" />
                <XAxis dataKey="store_id" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
                <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
                <Tooltip content={<BarTooltip />} />
                <Bar dataKey="total_revenue" fill="var(--warning)" radius={[5,5,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty />}
          <div style={{ marginTop: 20 }}>
            <Table
              columns={[
                { key: 'store_id',        label: 'Store' },
                { key: 'total_invoices',  label: 'Invoices' },
                { key: 'total_revenue',   label: 'Revenue',   render: v => `₹${Number(v).toFixed(2)}` },
                { key: 'avg_sale',        label: 'Avg Sale',  render: v => `₹${Number(v).toFixed(2)}` },
                { key: 'confirmed_count', label: 'Confirmed' },
                { key: 'cancelled_count', label: 'Cancelled' },
              ]}
              data={storePerf}
              emptyMsg="No store data for this period"
            />
          </div>
        </Card>
      )}

      {!loading && tab === 3 && (
        <Card title={`Expiry Report — Next 90 Days  ·  ${expiry.length} batches`}>
          <Table
            columns={[
              { key: 'medicine_name',  label: 'Medicine' },
              { key: 'batch_number',   label: 'Batch' },
              { key: 'store_id',       label: 'Store' },
              { key: 'quantity',       label: 'Qty' },
              { key: 'expiry_date',    label: 'Expiry Date' },
              { key: 'days_to_expiry', label: 'Days Left', render: v => (
                <span style={{ fontWeight: 700, color: v <= 7 ? 'var(--danger)' : v <= 15 ? 'var(--warning)' : 'var(--success)' }}>{v}d</span>
              )},
            ]}
            data={expiry}
            emptyMsg="No batches expiring within 90 days ✓"
          />
        </Card>
      )}
    </div>
  );
}

const Empty = () => (
  <div className="empty-state" style={{ padding: '40px 24px' }}>
    <div className="empty-state-icon">📊</div>
    No data for this period
  </div>
);
