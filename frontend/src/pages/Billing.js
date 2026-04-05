import React, { useEffect, useState } from 'react';
import { getMedicines, getInvoices, createInvoice, confirmInvoice, cancelInvoice } from '../services/api';
import { Card, Table, Badge, Btn } from '../components/Card';

export default function Billing() {
  const [tab, setTab] = useState(0);
  const [invoices, setInvoices] = useState([]);
  const [medicines, setMedicines] = useState([]);
  const [msg, setMsg] = useState('');

  const load = () => {
    getInvoices().then(r => setInvoices(r.data.invoices || []));
    getMedicines().then(r => setMedicines(r.data.medicines || []));
  };

  useEffect(() => { load(); }, []);

  const flash = (m, ok = true) => {
    setMsg({ text: m, ok });
    setTimeout(() => setMsg(''), 3000);
  };

  const handleConfirm = async id => {
    try {
      await confirmInvoice(id);
      flash('Invoice confirmed and stock deducted');
      load();
    } catch (e) {
      flash(e.response?.data?.error || 'Confirm failed', false);
    }
  };

  const handleCancel = async id => {
    try {
      await cancelInvoice(id);
      flash('Invoice cancelled');
      load();
    } catch (e) {
      flash(e.response?.data?.error || 'Cancel failed', false);
    }
  };

  return (
    <div>
      {msg && (
        <div style={{
          background: msg.ok ? '#d4edda' : '#f8d7da',
          color: msg.ok ? '#155724' : '#721c24',
          padding: '10px 16px', borderRadius: 8, marginBottom: 16
        }}>{msg.text}</div>
      )}

      <div style={{ display: 'flex', gap: 4, marginBottom: 20 }}>
        {['Invoices', 'New Invoice'].map((t, i) => (
          <button key={t} onClick={() => setTab(i)} style={{
            padding: '8px 18px', border: 'none', borderRadius: 6, cursor: 'pointer',
            background: tab === i ? '#4fc3f7' : '#e0e0e0',
            color: tab === i ? '#fff' : '#555', fontWeight: tab === i ? 600 : 400, fontSize: 13
          }}>{t}</button>
        ))}
      </div>

      {tab === 0 && (
        <Card title={`Invoices (${invoices.length})`}>
          <Table
            columns={[
              { key: 'invoice_number', label: 'Invoice #' },
              { key: 'store_id', label: 'Store' },
              { key: 'patient_name', label: 'Patient' },
              { key: 'subtotal', label: 'Subtotal', render: v => `₹${Number(v).toFixed(2)}` },
              { key: 'tax', label: 'GST', render: v => `₹${Number(v).toFixed(2)}` },
              { key: 'total', label: 'Total', render: v => <strong>₹{Number(v).toFixed(2)}</strong> },
              { key: 'payment_method', label: 'Payment' },
              { key: 'status', label: 'Status', render: v => <Badge text={v?.toUpperCase()} /> },
              {
                key: 'id', label: 'Actions', render: (id, row) => (
                  <div style={{ display: 'flex', gap: 6 }}>
                    {row.status === 'draft' && (
                      <>
                        <Btn size="sm" color="#27ae60" onClick={() => handleConfirm(id)}>Confirm</Btn>
                        <Btn size="sm" color="#e74c3c" onClick={() => handleCancel(id)}>Cancel</Btn>
                      </>
                    )}
                  </div>
                )
              },
            ]}
            data={invoices}
            emptyMsg="No invoices yet"
          />
        </Card>
      )}

      {tab === 1 && (
        <Card title="Create New Invoice">
          <InvoiceForm medicines={medicines} onSave={async data => {
            await createInvoice(data);
            flash('Invoice created as DRAFT. Confirm to deduct stock.');
            load();
            setTab(0);
          }} />
        </Card>
      )}
    </div>
  );
}

