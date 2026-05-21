import React, { useEffect, useState, useCallback } from 'react';
import { getMedicines, getInvoices, createInvoice, confirmInvoice, cancelInvoice } from '../services/api';
import { Card, Table, Badge, Btn } from '../components/Card';
import { useToast } from '../components/Toast';
import { getErrorMessage } from '../utils/errors';
import { Plus, Trash2 } from 'lucide-react';

export default function Billing() {
  const [tab, setTab]           = useState(0);
  const [invoices, setInvoices] = useState([]);
  const [medicines, setMeds]    = useState([]);
  const [loading, setLoading]   = useState(true);
  const toast = useToast();

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([getInvoices(), getMedicines()])
      .then(([inv, med]) => { setInvoices(inv.data.invoices || []); setMeds(med.data.medicines || []); })
      .catch(err => toast.error(getErrorMessage(err, 'Failed to load billing data')))
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line

  useEffect(() => { load(); }, [load]);

  const handleConfirm = async id => {
    try { await confirmInvoice(id); toast.success('Invoice confirmed — stock deducted'); load(); }
    catch (e) { toast.error(getErrorMessage(e, 'Confirm failed')); }
  };
  const handleCancel = async id => {
    try { await cancelInvoice(id); toast.success('Invoice cancelled'); load(); }
    catch (e) { toast.error(getErrorMessage(e, 'Cancel failed')); }
  };

  return (
    <div className="page-enter">
      <div className="tab-bar">
        {['Invoices', 'New Invoice'].map((t, i) => (
          <button key={t} onClick={() => setTab(i)} className={`tab-btn ${tab === i ? 'active' : ''}`}>{t}</button>
        ))}
      </div>

      {loading && (
        <div style={{ padding: '40px 0', textAlign: 'center' }}>
          <div className="spinner spinner-dark" style={{ width: 24, height: 24, margin: '0 auto 12px' }} />
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Loading billing data…</div>
        </div>
      )}

      {!loading && tab === 0 && (
        <Card title={`Invoices  ·  ${invoices.length} total`}>
          <Table
            columns={[
              { key: 'invoice_number', label: 'Invoice #' },
              { key: 'outlet_id',      label: 'Store' },
              { key: 'patient_name',   label: 'Patient' },
              { key: 'subtotal',       label: 'Subtotal',  render: v => `₹${Number(v||0).toFixed(2)}` },
              { key: 'tax',            label: 'GST',       render: v => `₹${Number(v||0).toFixed(2)}` },
              { key: 'total',          label: 'Total',     render: v => <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>₹{Number(v||0).toFixed(2)}</span> },
              { key: 'payment_method', label: 'Payment' },
              { key: 'status',         label: 'Status',    render: v => <Badge text={String(v||'').toUpperCase()} /> },
              { key: 'created_at',     label: 'Date',      render: v => v ? new Date(v).toLocaleDateString() : '—' },
              {
                key: 'id', label: 'Actions', render: (id, row) => (
                  String(row.status||'').toLowerCase() === 'draft' ? (
                    <div style={{ display: 'flex', gap: 6 }}>
                      <Btn size="sm" color="#10B981" onClick={() => handleConfirm(id)}>Confirm</Btn>
                      <Btn size="sm" color="#EF4444" onClick={() => handleCancel(id)}>Cancel</Btn>
                    </div>
                  ) : null
                ),
              },
            ]}
            data={invoices}
            emptyMsg="No invoices yet"
          />
        </Card>
      )}

      {!loading && tab === 1 && (
        <Card title="Create New Invoice">
          <InvoiceForm
            medicines={medicines}
            onSave={async data => {
              try { await createInvoice(data); toast.success('Invoice created as DRAFT — confirm to deduct stock'); load(); setTab(0); }
              catch (e) { toast.error(getErrorMessage(e, 'Failed to create invoice')); }
            }}
          />
        </Card>
      )}
    </div>
  );
}

