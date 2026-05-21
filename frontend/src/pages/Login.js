import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ArrowRight, Shield, BarChart2, Brain, Package } from 'lucide-react';

const FEATURES = [
  { Icon: BarChart2, title: 'Real-time Analytics',   desc: 'Live dashboard across all pharmacy outlets' },
  { Icon: Brain,     title: 'AI-Powered Insights',   desc: 'Demand forecasting & anomaly detection' },
  { Icon: Package,   title: 'Smart Inventory',        desc: 'FEFO stock management with expiry alerts' },
  { Icon: Shield,    title: 'Compliance Ready',       desc: 'Full audit trail & role-based access' },
];

export default function Login() {
  const [form, setForm]       = useState({ username: '', password: '' });
  const [error, setError]     = useState('');
  const [loading, setLoading] = useState(false);
  const { login }  = useAuth();
  const navigate   = useNavigate();

  const handleSubmit = async e => {
    e.preventDefault();
    if (!form.username.trim() || !form.password) return;
    setLoading(true); setError('');
    try {
      const user = await login(form.username.trim(), form.password);
      const dest = user.role === 'pharmacist' ? '/billing'
                 : user.role === 'inventory_planner' ? '/inventory' : '/';
      navigate(dest, { replace: true });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Invalid credentials. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      {/* ── Brand panel (hidden on mobile) ── */}
      <div className="login-brand">
        <div className="login-brand-grid" />
        <div className="login-brand-glow" style={{ top: '20%', left: '30%' }} />
        <div className="login-brand-glow" style={{ bottom: '15%', right: '20%', opacity: 0.5 }} />

        <div className="login-brand-content">
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 40 }}>
            <div style={{
              width: 48, height: 48, borderRadius: 14,
              background: 'linear-gradient(135deg, #0EA5E9, #6366F1)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 20, fontWeight: 800, color: '#fff',
              boxShadow: '0 8px 24px rgba(14,165,233,0.4)',
            }}>M</div>
            <div>
              <div style={{ fontSize: 22, fontWeight: 800, color: '#F1F5F9', letterSpacing: '-0.02em' }}>MedAxis</div>
              <div style={{ fontSize: 12, color: '#64748B', marginTop: 1 }}>Pharmacy Operations Platform</div>
            </div>
          </div>

          <h1 style={{
            fontSize: 36, fontWeight: 800, color: '#F8FAFC',
            lineHeight: 1.15, letterSpacing: '-0.03em', marginBottom: 16,
          }}>
            Enterprise pharmacy<br />
            <span style={{
              background: 'linear-gradient(135deg, #38BDF8, #818CF8)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
            }}>management platform</span>
          </h1>

          <p style={{ fontSize: 15, color: '#64748B', lineHeight: 1.7, marginBottom: 40, maxWidth: 360 }}>
            Manage inventory, billing, and replenishment across all your pharmacy outlets with AI-powered insights.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {FEATURES.map(({ Icon, title, desc }) => (
              <div key={title} style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
                <div style={{
                  width: 36, height: 36, borderRadius: 10, flexShrink: 0,
                  background: 'rgba(14,165,233,0.12)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <Icon size={16} style={{ color: '#38BDF8' }} />
                </div>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: '#E2E8F0' }}>{title}</div>
                  <div style={{ fontSize: 12, color: '#64748B', marginTop: 2 }}>{desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Login panel ── */}
      <div className="login-panel">
        <div className="login-card">
          {/* Mobile logo */}
          <div style={{ textAlign: 'center', marginBottom: 32 }}>
            <div style={{
              width: 52, height: 52, borderRadius: 15, margin: '0 auto 14px',
              background: 'linear-gradient(135deg, #0EA5E9, #6366F1)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 22, fontWeight: 800, color: '#fff',
              boxShadow: '0 8px 24px rgba(14,165,233,0.3)',
            }}>M</div>
            <h2 style={{ fontSize: 22, fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '-0.02em', marginBottom: 4 }}>
              Welcome back
            </h2>
            <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>Sign in to your MedAxis account</p>
          </div>

          <form onSubmit={handleSubmit} noValidate>
            <div className="form-group">
              <label className="form-label">Username</label>
              <input
                autoFocus autoComplete="username"
                className="login-input"
                value={form.username}
                onChange={e => setForm({ ...form, username: e.target.value })}
                placeholder="Enter your username"
                required
              />
            </div>

            <div className="form-group" style={{ marginBottom: 20 }}>
              <label className="form-label">Password</label>
              <input
                type="password" autoComplete="current-password"
                className="login-input"
                value={form.password}
                onChange={e => setForm({ ...form, password: e.target.value })}
                placeholder="Enter your password"
                required
              />
            </div>

            {error && (
              <div style={{
                background: 'var(--danger-50)', color: '#991B1B', border: '1px solid var(--danger-100)',
                padding: '11px 14px', borderRadius: 'var(--r-md)', fontSize: 13,
                marginBottom: 16, lineHeight: 1.5,
              }}>
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !form.username || !form.password}
              className="login-btn"
            >
              {loading ? (
                <><div className="spinner" /><span>Signing in…</span></>
              ) : (
                <><span>Sign In</span><ArrowRight size={16} /></>
              )}
            </button>
          </form>

          {/* Demo credentials */}
          <div className="demo-creds">
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Demo Credentials
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2px 12px' }}>
              {[
                ['admin',       'Admin@123',  'Full access'],
                ['pharmacist1', 'Pharma@123', 'Billing'],
                ['supervisor1', 'Super@123',  'Analytics'],
                ['planner1',    'Plan@123',   'Inventory'],
              ].map(([user, pass, role]) => (
                <div key={user} style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.9 }}>
                  <code>{user}</code> / <code>{pass}</code>
                  <span style={{ color: 'var(--text-muted)', marginLeft: 4 }}>— {role}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
