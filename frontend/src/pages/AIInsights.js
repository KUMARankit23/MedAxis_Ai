import React, { useState, useEffect } from 'react';
import { getMedicines, runForecast, detectAnomalies, nlQuery, getAnomalies, resolveAnomaly } from '../services/api';
import { Card, Table, Badge, Btn } from '../components/Card';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

const TABS = ['Demand Forecast', 'Anomaly Detection', 'AI Query', 'Anomaly Log'];

export default function AIInsights() {
  const [tab, setTab] = useState(0);
  const [medicines, setMedicines] = useState([]);

  useEffect(() => { getMedicines().then(r => setMedicines(r.data.medicines || [])); }, []);

  return (
    <div>
      <div style={{ display: 'flex', gap: 4, marginBottom: 20 }}>
        {TABS.map((t, i) => (
          <button key={t} onClick={() => setTab(i)} style={{
            padding: '8px 18px', border: 'none', borderRadius: 6, cursor: 'pointer',
            background: tab === i ? '#9b59b6' : '#e0e0e0',
            color: tab === i ? '#fff' : '#555', fontWeight: tab === i ? 600 : 400, fontSize: 13
          }}>{t}</button>
        ))}
      </div>

      {tab === 0 && <ForecastTab medicines={medicines} />}
      {tab === 1 && <AnomalyTab medicines={medicines} />}
      {tab === 2 && <QueryTab />}
      {tab === 3 && <AnomalyLog />}
    </div>
  );
}