function InvoiceForm({ medicines, onSave }) {
  const [storeId, setStoreId] = useState('STORE-001');
  const [patient, setPatient] = useState('');
  const [payment, setPayment] = useState('CASH');
  const [items, setItems] = useState([{ medicine_id: '', medicine_name: '', quantity: 1, unit_price: 0, category: 'OTC' }]);

  const addItem = () => setItems([...items, { medicine_id: '', medicine_name: '', quantity: 1, unit_price: 0, category: 'OTC' }]);
  const removeItem = i => setItems(items.filter((_, idx) => idx !== i));

  const updateItem = (i, field, val) => {
    const updated = [...items];
    updated[i] = { ...updated[i], [field]: val };
    if (field === 'medicine_id') {
      const med = medicines.find(m => m.id === val);
      if (med) {
        updated[i].medicine_name = med.name;
        updated[i].unit_price = med.unit_price;
        updated[i].category = med.category;
      }
    }
    setItems(updated);
  };

  const subtotal = items.reduce((s, it) => s + (it.unit_price * it.quantity), 0);
  const tax = items.reduce((s, it) => {
    const rate = it.category === 'OTC' ? 0.05 : it.category === 'SUPPLEMENT' ? 0.12 : 0.05;
    return s + (it.unit_price * it.quantity * rate);
  }, 0);

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 16 }}>
        <div>
          <label style={lbl}>Store ID</label>
          <input value={storeId} onChange={e => setStoreId(e.target.value)} style={inp} />
        </div>
        <div>
          <label style={lbl}>Patient Name</label>
          <input value={patient} onChange={e => setPatient(e.target.value)} style={inp} />
        </div>
        <div>
          <label style={lbl}>Payment Method</label>
          <select value={payment} onChange={e => setPayment(e.target.value)} style={inp}>
            {['CASH', 'CARD', 'INSURANCE', 'UPI'].map(p => <option key={p}>{p}</option>)}
          </select>
        </div>
      </div>

      <h4 style={{ marginBottom: 10, fontSize: 14, color: '#555' }}>Line Items</h4>
      {items.map((item, i) => (
        <div key={i} style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr auto', gap: 10, marginBottom: 8, alignItems: 'end' }}>
          <div>
            <label style={lbl}>Medicine</label>
            <select value={item.medicine_id} onChange={e => updateItem(i, 'medicine_id', e.target.value)} style={inp}>
              <option value="">Select medicine</option>
              {medicines.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
            </select>
          </div>
          <div>
            <label style={lbl}>Qty</label>
            <input type="number" min="1" value={item.quantity}
              onChange={e => updateItem(i, 'quantity', parseInt(e.target.value))} style={inp} />
          </div>
          <div>
            <label style={lbl}>Unit Price (₹)</label>
            <input type="number" value={item.unit_price}
              onChange={e => updateItem(i, 'unit_price', parseFloat(e.target.value))} style={inp} />
          </div>
          <Btn size="sm" color="#e74c3c" onClick={() => removeItem(i)}>✕</Btn>
        </div>
      ))}

      <Btn size="sm" color="#3498db" onClick={addItem} style={{ marginBottom: 16 }}>+ Add Item</Btn>

      {/* Totals */}
      <div style={{ background: '#f8fafc', padding: 16, borderRadius: 8, marginBottom: 16, maxWidth: 300 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, fontSize: 13 }}>
          <span>Subtotal:</span><strong>₹{subtotal.toFixed(2)}</strong>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, fontSize: 13 }}>
          <span>GST:</span><strong>₹{tax.toFixed(2)}</strong>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 15, fontWeight: 700, borderTop: '1px solid #ddd', paddingTop: 8 }}>
          <span>Total:</span><span>₹{(subtotal + tax).toFixed(2)}</span>
        </div>
      </div>

      <Btn color="#27ae60" onClick={() => onSave({
        store_id: storeId, patient_name: patient, payment_method: payment, items
      })}>Create Invoice</Btn>
    </div>
  );
}

const lbl = { fontSize: 12, fontWeight: 600, color: '#555', display: 'block', marginBottom: 4 };
const inp = { width: '100%', padding: '8px 10px', border: '1px solid #ddd', borderRadius: 6, fontSize: 13, boxSizing: 'border-box' };
