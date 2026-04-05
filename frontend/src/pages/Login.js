import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Login() {
  const [form, setForm] = useState({ username: '', password: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async e => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      const user = await login(form.username, form.password);
      navigate(user.role === 'pharmacist' ? '/billing' : '/');
    } catch (err) {
      setError(err.response?.data?.error || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center',
      justifyContent: 'center', background: 'linear-gradient(135deg, #1a2332 0%, #2d3f55 100%)'
    }}>
      <div style={{
        background: '#fff', borderRadius: 16, padding: '48px 40px',
        width: 380, boxShadow: '0 20px 60px rgba(0,0,0,0.3)'
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{ fontSize: 48, marginBottom: 8 }}>💊</div>
          <h1 style={{ fontSize: 24, fontWeight: 700, color: '#1a2332' }}>MedAxis</h1>
          <p style={{ color: '#888', fontSize: 13, marginTop: 4 }}>Pharmacy Operations Platform</p>
        </div>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ fontSize: 13, fontWeight: 600, color: '#555', display: 'block', marginBottom: 6 }}>
              Username
            </label>
            <input
              value={form.username}
              onChange={e => setForm({ ...form, username: e.target.value })}
              placeholder="Enter username"
              required
              style={{
                width: '100%', padding: '10px 14px', border: '1px solid #ddd',
                borderRadius: 8, fontSize: 14, outline: 'none',
                boxSizing: 'border-box'
              }}
            />
          </div>

          <div style={{ marginBottom: 24 }}>
            <label style={{ fontSize: 13, fontWeight: 600, color: '#555', display: 'block', marginBottom: 6 }}>
              Password
            </label>
            <input
              type="password"
              value={form.password}
              onChange={e => setForm({ ...form, password: e.target.value })}
              placeholder="Enter password"
              required
              style={{
                width: '100%', padding: '10px 14px', border: '1px solid #ddd',
                borderRadius: 8, fontSize: 14, outline: 'none',
                boxSizing: 'border-box'
              }}
            />
          </div>

          {error && (
            <div style={{
              background: '#ffeaea', color: '#e74c3c', padding: '10px 14px',
              borderRadius: 8, fontSize: 13, marginBottom: 16
            }}>{error}</div>
          )}

          <button type="submit" disabled={loading} style={{
            width: '100%', padding: '12px', background: loading ? '#aaa' : '#4fc3f7',
            color: '#fff', border: 'none', borderRadius: 8,
            fontSize: 15, fontWeight: 600, cursor: loading ? 'not-allowed' : 'pointer'
          }}>
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <div style={{ marginTop: 24, padding: '12px', background: '#f8fafc', borderRadius: 8, fontSize: 12, color: '#888' }}>
          <strong>Demo credentials:</strong><br />
          admin / Admin@123 &nbsp;|&nbsp; pharmacist1 / Pharma@123
        </div>
      </div>
    </div>
  );
}
