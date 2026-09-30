import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, MapPin, XCircle } from 'lucide-react'
import { domiciliosApi } from '../api'
import { ApiError } from '../api/client'
import { ESTADO_DOMICILIO, ESTADOS_DOMICILIO_CANCELABLES, formatearFecha } from '../lib/format'
import { Alert, Button, Card, CenteredLoader, EstadoBadge } from '../components/ui'

export default function DomicilioDetallePage() {
  const { ipsId, domicilioId } = useParams()
  const [domicilio, setDomicilio] = useState(null)
  const [historial, setHistorial] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [errorCancelar, setErrorCancelar] = useState('')
  const [cancelando, setCancelando] = useState(false)

  const cargar = () => {
    setCargando(true)
    setError('')
    return Promise.all([domiciliosApi.obtener(ipsId, domicilioId), domiciliosApi.historial(ipsId, domicilioId)])
      .then(([datosDomicilio, datosHistorial]) => {
        setDomicilio(datosDomicilio)
        setHistorial(datosHistorial)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'No se pudo cargar el domicilio.'))
      .finally(() => setCargando(false))
  }

  useEffect(() => {
    cargar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ipsId, domicilioId])

  const cancelar = async () => {
    if (!window.confirm('¿Seguro que quieres cancelar este domicilio?')) return
    setErrorCancelar('')
    setCancelando(true)
    try {
      await domiciliosApi.cancelar(ipsId, domicilioId)
      await cargar()
    } catch (err) {
      setErrorCancelar(err instanceof ApiError ? err.message : 'No se pudo cancelar el domicilio.')
    } finally {
      setCancelando(false)
    }
  }

  if (cargando) return <CenteredLoader label="Cargando domicilio…" />
  if (error) return <Alert variant="error">{error}</Alert>
  if (!domicilio) return null

  return (
    <div className="mx-auto max-w-2xl">
      <Link to="/domicilios" className="flex w-fit items-center gap-1.5 text-base font-semibold text-brand-700 hover:underline">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Volver a mis domicilios
      </Link>

      <Card className="mt-4">
        <div className="flex items-center justify-between gap-3">
          <h1 className="text-xl font-extrabold text-navy-800">Domicilio #{domicilio.id}</h1>
          <EstadoBadge config={ESTADO_DOMICILIO[domicilio.estado]} />
        </div>
        <p className="mt-1 text-base text-ink-soft">Orden médica asociada #{domicilio.orden_id}</p>
        {domicilio.lat_actual != null && (
          <p className="mt-3 flex items-center gap-1.5 text-base text-navy-800">
            <MapPin className="h-5 w-5 text-brand-600" aria-hidden="true" />
            Última posición conocida: {domicilio.lat_actual}, {domicilio.lng_actual}
          </p>
        )}

        {ESTADOS_DOMICILIO_CANCELABLES.has(domicilio.estado) && (
          <div className="mt-5">
            <Button variant="destructive" loading={cancelando} onClick={cancelar}>
              <XCircle className="h-5 w-5" aria-hidden="true" />
              Cancelar domicilio
            </Button>
          </div>
        )}
        {errorCancelar && (
          <div className="mt-3">
            <Alert variant="error">{errorCancelar}</Alert>
          </div>
        )}
      </Card>

      <Card className="mt-6">
        <h2 className="text-lg font-bold text-navy-800">Línea de tiempo</h2>
        <ol className="mt-5 flex flex-col gap-5 border-l-2 border-brand-200 pl-5">
          {historial.map((paso, indice) => (
            <li key={indice} className="relative">
              <span className="absolute -left-[1.65rem] top-1 h-3.5 w-3.5 rounded-full border-2 border-white bg-brand-500" />
              <div className="flex flex-wrap items-center gap-2.5">
                <EstadoBadge config={ESTADO_DOMICILIO[paso.estado]} />
                <span className="text-sm font-medium text-ink-soft">{formatearFecha(paso.registrado_en)}</span>
              </div>
              {paso.lat_actual != null && (
                <p className="mt-1.5 text-sm text-ink-soft">
                  Posición: {paso.lat_actual}, {paso.lng_actual}
                </p>
              )}
            </li>
          ))}
        </ol>
      </Card>
    </div>
  )
}
