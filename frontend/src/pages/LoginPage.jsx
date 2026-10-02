import { useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { LogIn } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { ApiError } from '../api/client'
import Captcha from '../components/Captcha'
import { Alert, Button, Card, Input } from '../components/ui'
import DecorativeBackdrop from '../components/DecorativeBackdrop'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [correo, setCorreo] = useState(location.state?.correo || '')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [captchaToken, setCaptchaToken] = useState('')
  const captchaRef = useRef(null)

  const enviar = async (evento) => {
    evento.preventDefault()
    setError('')
    setEnviando(true)
    try {
      await login(correo, password, captchaToken)
      navigate(location.state?.from || '/')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'No se pudo iniciar sesión.')
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
          <LogIn className="h-6 w-6" aria-hidden="true" />
        </div>
        <h1 className="text-2xl font-extrabold text-navy-800">Inicia sesión</h1>
        <p className="mt-1 text-base text-ink-soft">Accede con tu correo y contraseña.</p>

        <form className="mt-6 flex flex-col gap-5" onSubmit={enviar}>
          <Input
            label="Correo electrónico"
            type="email"
            autoComplete="email"
            required
            value={correo}
            onChange={(e) => setCorreo(e.target.value)}
          />
          <Input
            label="Contraseña"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          <Captcha ref={captchaRef} onCambio={setCaptchaToken} />

          {error && <Alert variant="error">{error}</Alert>}

          <Button type="submit" loading={enviando} className="mt-1 w-full">
            Iniciar sesión
          </Button>
        </form>

        <div className="mt-6 flex flex-col items-center gap-2 text-base text-ink-soft">
          <Link to="/recuperar-clave" className="font-semibold text-brand-700 hover:underline">
            ¿Olvidaste tu contraseña?
          </Link>
          <span>
            ¿No tienes cuenta?{' '}
            <Link to="/registro" className="font-semibold text-brand-700 hover:underline">
              Regístrate
            </Link>
          </span>
        </div>
      </Card>
    </div>
  )
}
