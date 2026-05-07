# app.py - GalloFino v2.0 (Corregido y Optimizado)
# =============================================================================
# Sistema Profesional de Gestión Genética de Gallos
# =============================================================================

import os
import csv
import io
import shutil
import zipfile
import secrets
import random
import string
import logging
from datetime import datetime, timedelta
from functools import wraps

# Flask y extensiones
from flask import Flask, request, session, redirect, url_for, send_from_directory, jsonify
from flask_wtf.csrf import CSRFProtect
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# Procesamiento de datos
import sqlite3
import pandas as pd

# Validación de imágenes (Pillow)
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# =============================================================================
# CONFIGURACIÓN DE LA APLICACIÓN
# =============================================================================

app = Flask(__name__)

# 🔐 SEGURIDAD: Secret key OBLIGATORIA desde variable de entorno
if not os.environ.get('SECRET_KEY'):
    raise RuntimeError(
        "⚠️ ERROR CRÍTICO: SECRET_KEY no configurada.\n"
        "   Ejecuta: export SECRET_KEY='$(openssl rand -hex 32)'"
    )
app.secret_key = os.environ['SECRET_KEY']
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hora
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB máximo para uploads

# Protección CSRF
csrf = CSRFProtect(app)

# Configuración de uploads
UPLOAD_FOLDER = 'uploads'
BACKUP_FOLDER = 'backups'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(BACKUP_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Base de datos
DB = 'gallos.db'

# Datos de dominio
RAZAS = [
    "Hatch", "Sweater", "Kelso", "Grey", "Albany",
    "Radio", "Asil (Aseel)", "Shamo", "Spanish", "Peruvian"
]
APARIENCIAS = ['Crestarosa', 'Cocolo', 'Tuceperne', 'Pava', 'Moton']
TABLAS_PERMITIDAS = {'individuos', 'cruces'}

# OTP seguro: {correo: {codigo, traba, expira, intentos}}
OTP_TEMP = {}

# =============================================================================
# CONFIGURACIÓN DE LOGGING
# =============================================================================

if not app.debug:
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        handlers=[
            logging.FileHandler('gallofino.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    app.logger.info("🚀 GalloFino iniciado en modo producción")


# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def allowed_file(filename):
    """Verifica que el archivo tenga extensión permitida"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def is_valid_image(file_stream):
    """Verifica que el archivo sea realmente una imagen válida (requiere Pillow)"""
    if not PIL_AVAILABLE:
        return True  # Si no hay Pillow, confiar en la extensión
    try:
        file_stream.seek(0)
        img = Image.open(file_stream)
        img.verify()
        file_stream.seek(0)
        return True
    except Exception:
        return False


def generar_codigo_unico(cursor):
    """Genera un código único de 8 caracteres alfanuméricos"""
    intentos = 0
    while intentos < 100:
        codigo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        cursor.execute('SELECT 1 FROM individuos WHERE codigo = ?', (codigo,))
        if not cursor.fetchone():
            return codigo
        intentos += 1
    # Fallback con timestamp si hay colisión extrema
    return f"UNIQ{datetime.now().timestamp():.0f}"[-8:].upper()


def limpiar_otps_expirados():
    """Elimina OTPs vencidos de la memoria temporal"""
    ahora = datetime.now()
    expirados = [c for c, d in OTP_TEMP.items() if d['expira'] < ahora]
    for correo in expirados:
        del OTP_TEMP[correo]
    return len(expirados)


def proteger_ruta(f):
    """Decorator para proteger rutas que requieren autenticación"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'traba' not in session:
            return redirect(url_for('bienvenida'))
        return f(*args, **kwargs)
    return wrapper


def init_db():
    """Inicializa la base de datos con todas las tablas e índices"""
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")  # ✅ Habilitar claves foráneas
    cursor = conn.cursor()
    
    # Tabla de usuarios (trabas)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS trabas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre_traba TEXT UNIQUE NOT NULL,
        nombre_completo TEXT NOT NULL,
        correo TEXT UNIQUE NOT NULL,
        contraseña_hash TEXT NOT NULL
    )
    ''')
    
    # Tabla de individuos (gallos)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS individuos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        traba TEXT NOT NULL,
        placa_traba TEXT NOT NULL,
        placa_regional TEXT,
        nombre TEXT,
        raza TEXT,
        color TEXT NOT NULL,
        apariencia TEXT NOT NULL,
        n_pelea TEXT,
        nacimiento DATE,
        foto TEXT,
        generacion INTEGER DEFAULT 1,
        codigo TEXT UNIQUE,
        UNIQUE(traba, placa_traba)
    )
    ''')
    
    # Tabla de progenitores (relaciones padre/madre)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS progenitores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        individuo_id INTEGER NOT NULL,
        madre_id INTEGER,
        padre_id INTEGER,
        FOREIGN KEY (individuo_id) REFERENCES individuos (id) ON DELETE CASCADE,
        FOREIGN KEY (madre_id) REFERENCES individuos (id) ON DELETE SET NULL,
        FOREIGN KEY (padre_id) REFERENCES individuos (id) ON DELETE SET NULL,
        UNIQUE(individuo_id)
    )
    ''')
    
    # Tabla de cruces
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cruces (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        traba TEXT NOT NULL,
        tipo TEXT NOT NULL,
        individuo1_id INTEGER NOT NULL,
        individuo2_id INTEGER NOT NULL,
        generacion INTEGER NOT NULL,
        porcentaje REAL NOT NULL,
        fecha DATE NOT NULL,
        notas TEXT,
        foto TEXT,
        FOREIGN KEY (individuo1_id) REFERENCES individuos (id),
        FOREIGN KEY (individuo2_id) REFERENCES individuos (id)
    )
    ''')
    
    # ✅ Crear índices para optimizar búsquedas frecuentes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_individuos_traba_placa ON individuos(traba, placa_traba)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_individuos_nombre ON individuos(traba, nombre)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_individuos_codigo ON individuos(codigo)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_progenitores_individuo ON progenitores(individuo_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_progenitores_madre ON progenitores(madre_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_progenitores_padre ON progenitores(padre_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_cruces_traba_fecha ON cruces(traba, fecha)')
    
    # Migraciones para versiones anteriores
    cols_trabas = [col[1] for col in cursor.execute("PRAGMA table_info(trabas)").fetchall()]
    if 'contraseña_hash' not in cols_trabas:
        try:
            cursor.execute("ALTER TABLE trabas ADD COLUMN contraseña_hash TEXT")
        except sqlite3.OperationalError:
            pass
    
    cols_individuos = [col[1] for col in cursor.execute("PRAGMA table_info(individuos)").fetchall()]
    if 'generacion' not in cols_individuos:
        try:
            cursor.execute("ALTER TABLE individuos ADD COLUMN generacion INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass
    if 'codigo' not in cols_individuos:
        try:
            cursor.execute("ALTER TABLE individuos ADD COLUMN codigo TEXT UNIQUE")
        except sqlite3.OperationalError:
            pass
    
    conn.commit()
    conn.close()
    app.logger.info("✅ Base de datos inicializada correctamente")


def generar_caracteristica(gallo_id, traba):
    """Genera una descripción de roles del gallo en la genealogía"""
    roles = []
    conn2 = sqlite3.connect(DB)
    conn2.row_factory = sqlite3.Row
    cur = conn2.cursor()
    
    # Buscar descendientes donde este gallo es madre
    cur.execute('''
        SELECT i.placa_traba 
        FROM individuos i 
        JOIN progenitores p ON i.id = p.individuo_id 
        WHERE p.madre_id = ?
    ''', (gallo_id,))
    for r in cur.fetchall():
        roles.append(f"Madre de {r['placa_traba']}")
        
    # Buscar descendientes donde este gallo es padre
    cur.execute('''
        SELECT i.placa_traba 
        FROM individuos i 
        JOIN progenitores p ON i.id = p.individuo_id 
        WHERE p.padre_id = ?
    ''', (gallo_id,))
    for r in cur.fetchall():
        roles.append(f"Padre de {r['placa_traba']}")
        
    # Buscar cruces recientes
    cur.execute('''
        SELECT tipo, fecha FROM cruces
        WHERE (individuo1_id = ? OR individuo2_id = ?) AND traba = ?
        ORDER BY fecha DESC LIMIT 2
    ''', (gallo_id, gallo_id, traba))
    for cr in cur.fetchall():
        roles.append(f"Cruce {cr['tipo']} ({cr['fecha']})")
    
    conn2.close()
    return "; ".join(roles[:3]) + ("..." if len(roles) > 3 else "") if roles else "—"


# =============================================================================
# RUTAS DE AUTENTICACIÓN
# =============================================================================

@app.route('/solicitar-otp', methods=['POST'])
@csrf.exempt  # Exento de CSRF para compatibilidad con formularios simples
def solicitar_otp():
    correo = request.form.get('correo', '').strip().lower()
    if not correo:
        return '<script>alert("❌ Ingresa tu correo."); window.location="/";</script>'
    
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute('SELECT nombre_traba FROM trabas WHERE correo = ?', (correo,))
    traba_row = cursor.fetchone()
    conn.close()
    
    if not traba_row:
        return '<script>alert("❌ Correo no registrado."); window.location="/";</script>'
    
    traba = traba_row[0]
    codigo = str(secrets.randbelow(1000000)).zfill(6)
    
    # ✅ OTP con expiración (5 minutos) y límite de intentos
    OTP_TEMP[correo] = {
        'codigo': codigo,
        'traba': traba,
        'expira': datetime.now() + timedelta(minutes=5),
        'intentos': 0
    }
    
    # En producción: enviar email real con sendgrid, smtp, etc.
    app.logger.info(f"📧 [OTP DEV para {correo}]: {codigo}")
    
    return f"""
    <script>
        alert("✅ Código enviado a tu correo. (Verifica la consola en desarrollo)");
        window.location="/verificar-otp?correo={correo}";
    </script>
    """


@app.route('/verificar-otp')
def pagina_verificar_otp():
    correo = request.args.get('correo', '').strip()
    if not correo:
        return redirect(url_for('bienvenida'))
    return f"""
<!DOCTYPE html>
<html><head><title>Verificar OTP</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body style="background:#01030a;color:white;text-align:center;padding:50px;font-family:sans-serif;">
    <h2>🔐 Ingresar Código</h2>
    <p>Código enviado a: <strong>{correo}</strong></p>
    <p style="color:#f39c12;font-size:0.9em;">⏱️ Válido por 5 minutos • Máximo 3 intentos</p>
    <form method="POST" action="/verificar-otp">
        <input type="hidden" name="correo" value="{correo}">
        <input type="text" name="codigo" required placeholder="Código de 6 dígitos" 
               maxlength="6" pattern="[0-9]{{6}}" 
               style="padding:10px;font-size:18px;text-align:center;letter-spacing:5px;width:200px;">
        <br><br>
        <button type="submit" style="padding:10px 20px;background:#2ecc71;color:#041428;border:none;border-radius:5px;font-weight:bold;">✅ Verificar</button>
    </form>
    <p><a href="/" style="color:#00ffff;text-decoration:none;">← Regresar</a></p>
</body></html>
"""


@app.route('/verificar-otp', methods=['POST'])
@csrf.exempt
def verificar_otp():
    correo = request.form.get('correo', '').strip()
    codigo = request.form.get('codigo', '').strip()
    
    if not correo or not codigo:
        return redirect(url_for('bienvenida'))
    
    # Limpiar OTPs expirados periódicamente
    limpiar_otps_expirados()
    
    if correo not in OTP_TEMP:
        return '<script>alert("❌ Código expirado o inválido."); window.location="/";</script>'
    
    otp_data = OTP_TEMP[correo]
    
    # Verificar expiración
    if datetime.now() > otp_data['expira']:
        del OTP_TEMP[correo]
        return '<script>alert("❌ Código expirado. Solicita uno nuevo."); window.location="/";</script>'
    
    # Limitar intentos (máximo 3)
    if otp_data['intentos'] >= 3:
        del OTP_TEMP[correo]
        return '<script>alert("❌ Demasiados intentos. Solicita un nuevo código."); window.location="/";</script>'
    
    if otp_data['codigo'] == codigo:
        traba = otp_data['traba']
        session['traba'] = traba.strip()
        session.permanent = True
        del OTP_TEMP[correo]
        app.logger.info(f"✅ Login exitoso para traba: {traba}")
        return redirect(url_for('menu_principal'))
    else:
        otp_data['intentos'] += 1
        restantes = 3 - otp_data['intentos']
        if restantes <= 0:
            del OTP_TEMP[correo]
            msg = "❌ Demasiados intentos. Solicita un nuevo código."
        else:
            msg = f"❌ Código incorrecto. Te quedan {restantes} intento(s)."
        return f'<script>alert("{msg}"); window.history.back();</script>'


@app.route('/registrar-traba', methods=['POST'])
@csrf.exempt
def registrar_traba():
    nombre = request.form.get('nombre', '').strip()
    apellido = request.form.get('apellido', '').strip()
    traba = request.form.get('traba', '').strip()
    correo = request.form.get('correo', '').strip().lower()
    contraseña = request.form.get('contraseña', '')
    
    if not all([nombre, apellido, traba, correo, contraseña]):
        return '<script>alert("❌ Todos los campos son obligatorios."); window.location="/";</script>'
    
    if len(contraseña) < 6:
        return '<script>alert("❌ La contraseña debe tener al menos 6 caracteres."); window.location="/";</script>'
    
    contraseña_hash = generate_password_hash(contraseña)
    nombre_completo = f"{nombre} {apellido}".strip()
    
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO trabas (nombre_traba, nombre_completo, correo, contraseña_hash)
            VALUES (?, ?, ?, ?)
        ''', (traba, nombre_completo, correo, contraseña_hash))
        conn.commit()
        app.logger.info(f"✅ Nueva traba registrada: {traba} ({correo})")
        return '<script>alert("✅ Registro exitoso. Ahora puedes iniciar sesión."); window.location="/";</script>'
    except sqlite3.IntegrityError as e:
        if "correo" in str(e).lower():
            msg = "❌ El correo ya está registrado."
        elif "nombre_traba" in str(e).lower() or "unique" in str(e).lower():
            msg = "❌ El nombre de la traba ya existe."
        else:
            msg = "❌ Error en el registro. Intenta nuevamente."
        app.logger.warning(f"⚠️ Error al registrar traba: {e}")
        return f'<script>alert("{msg}"); window.location="/";</script>'
    finally:
        conn.close()


@app.route('/iniciar-sesion', methods=['POST'])
@csrf.exempt
def iniciar_sesion():
    correo = request.form.get('correo', '').strip().lower()
    contraseña = request.form.get('contraseña', '')
    
    if not correo or not contraseña:
        return '<script>alert("❌ Correo y contraseña son obligatorios."); window.location="/";</script>'
    
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute('SELECT nombre_traba, contraseña_hash FROM trabas WHERE correo = ?', (correo,))
    traba_row = cursor.fetchone()
    conn.close()
    
    if not traba_row or not check_password_hash(traba_row[1], contraseña):
        app.logger.warning(f"⚠️ Intento de login fallido para: {correo}")
        return '<script>alert("❌ Correo o contraseña incorrectos."); window.location="/";</script>'
    
    session['traba'] = traba_row[0].strip()
    session.permanent = True
    app.logger.info(f"✅ Login exitoso para: {correo}")
    return redirect(url_for('menu_principal'))


@app.route('/cerrar-sesion')
@proteger_ruta
def cerrar_sesion():
    traba = session.get('traba', 'Desconocida')
    session.clear()
    app.logger.info(f"🚪 Sesión cerrada para traba: {traba}")
    return redirect(url_for('bienvenida'))


# =============================================================================
# RUTAS PRINCIPALES
# =============================================================================

@app.route('/')
def bienvenida():
    if 'traba' in session:
        return redirect(url_for('menu_principal'))
    
    fecha_actual = datetime.now().strftime('%Y-%m-%d')
    return f"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GalloFino - Inicio</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;500;700&display=swap');
*{{margin:0; padding:0; box-sizing:border-box; font-family:'Poppins', sans-serif;}}
body{{background:#01030a; color:white; font-size:17px;}}
.container{{width:90%; max-width:500px; margin:50px auto; background:rgba(255,255,255,0.05); border-radius:20px; padding:30px; backdrop-filter:blur(8px); box-shadow:0 0 25px rgba(0,255,255,0.3);}}
.logo{{width:80px; height:auto; filter:drop-shadow(0 0 6px #00ffff); float:right;}}
h1{{font-size:2rem; color:#00ffff; text-shadow:0 0 12px #00ffff; margin-bottom:10px;}}
.subtitle{{font-size:0.9rem; color:#bbb;}}
.form-container input, .form-container button{{width:100%; padding:14px; margin:8px 0 15px; border-radius:10px; border:none; outline:none; font-size:17px;}}
.form-container input{{background:rgba(255,255,255,0.08); color:white;}}
.form-container button{{background:linear-gradient(135deg,#3498db,#2ecc71); color:#041428; font-weight:bold; cursor:pointer; transition:0.3s;}}
.form-container button:hover{{transform:translateY(-3px); box-shadow:0 4px 15px rgba(0,255,255,0.4);}}
canvas{{position:fixed; top:0; left:0; width:100%; height:100%; z-index:-1;}}
.tabs{{display:flex; justify-content:space-around; margin-bottom:20px;}}
.tab{{padding:8px 16px; cursor:pointer; background:rgba(0,255,255,0.1); border-radius:8px;}}
.tab.active{{background:#00ffff; color:#041428; font-weight:bold;}}
#registro-form, #login-form{{display:none;}}
#registro-form.active{{display:block;}}
#login-form.active{{display:block;}}
</style>
</head>
<body>
<canvas id="bg"></canvas>
<div class="container">
<img src="/logo" alt="Logo" class="logo">
<h1>🐓 GalloFino</h1>
<p class="subtitle">Sistema Profesional de Gestión Genética • Año 2026</p>
<div class="tabs">
  <div class="tab active" onclick="mostrar('registro')">✅ Registrarme</div>
  <div class="tab" onclick="mostrar('login')">🔐 Iniciar Sesión</div>
</div>
<div id="registro-form" class="form-container active">
<form method="POST" action="/registrar-traba">
<input type="text" name="nombre" required placeholder="Nombre">
<input type="text" name="apellido" required placeholder="Apellido">
<input type="text" name="traba" required placeholder="Nombre de la Traba">
<input type="email" name="correo" required placeholder="Correo Electrónico">
<input type="password" name="contraseña" required placeholder="Contraseña (mín. 6 caracteres)" minlength="6">
<input type="hidden" name="fecha" value="{fecha_actual}">
<button type="submit">✅ Registrarme</button>
</form>
</div>
<div id="login-form" class="form-container">
<form method="POST" action="/iniciar-sesion">
<input type="email" name="correo" required placeholder="Correo Electrónico">
<input type="password" name="contraseña" required placeholder="Contraseña">
<button type="submit">🔐 Iniciar Sesión</button>
</form>
</div>
</div>
<script>
function mostrar(seccion) {{
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.form-container').forEach(f => f.classList.remove('active'));
  if (seccion === 'registro') {{
    document.querySelectorAll('.tab')[0].classList.add('active');
    document.getElementById('registro-form').classList.add('active');
  }} else {{
    document.querySelectorAll('.tab')[1].classList.add('active');
    document.getElementById('login-form').classList.add('active');
  }}
}}
// Animación de partículas de fondo
const canvas = document.getElementById("bg");
const ctx = canvas.getContext("2d");
canvas.width = window.innerWidth;
canvas.height = window.innerHeight;
let particles = [];
class Particle {{
  constructor() {{
    this.x = Math.random() * canvas.width;
    this.y = Math.random() * canvas.height;
    this.size = Math.random() * 2 + 1;
    this.speedX = Math.random() - 0.5;
    this.speedY = Math.random() - 0.5;
  }}
  update() {{
    this.x += this.speedX; this.y += this.speedY;
    if (this.x < 0) this.x = canvas.width;
    if (this.x > canvas.width) this.x = 0;
    if (this.y < 0) this.y = canvas.height;
    if (this.y > canvas.height) this.y = 0;
  }}
  draw() {{
    ctx.fillStyle = "rgba(0,255,255,0.7)";
    ctx.beginPath(); ctx.arc(this.x, this.y, this.size, 0, Math.PI*2); ctx.fill();
  }}
}}
function init() {{ for(let i=0;i<100;i++) particles.push(new Particle()); }}
function animate() {{
  ctx.clearRect(0,0,canvas.width,canvas.height);
  particles.forEach(p=>{{p.update();p.draw();}});
  requestAnimationFrame(animate);
}}
window.addEventListener("resize", ()=>{{canvas.width=window.innerWidth; canvas.height=window.innerHeight; init();}});
init(); animate();

// Indicador de carga en formularios
document.querySelectorAll('form').forEach(form => {{
    form.addEventListener('submit', function() {{
        const btn = this.querySelector('button[type="submit"]');
        if (btn) {{ btn.disabled = true; btn.textContent = '⏳ Procesando...'; }}
    }});
}});
</script>
</body>
</html>
"""


@app.route('/menu')
@proteger_ruta
def menu_principal():
    traba = session['traba']
    return f"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GalloFino - Menú</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;500;700&display=swap');
*{{margin:0; padding:0; box-sizing:border-box; font-family:'Poppins', sans-serif;}}
body{{background:#01030a; color:white; font-size:17px; overflow-x:hidden;}}
.container{{width:95%; max-width:900px; margin:40px auto; background:rgba(0,0,0,0.4); border-radius:20px; padding:25px; backdrop-filter:blur(10px); box-shadow:0 0 30px rgba(0,255,255,0.4); position:relative; z-index:2;}}
.header-modern{{display:flex; justify-content:space-between; align-items:center; margin-bottom:30px; flex-wrap:wrap; gap:15px;}}
.header-modern h1{{font-size:1.8rem; color:#00ffff; text-shadow:0 0 10px #00ffff;}}
.subtitle{{font-size:0.85rem; color:#bbb;}}
.logo{{width:80px; height:auto; filter:drop-shadow(0 0 6px #00ffff);}}
#scene3d{{position:fixed; top:0; left:0; width:100%; height:100%; z-index:0; background:radial-gradient(ellipse at center,#000410 0%,#01030a 100%);}}
#scene3d .layer{{position:absolute; top:0; left:0; width:200%; height:200%; background-repeat:no-repeat; background-size:400px; opacity:0.15; will-change:transform;}}
#scene3d .layer-1{{background:radial-gradient(circle,#00ffff 2px,transparent 2px); animation:float 25s infinite linear;}}
#scene3d .layer-2{{background:radial-gradient(circle,#ff7a18 1.5px,transparent 1.5px); animation:float 35s infinite linear reverse; opacity:0.1;}}
#scene3d .layer-3{{background:radial-gradient(circle,#f6c84c 1px,transparent 1px); animation:float 20s infinite linear; opacity:0.07;}}
@keyframes float{{0%{{transform:translate(0,0) rotate(0deg);}}100%{{transform:translate(-25%,-25%) rotate(360deg);}}}}
.content-wrapper{{position:relative; z-index:3;}}
.card{{background:rgba(255,255,255,0.06); border-radius:20px; padding:25px; backdrop-filter:blur(10px); box-shadow:0 0 30px rgba(0,255,255,0.4);}}
.menu-grid{{display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:15px; margin:20px 0;}}
.menu-btn{{display:block; width:100%; padding:16px; text-align:center; border-radius:10px; background:linear-gradient(135deg,#f6c84c,#ff7a18); color:#041428; font-weight:bold; text-decoration:none; transition:0.3s; font-size:17px;}}
.menu-btn:hover{{transform:translateY(-3px); box-shadow:0 6px 20px rgba(0,255,255,0.5);}}
</style>
</head>
<body>
<div id="scene3d">
    <div class="layer layer-1"></div>
    <div class="layer layer-2"></div>
    <div class="layer layer-3"></div>
</div>
<div class="content-wrapper">
    <div class="container">
        <div class="header-modern">
            <div><h1>🐓 Traba: {traba}</h1><p class="subtitle">Sistema moderno • Año 2026</p></div>
            <img src="/logo" alt="Logo" class="logo">
        </div>
        <div class="card">
            <div class="menu-grid">
                <a href="/formulario-gallo" class="menu-btn">🐓 Registrar Gallo</a>
                <a href="/cruce-inbreeding" class="menu-btn">🔁 Cruce Inbreeding</a>
                <a href="/lista" class="menu-btn">📋 Mis Gallos</a>
                <a href="/buscar" class="menu-btn">🔍 Buscar</a>
                <a href="/exportar" class="menu-btn">📤 Exportar</a>
                <a href="javascript:void(0);" class="menu-btn" onclick="crearBackup()">💾 Respaldo</a>
                <a href="/cerrar-sesion" class="menu-btn" style="background:linear-gradient(135deg,#7f8c8d,#95a5a6);">🚪 Cerrar Sesión</a>
            </div>
        </div>
    </div>
</div>
<div id="mensaje-backup" style="text-align:center; margin-top:15px; color:#27ae60; font-weight:bold;"></div>
<script>
function crearBackup() {{
    const btn = event.target;
    btn.disabled = true; btn.textContent = '⏳ Creando...';
    fetch("/backup", {{method: "POST"}})
        .then(r => r.json())
        .then(d => {{
            if (d.error) {{
                document.getElementById("mensaje-backup").innerHTML = `<span style="color:#e74c3c;">❌ ${{d.error}}</span>`;
            }} else {{
                document.getElementById("mensaje-backup").innerHTML = `<span style="color:#27ae60;">${{d.mensaje}}</span>`;
                window.location.href = "/download/" + d.archivo;
            }}
            btn.disabled = false; btn.textContent = '💾 Respaldo';
        }})
        .catch(e => {{
            document.getElementById("mensaje-backup").innerHTML = `<span style="color:#e74c3c;">❌ Error de red</span>`;
            btn.disabled = false; btn.textContent = '💾 Respaldo';
        }});
}}
</script>
</body>
</html>
"""


# =============================================================================
# RUTAS DE GESTIÓN DE GALLOS
# =============================================================================

@app.route('/formulario-gallo')
@proteger_ruta
def formulario_gallo():
    traba = session['traba']
    razas_html = ''.join([f'<option value="{r}">{r}</option>' for r in RAZAS])
    ap_html = ''.join([
        f'<label style="display:inline-block; margin-right:15px;"><input type="radio" name="gallo_apariencia" value="{a}" required> {a}</label>'
        for a in APARIENCIAS
    ])
    return f"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Registrar Gallo</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;500;700&display=swap');
*{{margin:0; padding:0; box-sizing:border-box; font-family:'Poppins', sans-serif;}}
body{{background:#01030a; color:white; overflow-x:hidden; font-size:17px;}}
.container{{width:95%; max-width:800px; margin:30px auto; padding:20px;}}
.header-modern{{display:flex; justify-content:space-between; align-items:center; margin-bottom:25px; flex-wrap:wrap; gap:15px;}}
.header-modern h1{{font-size:1.8rem; color:#00ffff; text-shadow:0 0 10px #00ffff;}}
.subtitle{{font-size:0.85rem; color:#bbb;}}
.logo{{width:80px; height:auto; filter:drop-shadow(0 0 6px #00ffff);}}
.form-container{{background:rgba(255,255,255,0.06); border-radius:20px; padding:25px; backdrop-filter:blur(10px); box-shadow:0 0 30px rgba(0,255,255,0.4);}}
label{{display:block; margin:12px 0 6px; font-weight:500;}}
input, select{{width:100%; padding:10px; margin:5px 0; background:rgba(0,0,0,0.3); color:white; border:none; border-radius:6px; font-size:16px;}}
.btn-ghost{{background:rgba(0,0,0,0.3); border:1px solid rgba(0,255,255,0.2); color:white; padding:10px; border-radius:8px; width:100%; margin:6px 0; font-size:16px;}}
button{{width:100%; padding:16px; border:none; border-radius:10px; background:linear-gradient(135deg,#00ffff,#008cff); color:#041428; font-size:1.2rem; font-weight:bold; cursor:pointer; transition:0.3s; margin-top:15px;}}
button:hover{{transform:translateY(-3px); box-shadow:0 6px 20px rgba(0,255,255,0.5);}}
button:disabled{{opacity:0.6; cursor:not-allowed; transform:none;}}
.back-btn{{display:inline-block; margin-top:20px; padding:10px 20px; background:#2c3e50; color:white; text-decoration:none; border-radius:6px; text-align:center;}}
</style>
</head>
<body>
<div class="container">
<div class="header-modern">
<div><h1>🐓 Traba: {traba}</h1><p class="subtitle">Sistema moderno • Año 2026</p></div>
<img src="/logo" alt="Logo" class="logo">
</div>
<form method="POST" action="/registrar-gallo" enctype="multipart/form-data" class="form-container">
    <h3 style="text-align:center; color:#2980b9; margin-bottom:20px;">A. Registrar Gallo Principal</h3>
    <label>Placa de Traba *</label>
    <input type="text" name="gallo_placa_traba" required class="btn-ghost">
    <label>Placa Regional (opcional)</label>
    <input type="text" name="gallo_placa_regional" class="btn-ghost">
    <label>N° Pelea (opcional)</label>
    <input type="text" name="gallo_n_pelea" class="btn-ghost">
    <label>Nombre del ejemplar (opcional)</label>
    <input type="text" name="gallo_nombre" class="btn-ghost">
    <label>Raza *</label>
    <select name="gallo_raza" required class="btn-ghost">{razas_html}</select>
    <label>Color *</label>
    <input type="text" name="gallo_color" required class="btn-ghost">
    <label>Apariencia *</label>
    <div style="margin:5px 0; font-size:16px;">{ap_html}</div>
    <label>Foto (opcional - PNG, JPG, JPEG, GIF)</label>
    <input type="file" name="gallo_foto" accept="image/*" class="btn-ghost">
    <button type="submit">✅ Registrar Gallo</button>
    <a href="/menu" class="back-btn">🏠 Regresar al Menú</a>
</form>
</div>
<script>
document.querySelector('form').addEventListener('submit', function() {{
    const btn = this.querySelector('button[type="submit"]');
    if (btn) {{ btn.disabled = true; btn.textContent = '⏳ Registrando...'; }}
}});
</script>
</body>
</html>
"""


@app.route('/registrar-gallo', methods=['POST'])
@proteger_ruta
def registrar_gallo():
    traba = session['traba']
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        placa = request.form.get('gallo_placa_traba', '').strip()
        if not placa:
            raise ValueError("La placa del gallo es obligatoria.")
        
        # Verificar duplicado de placa para esta traba
        cursor.execute('SELECT 1 FROM individuos WHERE placa_traba = ? AND traba = ?', (placa, traba))
        if cursor.fetchone():
            raise ValueError(f"Ya existe un gallo con placa '{placa}' en tu traba.")
        
        placa_regional = request.form.get('gallo_placa_regional', '').strip() or None
        nombre = request.form.get('gallo_nombre', '').strip() or None
        n_pelea = request.form.get('gallo_n_pelea', '').strip() or None
        raza = request.form.get('gallo_raza', '').strip()
        color = request.form.get('gallo_color', '').strip()
        apariencia = request.form.get('gallo_apariencia', '').strip()
        
        if not all([raza, color, apariencia]):
            raise ValueError("Raza, color y apariencia son obligatorios.")
        
        # Procesar foto
        foto = None
        if 'gallo_foto' in request.files:
            file = request.files['gallo_foto']
            if file and file.filename != '' and allowed_file(file.filename):
                if is_valid_image(file.stream):
                    safe_placa = secure_filename(placa)
                    fname = f"{safe_placa}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(file.filename)}"
                    ruta_destino = os.path.join(app.config['UPLOAD_FOLDER'], fname)
                    file.save(ruta_destino)
                    foto = fname
                else:
                    app.logger.warning(f"⚠️ Archivo de imagen inválido: {file.filename}")
        
        codigo = generar_codigo_unico(cursor)
        
        cursor.execute('''
            INSERT INTO individuos 
            (traba, placa_traba, placa_regional, nombre, raza, color, apariencia, n_pelea, nacimiento, foto, generacion, codigo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (traba, placa, placa_regional, nombre, raza, color, apariencia, n_pelea, None, foto, 1, codigo))
        
        conn.commit()
        app.logger.info(f"✅ Gallo registrado: {placa} (Traba: {traba})")
        
        return f'''
        <!DOCTYPE html>
        <html><body style="background:#01030a;color:white;text-align:center;padding:50px;font-family:sans-serif;">
        <div style="background:rgba(0,255,255,0.1);padding:30px;border-radius:10px;max-width:500px;margin:0 auto;">
            <h2 style="color:#00ffff;">✅ ¡Gallo registrado exitosamente!</h2>
            <p style="margin:15px 0;">Placa: <strong>{placa}</strong></p>
            <p style="margin:15px 0;">Código único: <strong>{codigo}</strong></p>
            <div style="margin-top:25px;">
                <a href="/menu" style="display:inline-block;padding:12px 24px;background:#2ecc71;color:#041428;text-decoration:none;border-radius:6px;margin:5px;">🏠 Menú</a>
                <a href="/lista" style="display:inline-block;padding:12px 24px;background:#00ffff;color:#041428;text-decoration:none;border-radius:6px;margin:5px;">📋 Mis Gallos</a>
            </div>
        </div>
        </body></html>
        '''
        
    except ValueError as e:
        app.logger.warning(f"⚠️ Error de validación: {e}")
        return f'''
        <!DOCTYPE html>
        <html><body style="background:#01030a;color:white;text-align:center;padding:50px;font-family:sans-serif;">
        <div style="background:rgba(231,76,60,0.1);padding:30px;border-radius:10px;max-width:500px;margin:0 auto;">
            <h2 style="color:#ff6b6b;">❌ Error de Validación</h2>
            <p>{str(e)}</p>
            <a href="/formulario-gallo" style="display:inline-block;margin-top:20px;padding:12px 24px;background:#c0392b;color:white;text-decoration:none;border-radius:6px;">← Volver al Formulario</a>
        </div>
        </body></html>
        '''
    except Exception as e:
        conn.rollback()
        app.logger.error(f"❌ Error crítico al registrar gallo: {e}", exc_info=True)
        return f'''
        <!DOCTYPE html>
        <html><body style="background:#01030a;color:white;text-align:center;padding:50px;font-family:sans-serif;">
        <div style="background:rgba(231,76,60,0.1);padding:30px;border-radius:10px;max-width:500px;margin:0 auto;">
            <h2 style="color:#ff6b6b;">❌ Error del Sistema</h2>
            <p>Ocurrió un error inesperado. Por favor intenta nuevamente.</p>
            <a href="/formulario-gallo" style="display:inline-block;margin-top:20px;padding:12px 24px;background:#c0392b;color:white;text-decoration:none;border-radius:6px;">← Volver</a>
        </div>
        </body></html>
        '''
    finally:
        conn.close()


# =============================================================================
# RUTAS DE BÚSQUEDA Y LISTADO
# =============================================================================

@app.route('/buscar', methods=['GET', 'POST'])
@proteger_ruta
def buscar():
    if request.method == 'GET':
        return '''
<!DOCTYPE html>
<html><head><title>Buscar Gallo</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body { background:#01030a; color:white; font-family:sans-serif; padding:30px; text-align:center; }
input[type="text"] { width:80%; padding:12px; margin:10px 0; background:rgba(0,0,0,0.3); color:white; border:none; border-radius:6px; font-size:17px; }
button { padding:12px 25px; background:#00ffff; color:#041428; border:none; border-radius:6px; font-weight:bold; margin-top:10px; }
a { display:inline-block; margin-top:20px; color:#00ffff; text-decoration:none; }
</style>
</head>
<body>
<h2 style="color:#00ffff;">🔍 Buscar Gallo</h2>
<form method="POST">
    <input type="text" name="termino" placeholder="Placa, nombre o color" required minlength="2">
    <br>
    <button type="submit">🔎 Buscar</button>
</form>
<a href="/menu">🏠 Menú</a>
</body></html>
'''
    
    termino = request.form.get('termino', '').strip()
    if len(termino) < 2:
        return '<script>alert("❌ Ingresa al menos 2 caracteres para buscar."); window.location="/buscar";</script>'
    
    traba = session['traba']
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Buscar coincidencia exacta por placa_traba
    cursor.execute('''
        SELECT i.id, i.placa_traba, i.placa_regional, i.nombre, i.raza, i.color, i.apariencia, i.n_pelea, i.foto,
               pr.madre_id, pr.padre_id
        FROM individuos i
        LEFT JOIN progenitores pr ON i.id = pr.individuo_id
        WHERE i.placa_traba = ? AND i.traba = ?
    ''', (termino, traba))
    
    por_placa = cursor.fetchall()
    
    if len(por_placa) == 1:
        gallo_principal = por_placa[0]
    elif len(por_placa) > 1:
        filas = "".join(f'''
            <tr onclick="window.location='/arbol/{r['id']}'" style="cursor:pointer;">
                <td style="padding:8px;">{"<img src='/uploads/%s' width='40' style='border-radius:4px;'>" % r["foto"] if r["foto"] else "—"}</td>
                <td style="padding:8px;">{r['placa_traba']}</td>
                <td style="padding:8px;">{r['nombre'] or "—"}</td>
                <td style="padding:8px;">{r['color']}</td>
                <td style="padding:8px;">{r['raza']}</td>
            </tr>
        ''' for r in por_placa)
        conn.close()
        return f'''
<!DOCTYPE html>
<html><head><title>Varios Resultados</title></head>
<body style="background:#01030a;color:white;padding:20px;font-family:sans-serif;">
<h2 style="text-align:center;color:#ff9900;">⚠️ {len(por_placa)} gallos con placa: "{termino}"</h2>
<p style="text-align:center;">Haz clic en una fila para ver su árbol genealógico.</p>
<table style="width:100%;max-width:700px;margin:0 auto;border-collapse:collapse;background:rgba(0,0,0,0.2);border-radius:10px;overflow:hidden;">
    <thead><tr style="color:#00ffff;background:rgba(0,255,255,0.1);">
        <th style="padding:10px;">Foto</th><th>Placa</th><th>Nombre</th><th>Color</th><th>Raza</th>
    </tr></thead>
    <tbody>{filas}</tbody>
</table>
<div style="text-align:center;margin-top:25px;">
    <a href="/buscar" style="padding:10px 20px;background:#2ecc71;color:#041428;text-decoration:none;border-radius:6px;">← Nueva búsqueda</a>
    <a href="/menu" style="padding:10px 20px;background:#7f8c8d;color:white;text-decoration:none;border-radius:6px;margin-left:10px;">🏠 Menú</a>
</div>
</body></html>
'''
    else:
        # Buscar por nombre o color (LIKE)
        cursor.execute('''
            SELECT i.id, i.placa_traba, i.placa_regional, i.nombre, i.raza, i.color, i.apariencia, i.n_pelea, i.foto,
                   pr.madre_id, pr.padre_id
            FROM individuos i
            LEFT JOIN progenitores pr ON i.id = pr.individuo_id
            WHERE (i.nombre LIKE ? OR i.color LIKE ?) AND i.traba = ?
            ORDER BY i.placa_traba
        ''', (f'%{termino}%', f'%{termino}%', traba))
        
        resultados = cursor.fetchall()
        
        if not resultados:
            conn.close()
            return '<script>alert("❌ No se encontró ningún gallo con esos criterios."); window.location="/buscar";</script>'
        elif len(resultados) == 1:
            gallo_principal = resultados[0]
        else:
            filas = "".join(f'''
                <tr onclick="window.location='/arbol/{r['id']}'" style="cursor:pointer;">
                    <td style="padding:8px;">{"<img src='/uploads/%s' width='40' style='border-radius:4px;'>" % r["foto"] if r["foto"] else "—"}</td>
                    <td style="padding:8px;">{r['placa_traba']}</td>
                    <td style="padding:8px;">{r['nombre'] or "—"}</td>
                    <td style="padding:8px;">{r['color']}</td>
                    <td style="padding:8px;">{r['raza']}</td>
                </tr>
            ''' for r in resultados)
            conn.close()
            return f'''
<!DOCTYPE html>
<html><head><title>Varios Resultados</title></head>
<body style="background:#01030a;color:white;padding:20px;font-family:sans-serif;">
<h2 style="text-align:center;color:#00ffff;">🔍 {len(resultados)} gallos encontrados</h2>
<p style="text-align:center;">Haz clic en una fila para ver su árbol genealógico.</p>
<table style="width:100%;max-width:700px;margin:0 auto;border-collapse:collapse;background:rgba(0,0,0,0.2);border-radius:10px;overflow:hidden;">
    <thead><tr style="color:#00ffff;background:rgba(0,255,255,0.1);">
        <th style="padding:10px;">Foto</th><th>Placa</th><th>Nombre</th><th>Color</th><th>Raza</th>
    </tr></thead>
    <tbody>{filas}</tbody>
</table>
<div style="text-align:center;margin-top:25px;">
    <a href="/buscar" style="padding:10px 20px;background:#2ecc71;color:#041428;text-decoration:none;border-radius:6px;">← Nueva búsqueda</a>
    <a href="/menu" style="padding:10px 20px;background:#7f8c8d;color:white;text-decoration:none;border-radius:6px;margin-left:10px;">🏠 Menú</a>
</div>
</body></html>
'''
    
    # === Mostrar detalle de un solo gallo ===
    madre = padre = None
    if gallo_principal['madre_id']:
        madre = cursor.execute('SELECT * FROM individuos WHERE id = ?', (gallo_principal['madre_id'],)).fetchone()
    if gallo_principal['padre_id']:
        padre = cursor.execute('SELECT * FROM individuos WHERE id = ?', (gallo_principal['padre_id'],)).fetchone()
    
    # Buscar hijos
    cursor.execute('''
        SELECT i.id, i.placa_traba, i.nombre, i.raza, i.color, i.apariencia, i.foto
        FROM individuos i
        JOIN progenitores p ON i.id = p.individuo_id
        WHERE p.madre_id = ? OR p.padre_id = ?
    ''', (gallo_principal['id'], gallo_principal['id']))
    hijos = cursor.fetchall()
    
    def tarjeta_gallo(g, titulo="", emoji=""):
        if not g:
            return f'''<div style="background:rgba(0,0,0,0.2);padding:20px;margin:20px 0;border-radius:15px;text-align:center;">
                <h3 style="color:#00ffff;">{emoji} {titulo}</h3>
                <p style="color:#bbb;">— No registrado —</p></div>'''
        nombre = g['nombre'] or g['placa_traba']
        foto_html = f'<img src="/uploads/{g["foto"]}" width="120" style="border-radius:10px;margin-bottom:15px;">' if g['foto'] else '<div style="width:120px;height:120px;background:rgba(0,0,0,0.3);border-radius:10px;margin:0 auto 15px;display:flex;align-items:center;justify-content:center;color:#aaa;">Sin Foto</div>'
        return f'''
        <div style="background:rgba(0,0,0,0.2);padding:20px;margin:20px 0;border-radius:15px;text-align:center;">
            <h3 style="color:#00ffff;margin-bottom:15px;">{emoji} {titulo}</h3>
            {foto_html}
            <div style="text-align:left;font-size:1.1em;line-height:1.6;">
                <p><strong>Placa:</strong> {g['placa_traba']}</p>
                <p><strong>Nombre:</strong> {nombre}</p>
                <p><strong>Raza:</strong> {g['raza']}</p>
                <p><strong>Color:</strong> {g['color']}</p>
                <p><strong>Apariencia:</strong> {g['apariencia']}</p>
            </div>
        </div>'''
    
    def tarjeta_hijo(h):
        nombre = h['nombre'] or h['placa_traba']
        foto_html = f'<img src="/uploads/{h["foto"]}" width="80" style="border-radius:8px;margin-bottom:10px;">' if h["foto"] else '<div style="width:80px;height:80px;background:rgba(0,0,0,0.3);border-radius:8px;display:flex;align-items:center;justify-content:center;color:#aaa;font-size:0.8em;">Sin foto</div>'
        return f'''<div style="background:rgba(0,0,0,0.2);padding:15px;margin:10px 0;border-radius:8px;text-align:center;">
            {foto_html}<p style="margin:5px 0;"><strong>{nombre}</strong></p>
            <p style="font-size:0.9em;">Placa: {h['placa_traba']}</p>
            <p style="font-size:0.8em;color:#bdc3c7;">Raza: {h['raza']}</p></div>'''
    
    caracteristica = generar_caracteristica(gallo_principal['id'], traba)
    
    resultado_html = tarjeta_gallo(gallo_principal, "Gallo Encontrado", "✅")
    resultado_html += f'<div style="background:rgba(0,0,0,0.2);padding:15px;margin:15px 0;border-radius:10px;text-align:center;"><strong>Característica clave:</strong><br><span style="color:#00ffff;">{caracteristica}</span></div>'
    resultado_html += tarjeta_gallo(padre, "Padre", "🐔")
    resultado_html += tarjeta_gallo(madre, "Madre", "🐔")
    
    if hijos:
        resultado_html += '<div style="background:rgba(0,0,0,0.2);padding:15px;margin:15px 0;border-radius:10px;text-align:center;"><strong>Hijos:</strong></div>'
        resultado_html += ''.join(tarjeta_hijo(h) for h in hijos)
    
    botones = f'''
    <div style="text-align:center;margin-top:30px;display:flex;justify-content:center;gap:15px;flex-wrap:wrap;">
        <a href="/buscar" style="padding:12px 20px;background:#2ecc71;color:#041428;text-decoration:none;border-radius:8px;">← Nueva búsqueda</a>
        <a href="/arbol/{gallo_principal['id']}" style="padding:12px 20px;background:#00ffff;color:#041428;text-decoration:none;border-radius:8px;">🌳 Ver Árbol</a>
        <a href="/menu" style="padding:12px 20px;background:#7f8c8d;color:white;text-decoration:none;border-radius:8px;">🏠 Menú</a>
    </div>'''
    
    conn.close()
    
    return f'''
<!DOCTYPE html>
<html><head><title>Resultado de Búsqueda</title></head>
<body style="background:#01030a;color:white;padding:20px;font-family:sans-serif;">
<h2 style="text-align:center;color:#00ffff;margin-bottom:30px;">🔍 Resultado</h2>
<div style="max-width:400px;margin:0 auto;">{resultado_html}</div>
{botones}
</body></html>
'''


@app.route('/lista')
@proteger_ruta
def lista_gallos():
    traba = session['traba']
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT i.id, i.placa_traba, i.placa_regional, i.nombre, i.raza, i.color, i.apariencia, i.n_pelea, i.foto, i.generacion, i.codigo,
               m.placa_traba as madre_placa, p.placa_traba as padre_placa
        FROM individuos i
        LEFT JOIN progenitores pr ON i.id = pr.individuo_id
        LEFT JOIN individuos m ON pr.madre_id = m.id
        LEFT JOIN individuos p ON pr.padre_id = p.id
        WHERE i.traba = ? 
        ORDER BY i.id DESC
    ''', (traba,))
    
    gallos = cursor.fetchall()
    conn.close()
    
    filas_html = ""
    for g in gallos:
        foto_html = f'<img src="/uploads/{g["foto"]}" width="50" style="border-radius:4px;">' if g["foto"] else "—"
        car = generar_caracteristica(g['id'], traba)
        filas_html += f'''
        <tr>
            <td style="padding:8px;text-align:center;">{foto_html}</td>
            <td style="padding:8px;">{g['placa_traba']}</td>
            <td style="padding:8px;">{g['placa_regional'] or "—"}</td>
            <td style="padding:8px;">{g['nombre'] or "—"}</td>
            <td style="padding:8px;">{g['raza'] or "—"}</td>
            <td style="padding:8px;">{g['color']}</td>
            <td style="padding:8px;">{g['apariencia']}</td>
            <td style="padding:8px;">{g['n_pelea'] or "—"}</td>
            <td style="padding:8px;">{g['madre_placa'] or "—"}</td>
            <td style="padding:8px;">{g['padre_placa'] or "—"}</td>
            <td style="padding:8px;">{g['codigo'] or "—"}</td>
            <td style="padding:8px;">{g['generacion'] or 1}</td>
            <td style="padding:8px;text-align:center;">
                <a href="/editar-gallo/{g['id']}" style="padding:6px 12px;background:#f39c12;color:black;text-decoration:none;border-radius:4px;margin-right:6px;">✏️</a>
                <a href="/arbol/{g['id']}" style="padding:6px 12px;background:#00ffff;color:#041428;text-decoration:none;border-radius:4px;margin-right:6px;">🌳</a>
                <a href="/eliminar-gallo/{g['id']}" style="padding:6px 12px;background:#e74c3c;color:white;text-decoration:none;border-radius:4px;">🗑️</a>
            </td>
        </tr>'''
    
    return f'''
<!DOCTYPE html>
<html><head><title>Mis Gallos</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{{background:#01030a;color:white;font-family:sans-serif;padding:20px;}}
h2{{text-align:center;color:#00ffff;margin-bottom:20px;}}
table{{width:100%;border-collapse:collapse;background:rgba(0,0,0,0.2);border-radius:10px;overflow:hidden;}}
th,td{{padding:10px;text-align:left;border-bottom:1px solid rgba(0,255,255,0.2);}}
th{{background:rgba(0,255,255,0.1);color:#00ffff;}}
tr:hover{{background:rgba(0,255,255,0.05);}}
a{{text-decoration:none;}}
.back-btn{{display:inline-block;margin:20px 0;padding:10px 20px;background:#2c3e50;color:white;text-decoration:none;border-radius:6px;}}
@media(max-width:768px){{table{{font-size:14px;}}td,th{{padding:6px;}}}}
</style>
</head>
<body>
<h2>📋 Mis Gallos - Traba: {traba}</h2>
<a href="/menu" class="back-btn">🏠 Menú</a>
<div style="overflow-x:auto;">
<table>
<thead><tr>
<th>Foto</th><th>Placa</th><th>Placa_reg</th><th>Nombre</th><th>Raza</th><th>Color</th>
<th>Apariencia</th><th>N°Pelea</th><th>Madre</th><th>Padre</th><th>Código</th><th>Gen</th><th>Acciones</th>
</tr></thead>
<tbody>{filas_html}</tbody>
</table>
</div>
</body></html>
'''


# =============================================================================
# RUTAS DE CRUCES E INBREEDING
# =============================================================================

@app.route('/cruce-inbreeding')
@proteger_ruta
def cruce_inbreeding():
    traba = session['traba']
    razas_html = ''.join([f'<option value="{r}">{r}</option>' for r in RAZAS])
    apariencias_html = ''.join([f'<option value="{a}">{a}</option>' for a in APARIENCIAS])
    
    return f'''
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cruce Inbreeding</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;500;700&display=swap');
*{{margin:0;padding:0;box-sizing:border-box;font-family:'Poppins',sans-serif;}}
body{{background:#01030a;color:white;font-size:16px;padding:20px;}}
.container{{max-width:700px;margin:0 auto;background:rgba(255,255,255,0.05);border-radius:12px;padding:20px;}}
h2{{color:#00ffff;text-align:center;margin:0 0 20px;}}
.section{{margin:20px 0;padding:15px;background:rgba(0,0,0,0.2);border-radius:8px;}}
h3{{color:#00ffff;margin-bottom:12px;font-size:1.1em;}}
.field{{margin:8px 0;}}
label{{display:block;margin-bottom:4px;font-weight:500;}}
input,select,textarea{{width:100%;padding:8px;background:rgba(0,0,0,0.3);color:white;border:1px solid #00ffff;border-radius:4px;}}
.btn-submit{{width:100%;padding:12px;background:linear-gradient(135deg,#e74c3c,#e67e22);color:#041428;border:none;border-radius:6px;font-weight:bold;margin-top:15px;cursor:pointer;}}
.btn-submit:disabled{{opacity:0.6;cursor:not-allowed;}}
.btn-menu{{display:inline-block;margin-top:20px;padding:10px 20px;background:#7f8c8d;color:white;text-decoration:none;border-radius:6px;font-size:16px;}}
#descripcion-cruce{{background:rgba(0,255,255,0.1);padding:15px;border-radius:8px;margin:15px 0;border-left:5px solid #00ffff;min-height:50px;}}
</style>
</head>
<body>
<div class="container">
<img src="/logo" alt="Logo" style="width:50px;float:right;filter:drop-shadow(0 0 4px #00ffff);">
<h2>🔁 Registro de Cruce Inbreeding</h2>

<form method="POST" action="/registrar-cruce" enctype="multipart/form-data">

<label for="tipo">Tipo de Cruce *</label>
<select name="tipo" id="tipo" required>
<option value="">-- Selecciona --</option>
<option value="Padre-Hija" data-ej1="Padre" data-ej2="Hija" data-estrategia="vertical">Padre - Hija</option>
<option value="Madre-Hijo" data-ej1="Madre" data-ej2="Hijo" data-estrategia="vertical">Madre - Hijo</option>
<option value="Abuelo-Nieta" data-ej1="Abuelo" data-ej2="Nieta" data-estrategia="vertical">Abuelo - Nieta</option>
<option value="Hermanos" data-ej1="Hermano A" data-ej2="Hermano B" data-estrategia="horizontal">Hermanos (Completos)</option>
<option value="MediosHermanos" data-ej1="Ejemplar 1" data-ej2="Ejemplar 2" data-estrategia="line">Medios Hermanos</option>
<option value="Tio-Sobrina" data-ej1="Tío" data-ej2="Sobrina" data-estrategia="line">Tío - Sobrina / Primo</option>
</select>

<div id="descripcion-cruce"><p>Selecciona un tipo de cruce para ver la estrategia asociada.</p></div>

<div class="section">
<h3 id="titulo1">🐔 Ejemplar 1</h3>
<div class="field"><label>Número de Placa *</label><input type="text" name="placa1" required></div>
<div class="field"><label>Placa Regional</label><input type="text" name="regional1"></div>
<div class="field"><label>N° Pelea</label><input type="text" name="pelea1"></div>
<div class="field"><label>Nombre</label><input type="text" name="nombre1"></div>
<div class="field"><label>Raza *</label><select name="raza1" required>{razas_html}</select></div>
<div class="field"><label>Color *</label><input type="text" name="color1" required></div>
<div class="field"><label>Apariencia *</label><select name="apariencia1" required>{apariencias_html}</select></div>
<div class="field"><label>Foto (opcional)</label><input type="file" name="foto1" accept="image/*"></div>
</div>

<div class="section">
<h3 id="titulo2">🐔 Ejemplar 2</h3>
<div class="field"><label>Número de Placa *</label><input type="text" name="placa2" required></div>
<div class="field"><label>Placa Regional</label><input type="text" name="regional2"></div>
<div class="field"><label>N° Pelea</label><input type="text" name="pelea2"></div>
<div class="field"><label>Nombre</label><input type="text" name="nombre2"></div>
<div class="field"><label>Raza *</label><select name="raza2" required>{razas_html}</select></div>
<div class="field"><label>Color *</label><input type="text" name="color2" required></div>
<div class="field"><label>Apariencia *</label><select name="apariencia2" required>{apariencias_html}</select></div>
<div class="field"><label>Foto (opcional)</label><input type="file" name="foto2" accept="image/*"></div>
</div>

<button type="submit" class="btn-submit">✅ Registrar Cruce</button>
</form>
<a href="/menu" class="btn-menu">🏠 Menú</a>
</div>

<script>
document.addEventListener('DOMContentLoaded', function() {{
    const selectTipo = document.getElementById('tipo');
    const descripcionDiv = document.getElementById('descripcion-cruce');
    const titulo1 = document.getElementById('titulo1');
    const titulo2 = document.getElementById('titulo2');
    
    const descripciones = {{
        'vertical': {{
            titulo: '1. Inbreeding Vertical',
            texto: 'Cruzar al mejor gallo con su mejor descendiente (hija, nieta). Fundamental para fijar características del macho fundador. Requiere selección rigurosa.'
        }},
        'horizontal': {{
            titulo: '2. Inbreeding Horizontal',
            texto: 'Cruzar hermanos completos entre sí. Método intensivo para rápida concentración de genes deseables. Aumenta riesgo de fijar defectos.'
        }},
        'line': {{
            titulo: '3. Line Breeding',
            texto: 'Forma moderada de inbreeding. Cruces entre parientes lejanos (medios hermanos, tíos/sobrinas). Fortalece virtudes con menor riesgo.'
        }}
    }};
    
    function actualizarCampos() {{
        const opt = selectTipo.options[selectTipo.selectedIndex];
        const estrategia = opt.getAttribute('data-estrategia');
        const ej1 = opt.getAttribute('data-ej1') || 'Ejemplar 1';
        const ej2 = opt.getAttribute('data-ej2') || 'Ejemplar 2';
        
        titulo1.innerHTML = '🐔 Ejemplar 1 (' + ej1 + ')';
        titulo2.innerHTML = '🐔 Ejemplar 2 (' + ej2 + ')';
        
        if (estrategia && descripciones[estrategia]) {{
            const info = descripciones[estrategia];
            descripcionDiv.innerHTML = '<h3>' + info.titulo + '</h3><p>' + info.texto + '</p>';
        }} else {{
            descripcionDiv.innerHTML = '<p>Selecciona un tipo de cruce para ver la estrategia asociada.</p>';
        }}
    }}
    
    selectTipo.addEventListener('change', actualizarCampos);
    actualizarCampos();
    
    // Indicador de carga
    document.querySelector('form').addEventListener('submit', function() {{
        const btn = this.querySelector('.btn-submit');
        if (btn) {{ btn.disabled = true; btn.textContent = '⏳ Registrando...'; }}
    }});
}});
</script>
</body>
</html>
'''


@app.route('/registrar-cruce', methods=['POST'])
@proteger_ruta
def registrar_cruce():
    traba = session['traba']
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()
    
    try:
        tipo = request.form.get('tipo', '').strip()
        if not tipo:
            raise ValueError("Selecciona un tipo de cruce.")
        
        def guardar_ejemplar(prefijo):
            placa = request.form.get(f'placa{prefijo}', '').strip()
            if not placa:
                raise ValueError(f"La placa del ejemplar {prefijo} es obligatoria.")
            
            # Verificar duplicado
            cursor.execute('SELECT 1 FROM individuos WHERE placa_traba = ? AND traba = ?', (placa, traba))
            if cursor.fetchone():
                # Si ya existe, retornar su ID
                cursor.execute('SELECT id FROM individuos WHERE placa_traba = ? AND traba = ?', (placa, traba))
                return cursor.fetchone()[0]
            
            placa_regional = request.form.get(f'regional{prefijo}', '').strip() or None
            nombre = request.form.get(f'nombre{prefijo}', '').strip() or None
            n_pelea = request.form.get(f'pelea{prefijo}', '').strip() or None
            raza = request.form.get(f'raza{prefijo}', '').strip()
            color = request.form.get(f'color{prefijo}', '').strip() or "Desconocido"
            apariencia = request.form.get(f'apariencia{prefijo}', '').strip()
            
            if not raza or not apariencia:
                raise ValueError(f"Raza y apariencia del ejemplar {prefijo} son obligatorios.")
            
            # Procesar foto
            foto = None
            if f'foto{prefijo}' in request.files:
                file = request.files[f'foto{prefijo}']
                if file and file.filename != '' and allowed_file(file.filename):
                    if is_valid_image(file.stream):
                        fname = f"{secure_filename(placa)}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(file.filename)}"
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                        foto = fname
            
            codigo = generar_codigo_unico(cursor)
            cursor.execute('''
                INSERT INTO individuos 
                (traba, placa_traba, placa_regional, nombre, raza, color, apariencia, n_pelea, foto, generacion, codigo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (traba, placa, placa_regional, nombre, raza, color, apariencia, n_pelea, foto, 1, codigo))
            return cursor.lastrowid
        
        id1 = guardar_ejemplar('1')
        id2 = guardar_ejemplar('2')
        
        # ✅ Validar: no cruzar consigo mismo
        if id1 == id2:
            raise ValueError("❌ No puedes cruzar un gallo consigo mismo.")
        
        # ✅ Validar: cruce no duplicado
        cursor.execute('''
            SELECT 1 FROM cruces 
            WHERE traba = ? AND ((individuo1_id = ? AND individuo2_id = ?) OR (individuo1_id = ? AND individuo2_id = ?))
            LIMIT 1
        ''', (traba, id1, id2, id2, id1))
        if cursor.fetchone():
            raise ValueError("⚠️ Este cruce ya está registrado.")
        
        # Porcentajes de consanguinidad
        porcentajes = {
            "Padre-Hija": 50.0, "Madre-Hijo": 50.0, "Hermanos": 50.0,
            "Abuelo-Nieta": 25.0, "MediosHermanos": 25.0, "Tio-Sobrina": 25.0
        }
        porcentaje = porcentajes.get(tipo, 0.0)
        
        cursor.execute('''
            INSERT INTO cruces 
            (traba, tipo, individuo1_id, individuo2_id, generacion, porcentaje, fecha, notas)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            traba, tipo, id1, id2, 1, porcentaje,
            datetime.now().strftime('%Y-%m-%d'),
            f"Cruce registrado desde formulario"
        ))
        
        conn.commit()
        app.logger.info(f"✅ Cruce registrado: {tipo} (IDs: {id1}, {id2})")
        
        return f'''
        <!DOCTYPE html>
        <html><body style="background:#01030a;color:white;text-align:center;padding:50px;font-family:sans-serif;">
        <div style="background:rgba(0,255,255,0.1);padding:30px;border-radius:10px;max-width:500px;margin:0 auto;">
            <h2 style="color:#00ffff;">✅ Cruce registrado exitosamente!</h2>
            <div style="margin-top:25px;">
                <a href="/lista-cruces" style="display:inline-block;padding:12px 24px;background:#00ffff;color:#041428;text-decoration:none;border-radius:6px;margin:5px;">📋 Ver Cruces</a>
                <a href="/menu" style="display:inline-block;padding:12px 24px;background:#2ecc71;color:#041428;text-decoration:none;border-radius:6px;margin:5px;">🏠 Menú</a>
            </div>
        </div>
        </body></html>
        '''
        
    except ValueError as e:
        app.logger.warning(f"⚠️ Error de validación en cruce: {e}")
        return f'''
        <!DOCTYPE html>
        <html><body style="background:#01030a;color:white;text-align:center;padding:50px;font-family:sans-serif;">
        <div style="background:rgba(231,76,60,0.1);padding:30px;border-radius:10px;max-width:500px;margin:0 auto;">
            <h2 style="color:#ff6b6b;">❌ Error</h2>
            <p>{str(e)}</p>
            <a href="/cruce-inbreeding" style="display:inline-block;margin-top:20px;padding:12px 24px;background:#c0392b;color:white;text-decoration:none;border-radius:6px;">← Volver</a>
        </div>
        </body></html>
        '''
    except Exception as e:
        conn.rollback()
        app.logger.error(f"❌ Error crítico en registrar_cruce: {e}", exc_info=True)
        return f'''
        <!DOCTYPE html>
        <html><body style="background:#01030a;color:white;text-align:center;padding:50px;font-family:sans-serif;">
        <div style="background:rgba(231,76,60,0.1);padding:30px;border-radius:10px;max-width:500px;margin:0 auto;">
            <h2 style="color:#ff6b6b;">❌ Error del Sistema</h2>
            <p>Ocurrió un error inesperado.</p>
            <a href="/cruce-inbreeding" style="display:inline-block;margin-top:20px;padding:12px 24px;background:#c0392b;color:white;text-decoration:none;border-radius:6px;">← Volver</a>
        </div>
        </body></html>
        '''
    finally:
        conn.close()


# =============================================================================
# RUTAS DE RESPALDO Y DESCARGA
# =============================================================================

@app.route('/backup', methods=['POST'])
@proteger_ruta
def crear_backup_manual():
    try:
        timestamp = datetime.now()
        fecha_archivo = timestamp.strftime("%Y%m%d_%H%M%S")
        temp_dir = f"temp_backup_{fecha_archivo}"
        os.makedirs(temp_dir, exist_ok=True)
        
        if os.path.exists(DB):
            shutil.copy2(DB, os.path.join(temp_dir, "gallos.db"))
        if os.path.exists(UPLOAD_FOLDER) and os.listdir(UPLOAD_FOLDER):
            shutil.copytree(UPLOAD_FOLDER, os.path.join(temp_dir, "uploads"), dirs_exist_ok=True)
        
        zip_filename = f"gallofino_backup_{fecha_archivo}.zip"
        os.makedirs(BACKUP_FOLDER, exist_ok=True)
        zip_path = os.path.join(BACKUP_FOLDER, zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    zipf.write(file_path, arcname)
        
        shutil.rmtree(temp_dir)
        app.logger.info(f"✅ Backup creado: {zip_filename}")
        return jsonify({"mensaje": "✅ Copia de seguridad creada.", "archivo": zip_filename})
        
    except Exception as e:
        app.logger.error(f"❌ Error creando backup: {e}", exc_info=True)
        if 'temp_dir' in locals() and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({"error": f"Error: {str(e)}"}), 500


@app.route('/download/<filename>')
@proteger_ruta
def descargar_backup(filename):
    # ✅ Protección contra path traversal
    if not filename or '..' in filename or filename.startswith('/'):
        app.logger.warning(f"⚠️ Intento de acceso inválido: {filename}")
        return "Archivo no válido", 400
    
    backups_dir = os.path.abspath(BACKUP_FOLDER)
    ruta_solicitada = os.path.abspath(os.path.join(backups_dir, filename))
    
    if not ruta_solicitada.startswith(backups_dir):
        app.logger.warning(f"⚠️ Intento de path traversal: {filename}")
        return "Acceso denegado", 403
    
    if not os.path.exists(ruta_solicitada) or not filename.endswith('.zip'):
        return "Archivo no encontrado", 404
    
    app.logger.info(f"📥 Descarga de backup: {filename}")
    return send_from_directory(BACKUP_FOLDER, filename, as_attachment=True)


# =============================================================================
# RUTAS AUXILIARES
# =============================================================================

@app.route('/uploads/<filename>')
@proteger_ruta
def uploaded_file(filename):
    # ✅ Validar que el archivo existe y está en la carpeta correcta
    ruta = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(ruta) or '..' in filename:
        return "Archivo no encontrado", 404
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/logo')
def logo():
    """Sirve el logo o un fallback SVG seguro"""
    try:
        if os.path.exists("static/OIP.png"):
            return send_from_directory("static", "OIP.png")
    except:
        pass
    
    # SVG sin emojis (compatible con todos los Python)
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80"><circle cx="40" cy="40" r="35" fill="#00ffff"/><text x="40" y="45" text-anchor="middle" fill="#041428" font-size="20" font-family="sans-serif">GF</text></svg>'
    return Response(svg.encode('utf-8'), mimetype='image/svg+xml')


@app.route('/exportar')
@proteger_ruta
def exportar():
    """Exportar datos a CSV"""
    traba = session['traba']
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM individuos WHERE traba = ?', (traba,))
    gallos = cursor.fetchall()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Placa', 'Placa_Regional', 'Nombre', 'Raza', 'Color', 'Apariencia', 'N_Pelea', 'Nacimiento', 'Foto', 'Generacion', 'Codigo'])
    
    for g in gallos:
        writer.writerow([g['id'], g['placa_traba'], g['placa_regional'], g['nombre'], g['raza'], g['color'], g['apariencia'], g['n_pelea'], g['nacimiento'], g['foto'], g['generacion'], g['codigo']])
    
    conn.close()
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=gallos_{traba}_{datetime.now().strftime("%Y%m%d")}.csv'}
    )


# =============================================================================
# RUTAS DE ÁRBOL GENEALÓGICO Y EDICIÓN
# =============================================================================

@app.route('/arbol/<int:id>')
@proteger_ruta
def arbol_gallo(id):
    traba = session['traba']
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM individuos WHERE traba = ? AND id = ?', (traba, id))
    gallo = cursor.fetchone()
    if not gallo:
        conn.close()
        return '<script>alert("❌ Gallo no encontrado."); window.location="/lista";</script>'
    
    # Obtener padres
    cursor.execute('SELECT madre_id, padre_id FROM progenitores WHERE individuo_id = ?', (id,))
    prog = cursor.fetchone()
    madre_id = prog['madre_id'] if prog else None
    padre_id = prog['padre_id'] if prog else None
    
    madre = cursor.execute('SELECT * FROM individuos WHERE id = ?', (madre_id,)).fetchone() if madre_id else None
    padre = cursor.execute('SELECT * FROM individuos WHERE id = ?', (padre_id,)).fetchone() if padre_id else None
    
    # Abuelos (simplificado)
    def obtener_abuelos(individuo):
        if not individuo:
            return None, None
        cursor.execute('SELECT madre_id, padre_id FROM progenitores WHERE individuo_id = ?', (individuo['id'],))
        row = cursor.fetchone()
        if not row:
            return None, None
        abuela = cursor.execute('SELECT * FROM individuos WHERE id = ?', (row['madre_id'],)).fetchone() if row['madre_id'] else None
        abuelo = cursor.execute('SELECT * FROM individuos WHERE id = ?', (row['padre_id'],)).fetchone() if row['padre_id'] else None
        return abuela, abuelo
    
    ab_materna, ab_materno = obtener_abuelos(madre)
    ab_paterna, ab_paterno = obtener_abuelos(padre)
    
    # Hijos
    cursor.execute('''
        SELECT i.id, i.placa_traba, i.nombre, i.raza, i.color, i.foto
        FROM individuos i
        JOIN progenitores p ON i.id = p.individuo_id
        WHERE p.madre_id = ? OR p.padre_id = ?
    ''', (id, id))
    hijos = cursor.fetchall()
    
    def tarjeta(g, titulo):
        if not g:
            return f'<div style="background:rgba(0,0,0,0.2);padding:15px;border-radius:8px;"><p style="color:#7f8c8d;">{titulo}: Desconocido</p></div>'
        nombre = g['nombre'] or g['placa_traba']
        foto = f'<img src="/uploads/{g["foto"]}" width="80" style="border-radius:8px;margin-bottom:10px;">' if g['foto'] else '<div style="width:80px;height:80px;background:rgba(0,0,0,0.3);border-radius:8px;margin:0 auto 10px;"></div>'
        return f'''<div style="background:rgba(0,0,0,0.2);padding:15px;border-radius:8px;text-align:center;">
            {foto}<p style="margin:5px 0;"><strong>{nombre}</strong></p>
            <p style="font-size:0.9em;">Placa: {g['placa_traba']}</p>
            <p style="font-size:0.8em;color:#bdc3c7;">{g['raza']}</p></div>'''
    
    conn.close()
    
    return f'''
<!DOCTYPE html>
<html><head><title>Árbol Genealógico</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{{background:#01030a;color:white;padding:20px;font-family:sans-serif;text-align:center;}}
.tree{{display:flex;flex-direction:column;align-items:center;gap:20px;max-width:1200px;margin:0 auto;}}
.gen{{display:flex;justify-content:center;gap:15px;flex-wrap:wrap;max-width:900px;}}
.card{{background:rgba(0,0,0,0.2);padding:15px;border-radius:8px;min-width:150px;max-width:200px;}}
.btn{{display:inline-block;padding:10px 20px;margin:5px;background:#00ffff;color:#041428;text-decoration:none;border-radius:6px;}}
</style>
</head>
<body>
<h2 style="color:#00ffff;">🌳 Árbol: {gallo['placa_traba']}</h2>
<div class="tree">
    <div><h3>Generación 1</h3>{tarjeta(gallo, "Principal")}</div>
    <div class="gen"><h3 style="width:100%;color:#00ffff;">Padres</h3>{tarjeta(madre, "Madre")}{tarjeta(padre, "Padre")}</div>
    <div class="gen"><h3 style="width:100%;color:#00ffff;">Abuelos</h3>{tarjeta(ab_materna, "Abuela M.")}{tarjeta(ab_materno, "Abuelo M.")}{tarjeta(ab_paterna, "Abuela P.")}{tarjeta(ab_paterno, "Abuelo P.")}</div>
    <div class="gen"><h3 style="width:100%;color:#2ecc71;">Hijos ({len(hijos)})</h3>{''.join(tarjeta(h, h['nombre'] or h['placa_traba']) for h in hijos) or '<p style="color:#7f8c8d;">— Sin hijos registrados —</p>'}</div>
</div>
<div style="margin-top:30px;">
    <a href="/agregar-descendiente/{gallo['id']}" class="btn">➕ Agregar Progenitor</a>
    <a href="/lista" class="btn" style="background:#2ecc71;">📋 Mis Gallos</a>
    <a href="/menu" class="btn" style="background:#7f8c8d;color:white;">🏠 Menú</a>
</div>
</body></html>
'''


@app.route('/editar-gallo/<int:id>', methods=['GET', 'POST'])
@proteger_ruta
def editar_gallo(id):
    traba = session['traba']
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM individuos WHERE id = ? AND traba = ?', (id, traba))
    gallo = cursor.fetchone()
    if not gallo:
        conn.close()
        return '<script>alert("❌ Gallo no encontrado."); window.location="/lista";</script>'
    
    if request.method == 'POST':
        try:
            placa = request.form.get('placa_traba', '').strip()
            if not placa:
                raise ValueError("La placa es obligatoria.")
            
            # Verificar duplicado (excluyendo el propio gallo)
            cursor.execute('SELECT 1 FROM individuos WHERE placa_traba = ? AND traba = ? AND id != ?', (placa, traba, id))
            if cursor.fetchone():
                raise ValueError(f"Ya existe otro gallo con placa '{placa}' en tu traba.")
            
            cursor.execute('''
                UPDATE individuos SET
                placa_traba = ?, placa_regional = ?, nombre = ?, raza = ?, color = ?, apariencia = ?, n_pelea = ?
                WHERE id = ?
            ''', (
                placa,
                request.form.get('placa_regional', '').strip() or None,
                request.form.get('nombre', '').strip() or None,
                request.form.get('raza', '').strip(),
                request.form.get('color', '').strip(),
                request.form.get('apariencia', '').strip(),
                request.form.get('n_pelea', '').strip() or None,
                id
            ))
            
            # Procesar nueva foto
            if 'foto' in request.files:
                file = request.files['foto']
                if file and file.filename != '' and allowed_file(file.filename):
                    if is_valid_image(file.stream):
                        # Eliminar foto anterior si existe
                        if gallo['foto']:
                            ruta_ant = os.path.join(app.config['UPLOAD_FOLDER'], gallo['foto'])
                            if os.path.exists(ruta_ant):
                                os.remove(ruta_ant)
                        fname = f"{secure_filename(placa)}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(file.filename)}"
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                        cursor.execute('UPDATE individuos SET foto = ? WHERE id = ?', (fname, id))
            
            conn.commit()
            app.logger.info(f"✅ Gallo actualizado: {placa}")
            return f'<script>alert("✅ Gallo actualizado."); window.location="/arbol/{id}";</script>'
            
        except ValueError as e:
            app.logger.warning(f"⚠️ Error validando edición: {e}")
            return f'<script>alert("❌ {str(e)}"); window.history.back();</script>'
        except Exception as e:
            conn.rollback()
            app.logger.error(f"❌ Error actualizando gallo: {e}", exc_info=True)
            return f'<script>alert("❌ Error del sistema."); window.history.back();</script>'
        finally:
            conn.close()
    
    # GET: mostrar formulario
    razas_html = ''.join([f'<option value="{r}" {"selected" if r == gallo["raza"] else ""}>{r}</option>' for r in RAZAS])
    ap_html = ''.join([f'<label><input type="radio" name="apariencia" value="{a}" {"checked" if a == gallo["apariencia"] else ""}> {a}</label> ' for a in APARIENCIAS])
    foto_html = f'<img src="/uploads/{gallo["foto"]}" width="100" style="border-radius:8px;">' if gallo["foto"] else '<p style="color:#aaa;">Sin foto</p>'
    
    conn.close()
    return f'''
<!DOCTYPE html>
<html><head><title>Editar Gallo</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{{background:#01030a;color:white;font-family:sans-serif;padding:20px;}}
.container{{max-width:600px;margin:0 auto;background:rgba(0,0,0,0.3);padding:25px;border-radius:15px;}}
h2{{text-align:center;color:#00ffff;}}
label{{display:block;margin:12px 0 6px;font-weight:500;}}
input,select{{width:100%;padding:10px;background:rgba(0,0,0,0.4);color:white;border:1px solid #00ffff;border-radius:6px;margin-bottom:10px;}}
.btn{{display:inline-block;padding:12px 24px;margin:10px 5px;background:#2ecc71;color:#041428;text-decoration:none;border-radius:6px;font-weight:bold;}}
.btn-cancel{{background:#7f8c8d;color:white;}}
</style>
</head>
<body>
<div class="container">
<h2>✏️ Editar: {gallo['placa_traba']}</h2>
<form method="POST" enctype="multipart/form-data">
<label>Placa de Traba *</label><input type="text" name="placa_traba" value="{gallo['placa_traba']}" required>
<label>Placa Regional</label><input type="text" name="placa_regional" value="{gallo['placa_regional'] or ''}">
<label>Nombre</label><input type="text" name="nombre" value="{gallo['nombre'] or ''}">
<label>Raza *</label><select name="raza" required>{razas_html}</select>
<label>Color *</label><input type="text" name="color" value="{gallo['color']}" required>
<label>Apariencia *</label><div style="margin:10px 0;">{ap_html}</div>
<label>N° Pelea</label><input type="text" name="n_pelea" value="{gallo['n_pelea'] or ''}">
<label>Foto actual</label><div style="margin:10px 0;">{foto_html}</div>
<label>Cambiar foto</label><input type="file" name="foto" accept="image/*">
<div style="text-align:center;margin-top:20px;">
<button type="submit" class="btn">✅ Guardar</button>
<a href="/arbol/{id}" class="btn btn-cancel">🚫 Cancelar</a>
</div>
</form>
</div>
</body></html>
'''


@app.route('/eliminar-gallo/<int:id>', methods=['GET', 'POST'])
@proteger_ruta
def eliminar_gallo(id):
    traba = session['traba']
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    
    cursor.execute('SELECT placa_traba, foto FROM individuos WHERE id = ? AND traba = ?', (id, traba))
    resultado = cursor.fetchone()
    if not resultado:
        conn.close()
        return '<script>alert("❌ Gallo no encontrado."); window.location="/lista";</script>'
    
    placa_correcta, foto_nombre = resultado
    
    if request.method == 'POST':
        placa_confirm = request.form.get('placa_confirm', '').strip()
        if placa_confirm == placa_correcta:
            try:
                # Eliminar foto si existe
                if foto_nombre:
                    ruta_foto = os.path.join(app.config['UPLOAD_FOLDER'], foto_nombre)
                    if os.path.exists(ruta_foto):
                        os.remove(ruta_foto)
                        app.logger.info(f"🗑️ Foto eliminada: {foto_nombre}")
                
                # Eliminar relaciones y gallo (CASCADE por FK)
                cursor.execute('DELETE FROM progenitores WHERE individuo_id = ?', (id,))
                cursor.execute('DELETE FROM individuos WHERE id = ? AND traba = ?', (id, traba))
                conn.commit()
                app.logger.info(f"✅ Gallo eliminado: {placa_correcta}")
                return f'<script>alert("✅ Gallo eliminado."); window.location="/lista";</script>'
            except Exception as e:
                conn.rollback()
                app.logger.error(f"❌ Error eliminando gallo: {e}", exc_info=True)
                return f'<script>alert("❌ Error al eliminar."); window.history.back();</script>'
            finally:
                conn.close()
        else:
            conn.close()
            return f'''
            <!DOCTYPE html><html><body style="background:#01030a;color:white;text-align:center;padding:40px;font-family:sans-serif;">
            <div style="background:rgba(231,76,60,0.2);padding:25px;border-radius:10px;max-width:500px;margin:0 auto;">
                <h3 style="color:#ff6b6b;">❌ Placa incorrecta</h3>
                <p>La placa ingresada no coincide con: <strong>{placa_correcta}</strong></p>
                <form method="POST"><input type="text" name="placa_confirm" placeholder="Escribe: {placa_correcta}" required
                style="width:100%;padding:10px;margin:15px 0;background:rgba(0,0,0,0.3);color:white;border:none;border-radius:6px;">
                <button type="submit" style="width:100%;padding:12px;background:#e74c3c;color:white;border:none;border-radius:6px;font-weight:bold;">🗑️ Intentar de nuevo</button></form>
                <a href="/lista" style="display:inline-block;margin-top:20px;padding:10px 20px;background:#7f8c8d;color:white;text-decoration:none;border-radius:6px;">← Cancelar</a>
            </div></body></html>
            '''
    
    conn.close()
    return f'''
    <!DOCTYPE html><html><body style="background:#01030a;color:white;text-align:center;padding:40px;font-family:sans-serif;">
        <div style="background:rgba(231,76,60,0.2);padding:25px;border-radius:10px;max-width:500px;margin:0 auto;">
            <h3 style="color:#e74c3c;">⚠️ Confirmar Eliminación</h3>
            <p>Eliminarás el gallo con <strong>Placa: {placa_correcta}</strong>. Esta acción no se puede deshacer.</p>
            <p>Escribe <strong>exactamente</strong> la placa para confirmar:</p>
            <form method="POST"><input type="text" name="placa_confirm" placeholder="{placa_correcta}" required
            style="width:100%;padding:10px;margin:15px 0;background:rgba(0,0,0,0.3);color:white;border:none;border-radius:6px;font-size:16px;">
            <button type="submit" style="width:100%;padding:12px;background:#e74c3c;color:white;border:none;border-radius:6px;font-weight:bold;">🗑️ Confirmar Eliminación</button></form>
            <a href="/lista" style="display:inline-block;margin-top:20px;padding:10px 20px;background:#7f8c8d;color:white;text-decoration:none;border-radius:6px;">← Cancelar</a>
        </div>
    </body></html>
    '''


# =============================================================================
# EJECUCIÓN PRINCIPAL
# =============================================================================

if __name__ == '__main__':
    init_db()
    app.logger.info("🐓 GalloFino iniciado")
    # En producción: usar gunicorn, no debug=True
    debug_mode = os.environ.get('FLASK_ENV') != 'production'
    app.run(debug=debug_mode, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
