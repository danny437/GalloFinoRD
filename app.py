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

# Almacenamiento temporal de OTPs (en producción, usa Redis o base de datos)
OTP_TEMP = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
            foto TEXT
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
            cursor.execute("ALTER TABLE trabas ADD COLUMN contraseña_hash TEXT")
        conn.commit()
        conn.close()

def proteger_ruta(f):
    def wrapper(*args, **kwargs):
        if 'traba' not in session:
            return redirect(url_for('bienvenida'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

def verificar_pertenencia(id_registro, tabla):
    if tabla not in TABLAS_PERMITIDAS:
        raise ValueError("Tabla no permitida")
    traba = session['traba']
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute(f'SELECT id FROM {tabla} WHERE id = ? AND traba = ?', (id_registro, traba))
    existe = cursor.fetchone()
    conn.close()
    return existe is not None

# =============== REGISTRO Y AUTENTICACIÓN (OTP) ===============
@app.route('/registrar-traba', methods=['POST'])
def registrar_traba():
    nombre = request.form.get('nombre', '').strip()
    apellido = request.form.get('apellido', '').strip()
    traba = request.form.get('traba', '').strip()
    correo = request.form.get('correo', '').strip().lower()
    contraseña = request.form.get('contraseña', '')
    if not nombre or not apellido or not traba or not correo or not contraseña:
        return '<script>alert("❌ Todos los campos son obligatorios."); window.location="/";</script>'
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id FROM trabas WHERE nombre_traba = ? OR correo = ?', (traba, correo))
        if cursor.fetchone():
            conn.close()
            return '<script>alert("❌ Nombre de traba o correo ya registrado."); window.location="/";</script>'
        nombre_completo = f"{nombre} {apellido}".strip()
        contraseña_hash = generate_password_hash(contraseña)
        cursor.execute('''
            INSERT INTO trabas (nombre_traba, nombre_completo, correo, contraseña_hash)
            VALUES (?, ?, ?, ?)
        ''', (traba, nombre_completo, correo, contraseña_hash))
        conn.commit()
        conn.close()
        session['traba'] = traba
        return redirect(url_for('menu_principal'))
    except Exception as e:
        conn.close()
        return f'<script>alert("❌ Error al registrar: {str(e)}"); window.location="/";</script>'

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
    print(f"\n📧 [OTP para {correo}]: {codigo}\n")
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
        session['traba'] = traba
        del OTP_TEMP[correo]
        return redirect(url_for('menu_principal'))
    else:
        return '<script>alert("❌ Código incorrecto o expirado."); window.location="/";</script>'

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route("/logo")
def logo():
    return send_from_directory(os.getcwd(), "OIP.png")

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

# =============== MENÚ PRINCIPAL ===============
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
body{{background:#01030a; color:white; font-size:17px;}}
.container{{width:95%; max-width:900px; margin:40px auto;}}
.header-modern{{display:flex; justify-content:space-between; align-items:center; margin-bottom:30px; flex-wrap:wrap; gap:15px;}}
.header-modern h1{{font-size:1.8rem; color:#00ffff; text-shadow:0 0 10px #00ffff;}}
.subtitle{{font-size:0.85rem; color:#bbb;}}
.logo{{width:80px; height:auto; filter:drop-shadow(0 0 6px #00ffff);}}
.card{{background:rgba(255,255,255,0.06); border-radius:20px; padding:25px; backdrop-filter:blur(10px); box-shadow:0 0 30px rgba(0,255,255,0.4);}}
.menu-grid{{display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0;}}
.menu-btn{{display: block; width:100%; padding:16px; text-align:center; border-radius:10px; background:linear-gradient(135deg,#f6c84c,#ff7a18); color:#041428; font-weight:bold; text-decoration:none; transition:0.3s; font-size:17px;}}
.menu-btn:hover{{transform:translateY(-3px); box-shadow:0 6px 20px rgba(0,255,255,0.5);}}
canvas{{position:fixed; top:0; left:0; width:100%; height:100%; z-index:-1;}}
</style>
</head>
<body>
<canvas id="bg"></canvas>
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
<a href="/lista" class="menu-btn">📋 Mis Gallos</a>
<a href="/buscar" class="menu-btn">🔍 Buscar</a>
<a href="/exportar" class="menu-btn">📤 Exportar</a>
<a href="javascript:void(0);" class="menu-btn" onclick="crearBackup()">💾 Respaldo</a>
<a href="/cerrar-sesion" class="menu-btn" style="background:linear-gradient(135deg,#7f8c8d,#95a5a6);">🚪 Cerrar Sesión</a>
</div>
</div>
</div>
<div id="mensaje-backup" style="text-align:center; margin-top:15px; color:#27ae60; font-weight:bold;"></div>
<script>
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

# =============== REGISTRO DE GALLO ===============
@app.route('/formulario-gallo')
@proteger_ruta
def formulario_gallo():
    traba = session['traba']
    razas_html = ''.join([f'<option value="{r}">{r}</option>' for r in RAZAS])
    apariencias = ['Crestarosa', 'Cocolo', 'Tuceperne', 'Pava', 'Moton']
    def columna(titulo, prefijo, color_fondo, color_titulo, required=False):
        req_attr = "required" if required else ""
        req_radio = "required" if required else ""
        ap_html = ''.join([f'<label><input type="radio" name="{prefijo}_apariencia" value="{a}" {req_radio}> {a}</label><br>' for a in apariencias])
        return f'''
        <div style="flex: 1; min-width: 280px; background: {color_fondo}; padding: 15px; border-radius: 10px; backdrop-filter: blur(4px);">
            <h3 style="color: {color_titulo}; text-align: center; margin-bottom: 12px;">{titulo}</h3>
            <label>Placa de Traba:</label>
            <input type="text" name="{prefijo}_placa_traba" {req_attr} class="btn-ghost" style="background: rgba(0,0,0,0.3); color: white; font-size:16px; padding:10px;">
            <small style="color:#aaa; display:block; margin:5px 0;">Puedes usar una nueva placa.</small>
            <label>Placa Regional (opcional):</label>
            <input type="text" name="{prefijo}_placa_regional" autocomplete="off" class="btn-ghost" style="background: rgba(0,0,0,0.3); color: white; font-size:16px; padding:10px;">
            <label>N° Pelea:</label>
            <input type="text" name="{prefijo}_n_pelea" autocomplete="off" class="btn-ghost" style="background: rgba(0,0,0,0.3); color: white; font-size:16px; padding:10px;">
            <label>Nombre del ejemplar:</label>
            <input type="text" name="{prefijo}_nombre" autocomplete="off" class="btn-ghost" style="background: rgba(0,0,0,0.3); color: white; font-size:16px; padding:10px;">
            <label>Raza:</label>
            <select name="{prefijo}_raza" {req_attr} class="btn-ghost" style="background: rgba(0,0,0,0.3); color: white; font-size:16px; padding:10px;">{razas_html}</select>
            <label>Color:</label>
            <input type="text" name="{prefijo}_color" autocomplete="off" {req_attr} class="btn-ghost" style="background: rgba(0,0,0,0.3); color: white; font-size:16px; padding:10px;">
            <label>Apariencia:</label>
            <div style="margin:5px 0; font-size:16px;">{ap_html}</div>
            <label>Foto (opcional):</label>
            <input type="file" name="{prefijo}_foto" accept="image/*" class="btn-ghost">
        </div>
        '''
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
.container{{width:95%; max-width:1300px; margin:30px auto; padding:20px;}}
.header-modern{{display:flex; justify-content:space-between; align-items:center; margin-bottom:25px; flex-wrap:wrap; gap:15px;}}
.header-modern h1{{font-size:1.8rem; color:#00ffff; text-shadow:0 0 10px #00ffff;}}
.subtitle{{font-size:0.85rem; color:#bbb;}}
.logo{{width:80px; height:auto; filter:drop-shadow(0 0 6px #00ffff);}}
.form-container{{background:rgba(255,255,255,0.06); border-radius:20px; padding:25px; backdrop-filter:blur(10px); box-shadow:0 0 30px rgba(0,255,255,0.4);}}
.btn-ghost{{background:rgba(0,0,0,0.3); border:1px solid rgba(0,255,255,0.2); color:white; padding:10px; border-radius:8px; width:100%; margin:6px 0; font-size:16px;}}
button{{width:100%; padding:16px; border:none; border-radius:10px; background:linear-gradient(135deg,#00ffff,#008cff); color:#041428; font-size:1.2rem; font-weight:bold; cursor:pointer; transition:0.3s; margin-top:15px;}}
button:hover{{transform:translateY(-3px); box-shadow:0 6px 20px rgba(0,255,255,0.5);}}
canvas{{position:fixed; top:0; left:0; width:100%; height:100%; z-index:-1;}}
</style>
</head>
<body>
<canvas id="bg"></canvas>
<div class="container">
<div class="header-modern">
<div>
<h1>🐓 Traba: {traba}</h1>
<p class="subtitle">Sistema moderno • Año 2026</p>
</div>
<img src="/logo" alt="Logo GFRD" class="logo">
</div>
<form method="POST" action="/registrar-gallo" enctype="multipart/form-data" class="form-container">
<div style="display: flex; gap: 15px; flex-wrap: wrap; justify-content: center;">
    {columna("A. Gallo (Obligatorio)", "gallo", "rgba(232,244,252,0.2)", "#2980b9", required=True)}
    {columna("B. Madre (Opcional)", "madre", "rgba(253,239,242,0.2)", "#c0392b", required=False)}
    {columna("C. Padre (Opcional)", "padre", "rgba(235,245,235,0.2)", "#27ae60", required=False)}
</div>
<div style="display: flex; gap: 15px; flex-wrap: wrap; justify-content: center; margin-top:20px;">
    {columna("D. Abuelo Materno (Opcional)", "ab_materno", "rgba(253,242,233,0.2)", "#e67e22", required=False)}
    {columna("E. Abuelo Paterno (Opcional)", "ab_paterno", "rgba(232,248,245,0.2)", "#1abc9c", required=False)}
</div>
<button type="submit">✅ Registrar Gallo</button>
<div style="text-align:center; margin-top:20px;">
    <a href="/menu" class="btn-ghost" style="padding:10px 25px; display:inline-block;">🏠 Regresar al Menú</a>
</div>
</form>
</div>
<script>
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
function init() {{
  particles = [];
  for(let i=0;i<100;i++) particles.push(new Particle());
}}
function animate() {{
  ctx.clearRect(0,0,canvas.width,canvas.height);
  particles.forEach(p=>{{p.update();p.draw();}});
  requestAnimationFrame(animate);
}}
window.addEventListener("resize", ()=>{{canvas.width=window.innerWidth; canvas.height=window.innerHeight; init();}});
init();
animate();
</script>
</body>
</html>
"""

# =============== RUTAS PRINCIPALES ===============
@app.route('/registrar-gallo', methods=['POST'])
@proteger_ruta
def registrar_gallo():
    traba = session['traba']
    conn = sqlite3.connect(DB()
    cursor = conn.cursor()
    def guardar_individuo(prefijo, es_gallo=False):
        placa = request.form.get(f'{prefijo}_placa_traba')
        if not placa:
            if es_gallo:
                raise ValueError("La placa del gallo es obligatoria.")
            else:
                return None
        placa_regional = request.form.get(f'{prefijo}_placa_regional') or None
        nombre = request.form.get(f'{prefijo}_nombre') or None
        n_pelea = request.form.get(f'{prefijo}_n_pelea') or None
        raza = request.form.get(f'{prefijo}_raza')
        color = request.form.get(f'{prefijo}_color')
        apariencia = request.form.get(f'{prefijo}_apariencia')
        if es_gallo and (not raza or not color or not apariencia):
            raise ValueError("Raza, color y apariencia son obligatorios para el gallo.")
        if not es_gallo and (not raza or not color or not apariencia):
            return None
        foto = None
        if f'{prefijo}_foto' in request.files and request.files[f'{prefijo}_foto'].filename != '':
            file = request.files[f'{prefijo}_foto']
            if allowed_file(file.filename):
                safe_placa = secure_filename(placa)
                fname = safe_placa + "_" + secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                foto = fname
        cursor.execute('''
        INSERT INTO individuos (traba, placa_traba, placa_regional, nombre, raza, color, apariencia, n_pelea, nacimiento, foto)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (traba, placa, placa_regional, nombre, raza, color, apariencia, n_pelea, None, foto))
        return cursor.lastrowid
    try:
        gallo_id = guardar_individuo('gallo', es_gallo=True)
        madre_id = guardar_individuo('madre')
        padre_id = guardar_individuo('padre')
        if madre_id is not None or padre_id is not None:
            cursor.execute('''
            INSERT INTO progenitores (individuo_id, madre_id, padre_id)
            VALUES (?, ?, ?)
            ''', (gallo_id, madre_id, padre_id))
        conn.commit()
        conn.close()
        return '''
<!DOCTYPE html>
<html><body style="background:#01030a;color:white;text-align:center;padding:50px;font-family:sans-serif;">
<div style="background:rgba(0,255,255,0.1);padding:30px;border-radius:10px;">
<h2 style="color:#00ffff;">✅ ¡Gallo registrado Exitosamente!</h2>
<a href="/lista" style="display:inline-block;margin-top:20px;padding:12px 24px;background:#00ffff;color:#041428;text-decoration:none;border-radius:6px;">📋 Ver mis gallos</a>
</div></body></html>
'''
    except Exception as e:
        conn.close()
        return f'''
<!DOCTYPE html>
<html><body style="background:#01030a;color:white;text-align:center;padding:50px;font-family:sans-serif;">
<div style="background:rgba(231,76,60,0.1);padding:30px;border-radius:10px;">
<h2 style="color:#ff6b6b;">❌ Error</h2>
<p>{str(e)}</p>
<a href="/formulario-gallo" style="display:inline-block;margin-top:20px;padding:12px 24px;background:#c0392b;color:white;text-decoration:none;border-radius:6px;">← Volver</a>
</div></body></html>
'''

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
<html><head><meta charset="UTF-8"><title>GFRD Cruce Inbreeding 2026</title></head><body style="background:#01030a;color:white;padding:30px;font-family:sans-serif;">
<h2 style="text-align:center;color:#00ffff;">GFRD Cruce Inbreeding</h2>
<form method="POST" action="/registrar-cruce" enctype="multipart/form-data">
<label style="display:block;margin:10px 0;color:#00e6ff;">Tipo de Cruce</label>
<select name="tipo" required style="width:100%;padding:10px;margin-bottom:15px;background:rgba(0,0,0,0.3);color:white;border:none;border-radius:6px;">
<option value="">-- Selecciona --</option>
<option value="Padre-Hija">Padre - Hija</option>
<option value="Madre-Hijo">Madre - Hijo</option>
<option value="Hermano-Hermana">Hermano - Hermana</option>
<option value="Medio-Hermanos">Medio Hermanos</option>
<option value="Tío-Sobrino">Tío - Sobrino</option>
</select>
<label style="display:block;margin:10px 0;color:#00e6ff;">Gallo 1</label>
<select name="gallo1" required style="width:100%;padding:10px;margin-bottom:15px;background:rgba(0,0,0,0.3);color:white;border:none;border-radius:6px;">
{opciones_gallos}
</select>
<label style="display:block;margin:10px 0;color:#00e6ff;">Gallo 2</label>
<select name="gallo2" required style="width:100%;padding:10px;margin-bottom:15px;background:rgba(0,0,0,0.3);color:white;border:none;border-radius:6px;">
{opciones_gallos}
</select>
<label style="display:block;margin:10px 0;color:#00e6ff;">Generación (1-6)</label>
<select name="generacion" required style="width:100%;padding:10px;margin-bottom:15px;background:rgba(0,0,0,0.3);color:white;border:none;border-radius:6px;">
<option value="">-- Elige --</option>
<option value="1">1 (25%)</option>
<option value="2">2 (37.5%)</option>
<option value="3">3 (50%)</option>
<option value="4">4 (62.5%)</option>
<option value="5">5 (75%)</option>
<option value="6">6 (87.5%)</option>
</select>
<label style="display:block;margin:10px 0;color:#00e6ff;">Notas (opcional)</label>
<textarea name="notas" style="width:100%;padding:10px;margin-bottom:15px;background:rgba(0,0,0,0.3);color:white;border:none;border-radius:6px;height:80px;"></textarea>
<label style="display:block;margin:10px 0;color:#00e6ff;">Foto del cruce (opcional)</label>
<input type="file" name="foto" accept="image/*" style="width:100%;margin-bottom:20px;">
<button type="submit" style="width:100%;padding:14px;background:linear-gradient(135deg,#00ffff,#008cff);color:#041428;border:none;border-radius:6px;font-weight:bold;">✅ Registrar Cruce</button>
</form>
<a href="/menu" style="display:inline-block;margin-top:20px;padding:12px 24px;background:#7f8c8d;color:white;text-decoration:none;border-radius:6px;">🏠 Menú</a>
</body></html>
'''

@app.route('/registrar-cruce', methods=['POST'])
@proteger_ruta
def registrar_cruce():
    try:
        tipo = request.form['tipo']
        gallo1_id = int(request.form['gallo1'])
        gallo2_id = int(request.form['gallo2'])
        generacion = int(request.form['generacion'])
        notas = request.form.get('notas', '')
        traba = session['traba']
        conn = sqlite3.connect(DB)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM individuos WHERE id IN (?, ?) AND traba = ?', (gallo1_id, gallo2_id, traba))
        if len(cursor.fetchall()) != 2:
            raise ValueError("Uno o ambos gallos no pertenecen a tu traba.")
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
        conn.close()
        return f'''
<!DOCTYPE html>
<html><body style="background:#01030a;color:white;text-align:center;padding:50px;font-family:sans-serif;">
<div style="background:rgba(0,255,255,0.1);padding:30px;border-radius:10px;">
<h2 style="color:#00ffff;">✅ ¡Cruce registrado!</h2>
<p>Tipo: {tipo}<br>Generación {generacion} ({porcentaje}%)</p>
<a href="/cruce-inbreeding" style="display:inline-block;margin:10px;padding:12px 24px;background:#00ffff;color:#041428;text-decoration:none;border-radius:6px;">🔄 Registrar otro</a>
<a href="/menu" style="display:inline-block;margin:10px;padding:12px 24px;background:#ff7a18;color:#041428;text-decoration:none;border-radius:6px;">🏠 Menú</a>
</div></body></html>
'''
    except Exception as e:
        return f'''
<!DOCTYPE html>
<html><body style="background:#01030a;color:white;text-align:center;padding:50px;font-family:sans-serif;">
<div style="background:rgba(231,76,60,0.1);padding:30px;border-radius:10px;">
<h2 style="color:#ff6b6b;">❌ Error</h2>
<p>{str(e)}</p>
<a href="/cruce-inbreeding" style="display:inline-block;margin:10px;padding:12px 24px;background:#c0392b;color:white;text-decoration:none;border-radius:6px;">← Volver</a>
<a href="/menu" style="display:inline-block;margin:10px;padding:12px 24px;background:#7f8c8d;color:white;text-decoration:none;border-radius:6px;">🏠 Menú</a>
</div></body></html>
'''

@app.route('/buscar', methods=['GET', 'POST'])
@proteger_ruta
def buscar():
    try:
        if request.method == 'POST':
            termino = request.form.get('termino', '').strip()
            if not termino:
                return redirect(url_for('buscar'))
            traba = session['traba']
            conn = sqlite3.connect(DB)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 'gallo' as tipo, i.*, m.placa_traba as madre_placa, p.placa_traba as padre_placa
                FROM individuos i
                LEFT JOIN progenitores pr ON i.id = pr.individuo_id
                LEFT JOIN individuos m ON pr.madre_id = m.id
                LEFT JOIN individuos p ON pr.padre_id = p.id
                WHERE (i.placa_traba LIKE ? OR i.placa_regional LIKE ? OR i.nombre LIKE ? OR i.color LIKE ?)
                  AND i.traba = ?
            ''', (f'%{termino}%', f'%{termino}%', f'%{termino}%', f'%{termino}%', traba))
            resultados = cursor.fetchall()
            conn.close()
            if not resultados:
                return '<script>alert("❌ No se encontraron resultados."); window.location="/buscar";</script>'
            resultados_html = ""
            for r in resultados:
                nombre = r['nombre'] or r['placa_traba']
                resultados_html += f'''
                <div style="background:rgba(0,0,0,0.2);padding:15px;margin:10px 0;border-left:3px solid #00ffff;">
                    <h3>🐓 Gallo: {nombre}</h3>
                    <p><strong>Placa Traba:</strong> {r['placa_traba']}</p>
                    <p><strong>Raza:</strong> {r['raza']}</p>
                    <p><strong>Color:</strong> {r['color']}</p>
                </div>
                '''
            return f'''
<!DOCTYPE html>
<html><head><title>Resultados</title></head>
<body style="background:#01030a;color:white;padding:30px;font-family:sans-serif;">
<h2 style="text-align:center;color:#00ffff;">Resultados de Búsqueda</h2>
{resultados_html}
<a href="/buscar" style="display:inline-block;margin:10px;padding:12px 24px;background:#2ecc71;color:#041428;text-decoration:none;border-radius:6px;">← Nueva búsqueda</a>
<a href="/menu" style="display:inline-block;margin:10px;padding:12px 24px;background:#7f8c8d;color:white;text-decoration:none;border-radius:6px;">🏠 Menú</a>
</body></html>
'''
        else:
            return '''
<!DOCTYPE html>
<html><head><title>Buscar Gallo</title></head>
<body style="background:#01030a;color:white;padding:30px;font-family:sans-serif;">
<h2 style="text-align:center;color:#00ffff;">Buscar Gallo o Cruce</h2>
<form method="POST">
<input type="text" name="termino" placeholder="Placa, nombre, color..." required style="width:100%;padding:12px;margin:15px 0;background:rgba(0,0,0,0.3);color:white;border:none;border-radius:6px;">
<button type="submit" style="width:100%;padding:14px;background:linear-gradient(135deg,#00ffff,#008cff);color:#041428;border:none;border-radius:6px;font-weight:bold;">🔎 Buscar</button>
</form>
<a href="/menu" style="display:inline-block;margin-top:20px;padding:12px 24px;background:#7f8c8d;color:white;text-decoration:none;border-radius:6px;">🏠 Menú</a>
</body></html>
'''
    except Exception as e:
        return f'<script>alert("❌ Error: {str(e)}"); window.location="/buscar";</script>'

@app.route('/lista')
@proteger_ruta
def lista_gallos():
    traba = session['traba']
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT i.id, i.placa_traba, i.placa_regional, i.nombre, i.raza, i.color, i.apariencia, i.n_pelea, i.foto,
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
    gallos_html = ""
    for g in gallos:
        foto_html = f'<img src="/uploads/{g["foto"]}" width="50" style="border-radius:4px;">' if g["foto"] else "—"
        nombre_mostrar = g['nombre'] or g['placa_traba']
        gallos_html += f'''
        <tr>
            <td>{foto_html}</td>
            <td>{g['placa_traba']}</td>
            <td>{nombre_mostrar}</td>
            <td>{g['raza']}</td>
            <td>{g['apariencia']}</td>
            <td>{g['n_pelea'] or "—"}</td>
            <td>{g['madre_placa'] or "—"}</td>
            <td>{g['padre_placa'] or "—"}</td>
            <td>
                <a href="/arbol/{g['id']}" style="margin:0 5px;color:#00ffff;text-decoration:underline;">🌳</a>
                <a href="/editar-gallo/{g['id']}" style="margin:0 5px;color:#00ffff;text-decoration:underline;">✏️</a>
                <a href="/eliminar-gallo/{g['id']}" style="margin:0 5px;color:#e74c3c;text-decoration:underline;">🗑️</a>
            </td>
        </tr>
        '''
    return f'''
<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Mis Gallos</title></head>
<body style="background:#01030a;color:white;padding:20px;font-family:sans-serif;">
<h1 style="color:#00ffff;text-align:center;">Mis Gallos — Traba: {traba}</h1>
<table style="width:100%;border-collapse:collapse;margin:20px 0;">
<thead>
<tr style="color:#00ffff;">
<th>Foto</th><th>Placa</th><th>Nombre</th><th>Raza</th><th>Apariencia</th><th>N° Pelea</th><th>Madre</th><th>Padre</th><th>Acciones</th>
</tr>
</thead>
<tbody style="border-top:1px solid rgba(0,255,255,0.2);">
{gallos_html}
</tbody>
</table>
<a href="/menu" style="display:inline-block;padding:12px 24px;background:#7f8c8d;color:white;text-decoration:none;border-radius:6px;">🏠 Menú</a>
</body></html>
'''

@app.route('/exportar')
@proteger_ruta
def exportar():
    traba = session['traba']
    conn = sqlite3.connect(DB)  # ✅ CORREGIDO: faltaba el paréntesis de cierre
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT i.placa_regional, i.placa_traba, i.nombre, i.raza, i.color, i.n_pelea,
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
    writer.writerow(['Placa_Regional', 'Placa_Traba', 'Nombre', 'Raza', 'Color', 'N_Pelea', 'Madre', 'Padre'])
    for g in gallos:
        writer.writerow([g['placa_regional'], g['placa_traba'], g['nombre'], g['raza'], g['color'], g['n_pelea'], g['madre'], g['padre']])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=gallos.csv"}
    )

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

@app.route('/cerrar-sesion')
def cerrar_sesion():
    session.clear()
    return redirect(url_for('bienvenida'))

# =============== INICIO DEL SERVIDOR ===============
if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
