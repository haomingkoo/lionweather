import React, { Suspense, lazy } from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';

// Each route loads only its own code: the dashboard never pulls in the map, and /haze skips the dashboard.
const App = lazy(() => import('./App').then((m) => ({ default: m.App })));
const HazePage = lazy(() => import('./haze/HazePage'));
const isHaze = window.location.pathname.replace(/\/+$/, '') === '/haze';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Suspense fallback={null}>{isHaze ? <HazePage /> : <App />}</Suspense>
  </React.StrictMode>
);
