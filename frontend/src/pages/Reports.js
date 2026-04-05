import React, { useEffect, useState } from 'react';
import { getSalesSummary, getTopMedicines, getStorePerformance, getExpiryReport } from '../services/api';
import { Card, Table } from '../components/Card';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';

const COLORS = ['#4fc3f7', '#27ae60', '#f39c12', '#e74c3c', '#9b59b6'];
const today = () => new Date().toISOString().split('T')[0];
const daysAgo = n => { const d = new Date(); d.setDate(d.getDate() - n); return d.toISOString().split('T')[0]; };

export default function Reports() {
  const [tab, setTab] = useState(0);
  const [sales, setSales] = useState([]);
  const [topMeds, setTopMeds] = useState([]);
  const [storePerf, setStorePerf] = useState([]);
  const [expiry, setExpiry] = useState([]);
  const [start, setStart] = useState(daysAgo(30));
  const [end, setEnd] = useState(today());

  useEffect(() => {
    getSalesSummary({ start_date: start, end_date: end }).then(r => setSales(r.data.records || []));
    getTopMedicines({ start_date: start, end_date: end, limit: 10 }).then(r => setTopMeds(r.data.top_medicines || []));
    getStorePerformance({ start_date: start, end_date: end }).then(r => setStorePerf(r.data.store_performance || []));
    getExpiryReport({ days: 90 }).then(r => setExpiry(r.data.expiring_batches || []));
  }, [start, end]);

  const TABS = ['Sales Summary', 'Top Medicines', 'Store Performance', 'Expiry Report'];

  return (
    <div>
      {/* Date range filter */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, alignItems: 'center', background: '#fff', padding: '12px 16px', borderRadius: 10, boxShadow: '0 2px 8px rgba(0,0,0,0.07)' }}>
        <span style={{ fontSize: 13, color: '#555', fontWeight: 600 }}>Date Range:</span>
        <input type="date" value={start} onChange={e => setStart(e.target.value)}
          style={{ padding: '6px 10px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13 }} />
        <span style={{ color: '#888' }}>to</span>
        <input type="date" value={end} onChange={e => setEnd(e.target.value)}
          style={{ padding: '6px 10px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13 }} />
        {[7, 30, 90].map(d => (
          <button key={d} onClick={() => { setStart(daysAgo(d)); setEnd(today()); }} style={{
            padding: '6px 12px', background: '#f0f4f8', border: '1px solid #ddd',
            borderRadius: 6, cursor: 'pointer', fontSize: 12
          }}>Last {d}d</button>
        ))}
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20 }}>
        {TABS.map((t, i) => (
          <button key={t} onClick={() => setTab(i)} style={{
            padding: '8px 18px', border: 'none', borderRadius: 6, cursor: 'pointer',
            background: tab === i ? '#4fc3f7' : '#e0e0e0',
            color: tab === i ? '#fff' : '#555', fontWeight: tab === i ? 600 : 400, fontSize: 13
          }}>{t}</button>
        ))}
      </div>

      {/* Sales Summary */}
      {tab === 0 && (
        <Card title="Daily Sales Summary">
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={sales.slice().reverse()}>
              <XAxis dataKey="sale_date" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={v => `₹${Number(v).toFixed(2)}`} />
              <Bar dataKey="revenue" fill="#4fc3f7" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <Table
            columns={[
              { key: 'store_id', label: 'Store' },
              { key: 'sale_date', label: 'Date' },
              { key: 'invoice_count', label: 'Invoices' },
              { key: 'revenue', label: 'Revenue', render: v => `₹${Number(v).toFixed(2)}` },
              { key: 'avg_invoice_value', label: 'Avg Value', render: v => `₹${Number(v).toFixed(2)}` },
            ]}
            data={sales}
          />
        </Card>
      )}

      {/* Top Medicines */}
      {tab === 1 && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
          <Card title="Top Medicines by Quantity">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={topMeds} layout="vertical">
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis dataKey="medicine_name" type="category" tick={{ fontSize: 11 }} width={130} />
                <Tooltip />
                <Bar dataKey="total_quantity" fill="#27ae60" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
          <Card title="Revenue Share">
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie data={topMeds} dataKey="total_revenue" nameKey="medicine_name" cx="50%" cy="50%" outerRadius={100}>
                  {topMeds.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip formatter={v => `₹${Number(v).toFixed(2)}`} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </Card>
        </div>
      )}

      {/* Store Performance */}
      {tab === 2 && (
        <Card title="Store Performance Comparison">
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={storePerf}>
              <XAxis dataKey="store_id" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={v => `₹${Number(v).toFixed(2)}`} />
              <Bar dataKey="total_revenue" fill="#f39c12" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <Table
            columns={[
              { key: 'store_id', label: 'Store' },
              { key: 'total_invoices', label: 'Total Invoices' },
              { key: 'total_revenue', label: 'Revenue', render: v => `₹${Number(v).toFixed(2)}` },
              { key: 'avg_sale', label: 'Avg Sale', render: v => `₹${Number(v).toFixed(2)}` },
              { key: 'confirmed_count', label: 'Confirmed' },
              { key: 'cancelled_count', label: 'Cancelled' },
            ]}
            data={storePerf}
          />
        </Card>
      )}

      {/* Expiry Report */}
      {tab === 3 && (
        <Card title="Expiry Report (Next 90 Days)">
          <Table
            columns={[
              { key: 'medicine_name', label: 'Medicine' },
              { key: 'batch_number', label: 'Batch' },
              { key: 'store_id', label: 'Store' },
              { key: 'quantity', label: 'Qty' },
              { key: 'expiry_date', label: 'Expiry Date' },
              { key: 'days_to_expiry', label: 'Days Left', render: v => (
                <span style={{ color: v <= 7 ? '#e74c3c' : v <= 15 ? '#f39c12' : '#27ae60', fontWeight: 600 }}>{v}</span>
              )},
            ]}
            data={expiry}
            emptyMsg="No batches expiring within 90 days"
          />
        </Card>
      )}
    </div>
  );
}
