import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  ClipboardCheck,
  FileText,
  LogOut,
  Menu,
  Pill,
  Stethoscope,
  Truck,
  User,
  X,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'

const linkClass = ({ isActive }) =>
  `flex items-center gap-2 rounded-xl px-3.5 py-2.5 text-base font-semibold transition ${
    isActive ? 'bg-brand-50 text-brand-700' : 'text-ink-soft hover:bg-slate-100 hover:text-navy-800'
  }`

export default function Navbar() {
  const { usuario, autenticado, esRegente, logout } = useAuth()
  const navigate = useNavigate()
  const [menuAbierto, setMenuAbierto] = useState(false)

  const cerrarSesion = async () => {
    await logout()
    setMenuAbierto(false)
    navigate('/')
  }

  const enlacesPaciente = [
    { to: '/catalogo', label: 'Catálogo', icon: Pill },
    { to: '/ordenes', label: 'Mis órdenes', icon: FileText },
    { to: '/domicilios', label: 'Mis domicilios', icon: Truck },
    { to: '/historia-clinica', label: 'Historia clínica', icon: Stethoscope },
  ]

  const enlacesRegente = [
    { to: '/catalogo', label: 'Catálogo', icon: Pill },
    { to: '/regente/ordenes', label: 'Órdenes por aprobar', icon: ClipboardCheck },
    { to: '/regente/domicilios', label: 'Domicilios activos', icon: Truck },
    { to: '/regente/historia-clinica', label: 'Historia clínica', icon: Stethoscope },
  ]

  const enlaces = autenticado ? (esRegente ? enlacesRegente : enlacesPaciente) : [{ to: '/catalogo', label: 'Catálogo', icon: Pill }]

  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <div className="flex items-center gap-6">
          <NavLink to="/" className="flex items-center gap-2.5 text-xl font-extrabold text-navy-800">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-brand-500 to-navy-800 text-white shadow-[0_6px_14px_-6px_rgba(18,59,93,0.6)]">
              <Pill className="h-5 w-5" aria-hidden="true" />
            </span>
            MediCerca
          </NavLink>
          <nav className="hidden items-center gap-1 lg:flex">
            {enlaces.map((enlace) => (
              <NavLink key={enlace.to} to={enlace.to} className={linkClass}>
                <enlace.icon className="h-5 w-5" aria-hidden="true" />
                {enlace.label}
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="hidden items-center gap-3 lg:flex">
          {autenticado ? (
            <>
              <NavLink
                to="/mi-cuenta"
                className="flex items-center gap-2.5 rounded-xl px-2 py-1.5 text-base text-ink-soft hover:bg-slate-100 hover:text-navy-800"
              >
                <span className="grid h-9 w-9 place-items-center rounded-full bg-gradient-to-br from-brand-500 to-navy-700 text-sm font-bold text-white shadow-[0_4px_10px_-4px_rgba(18,59,93,0.5)]">
                  {usuario.nombre?.charAt(0)?.toUpperCase() || <User className="h-4 w-4" aria-hidden="true" />}
                </span>
                <span className="font-semibold text-navy-800">
                  {usuario.nombre}
                  {esRegente && <span className="ml-1.5 text-sm font-medium text-brand-600">· regente</span>}
                </span>
              </NavLink>
              <button
                onClick={cerrarSesion}
                className="flex items-center gap-2 rounded-xl border-2 border-slate-200 px-4 py-2.5 text-base font-semibold text-navy-800 hover:border-brand-300 hover:bg-brand-50"
              >
                <LogOut className="h-5 w-5" aria-hidden="true" />
                Salir
              </button>
            </>
          ) : (
            <>
              <NavLink to="/login" className="rounded-xl px-4 py-2.5 text-base font-semibold text-navy-800 hover:bg-slate-100">
                Iniciar sesión
              </NavLink>
              <NavLink
                to="/registro"
                className="rounded-xl bg-brand-600 px-4 py-2.5 text-base font-semibold text-white hover:bg-brand-700"
              >
                Crear cuenta
              </NavLink>
            </>
          )}
        </div>

        <button
          className="grid h-11 w-11 place-items-center rounded-xl border-2 border-slate-200 text-navy-800 lg:hidden"
          onClick={() => setMenuAbierto((abierto) => !abierto)}
          aria-label={menuAbierto ? 'Cerrar menú' : 'Abrir menú'}
          aria-expanded={menuAbierto}
        >
          {menuAbierto ? <X className="h-6 w-6" aria-hidden="true" /> : <Menu className="h-6 w-6" aria-hidden="true" />}
        </button>
      </div>

      {menuAbierto && (
        <div className="border-t border-slate-200 bg-white px-4 py-3 lg:hidden">
          <nav className="flex flex-col gap-1">
            {enlaces.map((enlace) => (
              <NavLink key={enlace.to} to={enlace.to} className={linkClass} onClick={() => setMenuAbierto(false)}>
                <enlace.icon className="h-5 w-5" aria-hidden="true" />
                {enlace.label}
              </NavLink>
            ))}
            {autenticado ? (
              <>
                <NavLink to="/mi-cuenta" className={linkClass} onClick={() => setMenuAbierto(false)}>
                  <User className="h-5 w-5" aria-hidden="true" />
                  Mi cuenta {esRegente && '· regente'}
                </NavLink>
                <button
                  onClick={cerrarSesion}
                  className="flex items-center gap-2 rounded-xl px-3.5 py-2.5 text-left text-base font-semibold text-danger-600"
                >
                  <LogOut className="h-5 w-5" aria-hidden="true" />
                  Salir
                </button>
              </>
            ) : (
              <>
                <NavLink to="/login" className={linkClass} onClick={() => setMenuAbierto(false)}>
                  Iniciar sesión
                </NavLink>
                <NavLink to="/registro" className={linkClass} onClick={() => setMenuAbierto(false)}>
                  Crear cuenta
                </NavLink>
              </>
            )}
          </nav>
        </div>
      )}
    </header>
  )
}
