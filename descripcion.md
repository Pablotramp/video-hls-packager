# HLS Video Packager — Descripción del programa

## ¿Qué es?

**HLS Video Packager** es una aplicación de escritorio independiente, escrita en Python, cuyo objetivo es preparar colecciones de video para su distribución en streaming adaptativo (HLS — HTTP Live Streaming). Está pensada para creadores y desarrolladores que quieren publicar contenido multimedia de alta calidad en servicios como Cloudflare R2, Amazon S3 o cualquier CDN que sirva archivos estáticos.

---

## Propósito

Antes de publicar un video en la web moderna, conviene transformarlo en un formato optimizado para streaming:

- **Múltiples calidades** — el reproductor del usuario descarga la variante adecuada a su conexión y dispositivo.
- **Segmentos pequeños** — el video se divide en trozos de ~6 segundos, lo que permite comenzar la reproducción casi de inmediato y saltar a cualquier punto sin descargar el archivo completo.
- **Inicio rápido** — el navegador descarga primero el segmento inicial y va pidiendo los siguientes en segundo plano.

Este programa automatiza todo ese proceso: tú señalas una carpeta con tus videos originales, y él produce la estructura completa lista para subir al servidor.

---

## Flujo de trabajo

```
┌─────────────────────┐
│  Carpeta de origen  │   (contiene tus videos originales y otros archivos)
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Escaneo recursivo  │   detección de videos por extensión
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Análisis con       │   ffprobe: resolución, FPS, duración, audio
│  ffprobe            │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Selección de       │   1080p / 720p / 480p / "low"
│  variantes          │   (sin escalado hacia arriba)
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Transcodificación  │   FFmpeg: H.264 + AAC, segmentos .ts, GOP fijo
│  con FFmpeg         │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Carpeta de salida  │   estructura espejo + archivos HLS + informe
└─────────────────────┘
```

---

## Entradas

| Tipo | Descripción |
|------|-------------|
| Carpeta raíz | Cualquier carpeta local con subcarpetas y archivos mezclados |
| Videos | `.mp4`, `.mov`, `.mkv`, `.m4v`, `.avi`, `.webm` (case-insensitive) |
| Otros archivos | Imágenes, JSONs, PDFs, etc. → se copian sin modificar |

---

## Salidas

Para cada video `nombre.ext` en la carpeta de origen, se genera una carpeta `nombre/` en la salida con:

```
nombre/
├── master.m3u8      ← playlist maestra; apunta a las variantes disponibles
├── 1080p.m3u8       ← playlist de variante 1080p (si aplica)
├── 720p.m3u8        ← playlist de variante 720p  (si aplica)
├── 480p.m3u8        ← playlist de variante 480p  (si aplica)
├── 1080p_000.ts     ┐
├── 1080p_001.ts     ├─ segmentos de ~6s para cada variante
├── 720p_000.ts      │
├── 480p_000.ts      ┘
└── ...
```

Los archivos no-video se copian con su ruta relativa original intacta.

Adicionalmente, al finalizar se escriben en la raíz de salida:
- `conversion_report.json` — informe estructurado de la ejecución.
- `conversion_report.txt` — versión legible del mismo informe.

---

## Por qué se usan segmentos HLS (.ts)

HLS (HTTP Live Streaming) es el estándar de facto para video adaptativo en la web:

1. **Compatibilidad universal** — soportado de forma nativa en Safari/iOS y mediante `hls.js` en Chrome, Firefox y Edge.
2. **Adaptabilidad** — el reproductor elige automáticamente la variante (1080p, 720p, 480p) según el ancho de banda disponible.
3. **Segmentos independientes** — cada fichero `.ts` contiene un GOP completo (keyframe al inicio), por lo que el reproductor puede saltar a cualquier segmento sin depender de los anteriores.
4. **Servicio desde CDN estático** — los segmentos son simples ficheros estáticos; no se necesita un servidor de streaming dedicado.
5. **Inicio rápido** — el usuario comienza a ver el video en cuanto se descarga el primer segmento (~6 segundos de contenido), sin esperar a que cargue el archivo completo.

### Parámetros técnicos usados

| Parámetro | Valor | Motivo |
|-----------|-------|--------|
| Duración de segmento | 6 s | Balance entre inicio rápido y número de ficheros |
| GOP (Group of Pictures) | `fps × 6` | Keyframe al inicio de cada segmento → salto limpio |
| `sc_threshold 0` | desactivado | Evita keyframes extra por cambio de escena que romperían el alineado |
| `hls_playlist_type vod` | VOD | Playlist completa desde el inicio; ideal para contenido grabado |
| `hls_flags independent_segments` | activado | Cada segmento es decodificable de forma independiente |
| Video codec | H.264 (libx264) | Máxima compatibilidad de navegadores y dispositivos |
| Audio codec | AAC 128 kbps | Estándar de la web; compatible con todos los reproductores |
| Bitrates objetivo | 5 Mbps / 3 Mbps / 1.2 Mbps | 1080p / 720p / 480p respectivamente |

---

## Reglas de variantes (sin escalado hacia arriba)

- Se incluyen solo las variantes cuya altura ≤ altura del video original.
- Si el origen es menor de 480p, se produce una variante `low` a la resolución original.
- Ejemplo: un video de 720p genera variantes `720p` y `480p`, pero NO `1080p`.

---

## Interfaz gráfica

La app usa **Flet** (Flutter para Python) y ofrece:

- Selector de carpeta de origen.
- Visualización automática de la carpeta de salida.
- Toggle de sobrescritura.
- Barra de progreso global y estado por archivo.
- Área de log en tiempo real.
- Botón de cancelación con parada controlada.

---

## Distribución

La app puede empaquetarse con **PyInstaller** en un ejecutable nativo:

- **Windows**: `.exe` (requiere build en Windows)
- **macOS**: `.app` (requiere build en macOS)
- **Linux**: binario ejecutable (requiere build en Linux)

La carpeta de contenidos (`_optimized`) es completamente independiente del ejecutable y puede moverse libremente entre equipos.