// ── Demand Forecast ───────────────────────────────────────────────────────────
function ForecastTab({ medicines }) {
  const [medId, setMedId] = useState('');
  const [storeId, setStoreId] = useState('STORE-001');
  const [currentStock, setCurrentStock] = useState(50);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  // Generate 14 days of sample history
  const sampleHistory = Array.from({ length: 14 }, (_, i) => ({
    date: daysAgo(14 - i),
    quantity: Math.floor(15 + Math.random() * 20),
  }));

  const run = async () => {
    if (!medId) return;
    setLoading(true);
    try {
      const med = medicines.find(m => m.id === medId);
      const { data } = await runForecast({
        medicine_id: medId,
        medicine_name: med?.name,
        store_id: storeId,
        current_stock: parseInt(currentStock),
        sales_history: sampleHistory,
      });
      setResult(data);
    } catch (e) {
      alert(e.response?.data?.error || 'Forecast failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title="Demand Forecasting Agent">
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr auto', gap: 12, marginBottom: 16, alignItems: 'end' }}>
        <div>
          <label style={lbl}>Medicine</label>
          <select value={medId} onChange={e => setMedId(e.target.value)} style={inp}>
            <option value="">Select medicine</option>
            {medicines.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </div>
        <div>
          <label style={lbl}>Store ID</label>
          <input value={storeId} onChange={e => setStoreId(e.target.value)} style={inp} />
        </div>
        <div>
          <label style={lbl}>Current Stock</label>
          <input type="number" value={currentStock} onChange={e => setCurrentStock(e.target.value)} style={inp} />
        </div>
        <Btn onClick={run} disabled={loading || !medId} color="#9b59b6">
          {loading ? 'Running...' : 'Run Forecast'}
        </Btn>
      </div>

      {result && (
        <div>
          {/* Confidence + explanation */}
          <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
            <div style={{ background: '#f3e5f5', padding: '12px 16px', borderRadius: 8, flex: 1 }}>
              <div style={{ fontSize: 12, color: '#888' }}>Model</div>
              <div style={{ fontWeight: 600 }}>{result.model_used}</div>
            </div>
            <div style={{ background: '#e8f5e9', padding: '12px 16px', borderRadius: 8, flex: 1 }}>
              <div style={{ fontSize: 12, color: '#888' }}>Confidence (R²)</div>
              <div style={{ fontWeight: 600, color: '#27ae60' }}>{(result.confidence_score * 100).toFixed(1)}%</div>
            </div>
            <div style={{ background: '#fff3e0', padding: '12px 16px', borderRadius: 8, flex: 1 }}>
              <div style={{ fontSize: 12, color: '#888' }}>7-Day Total Demand</div>
              <div style={{ fontWeight: 600, color: '#f39c12' }}>{result.total_predicted} units</div>
            </div>
            {result.triggered_replenishment && (
              <div style={{ background: '#ffebee', padding: '12px 16px', borderRadius: 8, flex: 1 }}>
                <div style={{ fontSize: 12, color: '#e74c3c' }}>⚠️ Replenishment Triggered</div>
                <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>{result.replenishment_note}</div>
              </div>
            )}
          </div>

          {/* Explanation */}
          <div style={{ background: '#f8fafc', padding: 12, borderRadius: 8, fontSize: 13, color: '#555', marginBottom: 16 }}>
            <strong>AI Explanation:</strong> {result.explanation}
          </div>

          {/* Forecast chart */}
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={result.forecasts}>
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <ReferenceLine y={currentStock} stroke="#e74c3c" strokeDasharray="4 4" label={{ value: 'Current Stock', fontSize: 11 }} />
              <Line type="monotone" dataKey="predicted_demand" stroke="#9b59b6" strokeWidth={2} dot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}

// ── Anomaly Detection ─────────────────────────────────────────────────────────
function AnomalyTab({ medicines }) {
  const [medId, setMedId] = useState('');
  const [storeId, setStoreId] = useState('STORE-001');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  // Sample history with one spike
  const sampleHistory = Array.from({ length: 10 }, (_, i) => ({
    date: daysAgo(10 - i),
    quantity: i === 3 ? 200 : Math.floor(15 + Math.random() * 15),
  }));

  const run = async () => {
    if (!medId) return;
    setLoading(true);
    try {
      const med = medicines.find(m => m.id === medId);
      const { data } = await detectAnomalies({
        medicine_id: medId,
        medicine_name: med?.name,
        store_id: storeId,
        sales_history: sampleHistory,
      });
      setResult(data);
    } catch (e) {
      alert(e.response?.data?.error || 'Detection failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title="Anomaly Detection Agent">
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr auto', gap: 12, marginBottom: 16, alignItems: 'end' }}>
        <div>
          <label style={lbl}>Medicine</label>
          <select value={medId} onChange={e => setMedId(e.target.value)} style={inp}>
            <option value="">Select medicine</option>
            {medicines.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </div>
        <div>
          <label style={lbl}>Store ID</label>
          <input value={storeId} onChange={e => setStoreId(e.target.value)} style={inp} />
        </div>
        <Btn onClick={run} disabled={loading || !medId} color="#e74c3c">
          {loading ? 'Scanning...' : 'Detect Anomalies'}
        </Btn>
      </div>

      {result && (
        <div>
          <div style={{
            padding: '12px 16px', borderRadius: 8, marginBottom: 16,
            background: result.anomalies_detected > 0 ? '#ffebee' : '#e8f5e9',
            color: result.anomalies_detected > 0 ? '#c62828' : '#2e7d32',
          }}>
            {result.anomalies_detected > 0
              ? `⚠️ ${result.anomalies_detected} anomaly detected — alert sent to admin`
              : '✅ No anomalies detected in this data'}
          </div>

          {result.anomalies?.map((a, i) => (
            <div key={i} style={{ background: '#fff3e0', padding: 12, borderRadius: 8, marginBottom: 8 }}>
              <div style={{ display: 'flex', gap: 8, marginBottom: 6 }}>
                <Badge text={a.anomaly_type} color="#e74c3c" />
                <Badge text={a.severity} />
                <span style={{ fontSize: 12, color: '#888' }}>{a.date}</span>
              </div>
              <div style={{ fontSize: 13, color: '#555' }}>{a.description}</div>
              <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                Detected value: <strong>{a.detected_value}</strong> | Expected: {a.expected_range} | Model: {a.model_used}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

// ── Conversational Query ──────────────────────────────────────────────────────
function QueryTab() {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);

  const EXAMPLES = [
    'What are the top selling medicines?',
    'Show me low stock items',
    'Which batches are expiring soon?',
    "What are today's sales?",
    'Show recent anomalies',
  ];

  const run = async q => {
    const question = q || query;
    if (!question.trim()) return;
    setLoading(true);
    try {
      const { data } = await nlQuery(question);
      setResult(data);
      setHistory(h => [{ query: question, result: data }, ...h.slice(0, 4)]);
    } catch (e) {
      setResult({ error: e.response?.data?.error || 'Query failed' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title="Conversational AI Agent — Natural Language Query">
      <div style={{ marginBottom: 12 }}>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && run()}
            placeholder="Ask anything about your pharmacy data..."
            style={{ ...inp, flex: 1 }}
          />
          <Btn onClick={() => run()} disabled={loading} color="#9b59b6">
            {loading ? '...' : 'Ask'}
          </Btn>
        </div>
        <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
          {EXAMPLES.map(e => (
            <button key={e} onClick={() => { setQuery(e); run(e); }} style={{
              padding: '4px 10px', background: '#f0f4f8', border: '1px solid #ddd',
              borderRadius: 12, fontSize: 11, cursor: 'pointer', color: '#555'
            }}>{e}</button>
          ))}
        </div>
      </div>

      {result && (
        <div style={{ background: '#f8fafc', padding: 16, borderRadius: 8 }}>
          {result.error ? (
            <div style={{ color: '#e74c3c' }}>{result.error}</div>
          ) : (
            <>
              <div style={{ marginBottom: 8 }}>
                <span style={{ fontSize: 12, color: '#888' }}>Method: </span>
                <Badge text={result.method || 'pattern'} color="#9b59b6" />
                <span style={{ fontSize: 12, color: '#888', marginLeft: 8 }}>Target DB: </span>
                <Badge text={result.target_db || 'billing'} color="#3498db" />
              </div>
              <div style={{ fontSize: 13, color: '#555', marginBottom: 12 }}>
                <strong>Explanation:</strong> {result.explanation}
              </div>
              <div style={{ background: '#1a2332', color: '#4fc3f7', padding: 12, borderRadius: 6, fontFamily: 'monospace', fontSize: 12, overflowX: 'auto' }}>
                {result.generated_sql}
              </div>
            </>
          )}
        </div>
      )}
    </Card>
  );
}

// ── Anomaly Log ───────────────────────────────────────────────────────────────
function AnomalyLog() {
  const [anomalies, setAnomalies] = useState([]);
  const load = () => getAnomalies({ resolved: false }).then(r => setAnomalies(r.data.anomalies || []));
  useEffect(() => { load(); }, []);

  return (
    <Card title={`Unresolved Anomalies (${anomalies.length})`}>
      <Table
        columns={[
          { key: 'anomaly_type', label: 'Type', render: v => <Badge text={v} color="#e74c3c" /> },
          { key: 'medicine_id', label: 'Medicine', render: v => v?.slice(0, 8) + '...' },
          { key: 'store_id', label: 'Store' },
          { key: 'severity', label: 'Severity', render: v => <Badge text={v} /> },
          { key: 'description', label: 'Description', render: v => <span style={{ fontSize: 12 }}>{v?.slice(0, 80)}...</span> },
          { key: 'detected_at', label: 'Detected', render: v => new Date(v).toLocaleDateString() },
          {
            key: 'id', label: 'Action', render: id => (
              <Btn size="sm" color="#27ae60" onClick={async () => {
                await resolveAnomaly(id, { notes: 'Resolved via dashboard' });
                load();
              }}>Resolve</Btn>
            )
          },
        ]}
        data={anomalies}
        emptyMsg="No unresolved anomalies"
      />
    </Card>
  );
}

const daysAgo = n => { const d = new Date(); d.setDate(d.getDate() - n); return d.toISOString().split('T')[0]; };
const lbl = { fontSize: 12, fontWeight: 600, color: '#555', display: 'block', marginBottom: 4 };
const inp = { width: '100%', padding: '8px 10px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13, boxSizing: 'border-box' };
