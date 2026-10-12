import React from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import { HomePage } from './pages/HomePage';

const root = createRoot(document.getElementById('root')!);

root.render(
  <React.StrictMode>
    <HomePage />
  </React.StrictMode>
);