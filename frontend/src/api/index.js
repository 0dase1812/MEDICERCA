import { api } from './client'

export const authApi = {
  registrar: (payload) => api.post('/api/v1/auth/register', payload),
  verificarRegistro: (payload) => api.post('/api/v1/auth/verificar-registro', payload),
  login: (payload) => api.post('/api/v1/auth/login', payload),
  solicitarCambioPassword: (payload) => api.post('/api/v1/auth/solicitar-cambio-password', payload),
  confirmarCambioPassword: (payload) => api.post('/api/v1/auth/confirmar-cambio-password', payload),
  logout: () => api.post('/api/v1/auth/logout', undefined, { auth: true }),
  me: () => api.get('/api/v1/auth/me', undefined, { auth: true }),
}

export const medicamentosApi = {
  listar: (params) => api.get('/api/v1/medicamentos', params),
  obtener: (id) => api.get(`/api/v1/medicamentos/${id}`),
  crear: (payload) => api.post('/api/v1/medicamentos', payload, { auth: true }),
}

export const ipsApi = {
  listar: (params) => api.get('/api/v1/ips', params),
}

export const disponibilidadApi = {
  consultar: (payload) => api.post('/api/v1/disponibilidad', payload),
}

export const ordenesApi = {
  crear: (formData) => api.post('/api/v1/ordenes', formData, { auth: true }),
  misOrdenes: () => api.get('/api/v1/ordenes/mias', undefined, { auth: true }),
  pendientes: () => api.get('/api/v1/ordenes/pendientes', undefined, { auth: true }),
  obtener: (ipsId, ordenId) => api.get(`/api/v1/ordenes/${ipsId}/${ordenId}`, undefined, { auth: true }),
  historial: (ipsId, ordenId) => api.get(`/api/v1/ordenes/${ipsId}/${ordenId}/historial`, undefined, { auth: true }),
  aprobar: (ipsId, ordenId) => api.post(`/api/v1/ordenes/${ipsId}/${ordenId}/aprobar`, undefined, { auth: true }),
  rechazar: (ipsId, ordenId) => api.post(`/api/v1/ordenes/${ipsId}/${ordenId}/rechazar`, undefined, { auth: true }),
}

export const domiciliosApi = {
  crear: (payload) => api.post('/api/v1/domicilios', payload, { auth: true }),
  misDomicilios: () => api.get('/api/v1/domicilios/mias', undefined, { auth: true }),
  activos: () => api.get('/api/v1/domicilios/activos', undefined, { auth: true }),
  obtener: (ipsId, domicilioId) => api.get(`/api/v1/domicilios/${ipsId}/${domicilioId}`, undefined, { auth: true }),
  historial: (ipsId, domicilioId) =>
    api.get(`/api/v1/domicilios/${ipsId}/${domicilioId}/historial`, undefined, { auth: true }),
  actualizarEstado: (ipsId, domicilioId, payload) =>
    api.patch(`/api/v1/domicilios/${ipsId}/${domicilioId}/estado`, payload, { auth: true }),
}

export const historiaClinicaApi = {
  mia: () => api.get('/api/v1/historia-clinica/mia', undefined, { auth: true }),
}
