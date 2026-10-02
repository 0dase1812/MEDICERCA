import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'

// Si no hay site key configurada (desarrollo local), el componente no
// renderiza nada y el backend tampoco exige el captcha (ver
// app.core.captcha.verificar_captcha) — así se puede trabajar sin
// necesitar una cuenta real de reCAPTCHA.
const SITE_KEY = import.meta.env.VITE_RECAPTCHA_SITE_KEY

export const captchaActivado = Boolean(SITE_KEY)

const Captcha = forwardRef(function Captcha({ onCambio }, ref) {
  const contenedorRef = useRef(null)
  const widgetIdRef = useRef(null)

  useImperativeHandle(ref, () => ({
    reiniciar: () => {
      if (window.grecaptcha && widgetIdRef.current !== null) {
        window.grecaptcha.reset(widgetIdRef.current)
      }
    },
  }))

  useEffect(() => {
    if (!SITE_KEY) return undefined

    let detenido = false
    const renderizar = () => {
      if (detenido || widgetIdRef.current !== null || !contenedorRef.current) return
      if (!window.grecaptcha || !window.grecaptcha.render) return
      widgetIdRef.current = window.grecaptcha.render(contenedorRef.current, {
        sitekey: SITE_KEY,
        callback: onCambio,
        'expired-callback': () => onCambio(''),
      })
    }

    renderizar()
    const intervalo = window.grecaptcha ? null : setInterval(renderizar, 200)
    return () => {
      detenido = true
      if (intervalo) clearInterval(intervalo)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (!SITE_KEY) return null
  return <div ref={contenedorRef} className="mt-1" />
})

export default Captcha
