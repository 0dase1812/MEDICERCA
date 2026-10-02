import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { UserPlus } from 'lucide-react'
import { authApi, ipsApi } from '../api'
import { ApiError } from '../api/client'
import Captcha from '../components/Captcha'
import { Alert, Button, Card, Input, Select } from '../components/ui'
import DecorativeBackdrop from '../components/DecorativeBackdrop'

const FORM_INICIAL = { nombre: '', cedula: '', correo: '', password: '', ips_id: '', eps_id: '' }

export default function RegisterPage() {
  const navigate = useNavigate()
  const [form, setForm] = useState(FORM_INICIAL)
  const [ipsDisponibles, setIpsDisponibles] = useState([])
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [captchaToken, setCaptchaToken] = useState('')
  const captchaRef = useRef(null)

  useEffect(() => {
    ipsApi
      .listar({ limit: 200 })
      .then((pagina) => setIpsDisponibles(pagina.items))
      .catch(() => setIpsDisponibles([]))
  }, [])

  const actualizarCampo = (campo) => (evento) => setForm((prev) => ({ ...prev, [campo]: evento.target.value }))

  const enviar = async (evento) => {
    evento.preventDefault()
    setError('')
    setEnviando(true)
    try {
      const payload = {
        nombre: form.nombre,
        cedula: form.cedula,
        correo: form.correo,
        password: form.password,
        ips_id: form.ips_id ? Number(form.ips_id) : null,
        eps_id: form.eps_id ? Number(form.eps_id) : null,
        captcha_token: captchaToken,
      }
      const respuesta = await authApi.registrar(payload)
      navigate('/verificar-correo', { state: { correo: form.correo, codigoDemo: respuesta.codigo_demo } })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'No se pudo completar el registro.')
      captchaRef.current?.reiniciar()
      setCaptchaToken('')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="relative mx-auto max-w-md py-6">
      <DecorativeBackdrop variant="auth" />
      <Card className="relative">
        <div className="mb-2 grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-brand-500 to-navy-700 text-white shadow-[0_10px_20px_-10px_rgba(18,59,93,0.5)]">
          <UserPlus className="h-6 w-6" aria-hidden="true" />
        </div>
        <h1 className="text-2xl font-extrabold text-navy-800">Crea tu cuenta</h1>
        <p className="mt-1 text-base text-ink-soft">
          El registro público solo crea cuentas de paciente. Te enviaremos un código de verificación por correo.
        </p>

        <form className="mt-6 flex flex-col gap-5" onSubmit={enviar}>
          <Input label="Nombre completo" required value={form.nombre} onChange={actualizarCampo('nombre')} />
          <Input label="Cédula" required value={form.cedula} onChange={actualizarCampo('cedula')} />
          <Input
            label="Correo electrónico"
            type="email"
            autoComplete="email"
            required
            value={form.correo}
            onChange={actualizarCampo('correo')}
          />
          <Input
            label="Contraseña"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            hint="Mínimo 8 caracteres, con una mayúscula, una minúscula y un número."
            value={form.password}
            onChange={actualizarCampo('password')}
          />

          <Select label="IPS a la que perteneces" required value={form.ips_id} onChange={actualizarCampo('ips_id')}>
            <option value="">Selecciona tu IPS…</option>
            {ipsDisponibles.map((ips) => (
              <option key={ips.id} value={ips.id}>
                {ips.nombre_ficticio}
              </option>
            ))}
          </Select>

          <Input
            label="EPS (opcional)"
            type="number"
            hint="Número de identificación de tu EPS, si lo conoces."
            value={form.eps_id}
            onChange={actualizarCampo('eps_id')}
          />

          <Captcha ref={captchaRef} onCambio={setCaptchaToken} />

          {error && <Alert variant="error">{error}</Alert>}

          <Button type="submit" loading={enviando} className="mt-1 w-full">
            Crear cuenta
          </Button>
        </form>

        <p className="mt-6 text-center text-base text-ink-soft">
          ¿Ya tienes cuenta?{' '}
          <Link to="/login" className="font-semibold text-brand-700 hover:underline">
            Inicia sesión
          </Link>
        </p>
      </Card>
    </div>
  )
}
