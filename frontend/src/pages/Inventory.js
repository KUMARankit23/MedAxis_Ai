import React, { useEffect, useState, useCallback } from 'react';
import { getMedicines, createMedicine, getExpiryAlerts, getLowStock, receiveBatch } from '../services/api';
import { Card, Table, Badge, Btn } from '../components/Card';
import { useToast } from '../components/Toast';
import { getErrorMessage } from '../utils/errors';
import { Plus, X } from 'lucide-react';

const TABS = ['Medicines', 'Receive Stock', 'Expiry Alerts', 'Low Stock'];

export default function Inventory() {
  const [tab, setTab]           = useState(0);
  const [medicines, setMeds]    = useState([]);
  const [expiry, setExpiry]     = useState([]);
  const [lowStock, setLow]      = useState([]);
  const [loading, setLoading]   = useState(true);
  const [showForm, setShowForm] = useState(false);
  const toast = useToast();

  const loadAll = useCallback(() => {
    setLoading(true);
    Promise.all([getMedicines(), getExpiryAlerts({ days: 30 }), getLowStock()])
      .then(([m, e, l]) => {
        setMeds(m.data.medicines || []);
        setExpiry(e.data || []);
        setLow(l.data.low_stock_items || []);
      })
      .catch(err => toast.error(getErrorMessage(err, 'Failed to load inventory')))
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line

  useEffect(() => { loadAll(); }, [loadAll]);

  return (
    <div className="page-enter">
      <div className="tab-bar">
        {TABS.map((t, i) => (
          <button key={t} onClick={() => setTab(i)} className={`tab-btn ${tab === i ? 'active' : ''}`}>
            {t}
            {i === 2 && expiry.length > 0 && <span className="tab-badge">{expiry.length}</span>}
            {i === 3 && lowStock.length > 0 && <span className="tab-badge" style={{ background: 'var(--warning)' }}>{lowStock.length}</span>}
          </button>
        ))}
      </div>

      {loading && <LoadingRows />}

      {!loading && tab === 0 && (
        <Card
          title={`Medicine Catalog  ·  ${medicines.length} items`}
          action={
            <Btn onClick={() => setShowForm(!showForm)} color="#0EA5E9" size="sm">
              {showForm ? <><X size={12} /> Cancel</> : <><Plus size={12} /> Add Medicine</>}
            </Btn>
          }
        >
          {showForm && (
            <div style={{ background: 'var(--slate-50)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)', padding: 20, marginBottom: 20 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 14 }}>New Medicine</div>
              <MedicineForm
                onSave={async data => {
                  try { await createMedicine(data); toast.success('Medicine added'); setShowForm(false); loadAll(); }
                  catch (e) { toast.error(getErrorMessage(e, 'Failed to add medicine')); }
                }}
                onCancel={() => setShowForm(false)}
              />
            </div>
          )}
          <Table
            columns={[
              { key: 'name',          label: 'Name' },
              { key: 'generic_name',  label: 'Generic' },
              { key: 'category',      label: 'Category',  render: v => <Badge text={v} /> },
              { key: 'unit_price',    label: 'Price',     render: v => `₹${Number(v).toFixed(2)}` },
              { key: 'reorder_level', label: 'Reorder At' },
              { key: 'unit',          label: 'Unit' },
              { key: 'manufacturer',  label: 'Manufacturer' },
            ]}
            data={medicines}
            emptyMsg="No medicines yet — add one above"
          />
        </Card>
      )}

      {!loading && tab === 1 && (
        <Card title="Receive Stock Batch">
          <BatchForm medicines={medicines} onSave={async data => {
            try { await receiveBatch(data); toast.success('Stock received'); }
            catch (e) { toast.error(e.response?.data?.detail || 'Failed to receive stock'); }
          }} />
        </Card>
      )}

      {!loading && tab === 2 && (
        <Card title={`Expiry Alerts — ${expiry.length} batches expiring within 30 days`}>
          <Table
            columns={[
              { key: 'medicine_id',    label: 'Medicine',   render: v => <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{v?.slice(0,8)}…</span> },
              { key: 'batch_number',   label: 'Batch' },
              { key: 'outlet_id',      label: 'Store' },
              { key: 'quantity',       label: 'Qty' },
              { key: 'expiry_date',    label: 'Expiry Date' },
              { key: 'days_to_expiry', label: 'Days Left', render: v => (
                <span style={{ fontWeight: 700, color: v <= 7 ? 'var(--danger)' : v <= 15 ? 'var(--warning)' : 'var(--success)' }}>{v}d</span>
              )},
              { key: 'severity', label: 'Severity', render: v => <Badge text={v} /> },
            ]}
            data={expiry}
            emptyMsg="No batches expiring within 30 days ✓"
          />
        </Card>
      )}

      {!loading && tab === 3 && (
        <Card title={`Low Stock — ${lowStock.length} items below reorder level`}>
          <Table
            columns={[
              { key: 'name',                label: 'Medicine' },
              { key: 'outlet_id',           label: 'Store' },
              { key: 'total_stock',         label: 'Current Stock', render: v => <span style={{ fontWeight: 600, color: 'var(--danger)' }}>{v}</span> },
              { key: 'reorder_level',       label: 'Reorder Level' },
              { key: 'suggested_order_qty', label: 'Suggested Order' },
            ]}
            data={lowStock}
            emptyMsg="All stock levels are healthy ✓"
          />
        </Card>
      )}
    </div>
  );
}

function MedicineForm({ onSave, onCancel }) {
  const [f, setF] = useState({ name: '', category: 'OTC', unit_price: '', reorder_level: 50, reorder_quantity: 100, unit: 'tablets', manufacturer: '' });
  const set = k => e => setF({ ...f, [k]: e.target.value });
  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginBottom: 14 }}>
        <Field label="Name *"           value={f.name}             onChange={set('name')} />
        <Field label="Category"         value={f.category}         onChange={set('category')} type="select" options={['OTC','PRESCRIPTION','CONTROLLED']} />
        <Field label="Unit Price (₹) *" value={f.unit_price}       onChange={set('unit_price')} type="number" />
        <Field label="Reorder Level"    value={f.reorder_level}    onChange={set('reorder_level')} type="number" />
        <Field label="Reorder Qty"      value={f.reorder_quantity} onChange={set('reorder_quantity')} type="number" />
        <Field label="Unit"             value={f.unit}             onChange={set('unit')} />
        <Field label="Manufacturer"     value={f.manufacturer}     onChange={set('manufacturer')} />
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <Btn onClick={() => onSave({ ...f, unit_price: parseFloat(f.unit_price), reorder_level: parseInt(f.reorder_level), reorder_quantity: parseInt(f.reorder_quantity) })} color="#10B981">Save Medicine</Btn>
        <Btn onClick={onCancel} color="#95a5a6">Cancel</Btn>
      </div>
    </div>
  );
}

