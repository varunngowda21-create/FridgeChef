import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '@/lib/queryClient';
import { AuthProvider } from '@/features/auth/AuthContext';
import { AppRouter } from '@/app/Router';
import { registerSW } from 'virtual:pwa-register';
import '@/styles/globals.css';

// Register PWA service worker (app shell caching only per PRD Section 12.1)
registerSW({
  immediate: true,
  onNeedRefresh() {
    console.info('New FridgeChef app shell available.');
  },
  onOfflineReady() {
    console.info('FridgeChef app shell ready for offline launch.');
  },
});


ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AppRouter />
      </AuthProvider>
    </QueryClientProvider>
  </React.StrictMode>
);

