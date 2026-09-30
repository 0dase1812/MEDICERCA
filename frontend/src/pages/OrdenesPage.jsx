import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { FileCheck2, FileText, Link2, Plus, Truck, Upload } from 'lucide-react'
import { domiciliosApi, medicamentosApi, ordenesApi } from '../api'
import { ApiError } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { ESTADO_DOMICILIO, ESTADO_ORDEN, formatearFecha } from '../lib/format'
import { comprimirImagenSiAplica } from '../lib/imagen'
import { Alert, Button, Card, CenteredLoader, EmptyState, EstadoBadge, PageHeader, Select } from '../components/ui'

const TIPOS_ARCHIVO_ACEPTADOS = 'image/jpeg,image/png,image/webp,application/pdf'

function FormularioNuevaOrden({ usuario, medicamentos, medicamentoIdInicial, onCreada }) {
  const [medicamentoId, setMedicamentoId] = useState(medicamentoIdInicial ? String(medicamentoIdInicial) : '')
  const [archivo, setArchivo] = useState(null)
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [comprimiendo, setComprimiendo] = useState(false)
  const inputArchivoRef = useRef(null)

  const enviar = async (evento) => {
    evento.preventDefault()
    setError('')
    if (!usuario.ips_id) {
      setError('Tu cuenta no tiene una IPS afiliada, así que no puedes cargar órdenes médicas.')
      return
    }
    if (!archivo) {
      setError('Selecciona una foto o un PDF de tu fórmula médica.')
      return
    }
    setEnviando(true)
    try {
      setComprimiendo(true)
      const archivoFinal = await comprimirImagenSiAplica(archivo)
      setComprimiendo(false)
      const formData = new FormData()
      formData.append('ips_id', usuario.ips_id)
      formData.append('medicamento_id', medicamentoId)
      formData.append('archivo', archivoFinal)
      const orden = await ordenesApi.crear(formData)
      onCreada(orden)
      setArchivo(null)
      if (inputArchivoRef.current) inputArchivoRef.current.value = ''
      setMedicamentoId('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'No se pudo cargar la orden médica.')
    } finally {
      setComprimiendo(false)
      setEnviando(false)
    }
  }

  return (
    <Card className="mb-6 !border-brand-100 !bg-brand-50">
      <h2 className="text-lg font-bold text-navy-800">Cargar nueva orden médica</h2>
      <p className="mt-1 text-base text-ink-soft">
        Sube una foto o un PDF de tu fórmula médica escaneada. Un regente de tu IPS la revisará.
      </p>
      <form className="mt-5 flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-end" onSubmit={enviar}>
        <div className="min-w-56 flex-1">
          <Select label="Medicamento" required value={medicamentoId} onChange={(e) => setMedicamentoId(e.target.value)}>
            <option value="">Selecciona un medicamento…</option>
            {medicamentos.map((m) => (
              <option key={m.id} value={m.id}>
                {m.nombre_comercial} ({m.condicion_venta})
              </option>
            ))}
          </Select>
        </div>
        <div className="min-w-56 flex-1">
          <label className="block" htmlFor="archivo-formula">
            <span className="mb-1.5 block text-base font-semibold text-navy-800">Foto o PDF de la fórmula</span>
            <input
              id="archivo-formula"
              ref={inputArchivoRef}
              type="file"
              required
              accept={TIPOS_ARCHIVO_ACEPTADOS}
              onChange={(e) => setArchivo(e.target.files?.[0] || null)}
              className="block w-full min-h-12 cursor-pointer rounded-xl border-2 border-slate-200 bg-white px-4 py-2.5 text-base text-ink shadow-sm outline-none transition file:mr-4 file:rounded-lg file:border-0 file:bg-brand-600 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-white hover:file:bg-brand-700 focus:border-brand-500 focus:ring-4 focus:ring-brand-100"
            />
          </label>
          <span className="mt-1.5 block text-sm text-ink-soft">JPG, PNG, WEBP o PDF · máximo 5 MB.</span>
        </div>
        <Button type="submit" loading={enviando}>
          <Upload className="h-5 w-5" aria-hidden="true" />
          {comprimiendo ? 'Comprimiendo imagen…' : 'Cargar orden'}
        </Button>
      </form>
      {error && (
        <div className="mt-4">
          <Alert variant="error">{error}</Alert>
        </div>
      )}
    </Card>
  )
}

export default function OrdenesPage() {
  const { usuario } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [ordenes, setOrdenes] = useState([])
  const [medicamentos, setMedicamentos] = useState([])
  const [domicilios, setDomicilios] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [mostrarFormulario, setMostrarFormulario] = useState(Boolean(location.state?.medicamentoId))

  const medicamentosPorId = useMemo(() => new Map(medicamentos.map((m) => [m.id, m])), [medicamentos])
  const domicilioPorOrdenId = useMemo(
    () => new Map(domicilios.filter((d) => d.estado !== 'cancelado').map((d) => [d.orden_id, d])),
    [domicilios],
  )

  const cargar = async () => {
    setCargando(true)
    setError('')
    try {
      const [misOrdenes, pagina, misDomicilios] = await Promise.all([
        ordenesApi.misOrdenes(),
        medicamentosApi.listar({ limit: 200 }),
        domiciliosApi.misDomicilios(),
      ])
      setOrdenes(misOrdenes)
      setMedicamentos(pagina.items)
      setDomicilios(misDomicilios)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'No se pudieron cargar tus órdenes.')
    } finally {
      setCargando(false)
    }
  }

  useEffect(() => {
    cargar()
  }, [])

  return (
    <div>
      <PageHeader
        icon={FileText}
        title="Mis órdenes médicas"
        description="Fórmulas que has cargado y su estado de revisión."
        action={
          <Button onClick={() => setMostrarFormulario((v) => !v)}>
            <Plus className="h-5 w-5" aria-hidden="true" />
            {mostrarFormulario ? 'Cerrar formulario' : 'Cargar orden'}
          </Button>
        }
      />

      {mostrarFormulario && (
        <FormularioNuevaOrden
          usuario={usuario}
          medicamentos={medicamentos}
          medicamentoIdInicial={location.state?.medicamentoId}
          onCreada={(nueva) => {
            setOrdenes((prev) => [nueva, ...prev])
            setMostrarFormulario(false)
          }}
        />
      )}

      {error && <Alert variant="error">{error}</Alert>}

      {cargando ? (
        <CenteredLoader label="Cargando tus órdenes…" />
      ) : ordenes.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="Todavía no has cargado ninguna orden"
          description="Cuando tengas una fórmula médica, cárgala aquí para poder pedir tu medicamento a domicilio."
        />
      ) : (
        <div className="flex flex-col gap-4">
          {ordenes.map((orden) => {
            const medicamento = medicamentosPorId.get(orden.medicamento_id)
            const domicilio = domicilioPorOrdenId.get(orden.id)
            return (
              <Card key={orden.id} className="flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-4">
                  <div className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-brand-500 to-navy-700 text-white shadow-[0_10px_20px_-10px_rgba(18,59,93,0.5)]">
                    <FileText className="h-6 w-6" aria-hidden="true" />
                  </div>
                  <div>
                    <p className="text-lg font-bold text-navy-800">
                      {medicamento ? medicamento.nombre_comercial : `Medicamento #${orden.medicamento_id}`}
                    </p>
                    <p className="text-sm text-ink-soft">Cargada el {formatearFecha(orden.creado_en)}</p>
                    {orden.revisado_por && <p className="text-sm text-ink-soft">Revisada por {orden.revisado_por}</p>}
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <EstadoBadge config={ESTADO_ORDEN[orden.estado]} />
                  {orden.estado === 'aprobada' && !medicamento?.control_especial && domicilio && (
                    <Link
                      to={`/domicilios/${usuario.ips_id}/${domicilio.id}`}
                      className="flex items-center gap-1.5 text-base font-semibold text-brand-700 hover:underline"
                    >
                      <Truck className="h-4 w-4" aria-hidden="true" />
                      Domicilio <EstadoBadge config={ESTADO_DOMICILIO[domicilio.estado]} />
                    </Link>
                  )}
                  {orden.estado === 'aprobada' && !medicamento?.control_especial && !domicilio && (
                    <Button
                      variant="secondary"
                      onClick={() =>
                        navigate('/domicilios/nuevo', {
                          state: { orden, medicamento },
                        })
                      }
                    >
                      <Truck className="h-5 w-5" aria-hidden="true" />
                      Pedir a domicilio
                    </Button>
                  )}
                  {orden.estado === 'aprobada' && (
                    <Link
                      to={`/ordenes/${usuario.ips_id}/${orden.id}/comprobante`}
                      className="flex items-center gap-1.5 text-base font-semibold text-brand-700 hover:underline"
                    >
                      <FileCheck2 className="h-4 w-4" aria-hidden="true" />
                      Ver comprobante
                    </Link>
                  )}
                  <Link
                    to={`/ordenes/${usuario.ips_id}/${orden.id}`}
                    className="flex items-center gap-1.5 text-base font-semibold text-brand-700 hover:underline"
                  >
                    <Link2 className="h-4 w-4" aria-hidden="true" />
                    Ver detalle
                  </Link>
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
