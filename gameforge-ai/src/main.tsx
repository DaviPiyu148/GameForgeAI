import React from 'react'
import ReactDOM from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import App from './App.tsx'
import { AppProvider } from './context/AppContext.tsx'

// Local fonts (replaces Google Fonts CDN)
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/700.css'
import '@fontsource/press-start-2p/400.css'
import '@fontsource/space-grotesk/400.css'
import '@fontsource/space-grotesk/500.css'
import '@fontsource/space-grotesk/700.css'

// Local Material Symbols (replaces Google CDN)
import 'material-symbols/outlined.css'

import './styles/index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AppProvider>
      <HashRouter>
        <App />
      </HashRouter>
    </AppProvider>
  </React.StrictMode>
)
