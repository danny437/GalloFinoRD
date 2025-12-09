from flask import Flask, request, Response, session, redirect, url_for, send_from_directory, jsonify
import sqlite3
import os
import csv
import io
import shutil
import zipfile
from datetime import datetime
from werkzeug.utils import secure_filename
import secrets
import random
import string
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'clave_secreta_para_gallos_2025_mejor_cambiala')
DB = 'gallos.db'
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
RAZAS = [
    "Hatch", "Sweater", "Kelso", "Grey", "Albany",
    "Radio", "Asil (Aseel)", "Shamo", "Spanish", "Peruvian"
]
TABLAS_PERMITIDAS = {'individuos', 'cruces'}
OTP_TEMP = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generar_codigo_unico(cursor):
    while True:
        codigo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        cursor.execute('SELECT 1 FROM individuos WHERE codigo = ?', (codigo,))
        if not cursor.fetchone():
            return codigo

def init_db():
    if not os.path.exists(DB):
        conn = sqlite3.connect(DB)
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE trabas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_traba TEXT UNIQUE NOT NULL,
            nombre_completo TEXT NOT NULL,
            correo TEXT UNIQUE NOT NULL,
            contraseña_hash TEXT NOT NULL
        )
        ''')
        cursor.execute('''
        CREATE TABLE individuos (
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
            codigo TEXT UNIQUE
        )
        ''')
        cursor.execute('''
        CREATE TABLE progenitores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            individuo_id INTEGER NOT NULL,
            madre_id INTEGER,
            padre_id INTEGER,
            FOREIGN KEY (individuo_id) REFERENCES individuos (id),
            FOREIGN KEY (madre_id) REFERENCES individuos (id),
            FOREIGN KEY (padre_id) REFERENCES individuos (id)
        )
        ''')
        cursor.execute('''
        CREATE TABLE cruces (
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
        conn.commit()
        conn.close()
    else:
        conn = sqlite3.connect(DB)
        cursor = conn.cursor()
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

def proteger_ruta(f):
    def wrapper(*args, **kwargs):
        if 'traba' not in session:
            return redirect(url_for('bienvenida'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

@app.route('/solicitar-otp', methods=['POST'])
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
    OTP_TEMP[correo] = {'codigo': codigo, 'traba': traba}
    print(f"📧 [OTP para {correo}]: {codigo}")
    return f"""
    <script>
   
        alert("✅ Código enviado a tu correo. (Verifica la consola si estás en desarrollo)");
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
<html><head><title>Verificar OTP</title></head>
<body style="background:#01030a;color:white;text-align:center;padding:50px;font-family:sans-serif;">
    <h2>🔐 Ingresar Código</h2>
    <p>Código enviado a: <strong>{correo}</strong></p>
    <form method="POST" action="/verificar-otp">
        <input type="hidden" name="correo" value="{correo}">
        <input type="text" name="codigo" required placeholder="Código de 6 dígitos" maxlength="6" style="padding:10px;font-size:18px;">
        <br><br>
        <button type="submit" style="padding:10px 20px;background:#2ecc71;color:#041428;border:none;border-radius:5px;">✅ Verificar</button>
    </form>
    <p><a href="/" style="color:#00ffff;">← Regresar</a></p>
</body></html>
"""
@app.route('/verificar-otp', methods=['POST'])
def verificar_otp():
    correo = request.form.get('correo', '').strip()
    codigo = request.form.get('codigo', '').strip()
    if not correo or not codigo:
        return redirect(url_for('bienvenida'))
    if correo in OTP_TEMP and OTP_TEMP[correo]['codigo'] == codigo:
        traba = OTP_TEMP[correo]['traba']
        session['traba'] = traba.strip()
        del OTP_TEMP[correo]
        return redirect(url_for('menu_principal'))
    else:
        return '<script>alert("❌ Código incorrecto o expirado."); window.location="/";</script>'
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
@app.route("/logo")
def logo():
    return send_from_directory("static", "OIP.png")
# =============== INICIO ===============
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
<img src="/logo" alt="Logo GFRD" class="logo">
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
<input type="password" name="contraseña" required placeholder="Contraseña (mín. 6 caracteres)">
<input type="date" name="fecha" value="{fecha_actual}">
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
    this.x += this.speedX;
    this.y += this.speedY;
    if (this.x < 0) this.x = canvas.width;
    if (this.x > canvas.width) this.x = 0;
    if (this.y < 0) this.y = canvas.height;
    if (this.y > canvas.height) this.y = 0;
  }}
  draw() {{
    ctx.fillStyle = "rgba(0,255,255,0.7)";
    ctx.beginPath();
    ctx.arc(this.x, this.y, this.size, 0, Math.PI*2);
    ctx.fill();
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
</script>
</body>
</html>
"""
@app.route('/iniciar-sesion', methods=['POST'])
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
        return '<script>alert("❌ Correo o contraseña incorrectos."); window.location="/";</script>'
    session['traba'] = traba_row[0].strip()
    return redirect(url_for('menu_principal'))

# ===============✅ MENÚ PRINCIPAL ===============
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
<title>GFRD Menú 2026</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;500;700&display=swap');
*{{margin:0; padding:0; box-sizing:border-box; font-family:'Poppins', sans-serif;}}
body{{
    background: #01030a;
    color: white;
    font-size: 17px;
    overflow-x: hidden;
}}
.container{{
    width:95%;
    max-width:900px;
    margin:40px auto;
    background: rgba(0, 0, 0, 0.4);
    border-radius: 20px;
    padding: 25px;
    backdrop-filter: blur(10px);
    box-shadow: 0 0 30px rgba(0, 255, 255, 0.4);
    position: relative;
    z-index: 2;
}}
.header-modern{{
    display:flex;
    justify-content:space-between;
    align-items:center;
    margin-bottom:30px;
    flex-wrap:wrap;
    gap:15px;
}}
.header-modern h1{{
    font-size:1.8rem;
    color:#00ffff;
    text-shadow:0 0 10px #00ffff;
}}
.subtitle{{
    font-size:0.85rem;
    color:#bbb;
}}
.logo{{
    width:80px;
    height:auto;
    filter:drop-shadow(0 0 6px #00ffff);
}}
#scene3d {{
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: 0;
    background: radial-gradient(ellipse at center, #000410 0%, #01030a 100%);
}}
#scene3d .layer {{
    position: absolute;
    top: 0;
    left: 0;
    width: 200%;
    height: 200%;
    background-repeat: no-repeat;
    background-size: 400px;
    opacity: 0.15;
    will-change: transform;
}}
#scene3d .layer-1 {{
    background: radial-gradient(circle, #00ffff 2px, transparent 2px);
    animation: float 25s infinite linear;
}}
#scene3d .layer-2 {{
    background: radial-gradient(circle, #ff7a18 1.5px, transparent 1.5px);
    animation: float 35s infinite linear reverse;
    opacity: 0.1;
}}
#scene3d .layer-3 {{
    background: radial-gradient(circle, #f6c84c 1px, transparent 1px);
    animation: float 20s infinite linear;
    opacity: 0.07;
}}
@keyframes float {{
    0% {{ transform: translate(0, 0) rotate(0deg); }}
    100% {{ transform: translate(-25%, -25%) rotate(360deg); }}
}}
.content-wrapper {{
    position: relative;
    z-index: 3;
}}
.card{{
    background:rgba(255,255,255,0.06);
    border-radius:20px;
    padding:25px;
    backdrop-filter:blur(10px);
    box-shadow:0 0 30px rgba(0,255,255,0.4);
}}
.menu-grid{{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 15px;
    margin: 20px 0;
}}
.menu-btn{{
    display: block;
    width:100%;
    padding:16px;
    text-align:center;
    border-radius:10px;
    background:linear-gradient(135deg,#f6c84c,#ff7a18);
    color:#041428;
    font-weight:bold;
    text-decoration:none;
    transition:0.3s;
    font-size:17px;
}}
.menu-btn:hover{{
    transform:translateY(-3px);
    box-shadow:0 6px 20px rgba(0,255,255,0.5);
}}
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
                <div>
                    <h1>🐓 Traba: {traba}</h1>
                    <p class="subtitle">Sistema moderno • Año 2026</p>
                </div>
                <img src="/logo" alt="Logo GFRD" class="logo">
            </div>
            <div class="card">
                <div class="menu-grid">
                    <a href="/formulario-gallo" class="menu-btn">🐓 Registrar Gallo</a>
                    <a href="/cruce-inbreeding" class="menu-btn">🔁 Cruce Inbreeding</a>
                    <!-- ✅ CORRECCIÓN 1: enlace a /lista -->
                    <a href="/lista" class="menu-btn">📋 Mis Gallos</a>
                    <a href="/buscar" class="menu-btn">🔍 Buscar</a>
                    <a href="lista_gallos" class="menu-btn">📤 Exportar</a>
                    <a href="javascript:void(0);" class="menu-btn" onclick="crearBackup()">💾 Respaldo</a>
                    <a href="/cerrar-sesion" class="menu-btn" style="background:linear-gradient(135deg,#7f8c8d,#95a5a6);">🚪 Cerrar Sesión</a>
                </div>
            </div>
        </div>
    </div>
    <div id="mensaje-backup" style="text-align:center; margin-top:15px; color:#27ae60; font-weight:bold;"></div>
    <script>
    function crearBackup() {{
        fetch("/backup", {{ method: "POST" }})
            .then(r => r.json())
            .then(d => {{
                if (d.error) {{
                    document.getElementById("mensaje-backup").innerHTML = `<span style="color:#e74c3c;">❌ ${{d.error}}</span>`;
                }} else {{
                    document.getElementById("mensaje-backup").innerHTML = `<span style="color:#27ae60;">${{d.mensaje}}</span>`;
                    window.location.href = "/download/" + d.archivo;
                }}
            }});
    }}
    </script>
</body>
</html>
"""

# ===============✅ BUSCAR ===============
@app.route('/buscar', methods=['GET', 'POST'])
@proteger_ruta
def buscar():
    if request.method == 'GET':
        return f'''
<!DOCTYPE html>
<html><head><title>Buscar Gallo</title>
<style>
body {{ background:#01030a; color:white; font-family:sans-serif; padding:30px; text-align:center; }}
input[type="text"] {{ width:80%; padding:12px; margin:10px 0; background:rgba(0,0,0,0.3); color:white; border:none; border-radius:6px; font-size:17px; }}
button {{ padding:12px 25px; background:#00ffff; color:#041428; border:none; border-radius:6px; font-weight:bold; margin-top:10px; }}
a {{ display:inline-block; margin-top:20px; color:#00ffff; text-decoration:underline; }}
</style>
</head>
<body>
<h2 style="color:#00ffff;">🔍 Buscar Gallo</h2>
<form method="POST">
    <input type="text" name="termino" placeholder="Placa, nombre o color" required>
    <br>
    <button type="submit">🔎 Buscar</button>
</form>
<a href="/menu">🏠 Menú</a>
</body></html>
'''
    termino = request.form.get('termino', '').strip()
    if not termino:
        return '<script>alert("❌ Ingresa un término de búsqueda."); window.location="/buscar";</script>'
    traba = session['traba']
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    # 1. Buscar coincidencias exactas por placa_traba
    cursor.execute('''
        SELECT i.id, i.placa_traba, i.placa_regional, i.nombre, i.raza, i.color, i.apariencia, i.n_pelea, i.foto,
               pr.madre_id, pr.padre_id
        FROM individuos i
        LEFT JOIN progenitores pr ON i.id = pr.individuo_id
        WHERE i.placa_traba = ? AND i.traba = ?
    ''', (termino, traba))
    por_placa = cursor.fetchall()
    if len(por_placa) == 1:
        # Una sola coincidencia exacta → mostrar directamente
        gallo_principal = por_placa[0]
    elif len(por_placa) > 1:
        # Múltiples gallos con la misma placa → mostrar lista
        filas = ""
        for r in por_placa:
            nombre = r['nombre'] or "—"
            foto_html = f'<img src="/uploads/{r["foto"]}" width="40" style="border-radius:4px;">' if r["foto"] else "—"
            filas += f'''
            <tr onclick="window.location='/arbol/{r['id']}'" style="cursor:pointer; background:rgba(0,255,255,0.05);">
                <td style="padding:8px; text-align:center;">{foto_html}</td>
                <td style="padding:8px; text-align:center;">{r['placa_traba']}</td>
                <td style="padding:8px; text-align:center;">{nombre}</td>
                <td style="padding:8px; text-align:center;">{r['color']}</td>
                <td style="padding:8px; text-align:center;">{r['raza']}</td>
            </tr>
            '''
        conn.close()
        return f'''
<!DOCTYPE html>
<html><head><title>Varios con misma placa</title></head>
<body style="background:#01030a;color:white;padding:20px;font-family:sans-serif;">
<h2 style="text-align:center;color:#ff9900;">⚠️ {len(por_placa)} gallos con la placa: <code>{termino}</code></h2>
<p style="text-align:center; margin-bottom:20px;">Haz clic en cualquier fila para ver su árbol.</p>
<table style="width:100%; max-width:700px; margin:0 auto; border-collapse:collapse; background:rgba(0,0,0,0.2); border-radius:10px; overflow:hidden;">
    <thead>
        <tr style="color:#00ffff; background:rgba(0,255,255,0.1);">
            <th style="padding:10px;">Foto</th>
            <th style="padding:10px;">Placa</th>
            <th style="padding:10px;">Nombre</th>
            <th style="padding:10px;">Color</th>
            <th style="padding:10px;">Raza</th>
        </tr>
    </thead>
    <tbody>
        {filas}
    </tbody>
</table>
<div style="text-align:center; margin-top:25px;">
    <a href="/buscar" style="padding:10px 20px; background:#2ecc71; color:#041428; text-decoration:none; border-radius:6px;">← Nueva búsqueda</a>
    <a href="/menu" style="padding:10px 20px; background:#7f8c8d; color:white; text-decoration:none; border-radius:6px; margin-left:10px;">🏠 Menú</a>
</div>
</body></html>
'''
    else:
        # No hay coincidencia exacta por placa → buscar por nombre o color
        cursor.execute('''
            SELECT i.id, i.placa_traba, i.placa_regional, i.nombre, i.raza, i.color, i.apariencia, i.n_pelea, i.foto,
                   pr.madre_id, pr.padre_id
            FROM individuos i
            LEFT JOIN progenitores pr ON i.id = pr.individuo_id
            WHERE (i.nombre LIKE ? OR i.color LIKE ?) AND i.traba = ?
            ORDER BY i.placa_traba
        ''', (f'%{termino}%', f'%{termino}%', traba))
        por_nombre_color = cursor.fetchall()
        if len(por_nombre_color) == 0:
            conn.close()
            return '<script>alert("❌ No se encontró ningún gallo."); window.location="/buscar";</script>'
        elif len(por_nombre_color) == 1:
            gallo_principal = por_nombre_color[0]
        else:
            # Múltiples coincidencias por nombre/color → lista interactiva
            filas = ""
            for r in por_nombre_color:
                nombre = r['nombre'] or "—"
                foto_html = f'<img src="/uploads/{r["foto"]}" width="40" style="border-radius:4px;">' if r["foto"] else "—"
                filas += f'''
                <tr onclick="window.location='/arbol/{r['id']}'" style="cursor:pointer; background:rgba(0,255,255,0.05);">
                    <td style="padding:8px; text-align:center;">{foto_html}</td>
                    <td style="padding:8px; text-align:center;">{r['placa_traba']}</td>
                    <td style="padding:8px; text-align:center;">{nombre}</td>
                    <td style="padding:8px; text-align:center;">{r['color']}</td>
                    <td style="padding:8px; text-align:center;">{r['raza']}</td>
                </tr>
                '''
            conn.close()
            return f'''
<!DOCTYPE html>
<html><head><title>Varios Resultados</title></head>
<body style="background:#01030a;color:white;padding:20px;font-family:sans-serif;">
<h2 style="text-align:center;color:#ff9900;">🔍 {len(por_nombre_color)} gallos encontrados</h2>
<p style="text-align:center; margin-bottom:20px;">Haz clic en cualquier fila para ver su árbol genealógico.</p>
<table style="width:100%; max-width:700px; margin:0 auto; border-collapse:collapse; background:rgba(0,0,0,0.2); border-radius:10px; overflow:hidden;">
    <thead>
        <tr style="color:#00ffff; background:rgba(0,255,255,0.1);">
            <th style="padding:10px;">Foto</th>
            <th style="padding:10px;">Placa</th>
            <th style="padding:10px;">Nombre</th>
            <th style="padding:10px;">Color</th>
            <th style="padding:10px;">Raza</th>
        </tr>
    </thead>
    <tbody>
        {filas}
    </tbody>
</table>
<div style="text-align:center; margin-top:25px;">
    <a href="/buscar" style="padding:10px 20px; background:#2ecc71; color:#041428; text-decoration:none; border-radius:6px;">← Nueva búsqueda</a>
    <a href="/menu" style="padding:10px 20px; background:#7f8c8d; color:white; text-decoration:none; border-radius:6px; margin-left:10px;">🏠 Menú</a>
</div>
</body></html>
'''
    # === Mostrar un solo gallo ===
    madre = None
    padre = None
    if gallo_principal['madre_id']:
        cursor.execute('SELECT * FROM individuos WHERE id = ?', (gallo_principal['madre_id'],))
        madre = cursor.fetchone()
    if gallo_principal['padre_id']:
        cursor.execute('SELECT * FROM individuos WHERE id = ?', (gallo_principal['padre_id'],))
        padre = cursor.fetchone()
    def generar_caracteristica_busqueda(gallo_id, traba):
        roles = []
        conn2 = sqlite3.connect(DB)
        conn2.row_factory = sqlite3.Row
        cur = conn2.cursor()
        cur.execute('SELECT i.placa_traba FROM individuos i JOIN progenitores p ON i.id = p.individuo_id WHERE p.madre_id = ?', (gallo_id,))
        for r in cur.fetchall():
            roles.append(f"Madre del placa {r['placa_traba']}")
        cur.execute('SELECT i.placa_traba FROM individuos i JOIN progenitores p ON i.id = p.individuo_id WHERE p.padre_id = ?', (gallo_id,))
        for r in cur.fetchall():
            roles.append(f"Padre del placa {r['placa_traba']}")
        cur.execute('''
            SELECT DISTINCT i.placa_traba
            FROM individuos i
            JOIN progenitores p1 ON i.id = p1.individuo_id
            JOIN progenitores p2 ON p1.madre_id = ? OR p1.padre_id = ?
        ''', (gallo_id, gallo_id))
        for r in cur.fetchall():
            roles.append(f"Abuelo/a del placa {r['placa_traba']}")
        conn2.close()
        return "; ".join(roles[:2]) + ("..." if len(roles) > 2 else "") if roles else "—"
    caracteristica = generar_caracteristica_busqueda(gallo_principal['id'], traba)
    def tarjeta_gallo(g, titulo="", emoji=""):
        if not g:
            return f'''
            <div style="background:rgba(0,0,0,0.2); padding:20px; margin:20px 0; border-radius:15px; text-align:center; border:1px solid rgba(0,255,255,0.2);">
                <h3 style="color:#00ffff; margin-bottom:15px;">{emoji} {titulo}</h3>
                <p style="font-size:1.1em; color:#bbb;">— No registrado —</p>
            </div>
            '''
        nombre = g['nombre'] or g['placa_traba']
        foto_html = f'<img src="/uploads/{g["foto"]}" width="120" style="border-radius:10px; margin-bottom:15px; box-shadow:0 0 10px rgba(0,255,255,0.3);">' if g['foto'] else '<div style="width:120px; height:120px; background:rgba(0,0,0,0.3); border-radius:10px; display:flex; align-items:center; justify-content:center; margin-bottom:15px;"><span style="color:#aaa;">Sin Foto</span></div>'
        return f'''
        <div style="background:rgba(0,0,0,0.2); padding:20px; margin:20px 0; border-radius:15px; text-align:center; border:1px solid rgba(0,255,255,0.2);">
            <h3 style="color:#00ffff; margin-bottom:15px;">{emoji} {titulo}</h3>
            {foto_html}
            <div style="text-align:left; font-size:1.1em; line-height:1.6;">
                <p><strong>Placa:</strong> {g['placa_traba']}</p>
                <p><strong>Nombre:</strong> {nombre}</p>
                <p><strong>Raza:</strong> {g['raza']}</p>
                <p><strong>Color:</strong> {g['color']}</p>
                <p><strong>Apariencia:</strong> {g['apariencia']}</p>
                <p><strong>N° Pelea:</strong> {g['n_pelea'] or "—"}</p>
                <p><strong>Placa Regional:</strong> {g['placa_regional'] or "—"}</p>
            </div>
        </div>
        '''
    resultado_html = tarjeta_gallo(gallo_principal, "Gallo Encontrado", "✅")
    resultado_html += f'<div style="background:rgba(0,0,0,0.2); padding:15px; margin:15px 0; border-radius:10px; text-align:center;"><strong>Característica clave:</strong><br><span style="color:#00ffff;">{caracteristica}</span></div>'
    resultado_html += tarjeta_gallo(padre, "Padre", "🐔")
    resultado_html += tarjeta_gallo(madre, "Madre", "🐔")
    botones_html = f'''
    <div style="text-align:center; margin-top:30px; display:flex; justify-content:center; gap:15px; flex-wrap:wrap;">
        <a href="/buscar" style="padding:12px 20px; background:#2ecc71; color:#041428; text-decoration:none; border-radius:8px; font-weight:bold;">← Nueva búsqueda</a>
        <a href="/arbol/{gallo_principal['id']}" style="padding:12px 20px; background:#00ffff; color:#041428; text-decoration:none; border-radius:8px; font-weight:bold;">🌳 Ver Árbol</a>
        <a href="/menu" style="padding:12px 20px; background:#7f8c8d; color:white; text-decoration:none; border-radius:8px; font-weight:bold;">🏠 Menú</a>
    </div>
    '''
    conn.close()
    return f'''
<!DOCTYPE html>
<html><head><title>Resultado de Búsqueda</title></head>
<body style="background:#01030a;color:white;padding:20px;font-family:sans-serif;">
<h2 style="text-align:center;color:#00ffff;margin-bottom:30px;">🔍 Resultado de Búsqueda</h2>
<div style="max-width:400px; margin:0 auto;">
{resultado_html}
</div>
{botones_html}
</body></html>
'''
# ===================✅ REGISTRO DE GALLO ===================
@app.route('/formulario-gallo')
@proteger_ruta
def formulario_gallo():
    traba = session['traba']
    razas_html = ''.join([f'<option value="{r}">{r}</option>' for r in RAZAS])
    apariencias = ['Crestarosa', 'Cocolo', 'Tuceperne', 'Pava', 'Moton']
    ap_html = ''.join([f'<label style="display:inline-block; margin-right:15px;"><input type="radio" name="gallo_apariencia" value="{a}" required> {a}</label>' for a in apariencias])
    return f"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GFRD Registro de Gallo 2026</title>
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
.back-btn{{display:inline-block; margin-top:20px; padding:10px 20px; background:#2c3e50; color:white; text-decoration:none; border-radius:6px; text-align:center;}}
</style>
</head>
<body>
<div class="container">
<div class="header-modern">
<div>
<h1>🐓 Traba: {traba}</h1>
<p class="subtitle">Sistema moderno • Año 2026</p>
</div>
<img src="/logo" alt="Logo GFRD" class="logo">
</div>
<form method="POST" action="/registrar-gallo" enctype="multipart/form-data" class="form-container">
    <h3 style="text-align:center; color:#2980b9; margin-bottom:20px;">A. Registrar Gallo Principal (Obligatorio)</h3>
    <label>Placa de Traba:</label>
    <input type="text" name="gallo_placa_traba" required class="btn-ghost">
    <label>Placa Regional (opcional):</label>
    <input type="text" name="gallo_placa_regional" class="btn-ghost">
    <label>N° Pelea:</label>
    <input type="text" name="gallo_n_pelea" class="btn-ghost">
    <label>Nombre del ejemplar:</label>
    <input type="text" name="gallo_nombre" class="btn-ghost">
    <label>Raza:</label>
    <select name="gallo_raza" required class="btn-ghost">{razas_html}</select>
    <label>Color:</label>
    <input type="text" name="gallo_color" required class="btn-ghost">
    <label>Apariencia:</label>
    <div style="margin:5px 0; font-size:16px;">{ap_html}</div>
    <label>Foto (opcional):</label>
    <input type="file" name="gallo_foto" accept="image/*" class="btn-ghost">
    <button type="submit">✅ Registrar Gallo</button>
    <a href="/menu" class="back-btn">🏠 Regresar al Menú</a>
</form>
</div>
</body>
</html>
"""

@app.route('/registrar-gallo', methods=['POST'])
@proteger_ruta
def registrar_gallo():
    traba = session['traba']
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        placa = request.form.get('gallo_placa_traba')
        if not placa:
            raise ValueError("La placa del gallo es obligatoria.")
        placa_regional = request.form.get('gallo_placa_regional') or None
        nombre = request.form.get('gallo_nombre') or None
        n_pelea = request.form.get('gallo_n_pelea') or None
        raza = request.form.get('gallo_raza')
        color = request.form.get('gallo_color')
        apariencia = request.form.get('gallo_apariencia')
        if not raza or not color or not apariencia:
            raise ValueError("Raza, color y apariencia son obligatorios para el gallo.")
        foto = None
        if 'gallo_foto' in request.files and request.files['gallo_foto'].filename != '':
            file = request.files['gallo_foto']
            if allowed_file(file.filename):
                safe_placa = secure_filename(placa)
                fname = safe_placa + "_" + secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                foto = fname
        # Generar código único
        codigo = generar_codigo_unico(cursor)
        cursor.execute('''
            INSERT INTO individuos (traba, placa_traba, placa_regional, nombre, raza, color, apariencia, n_pelea, nacimiento, foto, generacion, codigo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (traba, placa, placa_regional, nombre, raza, color, apariencia, n_pelea, None, foto, 1, codigo))
        conn.commit()
        conn.close()
        return f'''
        <!DOCTYPE html>
        <html><body style="background:#01030a;color:white;text-align:center;padding:50px;font-family:sans-serif;">
        <div style="background:rgba(0,255,255,0.1);padding:30px;border-radius:10px;">
            <h2 style="color:#00ffff;">✅ ¡Gallo registrado exitosamente!</h2>
            <p>Placa: <strong>{placa}</strong></p>
            <p>Código único: <strong>{codigo}</strong></p>
            <a href="/menu" style="display:inline-block;margin-top:20px;padding:12px 24px;background:#2ecc71;color:#041428;text-decoration:none;border-radius:6px;">🏠 Ir al Menú</a>
            <a href="/lista" style="display:inline-block;margin-top:20px;padding:12px 24px;background:#00ffff;color:#041428;text-decoration:none;border-radius:6px;margin-left:10px;">📋 Ver Mis Gallos</a>
        </div>
        </body></html>
        '''
    except Exception as e:
        conn.rollback()
        conn.close()
        return f'''
        <!DOCTYPE html>
        <html><body style="background:#01030a;color:white;text-align:center;padding:50px;font-family:sans-serif;">
        <div style="background:rgba(231,76,60,0.1);padding:30px;border-radius:10px;">
            <h2 style="color:#ff6b6b;">❌ Error</h2>
            <p>{str(e)}</p>
            <a href="/formulario-gallo" style="display:inline-block;margin-top:20px;padding:12px 24px;background:#c0392b;color:white;text-decoration:none;border-radius:6px;">← Volver</a>
        </div>
        </body></html>
        '''

# =============== ✅ RUTA DE CRUCE INBREEDING ===============
@app.route('/cruce-inbreeding')
@proteger_ruta
def cruce_inbreeding():
    traba = session['traba']
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT id, placa_traba, placa_regional, nombre, raza FROM individuos WHERE traba = ? ORDER BY placa_traba', (traba,))
    gallos = cursor.fetchall()
    conn.close()
    opciones_gallos = ''.join([f'<option value="{g["id"]}">{g["placa_traba"]} ({g["raza"]}) - {g["nombre"] or "Sin nombre"}</option>' for g in gallos])
    return f'''
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GFRD Cruce Inbreeding 2026</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;500;700&display=swap');
*{{margin:0; padding:0; box-sizing:border-box; font-family:'Poppins', sans-serif;}}
body{{background:#01030a; color:white; font-size:17px; padding:30px;}}
.container{{max-width:600px; margin:0 auto; background:rgba(255,255,255,0.05); border-radius:15px; padding:25px;}}
h2{{color:#00ffff; text-align:center; margin-bottom:20px;}}
label{{display:block; margin:10px 0 5px;}}
select, input, textarea{{width:100%; padding:10px; margin:5px 0 15px; background:rgba(0,0,0,0.3); color:white; border:none; border-radius:6px;}}
.btn-submit{{width:100%; padding:12px; background:linear-gradient(135deg,#e74c3c,#e67e22); color:#041428; border:none; border-radius:6px; font-weight:bold; margin-top:10px;}}
.btn-menu{{display:inline-block; margin-top:20px; padding:10px 20px; background:#7f8c8d; color:white; text-decoration:none; border-radius:6px; font-size:16px;}}
.btn-menu:hover{{background:#95a5a6;}}
</style>
</head>
<body>
<div class="container">
<img src="/logo" alt="Logo GFRD" style="width:60px; float:right; filter:drop-shadow(0 0 4px #00ffff);">
<h2>🔁 Registro de Cruce Inbreeding</h2>
<form method="POST" action="/registrar-cruce" enctype="multipart/form-data">
<label for="gallo1">Gallo 1 (Ej. Padre)</label>
<select name="gallo1" id="gallo1" required>{opciones_gallos}</select>
<label for="gallo2">Gallo 2 (Ej. Hija)</label>
<select name="gallo2" id="gallo2" required>{opciones_gallos}</select>
<label for="tipo">Tipo de Cruce</label>
<select name="tipo" id="tipo" required>
<option value="">-- Selecciona --</option>
<option value="Padre-Hija">Padre - Hija</option>
<option value="Madre-Hijo">Madre - Hijo</option>
<option value="Hermanos">Hermanos</option>
<option value="Abuelo-Nieta">Abuelo - Nieta</option>
</select>
<label for="generacion">Generación de Inbreeding</label>
<select name="generacion" id="generacion" required>
<option value="1">1 (25%)</option>
<option value="2">2 (37.5%)</option>
<option value="3">3 (50%)</option>
<option value="4">4 (62.5%)</option>
<option value="5">5 (75%)</option>
<option value="6">6 (87.5%)</option>
</select>
<label for="notas">Notas (opcional)</label>
<textarea name="notas" id="notas" style="height:80px;"></textarea>
<label for="foto">Foto del cruce (opcional)</label>
<input type="file" name="foto" id="foto" accept="image/*">
<button type="submit" class="btn-submit">✅ Registrar Cruce</button>
</form>
<a href="/menu" class="btn-menu">🏠 Menú</a>
</div>
</body>
</html>
'''

# ===================✅ registrar-cruce) ===================
@app.route('/registrar-cruce', methods=['POST'])
@proteger_ruta
def registrar_cruce():
    traba = session['traba']
    gallo1_id = request.form.get('gallo1')
    gallo2_id = request.form.get('gallo2')
    tipo = request.form.get('tipo')
    generacion = int(request.form.get('generacion', 1))
    notas = request.form.get('notas', '')
    if not gallo1_id or not gallo2_id or not tipo:
        return '<script>alert("❌ Todos los campos son obligatorios."); window.location="/cruce-inbreeding";</script>'
    if gallo1_id == gallo2_id:
        return '<script>alert("❌ No puedes cruzar un gallo consigo mismo."); window.location="/cruce-inbreeding";</script>'
    conn = None
    try:
        conn = sqlite3.connect(DB)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM individuos WHERE id IN (?, ?) AND traba = ?', (gallo1_id, gallo2_id, traba))
        if len(cursor.fetchall()) != 2:
            return '<script>alert("❌ Uno o ambos gallos no pertenecen a tu traba."); window.location="/cruce-inbreeding";</script>'
        porcentajes = {1: 25, 2: 37.5, 3: 50, 4: 62.5, 5: 75, 6: 87.5}
        porcentaje = porcentajes.get(generacion, 25)
        foto_filename = None
        if 'foto' in request.files and request.files['foto'].filename != '':
            file = request.files['foto']
            if allowed_file(file.filename):
                fname = secure_filename(f"cruce_{gallo1_id}_{gallo2_id}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                foto_filename = fname
        cursor.execute('''
            INSERT INTO cruces (traba, tipo, individuo1_id, individuo2_id, generacion, porcentaje, fecha, notas, foto)
            VALUES (?, ?, ?, ?, ?, ?, date('now'), ?, ?)
        ''', (traba, tipo, gallo1_id, gallo2_id, generacion, porcentaje, notas, foto_filename))
        conn.commit()
        return f'''
        <!DOCTYPE html>
        <html><body style="background:#01030a;color:white;text-align:center;padding:50px;font-family:sans-serif;">
        <div style="background:rgba(0,255,255,0.1);padding:30px;border-radius:10px;">
            <h2 style="color:#00ffff;">✅ ¡Cruce registrado!</h2>
            <p>Tipo: {tipo}<br>Generación {generacion} ({porcentaje}%)</p>
            <a href="/cruce-inbreeding" style="display:inline-block;margin:10px;padding:12px 24px;background:#00ffff;color:#041428;text-decoration:none;border-radius:6px;">🔄 Registrar otro</a>
            <a href="/menu" style="display:inline-block;margin:10px;padding:12px 24px;background:#ff7a18;color:#041428;text-decoration:none;border-radius:6px;">🏠 Menú</a>
        </div>
        </body></html>
        '''
    except Exception as e:
        if conn:
            conn.rollback()
        return f'''
        <!DOCTYPE html>
        <html><body style="background:#01030a;color:white;text-align:center;padding:50px;font-family:sans-serif;">
        <div style="background:rgba(231,76,60,0.1);padding:30px;border-radius:10px;">
            <h2 style="color:#ff6b6b;">❌ Error</h2>
            <p>{str(e)}</p>
            <a href="/cruce-inbreeding" style="display:inline-block;margin:10px;padding:12px 24px;background:#c0392b;color:white;text-decoration:none;border-radius:6px;">← Volver</a>
            <a href="/menu" style="display:inline-block;margin:10px;padding:12px 24px;background:#7f8c8d;color:white;text-decoration:none;border-radius:6px;">🏠 Menú</a>
        </div>
        </body></html>
        '''
    finally:
        if conn:
            conn.close()

# ===============✅ LISTA DE GALLOS ===============
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
    def generar_caracteristica(gallo_id, traba):
        roles = []
        conn2 = sqlite3.connect(DB)
        conn2.row_factory = sqlite3.Row
        cur = conn2.cursor()
        cur.execute('SELECT i.placa_traba FROM individuos i JOIN progenitores p ON i.id = p.madre_id WHERE p.madre_id = ?', (gallo_id,))
        for r in cur.fetchall():
            roles.append(f"Madre del placa {r['placa_traba']}")
        cur.execute('SELECT i.placa_traba FROM individuos i JOIN progenitores p ON i.id = p.individuo_id WHERE p.padre_id = ?', (gallo_id,))
        for r in cur.fetchall():
            roles.append(f"Padre del placa {r['placa_traba']}")
        conn2.close()
        if roles:
            return "; ".join(roles[:2]) + ("..." if len(roles) > 2 else "")
        return "—"
    filas_html = ""
    for g in gallos:
        foto_html = f'<img src="/uploads/{g["foto"]}" width="50" style="border-radius:4px; vertical-align:middle;">' if g["foto"] else "—"
        placa = g['placa_traba']
        nombre = g['nombre'] or "—"
        raza = g['raza'] or "—"
        color = g['color'] or "—"
        car = generar_caracteristica(g['id'], traba)
        filas_html += f'''
        <tr>
            <td style="padding:8px; text-align:center;">{foto_html}</td>
            <td style="padding:8px;">{placa}</td>
            <td style="padding:8px;">{g['placa_regional'] or "—"}</td>
            <td style="padding:8px;">{nombre}</td>
            <td style="padding:8px;">{raza}</td>
            <td style="padding:8px;">{color}</td>
            <td style="padding:8px;">{g['apariencia']}</td>
            <td style="padding:8px;">{g['n_pelea'] or "—"}</td>
            <td style="padding:8px;">{g['madre_placa'] or "—"}</td>
            <td style="padding:8px;">{g['padre_placa'] or "—"}</td>
            <td style="padding:8px;">{g['codigo'] or "—"}</td>
            <td style="padding:8px;">{g['generacion'] if g['generacion'] is not None else 1}</td>
            <td style="padding:8px; text-align:center;">
                <a href="/editar-gallo/{g['id']}" style="padding:6px 12px; background:#f39c12; color:black; text-decoration:none; border-radius:4px; margin-right:6px;">✏️</a>
                <a href="/arbol/{g['id']}" style="padding:6px 12px; background:#00ffff; color:#041428; text-decoration:none; border-radius:4px; margin-right:6px;">🌳</a>
                <a href="/eliminar-gallo/{g['id']}" style="padding:6px 12px; background:#e74c3c; color:white; text-decoration:none; border-radius:4px;">🗑️</a>
            </td>
        </tr>
        '''
    return f'''
<!DOCTYPE html>
<html><head><title>Mis Gallos</title>
<style>
body {{ background:#01030a; color:white; font-family:sans-serif; padding:20px; }}
h2 {{ text-align:center; color:#00ffff; margin-bottom:20px; }}
table {{ width:100%; border-collapse:collapse; background:rgba(0,0,0,0.2); border-radius:10px; overflow:hidden; }}
th, td {{ padding:10px; text-align:left; border-bottom:1px solid rgba(0,255,255,0.2); }}
th {{ background:rgba(0,255,255,0.1); color:#00ffff; }}
tr:hover {{ background:rgba(0,255,255,0.05); }}
a {{ text-decoration:none; }}
a:hover {{ opacity:0.8; }}
.back-btn {{ display:inline-block; margin:20px 0; padding:10px 20px; background:#2c3e50; color:white; text-decoration:none; border-radius:6px; }}
</style>
</head>
<body>
<h2>📋 Mis Gallos - Traba: {traba}</h2>
<a href="/menu" class="back-btn">🏠  Menú</a>
<table>
<thead>
<tr>
<th>Foto</th>
<th>Placa</th>
<th>Placa_regional</th>
<th>Nombre</th>
<th>Raza</th>
<th>Color</th>
<th>Apariencia</th>
<th>N° Pelea</th>
<th>Madre</th>
<th>Padre</th>
<th>Código</th>
<th>Generación</th>
<th>Acciones</th>
</tr>
</thead>
<tbody>
{filas_html}
</tbody>
</table>
</body></html>
'''

# ===============✅ EXPORTAR ===============
@app.route('/lista_gallos')
@proteger_ruta
def exportar_gallos():
    traba = session['traba']
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT i.placa_regional, i.placa_traba, i.nombre, i.raza, i.color, i.n_pelea, i.codigo,
               m.placa_traba as madre, p.placa_traba as padre
        FROM individuos i
        LEFT JOIN progenitores pr ON i.id = pr.individuo_id
        LEFT JOIN individuos m ON pr.madre_id = m.id
        LEFT JOIN individuos p ON pr.padre_id = p.id
        WHERE i.traba = ?
    ''', (traba,))
    gallos = cursor.fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Placa_Regional', 'Placa_Traba', 'Nombre', 'Raza', 'Color', 'N_Pelea', 'Código', 'Madre', 'Padre'])
    for g in gallos:
        writer.writerow([g['placa_regional'], g['placa_traba'], g['nombre'], g['raza'], g['color'], g['n_pelea'], g['codigo'], g['madre'], g['padre']])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=gallos.csv"}
    )

# ===============✅ RESPALDO ===============
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
        if os.path.exists(UPLOAD_FOLDER):
            shutil.copytree(UPLOAD_FOLDER, os.path.join(temp_dir, "uploads"), dirs_exist_ok=True)
        zip_filename = f"gallofino_backup_{fecha_archivo}.zip"
        backups_dir = "backups"
        os.makedirs(backups_dir, exist_ok=True)
        zip_path = os.path.join(backups_dir, zip_filename)
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), temp_dir))
        shutil.rmtree(temp_dir)
        return jsonify({"mensaje": "✅ Copia de seguridad creada.", "archivo": zip_filename})
    except Exception as e:
        if 'temp_dir' in locals() and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return jsonify({"error": f"Error: {str(e)}"}), 500

@app.route('/download/<filename>')
@proteger_ruta
def descargar_backup(filename):
    backups_dir = "backups"
    ruta = os.path.join(backups_dir, filename)
    if not os.path.exists(ruta) or not filename.endswith('.zip'):
        return "Archivo no válido", 400
    return send_from_directory(backups_dir, filename, as_attachment=True)

# ===============✅ ÁRBOL ===============
@app.route('/arbol/<int:id>')
@proteger_ruta
def arbol_gallo(id):
    traba = session['traba']
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT i.id, i.placa_traba, i.placa_regional, i.nombre, i.raza, i.color, i.apariencia, i.n_pelea, i.foto, i.codigo,
               m.placa_traba as madre_placa, p.placa_traba as padre_placa
        FROM individuos i
        LEFT JOIN progenitores pr ON i.id = pr.individuo_id
        LEFT JOIN individuos m ON pr.madre_id = m.id
        LEFT JOIN individuos p ON pr.padre_id = p.id
        WHERE i.traba = ? AND i.id = ?
    ''', (traba, id))
    gallo = cursor.fetchone()
    if not gallo:
        conn.close()
        return '<script>alert("❌ Gallo no encontrado o no pertenece a tu traba."); window.location="/lista";</script>'
    madre = None
    if gallo['madre_placa']:
        cursor.execute('SELECT * FROM individuos WHERE placa_traba = ? AND traba = ?', (gallo['madre_placa'], traba))
        madre = cursor.fetchone()
    padre = None
    if gallo['padre_placa']:
        cursor.execute('SELECT * FROM individuos WHERE placa_traba = ? AND traba = ?', (gallo['padre_placa'], traba))
        padre = cursor.fetchone()
    # Abuelos maternos (de la madre)
    abuela_materna = None
    abuelo_materno = None
    if madre:
        cursor.execute('''
            SELECT m2.placa_traba as abuela, p2.placa_traba as abuelo
            FROM individuos i
            LEFT JOIN progenitores pr ON i.id = pr.individuo_id
            LEFT JOIN individuos m2 ON pr.madre_id = m2.id
            LEFT JOIN individuos p2 ON pr.padre_id = p2.id
            WHERE i.id = ?
        ''', (madre['id'],))
        abms = cursor.fetchone()
        if abms:
            if abms['abuela']:
                cursor.execute('SELECT * FROM individuos WHERE placa_traba = ? AND traba = ?', (abms['abuela'], traba))
                abuela_materna = cursor.fetchone()
            if abms['abuelo']:
                cursor.execute('SELECT * FROM individuos WHERE placa_traba = ? AND traba = ?', (abms['abuelo'], traba))
                abuelo_materno = cursor.fetchone()
    # Abuelos paternos (del padre)
    abuela_paterna = None
    abuelo_paterno = None
    if padre:
        cursor.execute('''
            SELECT m2.placa_traba as abuela, p2.placa_traba as abuelo
            FROM individuos i
            LEFT JOIN progenitores pr ON i.id = pr.individuo_id
            LEFT JOIN individuos m2 ON pr.madre_id = m2.id
            LEFT JOIN individuos p2 ON pr.padre_id = p2.id
            WHERE i.id = ?
        ''', (padre['id'],))
        abps = cursor.fetchone()
        if abps:
            if abps['abuela']:
                cursor.execute('SELECT * FROM individuos WHERE placa_traba = ? AND traba = ?', (abps['abuela'], traba))
                abuela_paterna = cursor.fetchone()
            if abps['abuelo']:
                cursor.execute('SELECT * FROM individuos WHERE placa_traba = ? AND traba = ?', (abps['abuelo'], traba))
                abuelo_paterno = cursor.fetchone()
    def crear_tarjeta_gallo(gallo_data, titulo):
        if not gallo_data:
            return f'<div style="background:rgba(0,0,0,0.2); padding:15px; margin:10px; text-align:center; border-radius:8px;"><p><strong>{titulo}:</strong> Desconocido</p></div>'
        nombre_mostrar = gallo_data['nombre'] or gallo_data['placa_traba']
        foto_html = f'<img src="/uploads/{gallo_data["foto"]}" width="80" style="border-radius:8px; margin-bottom:10px; display:block; margin-left:auto; margin-right:auto;">' if gallo_data["foto"] else ""
        return f'''
        <div style="background:rgba(0,0,0,0.2); padding:15px; margin:10px; border-radius:8px; text-align:center;">
            {foto_html}
            <h3 style="color:#00ffff; margin:10px 0;">{titulo}: {nombre_mostrar}</h3>
            <p><strong>Placa:</strong> {gallo_data['placa_traba']}</p>
            <p><strong>Código:</strong> {gallo_data['codigo'] or "—"}</p>
            <p><strong>Raza:</strong> {gallo_data['raza']}</p>
            <p><strong>Color:</strong> {gallo_data['color']}</p>
        </div>
        '''
    tarjeta_principal = crear_tarjeta_gallo(gallo, "Gallo Principal")
    tarjeta_madre = crear_tarjeta_gallo(madre, "Madre")
    tarjeta_padre = crear_tarjeta_gallo(padre, "Padre")
    tarjeta_abuela_materna = crear_tarjeta_gallo(abuela_materna, "Abuela Materna")
    tarjeta_abuelo_materno = crear_tarjeta_gallo(abuelo_materno, "Abuelo Materno")
    tarjeta_abuela_paterna = crear_tarjeta_gallo(abuela_paterna, "Abuela Paterna")
    tarjeta_abuelo_paterno = crear_tarjeta_gallo(abuelo_paterno, "Abuelo Paterno")
    conn.close()
    return f'''
<!DOCTYPE html>
<html>
<head>
<title>Árbol Genealógico</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body style="background:#01030a;color:white;padding:20px;font-family:sans-serif;margin:0;">
<h2 style="text-align:center;color:#00ffff;margin-bottom:30px;">🌳 Árbol Genealógico Completo</h2>
<div style="display:flex; flex-direction:column; align-items:center; gap:25px;">
    <!-- Generación 1 -->
    <div style="width:100%; max-width:600px; text-align:center;">
        <h3 style="color:#00ffff;">Generación 1 - Gallo Principal</h3>
        {tarjeta_principal}
    </div>
    <!-- Generación 2 -->
    <div style="display:flex; justify-content:space-around; width:100%; max-width:900px; flex-wrap:wrap; gap:20px;">
        <div style="flex:1; min-width:250px;">
            <h3 style="color:#00ffff;">Generación 2 - Madre</h3>
            {tarjeta_madre}
        </div>
        <div style="flex:1; min-width:250px;">
            <h3 style="color:#00ffff;">Generación 2 - Padre</h3>
            {tarjeta_padre}
        </div>
    </div>
    <!-- Generación 3 -->
    <div style="display:flex; justify-content:space-around; width:100%; max-width:900px; flex-wrap:wrap; gap:20px;">
        <div style="flex:1; min-width:250px;">
            <h3 style="color:#00ffff;">Generación 3 - Abuela Materna</h3>
            {tarjeta_abuela_materna}
        </div>
        <div style="flex:1; min-width:250px;">
            <h3 style="color:#00ffff;">Generación 3 - Abuelo Materno</h3>
            {tarjeta_abuelo_materno}
        </div>
        <div style="flex:1; min-width:250px;">
            <h3 style="color:#00ffff;">Generación 3 - Abuela Paterna</h3>
            {tarjeta_abuela_paterna}
        </div>
        <div style="flex:1; min-width:250px;">
            <h3 style="color:#00ffff;">Generación 3 - Abuelo Paterno</h3>
            {tarjeta_abuelo_paterno}
        </div>
    </div>
</div>
<div style="text-align:center; margin-top:30px;">
    <a href="/lista" style="display:inline-block;margin:10px;padding:12px 24px;background:#2ecc71;color:#041428;text-decoration:none;border-radius:6px;">📋 Volver a Mis Gallos</a>
    <a href="/menu" style="display:inline-block;margin:10px;padding:12px 24px;background:#7f8c8d;color:white;text-decoration:none;border-radius:6px;">🏠 Menú</a>
</div>
</body>
</html>
'''

# ===============✅ AGREGAR DESCENDIENTE ===============
@app.route('/agregar-descendiente/<int:id>', methods=['GET', 'POST'])
@proteger_ruta
def agregar_descendiente(id):
    traba = session['traba']
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT placa_traba, nombre FROM individuos WHERE id = ? AND traba = ?', (id, traba))
    gallo_actual = cursor.fetchone()
    if not gallo_actual:
        conn.close()
        return '<script>alert("❌ Gallo no encontrado."); window.location="/lista";</script>'
    razas_html = ''.join([f'<option value="{r}">{r}</option>' for r in RAZAS])
    apariencias = ['Crestarosa', 'Cocolo', 'Tuceperne', 'Pava', 'Moton']
    ap_html_gallo = ''.join([f'<label style="display:inline-block; margin-right:15px;"><input type="radio" name="gallo_apariencia" value="{a}" required> {a}</label>' for a in apariencias])
    if request.method == 'POST':
        try:
            placa_a = request.form.get('gallo_placa_traba')
            if not placa_a:
                raise ValueError("La placa del nuevo gallo es obligatoria.")
            raza_a = request.form.get('gallo_raza')
            color_a = request.form.get('gallo_color')
            apariencia_a = request.form.get('gallo_apariencia')
            if not raza_a or not color_a or not apariencia_a:
                raise ValueError("Raza, color y apariencia son obligatorios.")
            foto_a = None
            if 'gallo_foto' in request.files and request.files['gallo_foto'].filename != '':
                file = request.files['gallo_foto']
                if allowed_file(file.filename):
                    fname = secure_filename(placa_a + "_" + file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                    foto_a = fname
            cursor.execute('''
                INSERT INTO individuos (traba, placa_traba, placa_regional, nombre, raza, color, apariencia, n_pelea, nacimiento, foto, generacion)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                traba,
                placa_a,
                request.form.get('gallo_placa_regional') or None,
                request.form.get('gallo_nombre') or None,
                raza_a,
                color_a,
                apariencia_a,
                request.form.get('gallo_n_pelea') or None,
                None,
                foto_a,
                1
            ))
            nuevo_gallo_id = cursor.lastrowid
            rol = request.form.get('rol', 'padre')
            def crear_individuo_vacio(prefijo="intermedio"):
                placa = f"{gallo_actual['placa_traba']}_{prefijo}"
                cursor.execute('''
                    INSERT INTO individuos (traba, placa_traba, raza, color, apariencia)
                    VALUES (?, ?, ?, ?, ?)
                ''', (traba, placa, 'Desconocida', 'Desconocido', 'Desconocido'))
                return cursor.lastrowid
            if rol == "madre":
                cursor.execute('INSERT INTO progenitores (individuo_id, madre_id) VALUES (?, ?)', (id, nuevo_gallo_id))
            elif rol == "padre":
                cursor.execute('INSERT INTO progenitores (individuo_id, padre_id) VALUES (?, ?)', (id, nuevo_gallo_id))
            elif rol == "abuela_materna":
                madre_intermedia_id = crear_individuo_vacio("madre_m")
                cursor.execute('INSERT INTO progenitores (individuo_id, madre_id) VALUES (?, ?)', (id, madre_intermedia_id))
                cursor.execute('INSERT INTO progenitores (individuo_id, madre_id) VALUES (?, ?)', (madre_intermedia_id, nuevo_gallo_id))
            elif rol == "abuelo_materno":
                padre_intermedio_id = crear_individuo_vacio("padre_m")
                cursor.execute('INSERT INTO progenitores (individuo_id, padre_id) VALUES (?, ?)', (id, padre_intermedio_id))
                cursor.execute('INSERT INTO progenitores (individuo_id, padre_id) VALUES (?, ?)', (padre_intermedio_id, nuevo_gallo_id))
            elif rol == "abuela_paterna":
                padre_intermedio_id = crear_individuo_vacio("padre_p")
                cursor.execute('INSERT INTO progenitores (individuo_id, padre_id) VALUES (?, ?)', (id, padre_intermedio_id))
                cursor.execute('INSERT INTO progenitores (individuo_id, madre_id) VALUES (?, ?)', (padre_intermedio_id, nuevo_gallo_id))
            elif rol == "abuelo_paterno":
                madre_intermedia_id = crear_individuo_vacio("madre_p")
                cursor.execute('INSERT INTO progenitores (individuo_id, madre_id) VALUES (?, ?)', (id, madre_intermedia_id))
                cursor.execute('INSERT INTO progenitores (individuo_id, padre_id) VALUES (?, ?)', (madre_intermedia_id, nuevo_gallo_id))
            else:
                raise ValueError("Rol no reconocido.")
            conn.commit()
            conn.close()
            return f'<script>alert("✅ {{rol.replace("_", " ").title()}} agregado(a) correctamente."); window.location="/arbol/{id}";</script>'
        except Exception as e:
            conn.rollback()
            conn.close()
            return f'<script>alert("❌ Error: {{str(e)}}"); window.location="";</script>'
    conn.close()
    return f'''
<!DOCTYPE html>
<html>
<head>
    <title>Agregar Descendiente</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{
            background: #01030a;
            color: white;
            font-family: 'Poppins', sans-serif;
            padding: 20px;
            margin: 0;
        }}
        .container {{
            max-width: 600px;
            margin: 40px auto;
            background: rgba(0, 0, 0, 0.3);
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 0 20px rgba(0, 255, 255, 0.3);
        }}
        h2 {{
            text-align: center;
            color: #00ffff;
            margin-bottom: 20px;
        }}
        label {{
            display: block;
            margin: 12px 0 6px;
            font-weight: 500;
        }}
        input, select {{
            width: 100%;
            padding: 10px;
            background: rgba(0, 0, 0, 0.4);
            color: white;
            border: 1px solid rgba(0, 255, 255, 0.3);
            border-radius: 6px;
            box-sizing: border-box;
            font-size: 16px;
        }}
        .rol-buttons {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            justify-content: center;
            margin: 15px 0 25px;
        }}
        .rol-btn {{
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            font-weight: bold;
            cursor: pointer;
            font-size: 14px;
            transition: opacity 0.2s;
        }}
        .btn-submit {{
            width: 100%;
            padding: 12px;
            background: linear-gradient(135deg, #00ffff, #008cff);
            color: #041428;
            border: none;
            border-radius: 8px;
            font-weight: bold;
            font-size: 16px;
            margin-top: 15px;
        }}
        .btn-back {{
            display: inline-block;
            margin-top: 15px;
            padding: 10px 20px;
            background: #7f8c8d;
            color: white;
            text-decoration: none;
            border-radius: 6px;
            text-align: center;
        }}
        .apariencia-group {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 6px;
        }}
        #rol_seleccionado {{
            text-align: center;
            margin: 15px 0;
            color: #00ff99;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h2>👶 Agregar Descendiente de: <code>{gallo_actual['placa_traba']}</code></h2>
        <div style="text-align:center; color:#00e6ff; margin-bottom:10px;">Selecciona el rol del <strong>nuevo gallo</strong>:</div>
        <div class="rol-buttons">
            <button type="button" class="rol-btn" style="background:#c0392b;" onclick="setRol('madre')">B. Madre</button>
            <button type="button" class="rol-btn" style="background:#27ae60;" onclick="setRol('padre')">C. Padre</button>
            <button type="button" class="rol-btn" style="background:#e67e22;" onclick="setRol('abuela_materna')">D. Abuela Materna</button>
            <button type="button" class="rol-btn" style="background:#1abc9c;" onclick="setRol('abuelo_materno')">E. Abuelo Materno</button>
            <button type="button" class="rol-btn" style="background:#e67e22;" onclick="setRol('abuela_paterna')">F. Abuela Paterna</button>
            <button type="button" class="rol-btn" style="background:#1abc9c;" onclick="setRol('abuelo_paterno')">G. Abuelo Paterno</button>
        </div>
        <div id="rol_seleccionado">Rol actual: <strong>Padre</strong></div>
        <form method="POST" enctype="multipart/form-data">
            <input type="hidden" name="rol" id="rol_input" value="padre">
            <div style="background:rgba(232,244,252,0.2); padding:15px; border-radius:10px; margin-bottom:20px;">
                <h3 style="color:#2980b9; text-align:center;">A. Registrar Nuevo Gallo</h3>
                <label>Placa de Traba:</label>
                <input type="text" name="gallo_placa_traba" required>
                <label>Placa Regional (opcional):</label>
                <input type="text" name="gallo_placa_regional">
                <label>Nombre (opcional):</label>
                <input type="text" name="gallo_nombre">
                <label>Raza:</label>
                <select name="gallo_raza" required>{razas_html}</select>
                <label>Color:</label>
                <input type="text" name="gallo_color" required>
                <label>Apariencia:</label>
                <div class="apariencia-group">{ap_html_gallo}</div>
                <label>N° Pelea (opcional):</label>
                <input type="text" name="gallo_n_pelea">
                <label>Foto (opcional):</label>
                <input type="file" name="gallo_foto" accept="image/*">
            </div>
            <button type="submit" class="btn-submit">✅ Registrar y Vincular</button>
        </form>
        <a href="/lista" class="btn-back">📋 Volver a Mis Gallos</a>
    </div>
    <script>
    function setRol(rol) {{
        const labels = {{
            'madre': 'Madre',
            'padre': 'Padre',
            'abuela_materna': 'Abuela Materna',
            'abuelo_materno': 'Abuelo Materno',
            'abuela_paterna': 'Abuela Paterna',
            'abuelo_paterno': 'Abuelo Paterno'
        }};
        document.getElementById('rol_input').value = rol;
        document.getElementById('rol_seleccionado').innerHTML = "Rol actual: <strong>" + labels[rol] + "</strong>";
    }}
    </script>
</body>
</html>
'''

# ===============✅ EDITAR GALLO ===============
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
            placa = request.form.get('placa_traba')
            if not placa:
                raise ValueError("La placa es obligatoria.")
            placa_regional = request.form.get('placa_regional') or None
            nombre = request.form.get('nombre') or None
            raza = request.form.get('raza')
            color = request.form.get('color')
            apariencia = request.form.get('apariencia')
            n_pelea = request.form.get('n_pelea') or None
            if not raza or not color or not apariencia:
                raise ValueError("Raza, color y apariencia son obligatorios.")
            foto = gallo['foto']
            if 'foto' in request.files and request.files['foto'].filename != '':
                file = request.files['foto']
                if allowed_file(file.filename):
                    fname = secure_filename(placa + "_" + file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                    foto = fname
            cursor.execute('''
                UPDATE individuos
                SET placa_traba = ?, placa_regional = ?, nombre = ?, raza = ?, color = ?, apariencia = ?, n_pelea = ?, foto = ?
                WHERE id = ?
            ''', (placa, placa_regional, nombre, raza, color, apariencia, n_pelea, foto, id))
            conn.commit()
            conn.close()
            return f'<script>alert("✅ Gallo actualizado."); window.location="/arbol/{id}";</script>'
        except Exception as e:
            conn.rollback()
            conn.close()
            return f'<script>alert("❌ Error: {str(e)}"); window.location="";</script>'
    razas_html = ''.join([f'<option value="{r}" {"selected" if r == gallo["raza"] else ""}>{r}</option>' for r in RAZAS])
    apariencias = ['Crestarosa', 'Cocolo', 'Tuceperne', 'Pava', 'Moton']
    ap_html = ''.join([f'<label style="display:inline-block; margin-right:15px;"><input type="radio" name="apariencia" value="{a}" {"checked" if a == gallo["apariencia"] else ""}> {a}</label>' for a in apariencias])
    foto_html = f'<img src="/uploads/{gallo["foto"]}" width="100" style="border-radius:8px; display:block; margin:10px auto;">' if gallo["foto"] else "<p style='text-align:center; color:#aaa;'>Sin foto</p>"
    conn.close()
    return f'''
<!DOCTYPE html>
<html>
<head>
    <title>Editar Gallo</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{
            background: #01030a;
            color: white;
            font-family: 'Poppins', sans-serif;
            padding: 20px;
            margin: 0;
        }}
        .container {{
            max-width: 600px;
            margin: 40px auto;
            background: rgba(0, 0, 0, 0.3);
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 0 20px rgba(0, 255, 255, 0.3);
        }}
        h2 {{
            text-align: center;
            color: #00ffff;
            margin-bottom: 25px;
        }}
        label {{
            display: block;
            margin: 12px 0 6px;
            font-weight: 500;
        }}
        input, select {{
            width: 100%;
            padding: 10px;
            background: rgba(0, 0, 0, 0.4);
            color: white;
            border: 1px solid rgba(0, 255, 255, 0.3);
            border-radius: 6px;
            box-sizing: border-box;
            font-size: 16px;
        }}
        .apariencia-group {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 6px;
        }}
        .btn {{
            display: inline-block;
            padding: 12px 24px;
            margin: 10px 5px;
            border: none;
            border-radius: 8px;
            font-weight: bold;
            text-decoration: none;
            text-align: center;
            cursor: pointer;
            font-size: 16px;
        }}
        .save {{ background: linear-gradient(135deg, #2ecc71, #00ffff); color: #041428; }}
        .cancel {{ background: #7f8c8d; color: white; }}
        .foto-preview {{
            text-align: center;
            margin: 15px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h2>✏️ Editar Gallo: {gallo['placa_traba']}</h2>
        <form method="POST" enctype="multipart/form-data">
            <label>Placa de Traba</label>
            <input type="text" name="placa_traba" value="{gallo['placa_traba']}" required>
            <label>Placa Regional (opcional)</label>
            <input type="text" name="placa_regional" value="{gallo['placa_regional'] or ''}">
            <label>Nombre (opcional)</label>
            <input type="text" name="nombre" value="{gallo['nombre'] or ''}">
            <label>Raza</label>
            <select name="raza" required>{razas_html}</select>
            <label>Color</label>
            <input type="text" name="color" value="{gallo['color']}" required>
            <label>Apariencia</label>
            <div class="apariencia-group">{ap_html}</div>
            <label>N° Pelea (opcional)</label>
            <input type="text" name="n_pelea" value="{gallo['n_pelea'] or ''}">
            <div class="foto-preview">
                <label>Foto actual</label>
                {foto_html}
            </div>
            <label>Cambiar foto (opcional)</label>
            <input type="file" name="foto" accept="image/*">
            <div style="text-align:center; margin-top:25px;">
                <button type="submit" class="btn save">✅ Guardar Cambios</button>
                <a href="/arbol/{id}" class="btn cancel">🚫 Cancelar</a>
            </div>
        </form>
    </div>
</body>
</html>
'''

# ===============✅ ELIMINAR GALLO ===============
@app.route('/eliminar-gallo/<int:id>', methods=['GET', 'POST'])
@proteger_ruta
def eliminar_gallo(id):
    traba = session['traba']
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute('SELECT placa_traba FROM individuos WHERE id = ? AND traba = ?', (id, traba))
    gallo = cursor.fetchone()
    if not gallo:
        conn.close()
        return '<script>alert("❌ Gallo no encontrado."); window.location="/lista";</script>'
    placa_correcta = gallo[0]
    if request.method == 'POST':
        placa_confirm = request.form.get('placa_confirm', '').strip()
        if placa_confirm == placa_correcta:
            cursor.execute('DELETE FROM progenitores WHERE individuo_id = ? OR madre_id = ? OR padre_id = ?', (id, id, id))
            cursor.execute('DELETE FROM individuos WHERE id = ? AND traba = ?', (id, traba))
            conn.commit()
            conn.close()
            return f'<script>alert("✅ Gallo eliminado."); window.location="/lista";</script>'
        else:
            conn.close()
            return f'''
            <!DOCTYPE html>
            <html><body style="background:#01030a;color:white;text-align:center;padding:40px;font-family:sans-serif;">
            <div style="background:rgba(231,76,60,0.2);padding:25px;border-radius:10px;max-width:500px;margin:0 auto;">
                <h3 style="color:#ff6b6b;">❌ Placa incorrecta</h3>
                <p>La placa ingresada no coincide con la del gallo.</p>
                <form method="POST">
                <input type="text" name="placa_confirm" placeholder="Escribe la Placa de Traba: {placa_correcta}" required
                style="width:100%;padding:10px;margin:15px 0;background:rgba(0,0,0,0.3);color:white;border:none;border-radius:6px;font-size:16px;">
                <button type="submit" style="width:100%;padding:12px;background:#e74c3c;color:white;border:none;border-radius:6px;font-weight:bold;">🗑️ Confirmar Eliminación</button>
                </form>
                <a href="/lista" style="display:inline-block;margin-top:20px;padding:10px 20px;background:#7f8c8d;color:white;text-decoration:none;border-radius:6px;">← Cancelar</a>
            </div>
            </body></html>
            '''
    conn.close()
    return f'''
    <!DOCTYPE html>
    <html>
    <body style="background:#01030a;color:white;text-align:center;padding:40px;font-family:sans-serif;">
        <div style="background:rgba(231,76,60,0.2);padding:25px;border-radius:10px;max-width:500px;margin:0 auto;">
            <h3 style="color:#e74c3c;">⚠️ Confirmar Eliminación</h3>
            <p>Vas a eliminar el gallo con <strong>Placa de Traba: {placa_correcta}</strong>.</p>
            <p>Por seguridad, escribe <strong>exactamente</strong> esa placa para confirmar:</p>
            <form method="POST">
                <input type="text" name="placa_confirm" placeholder="Ej: {placa_correcta}" required
                style="width:100%;padding:10px;margin:15px 0;background:rgba(0,0,0,0.3);color:white;border:none;border-radius:6px;font-size:16px;">
                <button type="submit" style="width:100%;padding:12px;background:#e74c3c;color:white;border:none;border-radius:6px;font-weight:bold;">🗑️ Confirmar Eliminación</button>
            </form>
            <a href="/lista" style="display:inline-block;margin-top:20px;padding:10px 20px;background:#7f8c8d;color:white;text-decoration:none;border-radius:6px;">← Cancelar</a>
        </div>
    </body>
    </html>
    '''
# ===================✅ EJECUCIÓN ===================
if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))