function BatchForm({ medicines, onSave }) {
  const tomorrow = () => { const d = new Date(); d.setDate(d.getDate()+1); return d.toISOString().split('T')[0]; };
  const [f, setF]     = useState({ medicine_id: '', batch_number: '', outlet_id: 'OUTLET-001', quantity: '', expiry_date: tomorrow() });
  const [saving, setSaving] = useState(false);
  const set = k => e => setF({ ...f, [k]: e.target.value });
  const handleSave = async () => {
    if (!f.medicine_id || !f.batch_number || !f.quantity) return;
    setSaving(true);
    try { await onSave({ ...f, quantity: parseInt(f.quantity) }); setF({ ...f, batch_number: '', quantity: '' }); }
    finally { setSaving(false); }
  };
  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginBottom: 14 }}>
        <div className="form-group">
          <label className="form-label">Medicine *</label>
          <select value={f.medicine_id} onChange={set('medicine_id')} className="form-select">
            <option value="">Select medicine</option>
            {medicines.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </div>
        <Field label="Batch Number *" value={f.batch_number} onChange={set('batch_number')} />
        <Field label="Outlet ID"      value={f.outlet_id}    onChange={set('outlet_id')} />
        <Field label="Quantity *"     value={f.quantity}     onChange={set('quantity')} type="number" />
        <Field label="Expiry Date *"  value={f.expiry_date}  onChange={set('expiry_date')} type="date" />
      </div>
      <Btn onClick={handleSave} color="#10B981" disabled={saving || !f.medicine_id || !f.batch_number || !f.quantity}>
        {saving ? 'Saving…' : 'Receive Stock'}
      </Btn>
    </div>
  );
}

function Field({ label, value, onChange, type = 'text', options }) {
  return (
    <div className="form-group">
      <label className="form-label">{label}</label>
      {type === 'select' ? (
        <select value={value} onChange={onChange} className="form-select">
          {options.map(o => <option key={o} value={o}>{o}</option>)}
        </select>
      ) : (
        <input type={type} value={value} onChange={onChange} className="form-input" />
      )}
    </div>
  );
}

const LoadingRows = () => (
  <div style={{ padding: '40px 0', textAlign: 'center' }}>
    <div className="spinner spinner-dark" style={{ width: 24, height: 24, margin: '0 auto 12px' }} />
    <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Loading inventory…</div>
  </div>
);
