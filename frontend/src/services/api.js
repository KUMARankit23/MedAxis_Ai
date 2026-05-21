/**
 * API service layer — all calls go through the gateway at :8000
 * Handles token storage, auto-refresh on 401, and correlation ID forwarding.
 */
import axios from 'axios';

const BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: BASE,
  timeout: 30000,
});

// ── Request interceptor — attach token + correlation ID ───────────────────────
api.interceptors.request.use(cfg => {
  const token = localStorage.getItem('access_token');
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  // Generate correlation ID (compatible with all browsers)
  const corrId = (typeof crypto !== 'undefined' && crypto.randomUUID)
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2) + Date.now().toString(36);
  cfg.headers['X-Correlation-ID'] = corrId;
  return cfg;
});

// ── Response interceptor — auto-refresh on 401 ────────────────────────────────
let _refreshing = false;
let _refreshQueue = [];

api.interceptors.response.use(
  res => res,
  async err => {
    const original = err.config;
    if (err.response?.status === 401 && !original._retry) {
      original._retry = true;
      const refresh = localStorage.getItem('refresh_token');
      if (!refresh) {
        localStorage.clear();
        window.location.href = '/login';
        return Promise.reject(err);
      }

      if (_refreshing) {
        // Queue requests while refresh is in progress
        return new Promise((resolve, reject) => {
          _refreshQueue.push({ resolve, reject });
        }).then(token => {
          original.headers.Authorization = `Bearer ${token}`;
          return api(original);
        });
      }

      _refreshing = true;
      try {
        const { data } = await axios.post(`${BASE}/auth/refresh`, { refresh_token: refresh });
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('refresh_token', data.refresh_token);
        localStorage.setItem('user', JSON.stringify(data.user));
        const newToken = data.access_token;
        _refreshQueue.forEach(p => p.resolve(newToken));
        _refreshQueue = [];
        original.headers.Authorization = `Bearer ${newToken}`;
        return api(original);
      } catch (refreshErr) {
        _refreshQueue.forEach(p => p.reject(refreshErr));
        _refreshQueue = [];
        localStorage.clear();
        window.location.href = '/login';
        return Promise.reject(refreshErr);
      } finally {
        _refreshing = false;
      }
    }
    return Promise.reject(err);
  }
);

// ── Auth ──────────────────────────────────────────────────────────────────────
export const login          = (username, password) => api.post('/auth/login', { username, password });
export const logout         = ()                   => api.post('/auth/logout');
export const getMe          = ()                   => api.get('/auth/me');
export const getUsers       = ()                   => api.get('/auth/users');
export const createUser     = (data)               => api.post('/auth/users', data);
export const deactivateUser = (id)                 => api.post(`/auth/users/${id}/deactivate`);
export const unlockUser     = (id)                 => api.post(`/auth/users/${id}/unlock`);
export const changePassword = (id, data)           => api.post(`/auth/users/${id}/change-password`, data);
export const getAuditLogs   = (params)             => api.get('/auth/audit-logs', { params });

// ── Inventory ─────────────────────────────────────────────────────────────────
export const getMedicines   = (params)  => api.get('/inventory/medicines', { params });
export const createMedicine = (data)    => api.post('/inventory/medicines', data);
export const getStoreStock  = (id)      => api.get(`/inventory/stock/${id}`);
export const receiveBatch   = (data)    => api.post('/inventory/batches', data);
export const getExpiryAlerts = (params) => api.get('/inventory/alerts/expiring', { params });
export const getLowStock    = (params)  => api.get('/inventory/alerts/low-stock', { params });
export const adjustStock    = (data)    => api.post('/inventory/adjust', data);
export const getLedger      = (id, params) => api.get(`/inventory/ledger/${id}`, { params });
export const transferStock  = (data)    => api.post('/inventory/transfer', data);
export const quarantineBatch = (id, data) => api.post(`/inventory/batches/${id}/quarantine`, data);
export const releaseBatch   = (id)      => api.post(`/inventory/batches/${id}/release`);

// ── Billing ───────────────────────────────────────────────────────────────────
export const getInvoices        = (params) => api.get('/billing/invoices', { params });
export const getInvoice         = (id)     => api.get(`/billing/invoices/${id}`);
export const createInvoice      = (data)   => api.post('/billing/invoices', data);
export const confirmInvoice     = (id)     => api.post(`/billing/invoices/${id}/confirm`);
export const cancelInvoice      = (id)     => api.post(`/billing/invoices/${id}/cancel`);
export const refundInvoice      = (id, data) => api.post(`/billing/invoices/${id}/refund`, data);
export const createPrescription = (data)   => api.post('/billing/prescriptions', data);
export const getInvoiceStats    = (params) => api.get('/billing/invoices/stats', { params });

// ── Replenishment ─────────────────────────────────────────────────────────────
export const getOrders    = (params)      => api.get('/replenishment/orders', { params });
export const createOrder  = (data)        => api.post('/replenishment/orders', data);
export const approveOrder = (id, data)    => api.post(`/replenishment/orders/${id}/approve`, data || {});
export const markOrdered  = (id)          => api.post(`/replenishment/orders/${id}/mark-ordered`);
export const receiveOrder = (id, data)    => api.post(`/replenishment/orders/${id}/receive`, data || {});
export const cancelOrder  = (id, data)    => api.post(`/replenishment/orders/${id}/cancel`, data || {});

// ── Reporting ─────────────────────────────────────────────────────────────────
export const getDashboard       = ()       => api.get('/reporting/dashboard');
export const getSalesSummary    = (params) => api.get('/reporting/sales/summary', { params });
export const getTopMedicines    = (params) => api.get('/reporting/sales/top-products', { params });
export const getStorePerformance = (params) => api.get('/reporting/stores/performance', { params });
export const getExpiryReport    = (params) => api.get('/reporting/inventory/expiry', { params });
export const getLowStockReport  = ()       => api.get('/reporting/inventory/low-stock');

// ── AI Insights ───────────────────────────────────────────────────────────────
export const runForecast     = (data)      => api.post('/ai/forecast', data);
export const getForecasts    = (params)    => api.get('/ai/forecasts', { params });
export const detectAnomalies = (data)      => api.post('/ai/anomalies/detect', data);
export const stockMismatch   = (data)      => api.post('/ai/anomalies/stock-mismatch', data);
export const getAnomalies    = (params)    => api.get('/ai/anomalies', { params });
export const resolveAnomaly  = (id, data)  => api.post(`/ai/anomalies/${id}/resolve`, data);
export const nlQuery         = (query)     => api.post('/ai/query', { query });
export const getAIModels     = ()          => api.get('/ai/models');

// ── Notifications ─────────────────────────────────────────────────────────────
export const getNotifications = (params)  => api.get('/notifications', { params });

export default api;
