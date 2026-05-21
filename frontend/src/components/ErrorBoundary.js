import React from 'react';

// Lazily import Sentry so the app still works if the package is absent
let Sentry = null;
try {
  Sentry = require('@sentry/react');
} catch (_) {
  // Sentry not available — continue without it
}

/**
 * Initialize Sentry once at module load time.
 * Reads REACT_APP_SENTRY_DSN from the build-time environment.
 * No-ops silently if the DSN is not configured.
 */
if (Sentry && process.env.REACT_APP_SENTRY_DSN) {
  Sentry.init({
    dsn: process.env.REACT_APP_SENTRY_DSN,
    environment: process.env.REACT_APP_ENVIRONMENT || 'production',
    // Capture 10% of transactions for performance monitoring
    tracesSampleRate: 0.1,
    // Strip PII fields before sending to Sentry
    beforeSend(event) {
      try {
        const req = event.request || {};
        const data = req.data || {};
        const PII_FIELDS = [
          'password', 'new_password', 'token', 'access_token',
          'refresh_token', 'patient_name', 'patient_phone', 'email',
        ];
        if (typeof data === 'object') {
          PII_FIELDS.forEach(f => { if (f in data) data[f] = '[Filtered]'; });
        }
      } catch (_) {}
      return event;
    },
  });
}

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, eventId: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error('[ErrorBoundary]', error, info);

    // Report to Sentry with component stack trace
    if (Sentry && process.env.REACT_APP_SENTRY_DSN) {
      const eventId = Sentry.captureException(error, {
        contexts: { react: { componentStack: info.componentStack } },
      });
      this.setState({ eventId });
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          minHeight: '100vh', display: 'flex', alignItems: 'center',
          justifyContent: 'center', background: '#f0f4f8',
        }}>
          <div style={{
            background: '#fff', borderRadius: 12, padding: '40px 48px',
            boxShadow: '0 4px 20px rgba(0,0,0,0.1)', textAlign: 'center', maxWidth: 480,
          }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>⚠️</div>
            <h2 style={{ color: '#1a2332', marginBottom: 8 }}>Something went wrong</h2>
            <p style={{ color: '#666', fontSize: 14, marginBottom: 24 }}>
              {this.state.error?.message || 'An unexpected error occurred.'}
            </p>
            {this.state.eventId && (
              <p style={{ color: '#aaa', fontSize: 12, marginBottom: 16 }}>
                Error ID: {this.state.eventId}
              </p>
            )}
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null, eventId: null });
                window.location.reload();
              }}
              style={{
                padding: '10px 24px', background: '#4fc3f7', color: '#fff',
                border: 'none', borderRadius: 8, cursor: 'pointer', fontSize: 14, fontWeight: 600,
              }}
            >
              Reload Page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
