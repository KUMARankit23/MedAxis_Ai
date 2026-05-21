import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { getMedicines, runForecast, detectAnomalies, nlQuery, getAnomalies, resolveAnomaly } from '../services/api';
import { Card, Table, Badge, Btn } from '../components/Card';
import { useToast } from '../components/Toast';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, CartesianGrid } from 'recharts';
import { Sparkles, Send } from 'lucide-react';

const TABS = ['Demand Forecast', 'Anomaly Detection', 'AI Query', 'Anomaly Log'];

export default function AIInsights() {
  const [tab, setTab]         = useState(0);
  const [medicines, setMeds]  = useState([]);
  const [loading, setLoading] = useState(true);
  const toast = useToast();

  useEffect(() => {
    getMedicines()
      .then(r => setMeds(r.data.medicines || []))
      .catch(() => toast.error('Failed to load medicines'))
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line

  return (
    <div className="page-enter">
      <div className="tab-bar">
        {TABS.map((t, i) => (
          <button key={t} onClick={() => setTab(i)} className={`tab-btn ${tab === i ? 'active' : ''}`}>
            {i === 2 && <Sparkles size={12} style={{ color: 'var(--violet)' }} />}
            {t}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ padding: '40px 0', textAlign: 'center' }}>
          <div className="spinner spinner-dark" style={{ width: 24, height: 24, margin: '0 auto 12px' }} />
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Loading medicines…</div>
        </div>
      ) : (
        <>
          {tab === 0 && <ForecastTab medicines={medicines} />}
          {tab === 1 && <AnomalyTab medicines={medicines} />}
          {tab === 2 && <QueryTab />}
          {tab === 3 && <AnomalyLog />}
        </>
      )}
    </div>
  );
}

function ForecastTab({ medicines }) {
  const [medId, setMedId]        = useState('');
  const [outletId, setOutletId]  = useState('OUTLET-001');
  const [currentStock, setStock] = useState(50);
  const [result, setResult]      = useState(null);
  const [loading, setLoading]    = useState(false);
  const toast = useToast();

  const sampleHistory = useMemo(() => Array.from({ length: 14 }, (_, i) => ({
    date: daysAgo(14 - i), quantity: Math.floor(15 + Math.random() * 20),
  })), []);

  const run = async () => {
    if (!medId) return; setLoading(true);
    try {
      const med = medicines.find(m => m.id === medId);
      const { data } = await runForecast({ medicine_id: medId, medicine_name: med?.name, outlet_id: outletId, current_stock: parseInt(currentStock), sales_history: sampleHistory });
      setResult(data);
      if (data.triggered_replenishment) toast.warn('Replenishment triggered — stock may run out before forecast ends');
    } catch (e) { toast.error(e.response?.data?.detail || 'Forecast failed'); }
    finally { setLoading(false); }
  };

  return (
    <Card title="Demand Forecasting Agent">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr)) 120px', gap: 12, marginBottom: 20, alignItems: 'end' }}>
        <div className="form-group">
          <label className="form-label">Medicine</label>
          <select value={medId} onChange={e => setMedId(e.target.value)} className="form-select">
            <option value="">Select medicine…</option>
            {medicines.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Outlet ID</label>
          <input value={outletId} onChange={e => setOutletId(e.target.value)} className="form-input" />
        </div>
        <div className="form-group">
          <label className="form-label">Current Stock</label>
          <input type="number" value={currentStock} onChange={e => setStock(e.target.value)} className="form-input" />
        </div>
        <Btn onClick={run} disabled={loading || !medId} color="#8B5CF6">
          {loading ? <><div className="spinner" style={{ width: 14, height: 14, marginRight: 4 }} /> Running…</> : 'Run Forecast'}
        </Btn>
      </div>

      {result && (
        <div style={{ animation: 'fadeInUp 0.3s both' }}>
          <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
            <InfoBox label="Model"              value={result.model_used}                                  bg="var(--violet-50)"  color="var(--violet)" />
            <InfoBox label="Confidence (R²)"    value={`${(result.confidence_score * 100).toFixed(1)}%`}  bg="var(--success-50)" color="var(--success)" />
            <InfoBox label="7-Day Total Demand" value={`${result.total_predicted} units`}                 bg="var(--warning-50)" color="var(--warning)" />
            {result.triggered_replenishment && (
              <InfoBox label="Replenishment Alert" value={result.replenishment_note || 'Triggered'} bg="var(--danger-50)" color="var(--danger)" />
            )}
          </div>
          <div style={{ background: 'var(--slate-50)', border: '1px solid var(--border)', padding: '12px 16px', borderRadius: 'var(--r-md)', fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16, lineHeight: 1.6 }}>
            <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>AI Explanation: </span>
            {result.explanation}
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={result.forecasts} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--slate-100)" />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
              <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
              <Tooltip />
              <ReferenceLine y={currentStock} stroke="var(--danger)" strokeDasharray="4 4" label={{ value: 'Current Stock', fontSize: 10, fill: 'var(--danger)' }} />
              <Line type="monotone" dataKey="predicted_demand" stroke="var(--violet)" strokeWidth={2.5} dot={{ r: 3, fill: 'var(--violet)', strokeWidth: 0 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}

function AnomalyTab({ medicines }) {
  const [medId, setMedId]       = useState('');
  const [outletId, setOutletId] = useState('OUTLET-001');
  const [result, setResult]     = useState(null);
  const [loading, setLoading]   = useState(false);
  const toast = useToast();

  const sampleHistory = useMemo(() => Array.from({ length: 10 }, (_, i) => ({
    date: daysAgo(10 - i), quantity: i === 3 ? 200 : Math.floor(15 + Math.random() * 15),
  })), []);

  const run = async () => {
    if (!medId) return; setLoading(true);
    try {
      const med = medicines.find(m => m.id === medId);
      const { data } = await detectAnomalies({ medicine_id: medId, medicine_name: med?.name, outlet_id: outletId, sales_history: sampleHistory });
      setResult(data);
      if (data.anomalies_detected > 0) toast.warn(`${data.anomalies_detected} anomaly detected — admin notified`);
    } catch (e) { toast.error(e.response?.data?.detail || 'Detection failed'); }
    finally { setLoading(false); }
  };

  return (
    <Card title="Anomaly Detection Agent">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr)) 160px', gap: 12, marginBottom: 20, alignItems: 'end' }}>
        <div className="form-group">
          <label className="form-label">Medicine</label>
          <select value={medId} onChange={e => setMedId(e.target.value)} className="form-select">
            <option value="">Select medicine…</option>
            {medicines.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Outlet ID</label>
          <input value={outletId} onChange={e => setOutletId(e.target.value)} className="form-input" />
        </div>
        <Btn onClick={run} disabled={loading || !medId} color="#EF4444">
          {loading ? <><div className="spinner" style={{ width: 14, height: 14, marginRight: 4 }} /> Scanning…</> : 'Detect Anomalies'}
        </Btn>
      </div>

      {result && (
        <div style={{ animation: 'fadeInUp 0.3s both' }}>
          <div style={{
            padding: '13px 16px', borderRadius: 'var(--r-md)', marginBottom: 16,
            background: result.anomalies_detected > 0 ? 'var(--danger-50)'  : 'var(--success-50)',
            border: `1px solid ${result.anomalies_detected > 0 ? 'var(--danger-100)' : 'var(--success-100)'}`,
            color: result.anomalies_detected > 0 ? '#991B1B' : '#065F46',
            fontSize: 13, fontWeight: 600,
          }}>
            {result.anomalies_detected > 0
              ? `${result.anomalies_detected} anomaly detected — alert sent to admin`
              : 'No anomalies detected in this data'}
          </div>
          {result.anomalies?.map((a, i) => (
            <div key={i} style={{ background: 'var(--warning-50)', border: '1px solid var(--warning-100)', padding: '14px 16px', borderRadius: 'var(--r-md)', marginBottom: 10 }}>
              <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                <Badge text={a.anomaly_type} color="var(--danger)" />
                <Badge text={a.severity} />
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{a.date}</span>
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 6 }}>{a.description}</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                Detected: <strong style={{ color: 'var(--text-primary)' }}>{a.detected_value}</strong> &nbsp;|&nbsp;
                Expected: {a.expected_range} &nbsp;|&nbsp; Model: {a.model_used}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function QueryTab() {
  const [query, setQuery]     = useState('');
  const [result, setResult]   = useState(null);
  const [loading, setLoading] = useState(false);
  const toast = useToast();

  const EXAMPLES = [
    'What are the top selling medicines?',
    'Show me low stock items',
    'Which batches are expiring soon?',
    "What are today's sales?",
    'Show recent anomalies',
  ];

  const run = useCallback(async q => {
    const question = q || query;
    if (!question.trim()) return;
    setLoading(true);
    try {
      const { data } = await nlQuery(question);
      setResult(data);
    } catch (e) {
      const detail = e.response?.data?.detail;
      const msg = typeof detail === 'object' ? detail.error : (detail || 'Query failed');
      setResult({ error: msg });
      if (e.response?.status === 429) toast.warn('Rate limit reached — max 10 queries/minute');
    } finally { setLoading(false); }
  }, [query]); // eslint-disable-line

  return (
    <Card title="Natural Language Query — Ask in plain English">
      {/* Input */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && run()}
            placeholder="Ask anything about your pharmacy data…"
            className="form-input"
            style={{ flex: 1, fontSize: 14, padding: '11px 14px' }}
          />
          <Btn onClick={() => run()} disabled={loading} color="#8B5CF6">
            {loading ? <div className="spinner" style={{ width: 14, height: 14 }} /> : <Send size={14} />}
          </Btn>
        </div>
        <div style={{ display: 'flex', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
          {EXAMPLES.map(e => (
            <button key={e} onClick={() => { setQuery(e); run(e); }} style={{
              padding: '5px 12px', background: 'var(--slate-50)', border: '1px solid var(--border)',
              borderRadius: 'var(--r-full)', fontSize: 11, cursor: 'pointer', color: 'var(--text-secondary)',
              fontFamily: 'inherit', fontWeight: 500, transition: 'all var(--t-fast)',
            }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--violet)'; e.currentTarget.style.color = 'var(--violet)'; e.currentTarget.style.background = 'var(--violet-50)'; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-secondary)'; e.currentTarget.style.background = 'var(--slate-50)'; }}
            >{e}</button>
          ))}
        </div>
      </div>

      {result && (
        <div style={{ animation: 'fadeInUp 0.3s both' }}>
          {result.error ? (
            <div style={{ background: 'var(--danger-50)', border: '1px solid var(--danger-100)', color: '#991B1B', padding: '12px 16px', borderRadius: 'var(--r-md)', fontSize: 13 }}>
              {result.error}
            </div>
          ) : (
            <div style={{ background: 'var(--slate-50)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)', padding: 18 }}>
              <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap', alignItems: 'center' }}>
                <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600 }}>METHOD</span>
                <Badge text={result.method || 'pattern'} color="var(--violet)" />
                <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, marginLeft: 8 }}>DATABASE</span>
                <Badge text={result.target_db || 'billing'} color="var(--primary)" />
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 14, lineHeight: 1.6 }}>
                <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>Explanation: </span>{result.explanation}
              </div>
              <div className="sql-block">{result.generated_sql}</div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

function AnomalyLog() {
  const [anomalies, setAnomalies] = useState([]);
  const [loading, setLoading]     = useState(true);
  const toast = useToast();

  const load = useCallback(() => {
    setLoading(true);
    getAnomalies({ resolved: false })
      .then(r => setAnomalies(r.data || []))
      .catch(() => toast.error('Failed to load anomalies'))
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line

  useEffect(() => { load(); }, [load]);

  return (
    <Card title={`Unresolved Anomalies  ·  ${anomalies.length}`}>
      {loading ? (
        <div style={{ padding: '40px 0', textAlign: 'center' }}>
          <div className="spinner spinner-dark" style={{ width: 24, height: 24, margin: '0 auto 12px' }} />
        </div>
      ) : (
        <Table
          columns={[
            { key: 'anomaly_type', label: 'Type',        render: v => <Badge text={v} color="var(--danger)" /> },
            { key: 'medicine_id',  label: 'Medicine',    render: v => <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{v?.slice(0,8)}…</span> },
            { key: 'outlet_id',    label: 'Outlet' },
            { key: 'severity',     label: 'Severity',    render: v => <Badge text={v} /> },
            { key: 'description',  label: 'Description', render: v => <span style={{ fontSize: 12 }}>{v?.slice(0,80)}{v?.length > 80 ? '…' : ''}</span> },
            { key: 'detected_at',  label: 'Detected',    render: v => new Date(v).toLocaleString() },
            { key: 'id', label: 'Action', render: id => (
              <Btn size="sm" color="#10B981" onClick={async () => {
                try { await resolveAnomaly(id, { notes: 'Resolved via dashboard' }); toast.success('Anomaly resolved'); load(); }
                catch { toast.error('Failed to resolve'); }
              }}>Resolve</Btn>
            )},
          ]}
          data={anomalies}
          emptyMsg="No unresolved anomalies — all clear"
        />
      )}
    </Card>
  );
}

function InfoBox({ label, value, bg, color }) {
  return (
    <div className="info-box" style={{ background: bg, borderColor: bg }}>
      <div className="info-box-label">{label}</div>
      <div className="info-box-value" style={{ color }}>{value}</div>
    </div>
  );
}

const daysAgo = n => { const d = new Date(); d.setDate(d.getDate() - n); return d.toISOString().split('T')[0]; };
