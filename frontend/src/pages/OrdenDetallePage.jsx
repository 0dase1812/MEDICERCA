import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, CalendarCheck, ExternalLink, FileCheck2, Truck, UserCheck } from 'lucide-react'
import { domiciliosApi, medicamentosApi, ordenesApi } from '../api'
import { ApiError } from '../api/client'
import { calcularFechaVigencia, ESTADO_DOMICILIO, ESTADO_ORDEN, formatearFecha, formatearFechaCorta } from '../lib/format'
import { Alert, Button, Card, CenteredLoader, EstadoBadge } from '../components/ui'

export default function OrdenDetallePage() {
  const { ipsId, ordenId } = useParams()
  const navigate = useNavigate()
  const [orden, setOrden] = useState(null)
  const [medicamento, setMedicamento] = useState(null)
  const [historial, setHistorial] = useState([])
  const [domicilio, setDomicilio] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setCargando(true)
    setError('')
    Promise.all([ordenesApi.obtener(ipsId, ordenId), ordenesApi.historial(ipsId, ordenId), domiciliosApi.misDomicilios()])
      .then(async ([datosOrden, datosHistorial, misDomicilios]) => {
        setOrden(datosOrden)
        setHistorial(datosHistorial)
        setDomicilio(misDomicilios.find((d) => d.orden_id === datosOrden.id) || null)
        try {
          setMedicamento(await medicamentosApi.obtener(datosOrden.medicamento_id))
        } catch {
          setMedicamento(null)
        }
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'No se pudo cargar la orden.'))
      .finally(() => setCargando(false))
  }, [ipsId, ordenId])

  if (cargando) return <CenteredLoader label="Cargando orden…" />
  if (error) return <Alert variant="error">{error}</Alert>
  if (!orden) return null

  const fechaVigencia = calcularFechaVigencia(orden.aprobado_en, medicamento?.duracion_tratamiento_dias)

  return (
    <div className="mx-auto max-w-2xl">
      <Link to="/ordenes" className="flex w-fit items-center gap-1.5 text-base font-semibold text-brand-700 hover:underline">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Volver a mis órdenes
      </Link>

      <Card className="mt-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-extrabold text-navy-800">Orden médica #{orden.id}</h1>
            <p className="text-base text-ink-soft">{medicamento ? medicamento.nombre_comercial : `Medicamento #${orden.medicamento_id}`}</p>
          </div>
          <EstadoBadge config={ESTADO_ORDEN[orden.estado]} />
        </div>

        <dl className="mt-6 grid gap-5 text-base sm:grid-cols-2">
          <div>
            <dt className="text-sm font-semibold text-ink-soft">Cargada el</dt>
            <dd className="mt-1 font-semibold text-navy-800">{formatearFecha(orden.creado_en)}</dd>
          </div>
          <div>
            <dt className="flex items-center gap-1.5 text-sm font-semibold text-ink-soft">
              <UserCheck className="h-4 w-4" aria-hidden="true" /> Revisada por
            </dt>
            <dd className="mt-1 font-semibold text-navy-800">{orden.revisado_por || 'Pendiente de revisión'}</dd>
          </div>
          {orden.estado === 'aprobada' && (
            <div>
              <dt className="flex items-center gap-1.5 text-sm font-semibold text-ink-soft">
                <CalendarCheck className="h-4 w-4" aria-hidden="true" /> Válida hasta
              </dt>
              <dd className="mt-1 font-semibold text-navy-800">
                {fechaVigencia ? formatearFechaCorta(fechaVigencia) : '—'}
              </dd>
            </div>
          )}
          <div className="sm:col-span-2">
            <dt className="text-sm font-semibold text-ink-soft">Fórmula médica</dt>
            <dd>
              <a
                href={orden.archivo_url}
                target="_blank"
                rel="noreferrer"
                className="mt-1 inline-flex items-center gap-1.5 font-semibold text-brand-700 hover:underline"
              >
                Ver archivo adjunto
                <ExternalLink className="h-4 w-4" aria-hidden="true" />
              </a>
            </dd>
          </div>
        </dl>

        {orden.estado === 'pendiente' && (
          <div className="mt-5">
            <Alert variant="warning">Tu orden está pendiente de revisión por un regente de tu IPS.</Alert>
          </div>
        )}
        {orden.estado === 'rechazada' && (
          <div className="mt-5">
            <Alert variant="error">Esta orden fue rechazada.</Alert>
          </div>
        )}
        {orden.estado === 'aprobada' && medicamento?.control_especial && (
          <div className="mt-5">
            <Alert variant="warning">
              Este medicamento es de control especial: solo se entrega por recogida presencial, no por domicilio.
            </Alert>
          </div>
        )}

        {orden.estado === 'aprobada' && (
          <div className="mt-5 flex flex-wrap gap-3">
            <Button variant="secondary" onClick={() => navigate(`/ordenes/${ipsId}/${ordenId}/comprobante`)}>
              <FileCheck2 className="h-5 w-5" aria-hidden="true" />
              Ver comprobante de autorización
            </Button>
            {!medicamento?.control_especial && domicilio && (
              <Button onClick={() => navigate(`/domicilios/${ipsId}/${domicilio.id}`)}>
                <Truck className="h-5 w-5" aria-hidden="true" />
                Ver domicilio <EstadoBadge config={ESTADO_DOMICILIO[domicilio.estado]} className="ml-1" />
              </Button>
            )}
            {!medicamento?.control_especial && !domicilio && (
              <Button onClick={() => navigate('/domicilios/nuevo', { state: { orden, medicamento } })}>
                <Truck className="h-5 w-5" aria-hidden="true" />
                Pedir a domicilio
              </Button>
            )}
          </div>
        )}
      </Card>

      <Card className="mt-6">
        <h2 className="text-lg font-bold text-navy-800">Historial de revisión</h2>
        <ol className="mt-5 flex flex-col gap-5 border-l-2 border-brand-200 pl-5">
          {historial.map((paso, indice) => (
            <li key={indice} className="relative">
              <span className="absolute -left-[1.65rem] top-1 h-3.5 w-3.5 rounded-full border-2 border-white bg-brand-500" />
              <div className="flex flex-wrap items-center gap-2.5">
                <EstadoBadge config={ESTADO_ORDEN[paso.estado]} />
                <span className="text-sm font-medium text-ink-soft">{formatearFecha(paso.registrado_en)}</span>
              </div>
              {paso.revisado_por && <p className="mt-1.5 text-sm text-ink-soft">Por {paso.revisado_por}</p>}
            </li>
          ))}
        </ol>
      </Card>
    </div>
  )
}
