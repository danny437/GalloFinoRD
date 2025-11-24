from flask import Flask, request, Response, session, redirect, url_for, send_from_directory, jsonify
import sqlite3
import os
import csv
import io
import shutil
import zipfile
from datetime import datetime
from werkzeug.utils import secure_filename
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
            raza TEXT NOT NULL,
            color TEXT NOT NULL,
            apariencia TEXT NOT NULL,
            n_pelea TEXT,
            nacimiento TEXT,
            foto TEXT
        )
        ''')
        cursor.execute('''
        CREATE TABLE progenitores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            individuo_id INTEGER NOT NULL,
            madre_id INTEGER,
            padre_id INTEGER,
            FOREIGN KEY(individuo_id) REFERENCES individuos(id) ON DELETE CASCADE,
            FOREIGN KEY(madre_id) REFERENCES individuos(id),
            FOREIGN KEY(padre_id) REFERENCES individuos(id)
        )
        ''')
        cursor.execute('''
        CREATE TABLE cruces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            traba TEXT NOT NULL,
            tipo TEXT NOT NULL,
            individuo1_id INTEGER NOT NULL,
            individuo2_id INTEGER NOT NULL,
            generacion INTEGER NOT NULL CHECK(generacion BETWEEN 1 AND 6),
            porcentaje REAL NOT NULL,
            fecha TEXT,
            notas TEXT,
            foto TEXT,
            FOREIGN KEY(individuo1_id) REFERENCES individuos(id) ON DELETE CASCADE,
            FOREIGN KEY(individuo2_id) REFERENCES individuos(id) ON DELETE CASCADE
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
            except:
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

# =============== REGISTRO ===============
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

# =============== INICIO DE SESIÓN ===============
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
    if not traba_row:
        return '<script>alert("❌ Correo o contraseña incorrectos."); window.location="/";</script>'
    traba, contraseña_hash = traba_row
    if check_password_hash(contraseña_hash, contraseña):
        session['traba'] = traba
        return redirect(url_for('menu_principal'))
    else:
        return '<script>alert("❌ Correo o contraseña incorrectos."); window.location="/";</script>'

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

# =============== RESTO DE RUTAS (sin cambios) ===============
# Incluye aquí *exactamente* todas las rutas que ya tenías:
# - /formulario-gallo
# - /registrar-gallo
# - /cruce-inbreeding
# - /registrar-cruce
# - /buscar
# - /lista
# - /exportar
# - /editar-gallo/<int:id>
# - /actualizar-gallo/<int:id>
# - /eliminar-gallo/<int:id>
# - /confirmar-eliminar-gallo/<int:id>
# - /arbol/<int:id>
# - /backup
# - /download/<filename>
# - /cerrar-sesion

# Por brevedad y claridad, no repito esas funciones (ya las tienes bien implementadas).
# Solo copia y pega tus rutas existentes a partir de aquí.

