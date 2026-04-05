import React, { useEffect, useState } from 'react';
import { getMedicines, createMedicine, getExpiryAlerts, getLowStock, receiveBatch } from '../services/api';
import { Card, Table, Badge, Btn } from '../components/Card';

const TABS = ['Medicines', 'Receive Stock', 'Expiry Alerts', 'Low Stock'];

export default function Inventory() {
  const [tab, setTab] = useState(0);
  const [medicines, setMedicines] = useState([]);
  const [expiry, setExpiry] = useState([]);
  const [lowStock, setLowStock] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [showBatch, setShowBatch] = useState(false);
  const [msg, setMsg] = useState('');

  useEffect(() => {
    getMedicines().then(r => setMedicines(r.data.medicines || []));
    getExpiryAlerts({ days: 30 }).then(r => setExpiry(r.data.expiring_batches || []));
    getLowStock().then(r => setLowStock(r.data.low_stock_items || []));
  }, []);

  const flash = m => { setMsg(m); setTimeout(() => setMsg(''), 3000); };

  return (
    <div>
      {msg && <div style={{ background: '#d4edda', color: '#155724', padding: '10px 16px', borderRadius: 8, marginBottom: 16 }}>{msg}</div>}

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

      {/* Medicines tab */}
      {tab === 0 && (
        <Card title="Medicine Catalog">
          <div style={{ marginBottom: 12 }}>
            <Btn onClick={() => setShowForm(!showForm)} color="#3498db">+ Add Medicine</Btn>
          </div>
          {showForm && <MedicineForm onSave={async data => {
            await createMedicine(data);
            const r = await getMedicines();
            setMedicines(r.data.medicines || []);
            setShowForm(false);
            flash('Medicine added successfully');
          }} onCancel={() => setShowForm(false)} />}
          <Table
            columns={[
              { key: 'name', label: 'Name' },
              { key: 'category', label: 'Category', render: v => <Badge text={v} color="#3498db" /> },
              { key: 'unit_price', label: 'Price', render: v => `₹${v}` },
              { key: 'reorder_level', label: 'Reorder Level' },
              { key: 'unit', label: 'Unit' },
            ]}
            data={medicines}
            emptyMsg="No medicines yet. Add one above."
          />
        </Card>
      )}

      {/* Receive Stock tab */}
      {tab === 1 && (
        <Card title="Receive Stock Batch">
          <BatchForm medicines={medicines} onSave={async data => {
            await receiveBatch(data);
            flash('Stock received successfully');
          }} />
        </Card>
      )}

      {/* Expiry Alerts tab */}
      {tab === 2 && (
        <Card title={`Expiry Alerts — ${expiry.length} batches expiring within 30 days`}>
          <Table
            columns={[
              { key: 'medicine_id', label: 'Medicine ID', render: v => v?.slice(0, 8) + '...' },
              { key: 'batch_number', label: 'Batch' },
              { key: 'store_id', label: 'Store' },
              { key: 'quantity', label: 'Qty' },
              { key: 'expiry_date', label: 'Expiry Date' },
              { key: 'days_to_expiry', label: 'Days Left' },
              { key: 'severity', label: 'Severity', render: v => <Badge text={v} /> },
            ]}
            data={expiry}
            emptyMsg="No batches expiring within 30 days"
          />
        </Card>
      )}

      {/* Low Stock tab */}
      {tab === 3 && (
        <Card title={`Low Stock — ${lowStock.length} items below reorder level`}>
          <Table
            columns={[
              { key: 'name', label: 'Medicine' },
              { key: 'store_id', label: 'Store' },
              { key: 'total_stock', label: 'Current Stock' },
              { key: 'reorder_level', label: 'Reorder Level' },
              { key: 'suggested_order_qty', label: 'Suggested Order' },
            ]}
            data={lowStock}
            emptyMsg="All stock levels are healthy"
          />
        </Card>
      )}
    </div>
  );
}

function MedicineForm({ onSave, onCancel }) {
  const [f, setF] = useState({ name: '', category: 'OTC', unit_price: '', reorder_level: 50, unit: 'units', manufacturer: '' });
  const set = k => e => setF({ ...f, [k]: e.target.value });
  return (
    <div style={{ background: '#f8fafc', padding: 16, borderRadius: 8, marginBottom: 16 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 12 }}>
        <Field label="Name" value={f.name} onChange={set('name')} required />
        <Field label="Category" value={f.category} onChange={set('category')} type="select"
          options={['OTC', 'PRESCRIPTION', 'CONTROLLED']} />
        <Field label="Unit Price (₹)" value={f.unit_price} onChange={set('unit_price')} type="number" />
        <Field label="Reorder Level" value={f.reorder_level} onChange={set('reorder_level')} type="number" />
        <Field label="Unit" value={f.unit} onChange={set('unit')} />
        <Field label="Manufacturer" value={f.manufacturer} onChange={set('manufacturer')} />
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <Btn onClick={() => onSave(f)} color="#27ae60">Save</Btn>
        <Btn onClick={onCancel} color="#95a5a6">Cancel</Btn>
      </div>
    </div>
  );
}

function BatchForm({ medicines, onSave }) {
  const [f, setF] = useState({ medicine_id: '', batch_number: '', store_id: 'STORE-001', quantity: '', expiry_date: '' });
  const [done, setDone] = useState(false);
  const set = k => e => setF({ ...f, [k]: e.target.value });
  return (
    <div>
      {done && <div style={{ background: '#d4edda', color: '#155724', padding: 10, borderRadius: 8, marginBottom: 12 }}>Stock received!</div>}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 12 }}>
        <div>
          <label style={labelStyle}>Medicine</label>
          <select value={f.medicine_id} onChange={set('medicine_id')} style={inputStyle}>
            <option value="">Select medicine</option>
            {medicines.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </div>
        <Field label="Batch Number" value={f.batch_number} onChange={set('batch_number')} />
        <Field label="Store ID" value={f.store_id} onChange={set('store_id')} />
        <Field label="Quantity" value={f.quantity} onChange={set('quantity')} type="number" />
        <Field label="Expiry Date" value={f.expiry_date} onChange={set('expiry_date')} type="date" />
      </div>
      <Btn onClick={async () => { await onSave(f); setDone(true); setF({ ...f, batch_number: '', quantity: '' }); }} color="#27ae60">
        Receive Stock
      </Btn>
    </div>
  );
}

const labelStyle = { fontSize: 12, fontWeight: 600, color: '#555', display: 'block', marginBottom: 4 };
const inputStyle = { width: '100%', padding: '8px 10px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13, boxSizing: 'border-box' };

function Field({ label, value, onChange, type = 'text', options, required }) {
  return (
    <div>
      <label style={labelStyle}>{label}</label>
      {type === 'select' ? (
        <select value={value} onChange={onChange} style={inputStyle}>
          {options.map(o => <option key={o} value={o}>{o}</option>)}
        </select>
      ) : (
        <input type={type} value={value} onChange={onChange} required={required} style={inputStyle} />
      )}
    </div>
  );
}
