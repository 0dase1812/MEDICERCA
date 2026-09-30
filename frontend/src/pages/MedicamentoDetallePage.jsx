import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Beaker, Clock3, FileText, Layers, ListChecks, LocateFixed, MapPin, Package, Search, ShieldAlert } from 'lucide-react'
import { disponibilidadApi, medicamentosApi } from '../api'
import { ApiError } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { formatearDuracionTratamiento, NIVEL_DISPONIBILIDAD } from '../lib/format'
import { Alert, Badge, Button, Card, CenteredLoader, EmptyState, EstadoBadge, Input } from '../components/ui'

function useGeolocalizacion() {
  const [ubicacion, setUbicacion] = useState(null)
  const [error, setError] = useState('')
  const [buscando, setBuscando] = useState(false)

  const solicitar = () => {
    setError('')
    if (!navigator.geolocation) {
      setError('Tu navegador no soporta geolocalización. Ingresa tu ubicación manualmente si es necesario.')
      return
    }
    setBuscando(true)
    navigator.geolocation.getCurrentPosition(
      (posicion) => {
        setUbicacion({ lat: posicion.coords.latitude, lng: posicion.coords.longitude })
        setBuscando(false)
      },
      () => {
        setError('No pudimos acceder a tu ubicación. Puedes escribir tus coordenadas manualmente.')
        setBuscando(false)
      },
      { enableHighAccuracy: true, timeout: 8000 },
    )
  }

  return { ubicacion, error, buscando, solicitar }
}

