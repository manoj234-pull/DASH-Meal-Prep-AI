import React from 'react';
import { createRoot } from 'react-dom/client';
import MealPrepApp from './App';
import './index.css';
import { AppStateProvider } from './state';

const root = document.getElementById('root');

if (!root) {
  throw new Error('The application root element is missing.');
}

createRoot(root).render(
  <React.StrictMode>
    <AppStateProvider>
      <MealPrepApp />
    </AppStateProvider>
  </React.StrictMode>,
);
