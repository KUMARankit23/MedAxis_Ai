import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Inventory from './pages/Inventory';
import Billing from './pages/Billing';
import Replenishment from './pages/Replenishment';
import AIInsights from './pages/AIInsights';
import Reports from './pages/Reports';
import AuditLogs from './pages/AuditLogs';

function ProtectedRoute({ children, roles }) {
  const { user, loading } = useAuth();
  if (loading) return <div style={{ padding: 40, textAlign: 'center' }}>Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />;
  return <Layout>{children}</Layout>;
}

function AppRoutes() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" /> : <Login />} />
      <Route path="/" element={<ProtectedRoute roles={['admin','supervisor']}><Dashboard /></ProtectedRoute>} />
      <Route path="/inventory" element={<ProtectedRoute><Inventory /></ProtectedRoute>} />
      <Route path="/billing" element={<ProtectedRoute><Billing /></ProtectedRoute>} />
      <Route path="/replenishment" element={<ProtectedRoute roles={['admin','supervisor']}><Replenishment /></ProtectedRoute>} />
      <Route path="/ai" element={<ProtectedRoute roles={['admin','supervisor']}><AIInsights /></ProtectedRoute>} />
      <Route path="/reports" element={<ProtectedRoute roles={['admin','supervisor']}><Reports /></ProtectedRoute>} />
      <Route path="/audit" element={<ProtectedRoute roles={['admin']}><AuditLogs /></ProtectedRoute>} />
      <Route path="*" element={<Navigate to="/" />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  );
}
