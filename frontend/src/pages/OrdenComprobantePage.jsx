import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Beaker, CalendarCheck, FileCheck2, Layers, Pill, Printer, UserCheck } from 'lucide-react'
import { medicamentosApi, ordenesApi } from '../api'
import { ApiError } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { calcularFechaVigencia, formatearDuracionTratamiento, formatearFecha, formatearFechaCorta } from '../lib/format'
import { Alert, Button, Card, CenteredLoader } from '../components/ui'

export default function OrdenComprobantePage() {
  const { ipsId, ordenId } = useParams()
  const { usuario } = useAuth()
  const [orden, setOrden] = useState(null)
  const [medicamento, setMedicamento] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setCargando(true)
    setError('')
    ordenesApi
      .obtener(ipsId, ordenId)
      .then(async (datos) => {
        setOrden(datos)
        setMedicamento(await medicamentosApi.obtener(datos.medicamento_id))
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'No se pudo cargar el comprobante.'))
      .finally(() => setCargando(false))
  }, [ipsId, ordenId])

  if (cargando) return <CenteredLoader label="Cargando comprobante…" />
  if (error) return <Alert variant="error">{error}</Alert>
  if (!orden) return null

  if (orden.estado !== 'aprobada') {
    return (
      <div className="mx-auto max-w-2xl">
        <Link
          to={`/ordenes/${ipsId}/${ordenId}`}
          className="flex w-fit items-center gap-1.5 text-base font-semibold text-brand-700 hover:underline"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Volver a la orden
        </Link>
        <div className="mt-4">
          <Alert variant="warning">
            El comprobante de autorización de entrega solo está disponible para órdenes ya aprobadas.
          </Alert>
        </div>
      </div>
    )
  }

  const fechaVigencia = calcularFechaVigencia(orden.aprobado_en, medicamento?.duracion_tratamiento_dias)

  return (
    <div className="mx-auto max-w-2xl">
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <Link
          to={`/ordenes/${ipsId}/${ordenId}`}
          className="flex w-fit items-center gap-1.5 text-base font-semibold text-brand-700 hover:underline"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Volver a la orden
        </Link>
        <Button onClick={() => window.print()}>
          <Printer className="h-5 w-5" aria-hidden="true" />
          Imprimir / Guardar como PDF
        </Button>
      </div>

      <Card className="mt-4 print:border-none print:shadow-none">
        <div className="flex items-start justify-between gap-3 border-b border-slate-200 pb-5">
          <div className="flex items-center gap-3">
            <div className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-brand-500 to-navy-700 text-white shadow-[0_10px_20px_-10px_rgba(18,59,93,0.5)] print:hidden">
              <FileCheck2 className="h-6 w-6" aria-hidden="true" />
            </div>
            <div>
              <p className="text-sm font-semibold uppercase tracking-wide text-brand-700">MediCerca</p>
              <h1 className="text-xl font-extrabold text-navy-800">Comprobante de autorización de entrega</h1>
            </div>
          </div>
        </div>

        <dl className="mt-6 grid gap-5 text-base sm:grid-cols-2">
          <div>
            <dt className="text-sm font-semibold text-ink-soft">Paciente</dt>
            <dd className="mt-1 font-semibold text-navy-800">{usuario?.nombre}</dd>
          </div>
          <div>
            <dt className="text-sm font-semibold text-ink-soft">Cédula</dt>
            <dd className="mt-1 font-semibold text-navy-800">{orden.usuario_cedula}</dd>
          </div>
          <div>
            <dt className="text-sm font-semibold text-ink-soft">Orden médica</dt>
            <dd className="mt-1 font-semibold text-navy-800">#{orden.id}</dd>
          </div>
          <div>
            <dt className="flex items-center gap-1.5 text-sm font-semibold text-ink-soft">
              <UserCheck className="h-4 w-4" aria-hidden="true" /> Aprobada por
            </dt>
            <dd className="mt-1 font-semibold text-navy-800">{orden.revisado_por || '—'}</dd>
          </div>
          <div>
            <dt className="text-sm font-semibold text-ink-soft">Fecha de aprobación</dt>
            <dd className="mt-1 font-semibold text-navy-800">{formatearFecha(orden.aprobado_en)}</dd>
          </div>
          <div>
            <dt className="flex items-center gap-1.5 text-sm font-semibold text-ink-soft">
              <CalendarCheck className="h-4 w-4" aria-hidden="true" /> Próxima entrega válida hasta
            </dt>
            <dd className="mt-1 text-lg font-extrabold text-brand-700">
              {fechaVigencia ? formatearFechaCorta(fechaVigencia) : '—'}
            </dd>
          </div>
        </dl>

        <div className="mt-7 rounded-2xl border-2 border-brand-100 bg-brand-50 p-5 print:border-slate-300 print:bg-white">
          <div className="flex items-center gap-2">
            <Pill className="h-5 w-5 text-brand-700" aria-hidden="true" />
            <h2 className="text-lg font-bold text-navy-800">{medicamento?.nombre_comercial}</h2>
          </div>
          <p className="text-base text-ink-soft">{medicamento?.nombre_generico}</p>

          <dl className="mt-4 grid gap-4 text-base sm:grid-cols-2">
            <div>
              <dt className="flex items-center gap-1.5 text-sm font-semibold text-ink-soft">
                <Beaker className="h-4 w-4" aria-hidden="true" /> Dosis
              </dt>
              <dd className="mt-1 font-semibold text-navy-800">{medicamento?.dosis}</dd>
            </div>
            <div>
              <dt className="flex items-center gap-1.5 text-sm font-semibold text-ink-soft">
                <Layers className="h-4 w-4" aria-hidden="true" /> Presentación
              </dt>
              <dd className="mt-1 font-semibold text-navy-800">{medicamento?.presentacion}</dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-sm font-semibold text-ink-soft">Indicaciones de uso</dt>
              <dd className="mt-1 font-semibold text-navy-800">{medicamento?.indicaciones_uso}</dd>
            </div>
            <div>
              <dt className="text-sm font-semibold text-ink-soft">Cantidad autorizada por entrega</dt>
              <dd className="mt-1 font-semibold text-navy-800">{medicamento?.cantidad_por_entrega}</dd>
            </div>
            <div>
              <dt className="text-sm font-semibold text-ink-soft">Duración del tratamiento</dt>
              <dd className="mt-1 font-semibold text-navy-800">
                {formatearDuracionTratamiento(medicamento?.duracion_tratamiento_dias)}
              </dd>
            </div>
          </dl>
        </div>

        <p className="mt-6 text-sm text-ink-soft">
          Presenta este comprobante (impreso o en tu celular) en el punto de entrega. Es válido hasta la fecha
          indicada arriba; después de esa fecha deberás cargar una nueva orden médica.
        </p>
      </Card>
    </div>
  )
}
