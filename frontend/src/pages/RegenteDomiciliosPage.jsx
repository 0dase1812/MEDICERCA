import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { RefreshCw, Truck } from 'lucide-react'
import { domiciliosApi } from '../api'
import { ApiError } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { ahoraLegible, ESTADO_DOMICILIO } from '../lib/format'
import { useToast } from '../components/Toast'
import { Alert, Button, Card, CenteredLoader, EmptyState, EstadoBadge, PageHeader, Select } from '../components/ui'

const ESTADOS = ['confirmado', 'en_alistamiento', 'en_camino', 'entregado']

function FilaDomicilio({ domicilio, ipsId, onActualizado }) {
  const toast = useToast()
  const [nuevoEstado, setNuevoEstado] = useState(domicilio.estado)
  const [lat, setLat] = useState('')
  const [lng, setLng] = useState('')
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  const actualizar = async () => {
    setError('')
    setEnviando(true)
    try {
      const payload = { estado: nuevoEstado }
      if (lat !== '') payload.lat_actual = Number(lat)
      if (lng !== '') payload.lng_actual = Number(lng)
      const actualizado = await domiciliosApi.actualizarEstado(ipsId, domicilio.id, payload)
      onActualizado(actualizado)
      toast.exito(`Domicilio #${domicilio.id} actualizado`, `Nuevo estado: ${ESTADO_DOMICILIO[actualizado.estado].etiqueta} · ${ahoraLegible()}`)
    } catch (err) {
      const mensaje = err instanceof ApiError ? err.message : 'No se pudo actualizar el estado.'
      setError(mensaje)
      toast.error('No se pudo actualizar el estado', mensaje)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-brand-500 to-navy-700 text-white shadow-[0_10px_20px_-10px_rgba(18,59,93,0.5)]">
            <Truck className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <Link to={`/domicilios/${ipsId}/${domicilio.id}`} className="text-lg font-bold text-navy-800 hover:underline">
              Domicilio #{domicilio.id}
            </Link>
            <p className="text-sm text-ink-soft">Orden médica #{domicilio.orden_id}</p>
          </div>
        </div>
        <EstadoBadge config={ESTADO_DOMICILIO[domicilio.estado]} />
      </div>

      <div className="mt-5 flex flex-wrap items-end gap-3">
        <div className="min-w-44">
          <Select label="Nuevo estado" value={nuevoEstado} onChange={(e) => setNuevoEstado(e.target.value)}>
            {ESTADOS.map((estado) => (
              <option key={estado} value={estado}>
                {ESTADO_DOMICILIO[estado].etiqueta}
              </option>
            ))}
          </Select>
        </div>
        <div className="w-32">
          <label className="block text-sm" htmlFor={`lat-${domicilio.id}`}>
            <span className="mb-1.5 block font-semibold text-navy-800">Lat (opc.)</span>
            <input
              id={`lat-${domicilio.id}`}
              className="min-h-12 w-full rounded-xl border-2 border-slate-200 px-3 py-3 text-base shadow-sm outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-100"
              value={lat}
              onChange={(e) => setLat(e.target.value)}
            />
          </label>
        </div>
        <div className="w-32">
          <label className="block text-sm" htmlFor={`lng-${domicilio.id}`}>
            <span className="mb-1.5 block font-semibold text-navy-800">Lng (opc.)</span>
            <input
              id={`lng-${domicilio.id}`}
              className="min-h-12 w-full rounded-xl border-2 border-slate-200 px-3 py-3 text-base shadow-sm outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-100"
              value={lng}
              onChange={(e) => setLng(e.target.value)}
            />
          </label>
        </div>
        <Button loading={enviando} onClick={actualizar}>
          <RefreshCw className="h-5 w-5" aria-hidden="true" />
          Actualizar
        </Button>
      </div>
      {error && (
        <div className="mt-4">
          <Alert variant="error">{error}</Alert>
        </div>
      )}
    </Card>
  )
}

export default function RegenteDomiciliosPage() {
  const { usuario } = useAuth()
  const [domicilios, setDomicilios] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    domiciliosApi
      .activos()
      .then(setDomicilios)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'No se pudieron cargar los domicilios activos.'))
      .finally(() => setCargando(false))
  }, [])

  const manejarActualizacion = (domicilioActualizado) => {
    setDomicilios((prev) =>
      domicilioActualizado.estado === 'entregado'
        ? prev.filter((d) => d.id !== domicilioActualizado.id)
        : prev.map((d) => (d.id === domicilioActualizado.id ? domicilioActualizado : d)),
    )
  }

  return (
    <div>
      <PageHeader icon={Truck} title="Domicilios activos" description="Pedidos sin entregar en tu IPS. Actualiza su estado logístico aquí." />

      {error && <Alert variant="error">{error}</Alert>}

      {cargando ? (
        <CenteredLoader label="Cargando domicilios activos…" />
      ) : domicilios.length === 0 ? (
        <EmptyState icon={Truck} title="No hay domicilios activos" description="Todos los pedidos de tu IPS ya fueron entregados." />
      ) : (
        <div className="flex flex-col gap-4">
          {domicilios.map((domicilio) => (
            <FilaDomicilio
              key={domicilio.id}
              domicilio={domicilio}
              ipsId={usuario.ips_id}
              onActualizado={manejarActualizacion}
            />
          ))}
        </div>
      )}
    </div>
  )
}
