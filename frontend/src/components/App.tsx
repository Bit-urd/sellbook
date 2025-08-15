import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Layout from './Layout'
import Dashboard from './Dashboard'
import ShopAdmin from './ShopAdmin'
import BookAdmin from './BookAdmin'
import SalesAdmin from './SalesAdmin'
import CrawlerAdmin from './CrawlerAdmin'

export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="shops" element={<ShopAdmin />} />
          <Route path="books" element={<BookAdmin />} />
          <Route path="sales" element={<SalesAdmin />} />
          <Route path="crawler" element={<CrawlerAdmin />} />
        </Route>
      </Routes>
    </Router>
  )
}