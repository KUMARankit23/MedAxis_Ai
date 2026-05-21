import React from 'react';
import ReactDOM from 'react-dom/client';
import './styles/design.css';
import App from './App';

const sentryDsn = process.env.REACT_APP_SENTRY_DSN;
if (sentryDsn) {
  import('@sentry/react').then(Sentry => {
    Sentry.init({
      dsn: sentryDsn,
      environment: process.env.REACT_APP_ENVIRONMENT || 'production',
      release: 'medaxis-frontend@1.0.0',
      tracesSampleRate: 0.1,
      beforeSend(event) {
        if (event.request?.data) {
          const pii = ['password', 'new_password', 'token', 'access_token', 'refresh_token'];
          pii.forEach(f => { if (event.request.data[f]) event.request.data[f] = '[Filtered]'; });
        }
        return event;
      },
    });
  }).catch(() => {});
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<React.StrictMode><App /></React.StrictMode>);
