import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Clock3, Package, Pill, Plus, Search, ShieldAlert } from 'lucide-react'
import { medicamentosApi } from '../api'
import { ApiError } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { formatearDuracionTratamiento } from '../lib/format'
import { Alert, Badge, Button, Card, CenteredLoader, EmptyState, Input, PageHeader, Select } from '../components/ui'

const CONDICIONES = ['OTC', 'RX']

const FORM_INICIAL = {
  nombre_generico: '',
  nombre_comercial: '',
  dosis: '',
  presentacion: '',
  condicion_venta: 'OTC',
  control_especial: false,
  registro_sanitario: '',
  indicaciones_uso: '',
  cantidad_por_entrega: '',
  duracion_tratamiento_dias: '',
}

function FormularioNuevoMedicamento({ onCreado }) {
  const [form, setForm] = useState(FORM_INICIAL)
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  const actualizar = (campo) => (evento) => {
    const valor = evento.target.type === 'checkbox' ? evento.target.checked : evento.target.value
    setForm((prev) => ({ ...prev, [campo]: valor }))
  }

  const enviar = async (evento) => {
    evento.preventDefault()
    setError('')
    setEnviando(true)
    try {
      const creado = await medicamentosApi.crear({
        ...form,
        duracion_tratamiento_dias: Number(form.duracion_tratamiento_dias),
      })
      onCreado(creado)
      setForm(FORM_INICIAL)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'No se pudo crear el medicamento.')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Card className="mb-6 !border-brand-100 !bg-brand-50">
      <h2 className="text-lg font-bold text-navy-800">Agregar medicamento al catálogo</h2>
      <form className="mt-4 grid gap-5 sm:grid-cols-2" onSubmit={enviar}>
        <Input label="Nombre genérico" required value={form.nombre_generico} onChange={actualizar('nombre_generico')} />
        <Input label="Nombre comercial" required value={form.nombre_comercial} onChange={actualizar('nombre_comercial')} />
        <Input label="Dosis" required value={form.dosis} onChange={actualizar('dosis')} />
        <Input label="Presentación" required value={form.presentacion} onChange={actualizar('presentacion')} />
        <Select label="Condición de venta" value={form.condicion_venta} onChange={actualizar('condicion_venta')}>
          {CONDICIONES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </Select>
        <Input label="Registro sanitario (INVIMA)" required value={form.registro_sanitario} onChange={actualizar('registro_sanitario')} />
        <Input
          label="Indicaciones de uso"
          required
          placeholder="Ej.: Tomar 1 tableta cada 8 horas con alimentos"
          className="sm:col-span-2"
          value={form.indicaciones_uso}
          onChange={actualizar('indicaciones_uso')}
        />
        <Input
          label="Cantidad entregada por autorización"
          required
          placeholder="Ej.: 2 cajas"
          value={form.cantidad_por_entrega}
          onChange={actualizar('cantidad_por_entrega')}
        />
        <Input
          label="Duración del tratamiento (días)"
          type="number"
          min="1"
          required
          placeholder="Ej.: 30"
          value={form.duracion_tratamiento_dias}
          onChange={actualizar('duracion_tratamiento_dias')}
        />
        <label className="flex items-center gap-3 text-base font-medium text-navy-800 sm:col-span-2">
          <input type="checkbox" className="h-5 w-5 accent-brand-600" checked={form.control_especial} onChange={actualizar('control_especial')} />
          Medicamento de control especial (solo recogida presencial)
        </label>
        {error && (
          <div className="sm:col-span-2">
            <Alert variant="error">{error}</Alert>
          </div>
        )}
        <div className="sm:col-span-2">
          <Button type="submit" loading={enviando}>
            Guardar medicamento
          </Button>
        </div>
      </form>
    </Card>
  )
}

export default function CatalogoPage() {
  const { esRegente } = useAuth()
  const [medicamentos, setMedicamentos] = useState([])
  const [total, setTotal] = useState(0)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [busqueda, setBusqueda] = useState('')
  const [mostrarFormulario, setMostrarFormulario] = useState(false)

  const cargar = async () => {
    setCargando(true)
    setError('')
    try {
      const pagina = await medicamentosApi.listar({ skip: 0, limit: 200 })
      setMedicamentos(pagina.items)
      setTotal(pagina.total)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'No se pudo cargar el catálogo.')
    } finally {
      setCargando(false)
    }
  }

  useEffect(() => {
    cargar()
  }, [])

  const filtrados = useMemo(() => {
    const termino = busqueda.trim().toLowerCase()
    if (!termino) return medicamentos
    return medicamentos.filter(
      (m) => m.nombre_generico.toLowerCase().includes(termino) || m.nombre_comercial.toLowerCase().includes(termino),
    )
  }, [medicamentos, busqueda])

  return (
    <div>
      <PageHeader
        icon={Pill}
        title="Catálogo de medicamentos"
        description={`${total} medicamento(s) registrados en el catálogo central.`}
        action={
          esRegente && (
            <Button onClick={() => setMostrarFormulario((v) => !v)}>
              <Plus className="h-5 w-5" aria-hidden="true" />
              {mostrarFormulario ? 'Cerrar formulario' : 'Agregar medicamento'}
            </Button>
          )
        }
      />

      {esRegente && mostrarFormulario && (
        <FormularioNuevoMedicamento
          onCreado={(nuevo) => {
            setMedicamentos((prev) => [...prev, nuevo])
            setTotal((t) => t + 1)
            setMostrarFormulario(false)
          }}
        />
      )}

      <div className="relative mb-7 max-w-sm">
        <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-ink-soft" aria-hidden="true" />
        <Input
          placeholder="Buscar por nombre…"
          className="pl-11"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          aria-label="Buscar medicamento por nombre"
        />
      </div>

      {error && <Alert variant="error">{error}</Alert>}
      {cargando ? (
        <CenteredLoader label="Cargando catálogo…" />
      ) : filtrados.length === 0 ? (
        <EmptyState icon={Search} title="No hay medicamentos que coincidan" description="Prueba con otro término de búsqueda." />
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {filtrados.map((medicamento) => (
            <Link key={medicamento.id} to={`/catalogo/${medicamento.id}`}>
              <Card interactive className="h-full">
                <div className="mb-3 flex items-start justify-between gap-2">
                  <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-brand-400 to-brand-700 text-white shadow-[0_8px_16px_-8px_rgba(22,119,184,0.55)]">
                    <Pill className="h-5 w-5" aria-hidden="true" />
                  </div>
                  <Badge color={medicamento.condicion_venta === 'RX' ? 'yellow' : 'green'}>{medicamento.condicion_venta}</Badge>
                </div>
                <h3 className="text-lg font-bold text-navy-800">{medicamento.nombre_comercial}</h3>
                <p className="mt-0.5 text-base text-ink-soft">{medicamento.nombre_generico}</p>
                <p className="mt-2 text-sm text-ink-soft">
                  {medicamento.dosis} · {medicamento.presentacion}
                </p>
                <p className="mt-2 flex items-center gap-1.5 text-sm text-ink-soft">
                  <Package className="h-4 w-4 shrink-0" aria-hidden="true" />
                  {medicamento.cantidad_por_entrega}
                </p>
                <p className="mt-1 flex items-center gap-1.5 text-sm text-ink-soft">
                  <Clock3 className="h-4 w-4 shrink-0" aria-hidden="true" />
                  {formatearDuracionTratamiento(medicamento.duracion_tratamiento_dias)}
                </p>
                {medicamento.control_especial && (
                  <div className="mt-3">
                    <Badge color="red">
                      <ShieldAlert className="h-4 w-4" aria-hidden="true" />
                      Control especial
                    </Badge>
                  </div>
                )}
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
