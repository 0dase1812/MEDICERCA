import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { LocateFixed, MapPin, Package, Search, Truck } from 'lucide-react'
import { disponibilidadApi, domiciliosApi } from '../api'
import { ApiError } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../components/Toast'
import { ahoraLegible, enlaceMapa, formatearDistancia } from '../lib/format'
import { Alert, Button, Card, EmptyState, Input, PageHeader } from '../components/ui'

export default function CrearDomicilioPage() {
  const { usuario } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const toast = useToast()
  const orden = location.state?.orden
  const medicamento = location.state?.medicamento

  const [ciudad, setCiudad] = useState('Bogotá')
  const [ubicacion, setUbicacion] = useState(null)
  const [buscandoUbicacion, setBuscandoUbicacion] = useState(false)
  const [puntosElegibles, setPuntosElegibles] = useState(null)
  const [puntoSeleccionado, setPuntoSeleccionado] = useState(null)
  const [aviso, setAviso] = useState('')
  const [error, setError] = useState('')
  const [consultando, setConsultando] = useState(false)
  const [confirmando, setConfirmando] = useState(false)

  if (!orden) {
    return <Navigate to="/ordenes" replace />
  }

  const solicitarUbicacion = () => {
    setError('')
    if (!navigator.geolocation) {
      setError('Tu navegador no soporta geolocalización.')
      return
    }
    setBuscandoUbicacion(true)
    navigator.geolocation.getCurrentPosition(
      (posicion) => {
        setUbicacion({ lat: posicion.coords.latitude, lng: posicion.coords.longitude })
        setBuscandoUbicacion(false)
      },
      () => {
        setError('No pudimos acceder a tu ubicación.')
        setBuscandoUbicacion(false)
      },
      { enableHighAccuracy: true, timeout: 8000 },
    )
  }

  const buscarPuntos = async (evento) => {
    evento.preventDefault()
    setError('')
    if (!ubicacion) {
      setError('Primero comparte tu ubicación.')
      return
    }
    setConsultando(true)
    try {
      const respuesta = await disponibilidadApi.consultar({
        medicamento_id: orden.medicamento_id,
        lat_usuario: ubicacion.lat,
        lng_usuario: ubicacion.lng,
        ciudad_usuario: ciudad,
      })
      // Un domicilio solo puede salir de un punto de venta de TU propia IPS
      // (así lo valida el backend), aunque el buscador de disponibilidad
      // muestre resultados de las 3 IPS simuladas.
      setAviso(respuesta.aviso || '')
      const propios = respuesta.resultados.filter((r) => r.ips_id === usuario.ips_id && r.nivel !== 'no_disponible')
      setPuntosElegibles(propios)
      setPuntoSeleccionado(propios[0]?.punto_id ?? null)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'No se pudo consultar disponibilidad.')
    } finally {
      setConsultando(false)
    }
  }

  const confirmarDomicilio = async () => {
    setError('')
    if (!puntoSeleccionado) {
      setError('Selecciona un punto de venta de origen.')
      return
    }
    setConfirmando(true)
    try {
      const domicilio = await domiciliosApi.crear({
        ips_id: usuario.ips_id,
        orden_id: orden.id,
        punto_origen_id: puntoSeleccionado,
        medicamento_id: orden.medicamento_id,
      })
      const punto = puntosElegibles.find((p) => p.punto_id === puntoSeleccionado)
      toast.exito(
        `Domicilio #${domicilio.id} confirmado`,
        `Sale de ${punto?.punto_nombre} (${punto?.direccion}) · ${ahoraLegible()}`,
      )
      navigate(`/domicilios/${usuario.ips_id}/${domicilio.id}`)
    } catch (err) {
      const mensaje = err instanceof ApiError ? err.message : 'No se pudo crear el domicilio.'
      setError(mensaje)
      toast.error('No se pudo confirmar el domicilio', mensaje)
    } finally {
      setConfirmando(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader
        icon={Truck}
        title="Pedir a domicilio"
        description={`Orden #${orden.id} — ${medicamento ? medicamento.nombre_comercial : `Medicamento #${orden.medicamento_id}`}`}
      />

      <Card>
        <div className="mb-1 grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-brand-500 to-navy-700 text-white shadow-[0_10px_20px_-10px_rgba(18,59,93,0.5)]">
          <MapPin className="h-6 w-6" aria-hidden="true" />
        </div>
        <h2 className="text-lg font-bold text-navy-800">1. Elige el punto de venta de origen</h2>
        <p className="mt-1 text-base text-ink-soft">
          Solo se muestran puntos de tu propia IPS con inventario disponible.
        </p>

        <form className="mt-5 flex flex-wrap items-end gap-3" onSubmit={buscarPuntos}>
          <div className="min-w-48 flex-1">
            <Input label="Tu ciudad" value={ciudad} onChange={(e) => setCiudad(e.target.value)} required />
          </div>
          <Button type="button" variant="secondary" onClick={solicitarUbicacion} loading={buscandoUbicacion}>
            <LocateFixed className="h-5 w-5" aria-hidden="true" />
            {ubicacion ? 'Actualizar ubicación' : 'Usar mi ubicación'}
          </Button>
          <Button type="submit" loading={consultando}>
            <Search className="h-5 w-5" aria-hidden="true" />
            Buscar puntos
          </Button>
        </form>

        {error && (
          <div className="mt-4">
            <Alert variant="error">{error}</Alert>
          </div>
        )}

        {aviso && (
          <div className="mt-4">
            <Alert variant="warning">{aviso}</Alert>
          </div>
        )}

        {puntosElegibles && (
          <div className="mt-7">
            {puntosElegibles.length === 0 ? (
              <EmptyState
                icon={Package}
                title="No hay puntos de tu IPS con inventario"
                description="Prueba de nuevo más tarde o consulta disponibilidad en otras IPS desde el catálogo."
              />
            ) : (
              <div className="flex flex-col gap-3">
                {puntosElegibles.map((punto) => (
                  <label
                    key={punto.punto_id}
                    className={`flex cursor-pointer items-center justify-between gap-3 rounded-xl border-2 p-4 transition ${
                      puntoSeleccionado === punto.punto_id ? 'border-brand-500 bg-brand-50' : 'border-slate-200'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <input
                        type="radio"
                        name="punto"
                        className="h-5 w-5 accent-brand-600"
                        checked={puntoSeleccionado === punto.punto_id}
                        onChange={() => setPuntoSeleccionado(punto.punto_id)}
                      />
                      <div>
                        <p className="text-base font-bold text-navy-800">{punto.punto_nombre}</p>
                        <p className="text-sm text-ink-soft">
                          {punto.direccion} · {punto.ciudad}
                        </p>
                        <p className="mt-0.5 text-sm font-semibold text-navy-800">
                          A {formatearDistancia(punto.distancia_km)} ·{' '}
                          <a
                            href={enlaceMapa(punto.lat, punto.lng)}
                            target="_blank"
                            rel="noreferrer"
                            className="text-brand-700 hover:underline"
                          >
                            Ver en el mapa
                          </a>
                        </p>
                      </div>
                    </div>
                    <span className="text-sm font-semibold text-ink-soft">Stock: {punto.cantidad}</span>
                  </label>
                ))}
                <Button onClick={confirmarDomicilio} loading={confirmando} className="mt-2 self-start">
                  <Truck className="h-5 w-5" aria-hidden="true" />
                  Confirmar domicilio
                </Button>
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  )
}
