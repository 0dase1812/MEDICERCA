import { Outlet } from 'react-router-dom'
import Navbar from './Navbar'

export default function Layout() {
  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10 sm:px-6">
        <Outlet />
      </main>
      <footer className="border-t border-slate-200 bg-white py-7 text-center text-sm text-ink-soft print:hidden">
        <p className="font-semibold text-navy-800">MediCerca — Universidad Manuela Beltrán</p>
        <p className="mt-1">
          Por Elkin Aldana, Sebastián Ñustes, Juan David Traslaviña y Derly Sánchez · 2026 · Infraestructura tecnológica
        </p>
      </footer>
    </div>
  )
}
