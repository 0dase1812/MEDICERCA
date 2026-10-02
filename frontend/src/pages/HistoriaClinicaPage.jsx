import { useEffect, useMemo, useState } from 'react'
import { FileHeart, Printer, Stethoscope } from 'lucide-react'
import { historiaClinicaApi, medicamentosApi } from '../api'
import { ApiError } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { formatearFecha, formatearFechaCorta } from '../lib/format'
import { Alert, Badge, Button, Card, CenteredLoader, EmptyState, PageHeader } from '../components/ui'

export default function HistoriaClinicaPage() {
  const { usuario } = useAuth()
  const [historia, setHistoria] = useState(null)
  const [medicamentos, setMedicamentos] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [sinHistoria, setSinHistoria] = useState(false)

  useEffect(() => {
    setCargando(true)
    Promise.all([historiaClinicaApi.mia(), medicamentosApi.listar({ limit: 200 }).catch(() => ({ items: [] }))])
      .then(([datosHistoria, pagina]) => {
        setHistoria(datosHistoria)
        setMedicamentos(pagina.items)
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setSinHistoria(true)
        } else {
          setError(err instanceof ApiError ? err.message : 'No se pudo cargar tu historia clínica.')
        }
      })
      .finally(() => setCargando(false))
  }, [])

  const medicamentosPorId = useMemo(() => new Map(medicamentos.map((m) => [m.id, m])), [medicamentos])

  if (cargando) return <CenteredLoader label="Cargando tu historia clínica…" />

  return (
    <div className="mx-auto max-w-2xl">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <PageHeader icon={Stethoscope} title="Mi historia clínica" description="Información clínica simulada dentro de tu IPS." />
        {historia && !sinHistoria && (
          <div className="print:hidden">
            <Button variant="secondary" onClick={() => window.print()}>
              <Printer className="h-5 w-5" aria-hidden="true" />
              Imprimir / Guardar como PDF
            </Button>
          </div>
        )}
      </div>

      {historia && !sinHistoria && (
        <p className="mb-6 hidden text-sm text-ink-soft print:block">
          {usuario?.nombre} · Cédula {usuario?.cedula}
        </p>
      )}

      {error && <Alert variant="error">{error}</Alert>}

      {sinHistoria ? (
        <EmptyState
          icon={Stethoscope}
          title="Aún no hay historia clínica"
          description="Tu IPS todavía no ha registrado historia clínica para tu usuario."
        />
      ) : (
        historia && (
          <>
            <Card>
              <div className="flex items-start gap-4">
                <div className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-brand-500 to-navy-700 text-white shadow-[0_10px_20px_-10px_rgba(18,59,93,0.5)]">
                  <Stethoscope className="h-6 w-6" aria-hidden="true" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-ink-soft">{historia.ips_nombre}</p>
                  <h2 className="mt-0.5 text-lg font-bold text-navy-800">{historia.diagnostico_simulado}</h2>
                  <p className="mt-2 text-sm text-ink-soft">Actualizado el {formatearFecha(historia.actualizado_en)}</p>
                </div>
              </div>
            </Card>

            <h3 className="mb-4 mt-8 text-xl font-bold text-navy-800">Prescripciones</h3>
            {historia.prescripciones.length === 0 ? (
              <EmptyState icon={FileHeart} title="Sin prescripciones registradas" />
            ) : (
              <div className="flex flex-col gap-3">
                {historia.prescripciones.map((prescripcion) => {
                  const medicamento = medicamentosPorId.get(prescripcion.medicamento_id)
                  return (
                    <Card key={prescripcion.id} className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-4">
                        <div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-brand-500 to-navy-700 text-white shadow-[0_10px_20px_-10px_rgba(18,59,93,0.5)]">
                          <FileHeart className="h-5 w-5" aria-hidden="true" />
                        </div>
                        <div>
                          <p className="text-base font-bold text-navy-800">
                            {medicamento ? medicamento.nombre_comercial : `Medicamento #${prescripcion.medicamento_id}`}
                          </p>
                          <p className="text-sm text-ink-soft">Formulado el {formatearFechaCorta(prescripcion.fecha_formula)}</p>
                        </div>
                      </div>
                      <Badge color={prescripcion.vigente ? 'green' : 'slate'}>
                        {prescripcion.vigente ? 'Vigente' : 'No vigente'}
                      </Badge>
                    </Card>
                  )
                })}
              </div>
            )}
          </>
        )
      )}
    </div>
  )
}
