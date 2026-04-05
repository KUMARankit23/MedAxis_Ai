/**
 * API service layer — all calls go through the gateway at :8000
 * Handles token storage, refresh, and request/response interceptors.
 */
import axios from 'axios';

const BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({ baseURL: BASE });

// Attach access token to every request
api.interceptors.request.use(cfg => {
  const token = localStorage.getItem('access_token');
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

// Auto-refresh on 401
api.interceptors.response.use(
  res => res,
  async err => {
    if (err.response?.status === 401 && !err.config._retry) {
      err.config._retry = true;
      const refresh = localStorage.getItem('refresh_token');
      if (refresh) {
        try {
          const { data } = await axios.post(`${BASE}/auth/refresh`, { refresh_token: refresh });
          localStorage.setItem('access_token', data.access_token);
          err.config.headers.Authorization = `Bearer ${data.access_token}`;
          return api(err.config);
        } catch {
          localStorage.clear();
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(err);
  }
);

// ── Auth ──────────────────────────────────────────────────────────────────
export const login = (username, password) =>
  api.post('/auth/login', { username, password });

export const getMe = () => api.get('/auth/me');
export const getUsers = () => api.get('/auth/users');
export const getAuditLogs = (params) => api.get('/auth/audit-logs', { params });

// ── Inventory ─────────────────────────────────────────────────────────────
export const getMedicines = (params) => api.get('/inventory/medicines', { params });
export const createMedicine = (data) => api.post('/inventory/medicines', data);
export const getStoreStock = (storeId) => api.get(`/inventory/stock/${storeId}`);
export const receiveBatch = (data) => api.post('/inventory/batches', data);
export const getExpiryAlerts = (params) => api.get('/inventory/expiry-alerts', { params });
export const getLowStock = (params) => api.get('/inventory/low-stock', { params });
export const adjustStock = (data) => api.post('/inventory/adjust', data);
export const getLedger = (medicineId) => api.get(`/inventory/ledger/${medicineId}`);

// ── Billing ───────────────────────────────────────────────────────────────
export const getInvoices = (params) => api.get('/billing/invoices', { params });
export const createInvoice = (data) => api.post('/billing/invoices', data);
export const confirmInvoice = (id) => api.post(`/billing/invoices/${id}/confirm`);
export const cancelInvoice = (id) => api.post(`/billing/invoices/${id}/cancel`);
export const refundInvoice = (id, data) => api.post(`/billing/invoices/${id}/refund`, data);
export const createPrescription = (data) => api.post('/billing/prescriptions', data);

// ── Replenishment ─────────────────────────────────────────────────────────
export const getOrders = (params) => api.get('/replenishment/orders', { params });
export const createOrder = (data) => api.post('/replenishment/orders', data);
export const approveOrder = (id, data) => api.post(`/replenishment/orders/${id}/approve`, data);
export const markOrdered = (id) => api.post(`/replenishment/orders/${id}/mark-ordered`);
export const receiveOrder = (id) => api.post(`/replenishment/orders/${id}/receive`);

// ── Reporting ─────────────────────────────────────────────────────────────
export const getDashboard = () => api.get('/reporting/dashboard');
export const getSalesSummary = (params) => api.get('/reporting/sales/summary', { params });
export const getTopMedicines = (params) => api.get('/reporting/medicines/top', { params });
export const getStorePerformance = (params) => api.get('/reporting/stores/performance', { params });
export const getExpiryReport = (params) => api.get('/reporting/inventory/expiry', { params });

// ── AI Insights ───────────────────────────────────────────────────────────
export const runForecast = (data) => api.post('/ai/forecast', data);
export const detectAnomalies = (data) => api.post('/ai/anomalies/detect', data);
export const getAnomalies = (params) => api.get('/ai/anomalies', { params });
export const resolveAnomaly = (id, data) => api.post(`/ai/anomalies/${id}/resolve`, data);
export const nlQuery = (query) => api.post('/ai/query', { query });

export default api;
