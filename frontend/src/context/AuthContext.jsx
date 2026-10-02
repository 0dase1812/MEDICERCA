import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { authApi } from '../api'
import { getToken, setToken as guardarToken } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => getToken())
  const [usuario, setUsuario] = useState(null)
  const [cargando, setCargando] = useState(true)

  const cargarUsuario = useCallback(async () => {
    const tokenActual = getToken()
    if (!tokenActual) {
      setUsuario(null)
      setCargando(false)
      return
    }
    try {
      const datos = await authApi.me()
      setUsuario(datos)
    } catch {
      guardarToken(null)
      setToken(null)
      setUsuario(null)
    } finally {
      setCargando(false)
    }
  }, [])

  useEffect(() => {
    cargarUsuario()
  }, [cargarUsuario])

  const login = async (correo, password, captchaToken) => {
    const datos = await authApi.login({ correo, password, captcha_token: captchaToken })
    guardarToken(datos.access_token)
    setToken(datos.access_token)
    await cargarUsuario()
  }

  const logout = async () => {
    try {
      await authApi.logout()
    } catch {
      // El token puede ya estar vencido; igual limpiamos la sesión local.
    }
    guardarToken(null)
    setToken(null)
    setUsuario(null)
  }

  const valor = {
    usuario,
    token,
    cargando,
    autenticado: Boolean(usuario),
    esRegente: usuario?.rol === 'regente',
    login,
    logout,
    refrescarUsuario: cargarUsuario,
  }

  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const contexto = useContext(AuthContext)
  if (!contexto) throw new Error('useAuth debe usarse dentro de <AuthProvider>')
  return contexto
}
