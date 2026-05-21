import React, { createContext, useContext, useState, useCallback } from 'react';
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react';

const ToastContext = createContext(null);
let _id = 0;

function safeStr(msg) {
  if (msg === null || msg === undefined) return 'An error occurred';
  if (typeof msg === 'string') return msg;
  if (typeof msg === 'object') {
    if (msg.message) return msg.message;
    try { return JSON.stringify(msg); } catch { return 'An error occurred'; }
  }
  return String(msg);
}

const ICON = {
  success: <CheckCircle size={14} />,
  error:   <XCircle    size={14} />,
  warn:    <AlertTriangle size={13} />,
  info:    <Info       size={14} />,
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const add = useCallback((message, type = 'info', duration = 4000) => {
    const id = ++_id;
    setToasts(prev => [...prev, { id, message: safeStr(message), type }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), duration);
  }, []);

  const remove = useCallback(id => setToasts(prev => prev.filter(t => t.id !== id)), []);

  const toast = {
    success: msg => add(msg, 'success'),
    error:   msg => add(msg, 'error'),
    info:    msg => add(msg, 'info'),
    warn:    msg => add(msg, 'warn'),
  };

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div style={{
        position: 'fixed', top: 20, right: 20, zIndex: 9999,
        display: 'flex', flexDirection: 'column', gap: 10,
        pointerEvents: 'none',
      }}>
        {toasts.map(t => (
          <div key={t.id} className={`toast toast-${t.type}`}>
            <div className="toast-icon">{ICON[t.type]}</div>
            <span className="toast-msg">{t.message}</span>
            <button className="toast-close" onClick={() => remove(t.id)} style={{ color: 'var(--text-muted)' }}>
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    const noop = () => {};
    return { success: noop, error: noop, info: noop, warn: noop };
  }
  return ctx;
};
