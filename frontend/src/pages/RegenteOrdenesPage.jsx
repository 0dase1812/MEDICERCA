import { useEffect, useMemo, useState } from 'react'
import { Check, ClipboardCheck, ExternalLink, X } from 'lucide-react'
import { medicamentosApi, ordenesApi } from '../api'
import { ApiError } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../components/Toast'
import { ahoraLegible, formatearFecha } from '../lib/format'
import { Alert, Badge, Button, Card, CenteredLoader, EmptyState, PageHeader } from '../components/ui'

export default function RegenteOrdenesPage() {
  const { usuario } = useAuth()
  const toast = useToast()
  const [ordenes, setOrdenes] = useState([])
  const [medicamentos, setMedicamentos] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [procesando, setProcesando] = useState(null)

  const medicamentosPorId = useMemo(() => new Map(medicamentos.map((m) => [m.id, m])), [medicamentos])

  const cargar = async () => {
    setCargando(true)
    setError('')
    try {
      const [pendientes, pagina] = await Promise.all([ordenesApi.pendientes(), medicamentosApi.listar({ limit: 200 })])
      setOrdenes(pendientes)
      setMedicamentos(pagina.items)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'No se pudieron cargar las órdenes pendientes.')
    } finally {
      setCargando(false)
    }
  }

  useEffect(() => {
    cargar()
  }, [])

  const resolver = async (orden, accion) => {
    setProcesando(orden.id)
    setError('')
    try {
      if (accion === 'aprobar') await ordenesApi.aprobar(usuario.ips_id, orden.id)
      else await ordenesApi.rechazar(usuario.ips_id, orden.id)
      setOrdenes((prev) => prev.filter((o) => o.id !== orden.id))
      toast.exito(`Orden #${orden.id} ${accion === 'aprobar' ? 'aprobada' : 'rechazada'}`, `El paciente fue notificado · ${ahoraLegible()}`)
    } catch (err) {
      const mensaje = err instanceof ApiError ? err.message : 'No se pudo procesar la orden.'
      setError(mensaje)
      toast.error(`No se pudo ${accion} la orden #${orden.id}`, mensaje)
    } finally {
      setProcesando(null)
    }
  }

  return (
    <div>
      <PageHeader icon={ClipboardCheck} title="Órdenes por aprobar" description="Fórmulas médicas pendientes de revisión en tu IPS." />

      {error && <Alert variant="error">{error}</Alert>}

      {cargando ? (
        <CenteredLoader label="Cargando órdenes pendientes…" />
      ) : ordenes.length === 0 ? (
        <EmptyState
          icon={ClipboardCheck}
          title="No hay órdenes pendientes"
          description="Cuando un paciente cargue una fórmula, aparecerá aquí."
        />
      ) : (
        <div className="flex flex-col gap-4">
          {ordenes.map((orden) => {
            const medicamento = medicamentosPorId.get(orden.medicamento_id)
            return (
              <Card key={orden.id} className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <p className="text-lg font-bold text-navy-800">
                      {medicamento ? medicamento.nombre_comercial : `Medicamento #${orden.medicamento_id}`}
                    </p>
                    {medicamento && <Badge color={medicamento.condicion_venta === 'RX' ? 'yellow' : 'green'}>{medicamento.condicion_venta}</Badge>}
                  </div>
                  <p className="mt-1 text-sm text-ink-soft">Paciente (cédula): {orden.usuario_cedula}</p>
                  <p className="text-sm text-ink-soft">Cargada el {formatearFecha(orden.creado_en)}</p>
                  <a
                    href={orden.archivo_url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-1 inline-flex items-center gap-1.5 text-sm font-semibold text-brand-700 hover:underline"
                  >
                    Ver fórmula adjunta
                    <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                  </a>
                </div>
                <div className="flex gap-3">
                  <Button
                    variant="secondary"
                    loading={procesando === orden.id}
                    onClick={() => resolver(orden, 'rechazar')}
                  >
                    <X className="h-5 w-5" aria-hidden="true" />
                    Rechazar
                  </Button>
                  <Button loading={procesando === orden.id} onClick={() => resolver(orden, 'aprobar')}>
                    <Check className="h-5 w-5" aria-hidden="true" />
                    Aprobar
                  </Button>
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
