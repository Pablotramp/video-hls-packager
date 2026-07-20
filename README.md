# HLS Video Packager

Una aplicación de escritorio para preparar contenidos de video para streaming HLS, lista para subir a servicios como Cloudflare R2.

---

## Qué hace

Toma una carpeta de videos (con cualquier estructura de subcarpetas) y produce una carpeta espejo con:

- Los **archivos no-video** copiados sin cambios.
- Cada **archivo de video** (`nombre.ext`) convertido a una carpeta `nombre/` que contiene:
  - `master.m3u8` — playlist maestra HLS con todas las variantes.
  - `1080p.m3u8`, `720p.m3u8`, `480p.m3u8` — playlists de variante (según resolución de origen).
  - Segmentos `.ts` nombrados por variante (`1080p_000.ts`, `720p_000.ts`, …).

---

## Requisitos

| Herramienta | Versión mínima | Notas |
|-------------|---------------|-------|
| Python      | 3.11+         | [python.org](https://python.org) |
| FFmpeg      | 4.4+          | Incluye `ffprobe`. [ffmpeg.org](https://ffmpeg.org/download.html) |

> **FFmpeg debe estar disponible en el PATH del sistema.**  
> La app detecta su ausencia al arrancar y muestra un aviso.

---

## Instalación

```bash
# 1. Clona el repositorio
git clone https://github.com/Pablotramp/video-hls-packager.git
cd video-hls-packager

# 2. Crea entorno virtual (recomendado)
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
.venv\Scripts\activate         # Windows

# 3. Instala dependencias
pip install -r requirements.txt
```

---

## Ejecución local

```bash
python main.py
```

---

## Tests

```bash
pytest tests/ -v
```

---

## Construir ejecutable con PyInstaller

### Instalar PyInstaller

```bash
pip install pyinstaller
```

### Windows

```bat
build_scripts\build_windows.bat
```

Produce: `dist\HLSPackager\HLSPackager.exe`

### macOS

```bash
chmod +x build_scripts/build_macos.sh
./build_scripts/build_macos.sh
```

Produce: `dist/HLSPackager.app`

### Linux

```bash
chmod +x build_scripts/build_linux.sh
./build_scripts/build_linux.sh
```

Produce: `dist/HLSPackager` (binario)

> ⚠ **Cada plataforma requiere su propio build nativo.**  
> No es posible cross-compilar: un `.exe` de Windows debe construirse en Windows,  
> un `.app` de macOS en macOS, etc.

---

## Spec de PyInstaller (avanzado)

El fichero `video_hls_packager.spec` contiene la configuración completa.  
Úsalo para personalizar iconos, nombre del ejecutable, o incluir assets adicionales:

```bash
pyinstaller video_hls_packager.spec
```

---

## Uso paso a paso

1. **Abre la app** (`python main.py` o el ejecutable compilado).
2. Haz clic en **"Seleccionar…"** y elige la carpeta raíz de tus videos.
3. La **carpeta de salida** se calcula automáticamente (`<origen>_optimized`).
4. (Opcional) Activa **"Sobrescribir archivos existentes"** si quieres rehacer conversiones previas.
5. Haz clic en **"Iniciar"**.
6. Observa el progreso en la barra y los logs en tiempo real.
7. Haz clic en **"Cancelar"** en cualquier momento para detener el proceso.
8. Al terminar, se generan `conversion_report.json` y `conversion_report.txt` en la carpeta de salida.

---

## Estructura de salida de ejemplo

```
proyecto_optimized/
├── conversion_report.json
├── conversion_report.txt
├── imagen.jpg                  ← copiado tal cual
├── datos.json                  ← copiado tal cual
└── seccion/
    ├── thumbnail.png            ← copiado tal cual
    ├── video1/                  ← era video1.mp4
    │   ├── master.m3u8
    │   ├── 1080p.m3u8
    │   ├── 720p.m3u8
    │   ├── 480p.m3u8
    │   ├── 1080p_000.ts
    │   ├── 1080p_001.ts
    │   ├── 720p_000.ts
    │   └── 480p_000.ts
    └── clip_corto/              ← era clip_corto.webm (720p)
        ├── master.m3u8
        ├── 720p.m3u8
        ├── 480p.m3u8
        ├── 720p_000.ts
        └── 480p_000.ts
```

---

## Portabilidad de la carpeta de contenidos

La **carpeta de salida** (`_optimized`) es completamente independiente del ejecutable:
- Cópiala/muévela entre equipos libremente.
- Súbela directamente a Cloudflare R2, S3 u otro CDN.
- El ejecutable no necesita estar en el mismo lugar que los contenidos.

---

## Notas de arquitectura

```
src/hls_packager/
├── models.py       # Modelos de datos y enums
├── file_utils.py   # Escaneo y copia de ficheros
├── ffprobe.py      # Wrapper de ffprobe (sondeo de video)
├── ffmpeg.py       # Wrapper de FFmpeg (transcodificación HLS)
├── packager.py     # Motor de orquestación (hilo de trabajo)
├── report.py       # Generación de informes JSON/TXT
└── gui.py          # Interfaz gráfica Flet
```
