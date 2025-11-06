from flask import Flask, request, Response, session, redirect, url_for, send_from_directory, jsonify, send_file
import sqlite3
import os
import csv
import io
import shutil
import zipfile
from datetime import datetime
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from pathlib import Path

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
        cols = [col[1] for col in cursor.execute("PRAGMA table_info(individuos)").fetchall()]
        for col in ['placa_regional', 'nombre', 'n_pelea', 'nacimiento', 'foto']:
            if col not in cols:
                try:
                    cursor.execute(f"ALTER TABLE individuos ADD COLUMN {col} TEXT")
                except:
                    pass
        cols_cruces = [col[1] for col in cursor.execute("PRAGMA table_info(cruces)").fetchall()]
        if 'porcentaje' not in cols_cruces:
            try:
                cursor.execute("ALTER TABLE cruces ADD COLUMN porcentaje REAL")
            except:
                pass
        try:
            cursor.execute('''CREATE TABLE progenitores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                individuo_id INTEGER NOT NULL,
                madre_id INTEGER,
                padre_id INTEGER,
                FOREIGN KEY(individuo_id) REFERENCES individuos(id) ON DELETE CASCADE,
                FOREIGN KEY(madre_id) REFERENCES individuos(id),
                FOREIGN KEY(padre_id) REFERENCES individuos(id)
            )''')
        except: pass
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
body{{background:#01030a; color:white; overflow:hidden; font-size:17px;}}
.container{{width:90%; max-width:500px; margin:50px auto; background:rgba(255,255,255,0.05); border-radius:20px; padding:30px; backdrop-filter:blur(8px); box-shadow:0 0 25px rgba(0,255,255,0.3);}}
.logo{{width:80px; height:auto; filter:drop-shadow(0 0 6px #00ffff); float:right;}}
h1{{font-size:2rem; color:#00ffff; text-shadow:0 0 12px #00ffff; margin-bottom:10px;}}
.subtitle{{font-size:0.9rem; color:#bbb;}}
.form-container input, .form-container button{{width:100%; padding:14px; margin:8px 0 15px; border-radius:10px; border:none; outline:none; font-size:17px;}}
.form-container input{{background:rgba(255,255,255,0.08); color:white;}}
.form-container button{{background:linear-gradient(135deg,#3498db,#2ecc71); color:#041428; font-weight:bold; cursor:pointer; transition:0.3s;}}
.form-container button:hover{{transform:translateY(-3px); box-shadow:0 4px 15px rgba(0,255,255,0.4);}}
canvas{{position:fixed; top:0; left:0; width:100%; height:100%; z-index:-1;}}
</style>
</head>
<body>
<canvas id="bg"></canvas>
<div class="container">
<img src="/logo" alt="Logo GFRD" class="logo">
<h1>🐓 GalloFino</h1>
<p class="subtitle">Sistema Profesional de Gestión Genética • Año 2026</p>
<div class="form-container">
<form method="POST" action="/registrar-traba">
<input type="text" name="nombre" required placeholder="Nombre">
<input type="text" name="apellido" required placeholder="Apellido">
<input type="text" name="traba" required placeholder="Nombre de la Traba">
<input type="password" name="contraseña" required placeholder="Contraseña">
<input type="date" name="fecha" value="{fecha_actual}">
<button type="submit">✅ Registrarme</button>
</form>
<p style="margin-top: 20px; font-size: 14px;">¿Ya tienes cuenta?</p>
<form method="POST" action="/iniciar-sesion">
<input type="text" name="traba" required placeholder="Nombre de la Traba">
<input type="password" name="contraseña" required placeholder="Contraseña">
<button style="background:linear-gradient(135deg,#2ecc71,#3498db);">🔑 Iniciar Sesión</button>
</form>
</div>
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

# =============== MENÚ PRINCIPAL (CORREGIDO: sin /backup-manual) ===============
@app.route('/menu')
@proteger_ruta
def menu_principal():
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
body{{background:#01030a; color:white; overflow:hidden; font-size:17px;}}
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
<h1>GFRD Menú Principal</h1>
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

# =============== REGISTRO DE GALLO (CON PLACA EDITABLE) ===============
@app.route('/formulario-gallo')
@proteger_ruta
def formulario_gallo():
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
<h1>GFRD Registro de Gallo</h1>
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

# =============== Todas las demás rutas (igual que en tu archivo original) ===============
# Incluyen botón de "Regresar al Menú" y estilos mejorados
# Por brevedad no se repiten aquí, pero están en el archivo completo que puedes descargar

@app.route('/registrar-traba', methods=['POST'])
def registrar_traba():
    nombre = request.form.get('nombre', '').strip()
    apellido = request.form.get('apellido', '').strip()
    traba = request.form.get('traba', '').strip()
    contraseña = request.form.get('contraseña', '').strip()
    if not (nombre and apellido and traba and contraseña):
        return redirect(url_for('bienvenida'))
    try:
        conn = sqlite3.connect(DB)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM trabas WHERE nombre_traba = ?', (traba,))
        if cursor.fetchone():
            return '<script>alert("❌ Esa traba ya existe."); window.location="/";</script>'
        contraseña_hash = generate_password_hash(contraseña)
        cursor.execute('''
        INSERT INTO trabas (nombre_traba, nombre_completo, contraseña_hash)
        VALUES (?, ?, ?)
        ''', (traba, f"{nombre} {apellido}", contraseña_hash))
        conn.commit()
        conn.close()
        session['traba'] = traba
        session['fecha'] = request.form.get('fecha', '').strip() or "—"
        return redirect(url_for('menu_principal'))
    except Exception as e:
        return f'<script>alert("❌ Error: {str(e)}"); window.location="/";</script>'

@app.route('/iniciar-sesion', methods=['POST'])
def iniciar_sesion():
    traba = request.form.get('traba', '').strip()
    contraseña = request.form.get('contraseña', '').strip()
    if not (traba and contraseña):
        return redirect(url_for('bienvenida'))
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute('SELECT contraseña_hash FROM trabas WHERE nombre_traba = ?', (traba,))
    row = cursor.fetchone()
    conn.close()
    if row and check_password_hash(row[0], contraseña):
        session['traba'] = traba
        session['fecha'] = "—"
        return redirect(url_for('menu_principal'))
    return '<script>alert("❌ Traba o contraseña incorrecta."); window.location="/";</script>'

@app.route('/cerrar-sesion')
def cerrar_sesion():
    session.clear()
    return redirect(url_for('bienvenida'))

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
        foto_html = f'<img src="/uploads/{g["foto"]}" width="60" style="border-radius:4px;">' if g["foto"] else "—"
        nombre_mostrar = g['nombre'] or g['placa_traba']
        placa_traba = g['placa_traba'] or "—"
        madre_txt = g['madre_placa'] or "—"
        padre_txt = g['padre_placa'] or "—"
        gallos_html += f'''
        <tr>
            <td>{foto_html}</td>
            <td>{placa_traba}</td>
            <td>{g['placa_regional'] or "—"}</td>
            <td>{nombre_mostrar}</td>
            <td>{g['raza']}</td>
            <td>{g['apariencia']}</td>
            <td>{g['n_pelea'] or "—"}</td>
            <td>{madre_txt}</td>
            <td>{padre_txt}</td>
            <td>
                <a href="/arbol/{g['id']}" class="btn-ghost">🌳</a>
                <a href="/editar-gallo/{g['id']}" class="btn-ghost">✏️</a>
                <a href="/eliminar-gallo/{g['id']}" class="btn-ghost">🗑️</a>
            </td>
        </tr>
        '''
    return f"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GFRD Mis Gallos 2026</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;500;700&display=swap');
*{{margin:0; padding:0; box-sizing:border-box; font-family:'Poppins', sans-serif;}}
body{{background:#01030a; color:white; overflow-x:hidden; font-size:17px;}}
.container{{width:95%; max-width:1200px; margin:30px auto;}}
.header-modern{{display:flex; justify-content:space-between; align-items:center; margin-bottom:25px; flex-wrap:wrap; gap:15px;}}
.header-modern h1{{font-size:1.8rem; color:#00ffff; text-shadow:0 0 10px #00ffff;}}
.subtitle{{font-size:0.85rem; color:#bbb;}}
.logo{{width:80px; height:auto; filter:drop-shadow(0 0 6px #00ffff);}}
.card{{background:rgba(255,255,255,0.06); border-radius:20px; padding:25px; backdrop-filter:blur(10px); box-shadow:0 0 30px rgba(0,255,255,0.4); margin-top:10px;}}
table{{width:100%; border-collapse:collapse; margin-top:15px;}}
th, td{{padding:12px; text-align:left; border-bottom:1px solid rgba(0,255,255,0.1); font-size:16px;}}
th{{color:#00ffff;}}
.btn-ghost{{background:transparent; border:1px solid rgba(0,255,255,0.3); color:#00ffff; padding:6px 10px; border-radius:6px; text-decoration:none; display:inline-block; margin:0 2px;}}
.btn-ghost:hover{{background:rgba(0,255,255,0.1);}}
canvas{{position:fixed; top:0; left:0; width:100%; height:100%; z-index:-1;}}
</style>
</head>
<body>
<canvas id="bg"></canvas>
<div class="container">
<div class="header-modern">
<div>
<h1>GFRD Mis Gallos</h1>
<p class="subtitle">Sistema moderno • Año 2026</p>
</div>
<img src="/logo" alt="Logo GFRD" class="logo">
</div>
<div class="card">
<table>
<thead>
    <tr>
        <th>Foto</th>
        <th>Placa Traba</th>
        <th>Regional</th>
        <th>Nombre</th>
        <th>Raza</th>
        <th>Apariencia</th>
        <th>N° Pelea</th>
        <th>Madre</th>
        <th>Padre</th>
        <th>Acciones</th>
    </tr>
</thead>
<tbody>
{gallos_html}
</tbody>
</table>
<div style="text-align:center; margin-top:20px;">
    <a href="/menu" class="btn-ghost" style="padding:10px 25px;">🏠 Regresar al Menú</a>
</div>
</div>
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

# =============== RUTAS ADICIONALES (mismas que en tu archivo) ===============
# /buscar, /arbol/<id>, /exportar, /editar-gallo/<id>, /actualizar-gallo/<id>, /eliminar-gallo/<id>, /confirmar-eliminar-gallo/<id>, /cruce-inbreeding, /registrar-cruce

@app.route('/buscar', methods=['GET', 'POST'])
@proteger_ruta
def buscar():
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
        if not resultados:
            cursor.execute('''
                SELECT 'cruce' as tipo, c.*, 
                       i1.placa_traba as placa1, i1.nombre as nombre1,
                       i2.placa_traba as placa2, i2.nombre as nombre2
                FROM cruces c
                JOIN individuos i1 ON c.individuo1_id = i1.id
                JOIN individuos i2 ON c.individuo2_id = i2.id
                WHERE (i1.placa_traba LIKE ? OR i2.placa_traba LIKE ? OR c.tipo LIKE ?)
                  AND c.traba = ?
            ''', (f'%{termino}%', f'%{termino}%', f'%{termino}%', traba))
            resultados = cursor.fetchall()
        conn.close()
        resultados_html = ""
        for r in resultados:
            if r['tipo'] == 'gallo':
                nombre = r['nombre'] or r['placa_traba']
                resultados_html += f'''
                <div class="resultado-card">
                    <h3>🐓 Gallo: {nombre}</h3>
                    <p><strong>Placa Traba:</strong> {r['placa_traba']}</p>
                    <p><strong>Raza:</strong> {r['raza']}</p>
                    <p><strong>Color:</strong> {r['color']}</p>
                    <p><strong>Madre:</strong> {r['madre_placa'] or '—'}</p>
                    <p><strong>Padre:</strong> {r['padre_placa'] or '—'}</p>
                </div>
                '''
            else:
                resultados_html += f'''
                <div class="resultado-card">
                    <h3>🔁 Cruce: {r['tipo']}</h3>
                    <p><strong>Generación:</strong> {r['generacion']} ({r['porcentaje']}%)</p>
                    <p><strong>Gallo 1:</strong> {r['placa1']} - {r['nombre1'] or '—'}</p>
                    <p><strong>Gallo 2:</strong> {r['placa2']} - {r['nombre2'] or '—'}</p>
                </div>
                '''
        return f"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GFRD Buscar Resultados 2026</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;500;700&display=swap');
*{{margin:0; padding:0; box-sizing:border-box; font-family:'Poppins', sans-serif;}}
body{{background:#01030a; color:white; overflow-x:hidden; font-size:17px;}}
.container{{width:95%; max-width:800px; margin:30px auto;}}
.header-modern{{display:flex; justify-content:space-between; align-items:center; margin-bottom:25px; flex-wrap:wrap; gap:15px;}}
.header-modern h1{{font-size:1.8rem; color:#00ffff; text-shadow:0 0 10px #00ffff;}}
.subtitle{{font-size:0.85rem; color:#bbb;}}
.logo{{width:80px; height:auto; filter:drop-shadow(0 0 6px #00ffff);}}
.card{{background:rgba(255,255,255,0.06); border-radius:20px; padding:25px; backdrop-filter:blur(10px); box-shadow:0 0 30px rgba(0,255,255,0.4); margin-top:10px;}}
.resultado-card{{background:rgba(0,0,0,0.2); padding:15px; border-radius:12px; margin:10px 0; border-left:3px solid #00ffff;}}
.btn-ghost{{display:inline-block; padding:10px 20px; background:rgba(0,255,255,0.1); border:1px solid #00ffff; color:#00ffff; text-decoration:none; border-radius:8px; margin:5px;}}
canvas{{position:fixed; top:0; left:0; width:100%; height:100%; z-index:-1;}}
</style>
</head>
<body>
<canvas id="bg"></canvas>
<div class="container">
<div class="header-modern">
<div>
<h1>GFRD Resultados de Búsqueda</h1>
<p class="subtitle">Sistema moderno • Año 2026</p>
</div>
<img src="/logo" alt="Logo GFRD" class="logo">
</div>
<div class="card">
{resultados_html if resultados_html else '<p style="text-align:center; color:#ff6b6b;">❌ No se encontraron resultados.</p>'}
<div style="text-align:center; margin-top:20px;">
    <a href="/buscar" class="btn-ghost">← Nueva búsqueda</a>
    <a href="/menu" class="btn-ghost">🏠 Menú</a>
</div>
</div>
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
    else:
        return f"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GFRD Buscar Gallo 2026</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;500;700&display=swap');
*{{margin:0; padding:0; box-sizing:border-box; font-family:'Poppins', sans-serif;}}
body{{background:#01030a; color:white; overflow-x:hidden; font-size:17px;}}
.container{{width:95%; max-width:600px; margin:50px auto;}}
.header-modern{{display:flex; justify-content:space-between; align-items:center; margin-bottom:25px; flex-wrap:wrap; gap:15px;}}
.header-modern h1{{font-size:1.8rem; color:#00ffff; text-shadow:0 0 10px #00ffff;}}
.subtitle{{font-size:0.85rem; color:#bbb;}}
.logo{{width:80px; height:auto; filter:drop-shadow(0 0 6px #00ffff);}}
.card{{background:rgba(255,255,255,0.06); border-radius:20px; padding:30px; backdrop-filter:blur(10px); box-shadow:0 0 30px rgba(0,255,255,0.4);}}
input, button{{width:100%; padding:14px; margin:10px 0; border-radius:10px; border:none;}}
input{{background:rgba(0,0,0,0.3); color:white;}}
button{{background:linear-gradient(135deg,#00ffff,#008cff); color:#041428; font-weight:bold; font-size:1.1rem;}}
button:hover{{transform:translateY(-3px); box-shadow:0 6px 20px rgba(0,255,255,0.5);}}
canvas{{position:fixed; top:0; left:0; width:100%; height:100%; z-index:-1;}}
</style>
</head>
<body>
<canvas id="bg"></canvas>
<div class="container">
<div class="header-modern">
<div>
<h1>GFRD Buscar Gallo o Cruce</h1>
<p class="subtitle">Sistema moderno • Año 2026</p>
</div>
<img src="/logo" alt="Logo GFRD" class="logo">
</div>
<div class="card">
<form method="POST">
    <label style="color:#00e6ff; font-weight:600; display:block; margin-bottom:8px;">Término de búsqueda:</label>
    <input type="text" name="termino" placeholder="Placa, nombre, color, tipo de cruce..." required>
    <button type="submit">🔎 Buscar</button>
</form>
<div style="text-align:center; margin-top:20px;">
    <a href="/menu" class="btn-ghost" style="padding:10px 25px; display:inline-block;">🏠 Menú Principal</a>
</div>
</div>
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

@app.route('/arbol/<int:id>')
@proteger_ruta
def arbol_genealogico(id):
    traba = session['traba']
    def get_individuo(ind_id):
        if not ind_id: return None
        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM individuos WHERE id = ? AND traba = ?', (ind_id, traba))
        row = cursor.fetchone()
        conn.close()
        return row
    def get_progenitores(ind_id):
        if not ind_id: return None, None
        conn = sqlite3.connect(DB)
        cursor = conn.cursor()
        cursor.execute('SELECT madre_id, padre_id FROM progenitores WHERE individuo_id = ?', (ind_id,))
        row = cursor.fetchone()
        conn.close()
        return (row['madre_id'], row['padre_id']) if row else (None, None)
    gallo = get_individuo(id)
    if not gallo:
        return '<script>alert("❌ Gallo no encontrado."); window.location="/lista";</script>'
    madre_id, padre_id = get_progenitores(id)
    madre = get_individuo(madre_id)
    padre = get_individuo(padre_id)
    abuelos = []
    if madre_id:
        ab_m, ab_p = get_progenitores(madre_id)
        abuelos.extend([get_individuo(ab_m), get_individuo(ab_p)])
    else:
        abuelos.extend([None, None])
    if padre_id:
        ab_m, ab_p = get_progenitores(padre_id)
        abuelos.extend([get_individuo(ab_m), get_individuo(ab_p)])
    else:
        abuelos.extend([None, None])
    def detalle_card(ind, title, color):
        if not ind:
            return f'<div class="card" style="background:#f8f9fa;color:#6c757d;text-align:center;"><strong>{title}</strong><br><em>— Sin datos —</em></div>'
        nombre = ind['nombre'] or "—"
        placa_traba = ind['placa_traba'] or "—"
        placa_regional = ind['placa_regional'] or "—"
        n_pelea = ind['n_pelea'] or "—"
        raza = ind['raza'] or "—"
        color_val = ind['color'] or "—"
        apariencia = ind['apariencia'] or "—"
        foto_url = f"/uploads/{ind['foto']}" if ind['foto'] else None
        foto_html = f'<img src="{foto_url}" style="width:80px;height:80px;object-fit:cover;border-radius:8px;margin-right:15px;">' if foto_url else '<div style="width:80px;height:80px;background:#e9ecef;border-radius:8px;margin-right:15px;"></div>'
        return f'''
        <div class="card" style="background:{color};color:white;">
            <h3 style="margin:0 0 12px;text-align:center;">{title}</h3>
            <div style="display:flex;align-items:flex-start;">
                {foto_html}
                <div style="flex:1;">
                    <p style="margin:4px 0;"><strong>Nombre:</strong> {nombre}</p>
                    <p style="margin:4px 0;"><strong>Placa Traba:</strong> {placa_traba}</p>
                    <p style="margin:4px 0;"><strong>Placa Regional:</strong> {placa_regional}</p>
                    <p style="margin:4px 0;"><strong>N° Pelea:</strong> {n_pelea}</p>
                    <p style="margin:4px 0;"><strong>Raza:</strong> {raza}</p>
                    <p style="margin:4px 0;"><strong>Color:</strong> {color_val}</p>
                    <p style="margin:4px 0;"><strong>Apariencia:</strong> {apariencia}</p>
                </div>
            </div>
        </div>
        '''
    html_content = f'''
    <div style="max-width:900px;margin:0 auto;background:rgba(0,0,0,0.15);padding:25px;border-radius:12px;">
        <h2 style="text-align:center;color:#2c3e50;">🌳 Árbol Genealógico</h2>
        {detalle_card(gallo, '🐓 Gallo', '#3498db')}
        <h3 style="text-align:center;margin:25px 0 15px;color:#2c3e50;"> Padres </h3>
        <div style="display:flex;flex-wrap:wrap;gap:15px;justify-content:space-between;">
            <div style="flex:1;min-width:250px;">{detalle_card(madre, '👩 Madre', '#e74c3c')}</div>
            <div style="flex:1;min-width:250px;">{detalle_card(padre, '🐓 Padre', '#27ae60')}</div>
        </div>
        <h3 style="text-align:center;margin:25px 0 15px;color:#2c3e50;"> Abuelos </h3>
        <div style="display:flex;flex-wrap:wrap;gap:15px;justify-content:space-between;">
            <div style="flex:1;min-width:200px;">{detalle_card(abuelos[0], '👵 Abuela Materna', '#e67e22')}</div>
            <div style="flex:1;min-width:200px;">{detalle_card(abuelos[1], '👴 Abuelo Materno', '#e67e22')}</div>
            <div style="flex:1;min-width:200px;">{detalle_card(abuelos[2], '👵 Abuela Paterna', '#1abc9c')}</div>
            <div style="flex:1;min-width:200px;">{detalle_card(abuelos[3], '👴 Abuelo Paterno', '#1abc9c')}</div>
        </div>
        <div style="text-align:center;margin-top:25px;">
            <a href="/lista" class="btn-ghost" style="display:inline-block;padding:10px 20px;background:linear-gradient(135deg,#3498db,#2980b9);color:white;text-decoration:none;border-radius:8px;">← Volver</a>
            <a href="/menu" class="btn-ghost" style="display:inline-block;padding:10px 20px;background:linear-gradient(135deg,#f6c84c,#ff7a18);color:#041428;text-decoration:none;border-radius:8px;margin-left:10px;">🏠 Menú</a>
        </div>
    </div>
    '''
    return f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GFRD Árbol 2026</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;500;700&display=swap');
*{{margin:0; padding:0; box-sizing:border-box; font-family:'Poppins', sans-serif;}}
body{{background:#01030a; color:white; overflow-x:hidden; font-size:17px;}}
.container{{width:95%; max-width:1000px; margin:30px auto;}}
.card{{background:rgba(255,255,255,0.06); border-radius:12px; padding:16px; margin:12px 0; box-shadow:0 4px 12px rgba(0,0,0,0.1);}}
.btn-ghost{{display:inline-block; padding:10px 20px; background:rgba(0,255,255,0.1); border:1px solid #00ffff; color:#00ffff; text-decoration:none; border-radius:8px; margin:5px;}}
canvas{{position:fixed; top:0; left:0; width:100%; height:100%; z-index:-1;}}
</style>
</head>
<body>
<canvas id="bg"></canvas>
<div class="container">{html_content}</div>
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
</script>
</body>
</html>
"""

@app.route('/exportar')
@proteger_ruta
def exportar():
    traba = session['traba']
    conn = sqlite3.connect(DB)
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

@app.route('/editar-gallo/<int:id>')
@proteger_ruta
def editar_gallo(id):
    if not verificar_pertenencia(id, 'individuos'):
        return '<script>alert("❌ No tienes permiso."); window.location="/lista";</script>'
    traba = session['traba']
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM individuos WHERE id = ?', (id,))
    gallo = cursor.fetchone()
    if not gallo:
        conn.close()
        return '<script>alert("❌ Gallo no encontrado."); window.location="/lista";</script>'
    cursor.execute('SELECT madre_id, padre_id FROM progenitores WHERE individuo_id = ?', (id,))
    progen = cursor.fetchone()
    madre_actual = progen['madre_id'] if progen else None
    padre_actual = progen['padre_id'] if progen else None
    cursor.execute('SELECT id, placa_traba, nombre, raza FROM individuos WHERE traba = ? AND id != ? ORDER BY placa_traba', (traba, id))
    todos_gallos = cursor.fetchall()
    conn.close()
    razas_html = ''.join([f'<option value="{r}" {"selected" if r == gallo["raza"] else ""}>{r}</option>' for r in RAZAS])
    apariencias = ['Crestarosa', 'Cocolo', 'Tuceperne', 'Pava', 'Moton']
    apariencias_html = ''.join([f'<label><input type="radio" name="apariencia" value="{a}" {"checked" if a == gallo["apariencia"] else ""}> {a}</label><br>' for a in apariencias])
    opciones_gallos = ''.join([
        f'<option value="{g["id"]}" {"selected" if g["id"] == madre_actual else ""}>{g["placa_traba"]} ({g["raza"]}) - {g["nombre"] or "Sin nombre"}</option>'
        for g in todos_gallos
    ])
    return f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>GFRD Editar Gallo 2026</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;500;700&display=swap');
*{{margin:0; padding:0; box-sizing:border-box; font-family:'Poppins', sans-serif;}}
body{{background:#01030a; color:white; overflow:hidden; font-size:17px;}}
.container{{width:95%; max-width:700px; margin:30px auto;}}
.header-modern{{display:flex; justify-content:space-between; align-items:center; margin-bottom:25px; flex-wrap:wrap; gap:15px;}}
.header-modern h1{{font-size:1.8rem; color:#00ffff; text-shadow:0 0 10px #00ffff;}}
.subtitle{{font-size:0.85rem; color:#bbb;}}
.logo{{width:80px; height:auto; filter:drop-shadow(0 0 6px #00ffff);}}
.form-container{{background:rgba(255,255,255,0.06); border-radius:20px; padding:25px; backdrop-filter:blur(10px); box-shadow:0 0 30px rgba(0,255,255,0.4);}}
input, select, textarea{{width:100%; padding:10px; margin:8px 0; border-radius:8px; background:rgba(0,0,0,0.3); color:white; border:none;}}
button{{width:100%; padding:14px; margin-top:20px; border-radius:10px; background:linear-gradient(135deg,#00ffff,#008cff); color:#041428; font-weight:bold; cursor:pointer;}}
canvas{{position:fixed; top:0; left:0; width:100%; height:100%; z-index:-1;}}
</style>
</head>
<body>
<canvas id="bg"></canvas>
<div class="container">
<div class="header-modern">
<div>
<h1>GFRD Editar Gallo</h1>
<p class="subtitle">Sistema moderno • Año 2026</p>
</div>
<img src="/logo" alt="Logo GFRD" class="logo">
</div>
<form method="POST" action="/actualizar-gallo/{id}" enctype="multipart/form-data" class="form-container">
<label>Placa de Traba:</label>
<input type="text" name="placa_traba" value="{gallo['placa_traba']}" required>
<label>Placa Regional:</label>
<input type="text" name="placa_regional" value="{gallo['placa_regional'] or ''}">
<label>N° Pelea:</label>
<input type="text" name="n_pelea" value="{gallo['n_pelea'] or ''}">
<label>Nombre:</label>
<input type="text" name="nombre" value="{gallo['nombre'] or ''}">
<label>Raza:</label>
<select name="raza" required>{razas_html}</select>
<label>Color:</label>
<input type="text" name="color" value="{gallo['color']}" required>
<label>Apariencia:</label>
<div style="margin:5px 0;">{apariencias_html}</div>
<label>Foto actual:</label>
<div>{f'<img src="/uploads/{gallo["foto"]}" width="100" style="border-radius:4px;">' if gallo["foto"] else "—"}</div>
<label>Nueva foto:</label>
<input type="file" name="foto" accept="image/*">
<label>Madre:</label>
<select name="madre_id">
<option value="">-- Ninguna --</option>
{opciones_gallos}
</select>
<label>Padre:</label>
<select name="padre_id">
<option value="">-- Ninguno --</option>
{opciones_gallos}
</select>
<button type="submit">✅ Actualizar</button>
<div style="text-align:center; margin-top:20px;">
    <a href="/lista" class="btn-ghost" style="padding:10px 25px; display:inline-block;">❌ Cancelar</a>
    <a href="/menu" class="btn-ghost" style="padding:10px 25px; display:inline-block; margin-left:10px;">🏠 Menú</a>
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

@app.route('/actualizar-gallo/<int:id>', methods=['POST'])
@proteger_ruta
def actualizar_gallo(id):
    if not verificar_pertenencia(id, 'individuos'):
        return '<script>alert("❌ No tienes permiso."); window.location="/lista";</script>'
    traba = session['traba']
    placa_traba = request.form['placa_traba']
    placa_regional = request.form.get('placa_regional', None) or None
    nombre = request.form.get('nombre', None) or None
    n_pelea = request.form.get('n_pelea', None) or None
    raza = request.form['raza']
    color = request.form['color']
    apariencia = request.form['apariencia']
    madre_id = request.form.get('madre_id') or None
    padre_id = request.form.get('padre_id') or None
    if madre_id == "": madre_id = None
    if padre_id == "": padre_id = None
    if madre_id: madre_id = int(madre_id)
    if padre_id: padre_id = int(padre_id)
    foto_filename = None
    if 'foto' in request.files and request.files['foto'].filename != '':
        file = request.files['foto']
        if allowed_file(file.filename):
            fname = secure_filename(f"g_{placa_traba}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
            foto_filename = fname
    try:
        conn = sqlite3.connect(DB)
        cursor = conn.cursor()
        if foto_filename:
            cursor.execute('''
            UPDATE individuos SET placa_regional=?, placa_traba=?, nombre=?, raza=?, color=?, apariencia=?, n_pelea=?, foto=?
            WHERE id=? AND traba=?
            ''', (placa_regional, placa_traba, nombre, raza, color, apariencia, n_pelea, foto_filename, id, traba))
        else:
            cursor.execute('''
            UPDATE individuos SET placa_regional=?, placa_traba=?, nombre=?, raza=?, color=?, apariencia=?, n_pelea=?
            WHERE id=? AND traba=?
            ''', (placa_regional, placa_traba, nombre, raza, color, apariencia, n_pelea, id, traba))
        cursor.execute('SELECT 1 FROM progenitores WHERE individuo_id = ?', (id,))
        if cursor.fetchone():
            cursor.execute('''
                UPDATE progenitores SET madre_id = ?, padre_id = ? WHERE individuo_id = ?
            ''', (madre_id, padre_id, id))
        else:
            cursor.execute('''
                INSERT INTO progenitores (individuo_id, madre_id, padre_id)
                VALUES (?, ?, ?)
            ''', (id, madre_id, padre_id))
        conn.commit()
        conn.close()
        return '<script>alert("✅ ¡Gallo actualizado!"); window.location="/lista";</script>'
    except Exception as e:
        return f'<script>alert("❌ Error: {str(e)}"); window.location="/editar-gallo/{id}";</script>'

@app.route('/eliminar-gallo/<int:id>')
@proteger_ruta
def eliminar_gallo(id):
    if not verificar_pertenencia(id, 'individuos'):
        return '<script>alert("❌ No tienes permiso."); window.location="/lista";</script>'
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute('SELECT placa_traba FROM individuos WHERE id = ? AND traba = ?', (id, session['traba']))
    gallo = cursor.fetchone()
    conn.close()
    if not gallo:
        return '<script>alert("❌ Gallo no encontrado."); window.location="/lista";</script>'
    return f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>GFRD Eliminar Gallo 2026</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;500;700&display=swap');
*{{margin:0; padding:0; box-sizing:border-box; font-family:'Poppins', sans-serif;}}
body{{background:#01030a; color:white; overflow:hidden; font-size:17px;}}
.container{{width:95%; max-width:500px; margin:50px auto; text-align:center;}}
.card{{background:rgba(255,245,245,0.1); border-radius:10px; padding:30px; border:2px solid #e74c3c;}}
h3{{color:#c0392b;}}
.button-group{{margin-top:20px;}}
.button-group a{{display:inline-block; padding:10px 20px; margin:0 10px; border-radius:8px; text-decoration:none; font-weight:bold;}}
.button-group a.yes{{background:linear-gradient(135deg,#c0392b,#e74c3c); color:white;}}
.button-group a.no{{background:linear-gradient(135deg,#7f8c8d,#95a5a6); color:white;}}
canvas{{position:fixed; top:0; left:0; width:100%; height:100%; z-index:-1;}}
</style>
</head>
<body>
<canvas id="bg"></canvas>
<div class="container">
<div class="card">
<h3>⚠️ Confirmar Eliminación</h3>
<p>¿Eliminar el gallo <strong>{gallo[0]}</strong>?</p>
<p style="color:#e74c3c; font-size:14px;">Esta acción no se puede deshacer.</p>
<div class="button-group">
<a href="/confirmar-eliminar-gallo/{id}" class="yes">✅ Sí, eliminar</a>
<a href="/lista" class="no">❌ Cancelar</a>
</div>
<div style="margin-top:20px;">
    <a href="/menu" class="btn-ghost" style="display:inline-block;padding:10px 20px;background:linear-gradient(135deg,#f6c84c,#ff7a18);color:#041428;text-decoration:none;border-radius:8px;">🏠 Menú</a>
</div>
</div>
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

@app.route('/confirmar-eliminar-gallo/<int:id>')
@proteger_ruta
def confirmar_eliminar_gallo(id):
    if not verificar_pertenencia(id, 'individuos'):
        return '<script>alert("❌ No tienes permiso."); window.location="/lista";</script>'
    try:
        conn = sqlite3.connect(DB)
        cursor = conn.cursor()
        cursor.execute('SELECT foto FROM individuos WHERE id = ? AND traba = ?', (id, session['traba']))
        foto = cursor.fetchone()
        if foto and foto[0]:
            foto_path = os.path.join(app.config['UPLOAD_FOLDER'], foto[0])
            if os.path.exists(foto_path):
                os.remove(foto_path)
        cursor.execute('DELETE FROM individuos WHERE id = ? AND traba = ?', (id, session['traba']))
        conn.commit()
        conn.close()
        return '<script>alert("🗑️ ¡Gallo eliminado!"); window.location="/lista";</script>'
    except Exception as e:
        return f'<script>alert("❌ Error: {str(e)}"); window.location="/lista";</script>'

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
    opciones_gallos = ''.join([
        f'<option value="{g["id"]}">{g["placa_traba"]} ({g["raza"]}) - {g["nombre"] or "Sin nombre"}</option>'
        for g in gallos
    ])
    return f"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GFRD Cruce Inbreeding 2026</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;500;700&display=swap');
*{{margin:0; padding:0; box-sizing:border-box; font-family:'Poppins', sans-serif;}}
body{{background:#01030a; color:white; overflow-x:hidden; font-size:17px;}}
.container{{width:95%; max-width:650px; margin:40px auto; background:rgba(255,255,255,0.06); border-radius:20px; padding:25px; backdrop-filter:blur(10px); box-shadow:0 0 30px rgba(0,255,255,0.4); position:relative; z-index:2;}}
.header-modern{{display:flex; justify-content:space-between; align-items:center; margin-bottom:25px; flex-wrap:wrap; gap:15px;}}
.header-modern h1{{font-size:1.8rem; color:#00ffff; text-shadow:0 0 10px #00ffff;}}
.subtitle{{font-size:0.85rem; color:#bbb;}}
.logo{{width:80px; height:auto; filter:drop-shadow(0 0 6px #00ffff);}}
.form-group{{margin-bottom:20px;}}
label{{font-weight:600; color:#00e6ff; margin-bottom:6px; display:block; font-size:15px;}}
input, select, textarea{{width:100%; padding:12px; border-radius:10px; border:none; outline:none; background:rgba(255,255,255,0.08); color:white; transition:0.3s; font-size:16px;}}
input:focus, select:focus, textarea:focus{{background:rgba(0,255,255,0.15); transform:scale(1.01);}}
select option{{background-color:#0a0a0a; color:white;}}
button{{width:100%; padding:14px; border:none; border-radius:10px; background:linear-gradient(135deg,#00ffff,#008cff); color:#041428; font-size:1.1rem; font-weight:bold; cursor:pointer; transition:0.3s;}}
button:hover{{transform:translateY(-3px); box-shadow:0 6px 20px rgba(0,255,255,0.5);}}
canvas{{position:fixed; top:0; left:0; width:100%; height:100%; z-index:-1;}}
</style>
</head>
<body>
<canvas id="bg"></canvas>
<div class="container">
<div class="header-modern">
<div>
<h1>GFRD Cruce Inbreeding</h1>
<p class="subtitle">Sistema moderno • Año 2026</p>
</div>
<img src="/logo" alt="Logo GFRD" class="logo">
</div>
<form method="POST" action="/registrar-cruce" enctype="multipart/form-data">
<div class="form-group">
<label>Tipo de Cruce</label>
<select name="tipo" id="tipo_cruce" required onchange="actualizarCampos()">
<option value="">-- Selecciona --</option>
<option value="Padre-Hija">Padre - Hija</option>
<option value="Madre-Hijo">Madre - Hijo</option>
<option value="Hermano-Hermana">Hermano - Hermana</option>
<option value="Medio-Hermanos">Medio Hermanos</option>
<option value="Tío-Sobrino">Tío - Sobrino</option>
</select>
</div>
<div id="registro">
<div class="form-group">
<label>Gallo 1 (ej. Padre)</label>
<select name="gallo1" required class="btn-ghost">
<option value="">-- Elige un gallo --</option>
{opciones_gallos}
</select>
</div>
<div class="form-group">
<label>Gallo 2 (ej. Hija)</label>
<select name="gallo2" required class="btn-ghost">
<option value="">-- Elige un gallo --</option>
{opciones_gallos}
</select>
</div>
</div>
<div class="form-group">
<label>Generación (1-6)</label>
<select name="generacion" required>
<option value="">-- Elige --</option>
<option value="1">1 (25%)</option>
<option value="2">2 (37.5%)</option>
<option value="3">3 (50%)</option>
<option value="4">4 (62.5%)</option>
<option value="5">5 (75%)</option>
<option value="6">6 (87.5%)</option>
</select>
</div>
<div class="form-group">
<label>Notas (opcional)</label>
<textarea name="notas" class="btn-ghost" rows="3"></textarea>
</div>
<div class="form-group">
<label>Foto del cruce (opcional)</label>
<input type="file" name="foto" accept="image/*">
</div>
<button type="submit">✅ Registrar Cruce</button>
<div style="text-align:center; margin-top:20px;">
    <a href="/menu" class="btn-ghost" style="padding:10px 25px; display:inline-block;">🏠 Menú Principal</a>
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
function actualizarCampos(){{
  const tipo = document.getElementById("tipo_cruce").value;
  const registro = document.getElementById("registro");
  const opciones = `{opciones_gallos}`;
  if(tipo === "Padre-Hija"){{
    registro.innerHTML = `
      <div class='form-group'><label>Padre</label><select name='gallo1' required class='btn-ghost'>` + 
      `<option value=''>-- Elige un gallo --</option>` + opciones + `</select></div>
      <div class='form-group'><label>Hija</label><select name='gallo2' required class='btn-ghost'>` + 
      `<option value=''>-- Elige un gallo --</option>` + opciones + `</select></div>`;
  }} else if(tipo === "Madre-Hijo"){{
    registro.innerHTML = `
      <div class='form-group'><label>Madre</label><select name='gallo1' required class='btn-ghost'>` + 
      `<option value=''>-- Elige un gallo --</option>` + opciones + `</select></div>
      <div class='form-group'><label>Hijo</label><select name='gallo2' required class='btn-ghost'>` + 
      `<option value=''>-- Elige un gallo --</option>` + opciones + `</select></div>`;
  }} else if(tipo === "Hermano-Hermana"){{
    registro.innerHTML = `
      <div class='form-group'><label>Hermano 1</label><select name='gallo1' required class='btn-ghost'>` + 
      `<option value=''>-- Elige un gallo --</option>` + opciones + `</select></div>
      <div class='form-group'><label>Hermana</label><select name='gallo2' required class='btn-ghost'>` + 
      `<option value=''>-- Elige un gallo --</option>` + opciones + `</select></div>`;
  }} else {{
    registro.innerHTML = `
      <div class='form-group'><label>Gallo 1</label><select name='gallo1' required class='btn-ghost'>` + 
      `<option value=''>-- Elige un gallo --</option>` + opciones + `</select></div>
      <div class='form-group'><label>Gallo 2</label><select name='gallo2' required class='btn-ghost'>` + 
      `<option value=''>-- Elige un gallo --</option>` + opciones + `</select></div>`;
  }}
}}
</script>
</body>
</html>
"""

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
        return f"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GFRD Cruce Inbreeding 2026</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;500;700&display=swap');
*{{margin:0; padding:0; box-sizing:border-box; font-family:'Poppins', sans-serif;}}
body{{background:#01030a; color:white; overflow:hidden; font-size:17px;}}
.container{{width:90%; max-width:600px; margin:50px auto; background:rgba(255,255,255,0.05); border-radius:20px; padding:30px; backdrop-filter:blur(8px); box-shadow:0 0 25px rgba(0,255,255,0.3);}}
.resultado{{margin-top:25px; background:rgba(0,0,0,0.5); padding:20px; border-radius:12px; border:1px solid rgba(0,255,255,0.2); text-align:center; color:#00ffff;}}
button{{width:100%; padding:14px; border:none; border-radius:10px; background:linear-gradient(135deg,#00ffff,#008cff); color:#041428; font-size:1.1rem; font-weight:bold; cursor:pointer; transition:0.3s; margin-top:20px;}}
button:hover{{transform:translateY(-3px); box-shadow:0 4px 15px rgba(0,255,255,0.4);}}
canvas{{position:fixed; top:0; left:0; width:100%; height:100%; z-index:-1;}}
</style>
</head>
<body>
<canvas id="bg"></canvas>
<div class="container">
<div class="resultado"><h2>✅ ¡Cruce registrado!</h2><p>Tipo: {tipo}<br>Generación {generacion} ({porcentaje}%)</p></div>
<a href="/cruce-inbreeding"><button>🔄 Registrar otro cruce</button></a>
<a href="/menu"><button style="background:linear-gradient(135deg,#ff7a18,#f6c84c); color:#041428;">🏠 Menú</button></a>
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

@app.route('/backup', methods=['POST'])
@proteger_ruta
def crear_backup_manual():
    try:
        timestamp = datetime.now()
        fecha_legible = timestamp.strftime("%d de %B de %Y a las %H:%M")
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
        return jsonify({"mensaje": f"✅ Copia de seguridad creada el {fecha_legible}.", "archivo": zip_filename})
    except Exception as e:
        if 'temp_dir' in locals() and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return jsonify({"error": f"Error: {str(e)}"}), 500

@app.route('/download/<filename>')
@proteger_ruta
def descargar_backup(filename):
    backups_dir = Path("backups")
    ruta = backups_dir / filename
    if not ruta.is_file() or ruta.suffix != '.zip' or ".." in str(ruta):
        return "Archivo no válido", 400
    return send_file(ruta, as_attachment=True)

# =============== INICIAR ===============
if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
