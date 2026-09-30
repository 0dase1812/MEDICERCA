// Comprime fotos de fórmulas médicas tomadas con el celular (suelen pesar
// varios MB) antes de subirlas, para que carguen más rápido y no infle la
// base de datos. Los PDF y las imágenes que ya son livianas se dejan igual.
const LADO_MAXIMO_PX = 1600
const CALIDAD_JPEG = 0.8
const UMBRAL_COMPRESION_BYTES = 800 * 1024

export async function comprimirImagenSiAplica(archivo) {
  if (!archivo.type.startsWith('image/') || archivo.size <= UMBRAL_COMPRESION_BYTES) {
    return archivo
  }

  try {
    const bitmap = await createImageBitmap(archivo)
    const escala = Math.min(1, LADO_MAXIMO_PX / Math.max(bitmap.width, bitmap.height))
    const ancho = Math.round(bitmap.width * escala)
    const alto = Math.round(bitmap.height * escala)

    const canvas = document.createElement('canvas')
    canvas.width = ancho
    canvas.height = alto
    canvas.getContext('2d').drawImage(bitmap, 0, 0, ancho, alto)

    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', CALIDAD_JPEG))
    if (!blob || blob.size >= archivo.size) {
      return archivo
    }
    const nombreBase = archivo.name.replace(/\.[^.]+$/, '')
    return new File([blob], `${nombreBase}.jpg`, { type: 'image/jpeg' })
  } catch {
    // Si el navegador no soporta esto o algo falla, se sube la imagen original.
    return archivo
  }
}
