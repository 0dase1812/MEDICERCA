import { useEffect, useState } from 'react'
import { Stethoscope } from 'lucide-react'
import { historiaClinicaApi, medicamentosApi } from '../api'
import { ApiError } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { Alert, Button, Card, Input, PageHeader, Select } from '../components/ui'

const FORM_INICIAL = { cedula_paciente: '', diagnostico_simulado: '' }

export default function RegenteHistoriaClinicaPage() {
  const { usuario } = useAuth()
  const [form, setForm] = useState(FORM_INICIAL)
  const [medicamentoIds, setMedicamentoIds] = useState([])
  const [medicamentos, setMedicamentos] = useState([])
  const [error, setError] = useState('')
  const [exito, setExito] = useState('')
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    medicamentosApi
      .listar({ limit: 200 })
      .then((pagina) => setMedicamentos(pagina.items))
      .catch(() => setMedicamentos([]))
  }, [])

  const actualizar = (campo) => (evento) => setForm((prev) => ({ ...prev, [campo]: evento.target.value }))

  const enviar = async (evento) => {
    evento.preventDefault()
    setError('')
    setExito('')
    setEnviando(true)
    try {
      await historiaClinicaApi.registrar(usuario.ips_id, {
        cedula_paciente: form.cedula_paciente,
        diagnostico_simulado: form.diagnostico_simulado,
        medicamento_ids: medicamentoIds,
      })
      setExito(`Historia clínica guardada para la cédula ${form.cedula_paciente}.`)
      setForm(FORM_INICIAL)
      setMedicamentoIds([])
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'No se pudo guardar la historia clínica.')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader
        icon={Stethoscope}
        title="Registrar historia clínica"
        description="Versión básica: diagnóstico y medicamentos formulados para un paciente de tu IPS. En un próximo sprint se amplía para editar/retirar prescripciones una por una."
      />

      <Card>
        <form className="flex flex-col gap-5" onSubmit={enviar}>
          <Input
            label="Cédula del paciente"
            required
            value={form.cedula_paciente}
            onChange={actualizar('cedula_paciente')}
          />

          <label className="block">
            <span className="mb-1.5 block text-base font-semibold text-navy-800">Diagnóstico</span>
            <textarea
              required
              rows={3}
              className="w-full rounded-xl border-2 border-slate-200 bg-white px-4 py-3 text-base text-ink shadow-sm outline-none transition placeholder:text-ink-soft/70 focus:border-brand-500 focus:ring-4 focus:ring-brand-100"
              value={form.diagnostico_simulado}
              onChange={actualizar('diagnostico_simulado')}
            />
          </label>

          <Select
            label="Medicamentos formulados (opcional)"
            multiple
            hint="Mantén Ctrl (o Cmd en Mac) para seleccionar varios."
            className="h-40"
            value={medicamentoIds.map(String)}
            onChange={(e) => setMedicamentoIds(Array.from(e.target.selectedOptions).map((o) => Number(o.value)))}
          >
            {medicamentos.map((m) => (
              <option key={m.id} value={m.id}>
                {m.nombre_comercial} ({m.dosis})
              </option>
            ))}
          </Select>

          {error && <Alert variant="error">{error}</Alert>}
          {exito && <Alert variant="success">{exito}</Alert>}

          <Button type="submit" loading={enviando} className="w-full">
            Guardar historia clínica
          </Button>
        </form>
      </Card>
    </div>
  )
}
