import { createRoot } from 'react-dom/client'
import App from './components/App'
import './styles/globals.css'

// Mount the App component to the DOM
const container = document.getElementById('root')
if (container) {
  const root = createRoot(container)
  root.render(<App />)
} else {
  console.error('App mount point not found')
}