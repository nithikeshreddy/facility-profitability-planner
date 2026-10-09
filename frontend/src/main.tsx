import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import 'leaflet/dist/leaflet.css'
import './index.css'
import Layout from './components/Layout.tsx'
import ComparePlans from './pages/ComparePlans.tsx'
import LocationDetails from './pages/LocationDetails.tsx'
import Overview from './pages/Overview.tsx'
import RenewalReview from './pages/RenewalReview.tsx'
import VendorIncentives from './pages/VendorIncentives.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Overview />} />
          <Route path="locations" element={<LocationDetails />} />
          <Route path="locations/:id" element={<LocationDetails />} />
          <Route path="compare" element={<ComparePlans />} />
          <Route path="renewals" element={<RenewalReview />} />
          <Route path="incentives" element={<VendorIncentives />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
