import { Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { RutaProtegida, RutaRegente } from './components/RutaProtegida'

import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import VerifyEmailPage from './pages/VerifyEmailPage'
import ForgotPasswordPage from './pages/ForgotPasswordPage'
import CatalogoPage from './pages/CatalogoPage'
import MedicamentoDetallePage from './pages/MedicamentoDetallePage'
import MiCuentaPage from './pages/MiCuentaPage'
import OrdenesPage from './pages/OrdenesPage'
import OrdenDetallePage from './pages/OrdenDetallePage'
import OrdenComprobantePage from './pages/OrdenComprobantePage'
import CrearDomicilioPage from './pages/CrearDomicilioPage'
import DomiciliosPage from './pages/DomiciliosPage'
import DomicilioDetallePage from './pages/DomicilioDetallePage'
import HistoriaClinicaPage from './pages/HistoriaClinicaPage'
import RegenteOrdenesPage from './pages/RegenteOrdenesPage'
import RegenteDomiciliosPage from './pages/RegenteDomiciliosPage'
import RegenteHistoriaClinicaPage from './pages/RegenteHistoriaClinicaPage'
import NotFoundPage from './pages/NotFoundPage'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/registro" element={<RegisterPage />} />
        <Route path="/verificar-correo" element={<VerifyEmailPage />} />
        <Route path="/recuperar-clave" element={<ForgotPasswordPage />} />
        <Route path="/catalogo" element={<CatalogoPage />} />
        <Route path="/catalogo/:id" element={<MedicamentoDetallePage />} />

        <Route element={<RutaProtegida />}>
          <Route path="/mi-cuenta" element={<MiCuentaPage />} />
          <Route path="/historia-clinica" element={<HistoriaClinicaPage />} />
          <Route path="/ordenes" element={<OrdenesPage />} />
          <Route path="/ordenes/:ipsId/:ordenId" element={<OrdenDetallePage />} />
          <Route path="/ordenes/:ipsId/:ordenId/comprobante" element={<OrdenComprobantePage />} />
          <Route path="/domicilios/nuevo" element={<CrearDomicilioPage />} />
          <Route path="/domicilios" element={<DomiciliosPage />} />
          <Route path="/domicilios/:ipsId/:domicilioId" element={<DomicilioDetallePage />} />
        </Route>

        <Route element={<RutaRegente />}>
          <Route path="/regente/ordenes" element={<RegenteOrdenesPage />} />
          <Route path="/regente/domicilios" element={<RegenteDomiciliosPage />} />
          <Route path="/regente/historia-clinica" element={<RegenteHistoriaClinicaPage />} />
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