# -----------------------------
# Ejemplo de cómo continuar:
@app.route('/formulario-gallo')
@proteger_ruta
def formulario_gallo():
    traba = session['traba']
    return f'''
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🐓 Registrar Gallo — {traba}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;500;700&display=swap');
*{{margin:0; padding:0; box-sizing:border-box; font-family:'Poppins',sans-serif;}}
body{{background:#01030a; color:#fff; padding:20px;}}
.container{{max-width:800px; margin:auto; background:rgba(255,255,255,0.05); border-radius:20px; padding:25px; backdrop-filter:blur(10px);}}
h1{{color:#00ffff; margin-bottom:20px; text-align:center;}}
h2{{color:#00ccaa; margin:25px 0 12px; font-size:1.2rem;}}
.group{{margin-bottom:20px;}}
label{{display:block; margin-bottom:6px; color:#ccc;}}
input, select{{width:100%; padding:10px; background:rgba(255,255,255,0.08); color:white; border:1px solid #00ffff; border-radius:8px;}}
input:focus, select:focus{{outline:none; border-color:#00ffcc;}}
button{{width:100%; padding:14px; background:linear-gradient(135deg,#2ecc71,#3498db); color:#041428; font-weight:bold; border:none; border-radius:10px; cursor:pointer; font-size:17px; margin-top:10px;}}
button:hover{{transform:translateY(-2px); box-shadow:0 4px 15px rgba(0,255,255,0.4);}}
a.back{{display:inline-block; margin-top:20px; color:#00ffcc; text-decoration:underline;}}
</style>
</head>
<body>
<div class="container">
<h1>🐓 Registro de Gallo — Traba: {traba}</h1>

<form method="POST" action="/registrar-gallo" enctype="multipart/form-data">

<h2>✅ Gallo Principal</h2>
<div class="group">
<label>Placa Traba *</label>
<input type="text" name="gallo_placa_traba" required>
</div>
<div class="group">
<label>Placa Regional</label>
<input type="text" name="gallo_placa_regional">
</div>
<div class="group">
<label>Nombre</label>
<input type="text" name="gallo_nombre">
</div>
<div class="group">
<label>N° Pelea</label>
<input type="text" name="gallo_n_pelea">
</div>
<div class="group">
<label>Raza *</label>
<select name="gallo_raza" required>
<option value="">Seleccionar</option>
{"".join(f'<option value="{r}">{r}</option>' for r in RAZAS)}
</select>
</div>
<div class="group">
<label>Color *</label>
<input type="text" name="gallo_color" required>
</div>
<div class="group">
<label>Apariencia *</label>
<input type="text" name="gallo_apariencia" required>
</div>
<div class="group">
<label>Foto</label>
<input type="file" name="gallo_foto" accept=".png,.jpg,.jpeg,.gif">
</div>

<h2>🪺 Madre (opcional)</h2>
<div class="group">
<label>Placa Traba</label>
<input type="text" name="madre_placa_traba">
</div>
<div class="group">
<label>Raza</label>
<select name="madre_raza">
<option value="">— No aplica —</option>
{"".join(f'<option value="{r}">{r}</option>' for r in RAZAS)}
</select>
</div>
<div class="group">
<label>Color</label>
<input type="text" name="madre_color">
</div>
<div class="group">
<label>Apariencia</label>
<input type="text" name="madre_apariencia">
</div>
<div class="group">
<label>Foto</label>
<input type="file" name="madre_foto" accept=".png,.jpg,.jpeg,.gif">
</div>

<h2>🦚 Padre (opcional)</h2>
<div class="group">
<label>Placa Traba</label>
<input type="text" name="padre_placa_traba">
</div>
<div class="group">
<label>Raza</label>
<select name="padre_raza">
<option value="">— No aplica —</option>
{"".join(f'<option value="{r}">{r}</option>' for r in RAZAS)}
</select>
</div>
<div class="group">
<label>Color</label>
<input type="text" name="padre_color">
</div>
<div class="group">
<label>Apariencia</label>
<input type="text" name="padre_apariencia">
</div>
<div class="group">
<label>Foto</label>
<input type="file" name="padre_foto" accept=".png,.jpg,.jpeg,.gif">
</div>

<h2>👴 Abuelo Materno (opcional)</h2>
<div class="group">
<label>Placa Traba</label>
<input type="text" name="ab_materno_placa_traba">
</div>
<div class="group">
<label>Raza</label>
<select name="ab_materno_raza">
<option value="">— No aplica —</option>
{"".join(f'<option value="{r}">{r}</option>' for r in RAZAS)}
</select>
</div>
<div class="group">
<label>Color</label>
<input type="text" name="ab_materno_color">
</div>
<div class="group">
<label>Apariencia</label>
<input type="text" name="ab_materno_apariencia">
</div>

<h2>👴 Abuelo Paterno (opcional)</h2>
<div class="group">
<label>Placa Traba</label>
<input type="text" name="ab_paterno_placa_traba">
</div>
<div class="group">
<label>Raza</label>
<select name="ab_paterno_raza">
<option value="">— No aplica —</option>
{"".join(f'<option value="{r}">{r}</option>' for r in RAZAS)}
</select>
</div>
<div class="group">
<label>Color</label>
<input type="text" name="ab_paterno_color">
</div>
<div class="group">
<label>Apariencia</label>
<input type="text" name="ab_paterno_apariencia">
</div>

<button type="submit">✅ Registrar Gallo y Linaje</button>
</form>
<a href="/menu" class="back">⬅️ Volver al Menú</a>
</div>
</body>
</html>
'''

# ... (todas tus demás rutas)

# -----------------------------

@app.route('/cerrar-sesion')
def cerrar_sesion():
    session.clear()
    return redirect(url_for('bienvenida'))

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