function InvoiceForm({ medicines, onSave }) {
  const [outletId, setOutletId] = useState('OUTLET-001');
  const [patient, setPatient]   = useState('');
  const [payment, setPayment]   = useState('CASH');
  const [saving, setSaving]     = useState(false);
  const [items, setItems] = useState([
    { medicine_id: '', medicine_name: '', quantity: 1, unit_price: 0, category: 'OTC' },
  ]);

  const addItem    = () => setItems([...items, { medicine_id: '', medicine_name: '', quantity: 1, unit_price: 0, category: 'OTC' }]);
  const removeItem = i => setItems(items.filter((_, idx) => idx !== i));
  const updateItem = (i, field, val) => {
    const updated = [...items];
    updated[i] = { ...updated[i], [field]: val };
    if (field === 'medicine_id') {
      const med = medicines.find(m => m.id === val);
      if (med) { updated[i].medicine_name = med.name; updated[i].unit_price = med.unit_price; updated[i].category = med.category; }
    }
    setItems(updated);
  };

  const subtotal = items.reduce((s, it) => s + (Number(it.unit_price) * Number(it.quantity)), 0);
  const tax      = items.reduce((s, it) => {
    const rate = String(it.category).toUpperCase() === 'SUPPLEMENT' ? 0.12 : 0.05;
    return s + (Number(it.unit_price) * Number(it.quantity) * rate);
  }, 0);

  const handleSave = async () => {
    if (!items.every(it => it.medicine_id)) return;
    setSaving(true);
    try { await onSave({ outlet_id: outletId, patient_name: patient, payment_method: payment, items }); }
    finally { setSaving(false); }
  };

  return (
    <div>
      {/* Header fields */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginBottom: 20 }}>
        <div className="form-group">
          <label className="form-label">Outlet ID</label>
          <input value={outletId} onChange={e => setOutletId(e.target.value)} className="form-input" />
        </div>
        <div className="form-group">
          <label className="form-label">Patient Name</label>
          <input value={patient} onChange={e => setPatient(e.target.value)} className="form-input" placeholder="Optional" />
        </div>
        <div className="form-group">
          <label className="form-label">Payment Method</label>
          <select value={payment} onChange={e => setPayment(e.target.value)} className="form-select">
            {['CASH','CARD','INSURANCE','UPI'].map(p => <option key={p}>{p}</option>)}
          </select>
        </div>
      </div>

      {/* Line items */}
      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
        Line Items
        <span style={{ fontSize: 11, background: 'var(--primary-100)', color: 'var(--primary-dark)', borderRadius: 'var(--r-full)', padding: '2px 8px', fontWeight: 600 }}>
          {items.length}
        </span>
      </div>

      <div style={{ background: 'var(--slate-50)', borderRadius: 'var(--r-md)', border: '1px solid var(--border)', overflow: 'hidden', marginBottom: 16 }}>
        {items.map((item, i) => (
          <div key={i} style={{
            display: 'grid', gridTemplateColumns: '2fr 80px 120px 40px', gap: 0,
            padding: '12px 14px', borderBottom: i < items.length - 1 ? '1px solid var(--border)' : 'none',
            alignItems: 'end', background: i % 2 === 0 ? 'transparent' : 'rgba(0,0,0,0.01)',
          }}>
            <div style={{ paddingRight: 10 }}>
              {i === 0 && <div className="form-label" style={{ marginBottom: 6 }}>Medicine</div>}
              <select value={item.medicine_id} onChange={e => updateItem(i, 'medicine_id', e.target.value)} className="form-select">
                <option value="">Select medicine</option>
                {medicines.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
              </select>
            </div>
            <div style={{ paddingRight: 10 }}>
              {i === 0 && <div className="form-label" style={{ marginBottom: 6 }}>Qty</div>}
              <input type="number" min="1" value={item.quantity}
                onChange={e => updateItem(i, 'quantity', parseInt(e.target.value)||1)} className="form-input" />
            </div>
            <div style={{ paddingRight: 10 }}>
              {i === 0 && <div className="form-label" style={{ marginBottom: 6 }}>Unit Price (₹)</div>}
              <input type="number" min="0" step="0.01" value={item.unit_price}
                onChange={e => updateItem(i, 'unit_price', parseFloat(e.target.value)||0)} className="form-input" />
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end', paddingBottom: 1 }}>
              {i === 0 && <div style={{ height: 22 }} />}
              <button onClick={() => removeItem(i)} disabled={items.length === 1} style={{
                width: 32, height: 32, border: '1px solid var(--border)', borderRadius: 'var(--r-sm)',
                background: 'transparent', cursor: items.length === 1 ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: 'var(--danger)', opacity: items.length === 1 ? 0.3 : 1, transition: 'all var(--t-fast)',
              }}>
                <Trash2 size={13} />
              </button>
            </div>
          </div>
        ))}
      </div>

      <button onClick={addItem} style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        padding: '7px 14px', background: 'transparent',
        border: '1.5px dashed var(--border)', borderRadius: 'var(--r-sm)',
        fontSize: 12, fontWeight: 600, color: 'var(--primary)', cursor: 'pointer', marginBottom: 20,
        transition: 'all var(--t-fast)',
      }} onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--primary)'; e.currentTarget.style.background = 'var(--primary-50)'; }}
         onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.background = 'transparent'; }}>
        <Plus size={13} /> Add Line Item
      </button>

      {/* Totals */}
      <div style={{ background: 'var(--slate-50)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)', padding: '16px 20px', maxWidth: 280, marginBottom: 20 }}>
        {[['Subtotal', subtotal], ['GST (5%)', tax]].map(([lbl, val]) => (
          <div key={lbl} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, fontSize: 13, color: 'var(--text-secondary)' }}>
            <span>{lbl}</span><span style={{ fontWeight: 600 }}>₹{val.toFixed(2)}</span>
          </div>
        ))}
        <div style={{ height: 1, background: 'var(--border)', margin: '10px 0' }} />
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 16, fontWeight: 800, color: 'var(--text-primary)' }}>
          <span>Total</span><span>₹{(subtotal + tax).toFixed(2)}</span>
        </div>
      </div>

      <Btn color="#10B981" onClick={handleSave} disabled={saving || !items.every(it => it.medicine_id)}>
        {saving ? 'Creating…' : 'Create Invoice (Draft)'}
      </Btn>
    </div>
  );
}
