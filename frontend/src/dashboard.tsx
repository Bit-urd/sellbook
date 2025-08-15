import { createRoot } from 'react-dom/client'
import SimpleApp from './components/SimpleApp'
import './styles/globals.css'

// Mount the SimpleApp component to the DOM
const container = document.getElementById('dashboard-root')
if (container) {
  const root = createRoot(container)
  root.render(<SimpleApp />)
} else {
  console.error('App mount point not found')
}