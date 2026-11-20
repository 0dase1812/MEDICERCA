import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'
import { CheckCircle2, X, XCircle } from 'lucide-react'

/** Avisos temporales de resultado de una acción: verde = éxito, rojo = error.
 * Siempre icono + texto (nunca solo color), con aria-live para lectores de pantalla.
 * Escenario de calidad "Usabilidad 3": el paciente debe saber al instante, y sin
 * ayuda, qué pasó, cuándo y dónde. */
const ToastContext = createContext(null)
const DURACION_MS = 8000

const ESTILOS = {
  exito: { clases: 'border-emerald-200 bg-success-50', icono: CheckCircle2, colorIcono: 'text-success-600', rol: 'status' },
  error: { clases: 'border-red-200 bg-danger-50', icono: XCircle, colorIcono: 'text-danger-600', rol: 'alert' },
}

export function ToastProvider({ children }) {
  const [avisos, setAvisos] = useState([])
  const contador = useRef(0)

  const cerrar = useCallback((id) => setAvisos((prev) => prev.filter((aviso) => aviso.id !== id)), [])

  const mostrar = useCallback(
    (tipo, titulo, detalle) => {
      contador.current += 1
      const id = contador.current
      setAvisos((prev) => [...prev, { id, tipo, titulo, detalle }])
      setTimeout(() => cerrar(id), DURACION_MS)
    },
    [cerrar],
  )

  const api = useMemo(
    () => ({
      exito: (titulo, detalle) => mostrar('exito', titulo, detalle),
      error: (titulo, detalle) => mostrar('error', titulo, detalle),
    }),
    [mostrar],
  )

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        className="pointer-events-none fixed inset-x-0 top-4 z-50 flex flex-col items-center gap-3 px-4 print:hidden sm:items-end sm:px-6"
        aria-live="polite"
      >
        {avisos.map((aviso) => {
          const { clases, icono: Icono, colorIcono, rol } = ESTILOS[aviso.tipo]
          return (
            <div
              key={aviso.id}
              role={rol}
              className={`pointer-events-auto flex w-full max-w-md items-start gap-3 rounded-xl border-2 px-4 py-3.5 text-base shadow-[0_12px_32px_-12px_rgba(18,59,93,0.35)] ${clases}`}
            >
              <Icono className={`mt-0.5 h-6 w-6 shrink-0 ${colorIcono}`} aria-hidden="true" />
              <div className="flex-1 leading-snug">
                <p className="font-bold text-navy-800">{aviso.titulo}</p>
                {aviso.detalle && <p className="mt-0.5 text-sm text-ink-soft">{aviso.detalle}</p>}
              </div>
              <button
                onClick={() => cerrar(aviso.id)}
                className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-ink-soft hover:bg-white/60"
                aria-label="Cerrar aviso"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const contexto = useContext(ToastContext)
  if (!contexto) throw new Error('useToast debe usarse dentro de <ToastProvider>')
  return contexto
}