export default function MedicamentoDetallePage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { autenticado } = useAuth()
  const [medicamento, setMedicamento] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')

  const { ubicacion, error: errorUbicacion, buscando, solicitar } = useGeolocalizacion()
  const [ciudad, setCiudad] = useState('Bogotá')
  const [resultados, setResultados] = useState(null)
  const [errorDisponibilidad, setErrorDisponibilidad] = useState('')
  const [consultando, setConsultando] = useState(false)

  useEffect(() => {
    setCargando(true)
    medicamentosApi
      .obtener(id)
      .then(setMedicamento)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'No se pudo cargar el medicamento.'))
      .finally(() => setCargando(false))
  }, [id])

  const consultarDisponibilidad = async (evento) => {
    evento.preventDefault()
    setErrorDisponibilidad('')
    if (!ubicacion) {
      setErrorDisponibilidad('Primero comparte tu ubicación o ingrésala manualmente.')
      return
    }
    setConsultando(true)
    try {
      const datos = await disponibilidadApi.consultar({
        medicamento_id: Number(id),
        lat_usuario: ubicacion.lat,
        lng_usuario: ubicacion.lng,
        ciudad_usuario: ciudad,
      })
      setResultados(datos)
    } catch (err) {
      setErrorDisponibilidad(err instanceof ApiError ? err.message : 'No se pudo consultar disponibilidad.')
    } finally {
      setConsultando(false)
    }
  }

  if (cargando) return <CenteredLoader label="Cargando medicamento…" />
  if (error) return <Alert variant="error">{error}</Alert>
  if (!medicamento) return null

  return (
    <div className="flex flex-col gap-6">
      <Link to="/catalogo" className="flex w-fit items-center gap-1.5 text-base font-semibold text-brand-700 hover:underline">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Volver al catálogo
      </Link>

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-extrabold text-navy-800">{medicamento.nombre_comercial}</h1>
            <p className="text-base text-ink-soft">{medicamento.nombre_generico}</p>
          </div>
          <div className="flex gap-2">
            <Badge color={medicamento.condicion_venta === 'RX' ? 'yellow' : 'green'}>{medicamento.condicion_venta}</Badge>
            {medicamento.control_especial && (
              <Badge color="red">
                <ShieldAlert className="h-4 w-4" aria-hidden="true" />
                Control especial
              </Badge>
            )}
          </div>
        </div>
        <dl className="mt-6 grid grid-cols-2 gap-5 text-base sm:grid-cols-4">
          <div>
            <dt className="flex items-center gap-1.5 text-sm font-semibold text-ink-soft">
              <Beaker className="h-4 w-4" aria-hidden="true" /> Dosis
            </dt>
            <dd className="mt-1 font-semibold text-navy-800">{medicamento.dosis}</dd>
          </div>
          <div>
            <dt className="flex items-center gap-1.5 text-sm font-semibold text-ink-soft">
              <Layers className="h-4 w-4" aria-hidden="true" /> Presentación
            </dt>
            <dd className="mt-1 font-semibold text-navy-800">{medicamento.presentacion}</dd>
          </div>
          <div className="col-span-2">
            <dt className="flex items-center gap-1.5 text-sm font-semibold text-ink-soft">
              <FileText className="h-4 w-4" aria-hidden="true" /> Registro sanitario
            </dt>
            <dd className="mt-1 font-semibold text-navy-800">{medicamento.registro_sanitario}</dd>
          </div>
        </dl>

        <dl className="mt-6 grid gap-5 border-t border-slate-100 pt-6 text-base sm:grid-cols-3">
          <div className="sm:col-span-3">
            <dt className="flex items-center gap-1.5 text-sm font-semibold text-ink-soft">
              <ListChecks className="h-4 w-4" aria-hidden="true" /> Indicaciones de uso
            </dt>
            <dd className="mt-1 font-semibold text-navy-800">{medicamento.indicaciones_uso}</dd>
          </div>
          <div>
            <dt className="flex items-center gap-1.5 text-sm font-semibold text-ink-soft">
              <Package className="h-4 w-4" aria-hidden="true" /> Cantidad por entrega
            </dt>
            <dd className="mt-1 font-semibold text-navy-800">{medicamento.cantidad_por_entrega}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="flex items-center gap-1.5 text-sm font-semibold text-ink-soft">
              <Clock3 className="h-4 w-4" aria-hidden="true" /> Duración del tratamiento
            </dt>
            <dd className="mt-1 font-semibold text-navy-800">
              {formatearDuracionTratamiento(medicamento.duracion_tratamiento_dias)}
            </dd>
          </div>
        </dl>

        {medicamento.condicion_venta === 'RX' && (
          <div className="mt-5">
            <Alert variant="warning">
              Este medicamento requiere fórmula médica aprobada por tu IPS antes de poder pedirlo a domicilio.
              {medicamento.control_especial && ' Al ser de control especial, solo se entrega por recogida presencial.'}
            </Alert>
          </div>
        )}

        {autenticado && !medicamento.control_especial && (
          <div className="mt-5">
            <Button
              variant="secondary"
              onClick={() => navigate('/ordenes', { state: { medicamentoId: medicamento.id } })}
            >
              <FileText className="h-5 w-5" aria-hidden="true" />
              Cargar orden médica para este medicamento
            </Button>
          </div>
        )}
      </Card>

      <Card>
        <div className="mb-1 grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-brand-500 to-navy-700 text-white shadow-[0_10px_20px_-10px_rgba(18,59,93,0.5)]">
          <MapPin className="h-6 w-6" aria-hidden="true" />
        </div>
        <h2 className="text-lg font-bold text-navy-800">Consultar disponibilidad cercana</h2>
        <p className="mt-1 text-base text-ink-soft">
          Comparte tu ubicación para ver en qué puntos de venta hay inventario, ordenados por cercanía.
        </p>

        <form className="mt-5 flex flex-wrap items-end gap-3" onSubmit={consultarDisponibilidad}>
          <div className="min-w-48 flex-1">
            <Input label="Tu ciudad" value={ciudad} onChange={(e) => setCiudad(e.target.value)} required />
          </div>
          <Button type="button" variant="secondary" onClick={solicitar} loading={buscando}>
            <LocateFixed className="h-5 w-5" aria-hidden="true" />
            {ubicacion ? 'Actualizar ubicación' : 'Usar mi ubicación'}
          </Button>
          <Button type="submit" loading={consultando}>
            <Search className="h-5 w-5" aria-hidden="true" />
            Buscar disponibilidad
          </Button>
        </form>

        {ubicacion && (
          <p className="mt-3 text-sm text-ink-soft">
            Ubicación: {ubicacion.lat.toFixed(4)}, {ubicacion.lng.toFixed(4)}
          </p>
        )}
        {errorUbicacion && (
          <div className="mt-3">
            <Alert variant="warning">{errorUbicacion}</Alert>
          </div>
        )}
        {errorDisponibilidad && (
          <div className="mt-3">
            <Alert variant="error">{errorDisponibilidad}</Alert>
          </div>
        )}

        {resultados && (
          <div className="mt-7">
            {resultados.length === 0 ? (
              <EmptyState icon={MapPin} title="Sin resultados" description="No encontramos inventario para este medicamento." />
            ) : (
              <ul className="flex flex-col gap-3">
                {resultados.map((resultado, indice) => (
                  <li
                    key={`${resultado.ips_id}-${resultado.punto_id}-${indice}`}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-xl border-2 border-slate-100 p-4"
                  >
                    <div>
                      <p className="text-base font-bold text-navy-800">{resultado.punto_nombre}</p>
                      <p className="text-sm text-ink-soft">
                        {resultado.ciudad} · {resultado.ips_nombre}
                      </p>
                      {resultado.fecha_reabastecimiento && (
                        <p className="mt-0.5 text-sm text-ink-soft">Reabastece: {resultado.fecha_reabastecimiento}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-semibold text-ink-soft">Cantidad: {resultado.cantidad}</span>
                      <EstadoBadge config={NIVEL_DISPONIBILIDAD[resultado.nivel]} />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </Card>
    </div>
  )
}
