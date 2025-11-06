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

# === FUNCIONES AUXILIARES ===
def get_db_connection():
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")  # ✅ ACTIVADO
    conn.row_factory = sqlite3.Row
    return conn

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def estilos_globales():
    return '''
    <style>
    /* ===== ESTILOS PARA DISPOSITIVOS MÓVILES - Mejor contraste ===== */
    body {
        font-family: 'Segoe UI', Arial, sans-serif;
        background: #041428;
        color: #f0f8ff; /* ✅ Más claro para mejor legibilidad */
        margin: 0;
        padding: 0;
    }
    .container {
        max-width: 1200px;
        margin: 0 auto;
        padding: 15px;
    }
    h1, h2, h3, h4 {
        color: #f6c84c;
        margin-bottom: 16px;
    }
    h2 { color: #ff7a18; }
    .btn, button, .btn-link {
        background: linear-gradient(90deg, #f6c84c, #ff7a18);
        border: none;
        color: #041428;
        font-weight: bold;
        padding: 10px 20px;
        border-radius: 8px;
        cursor: pointer;
        font-size: 16px;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        box-shadow: 0 4px 0 #c4600d;
        display: inline-block;
        text-decoration: none;
        text-align: center;
        margin: 6px 4px;
    }
    .card {
        background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(0,0,0,0.08));
        border-radius: 12px;
        padding: 16px;
        margin: 12px 0;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    input, select, textarea {
        width: 100%;
        padding: 12px; /* ✅ Más grande para móviles */
        margin: 6px 0 12px;
        border-radius: 8px;
        border: 1px solid rgba(255,255,255,0.1);
        background: rgba(0,0,0,0.3);
        color: white;
        box-sizing: border-box;
        font-size: 16px; /* ✅ Evita zoom en iOS */
    }
    table {
        width: 100%;
        border-collapse: collapse;
        margin: 20px 0;
        background: rgba(0,0,0,0.2);
        border-radius: 10px;
        overflow: hidden;
    }
    th, td {
        padding: 14px; /* ✅ Más espacio */
        text-align: left;
        border-bottom: 1px solid rgba(255,255,255,0.08);
    }
    @media (max-width: 600px) {
        .container { padding: 10px; }
        input, select, textarea { padding: 14px; }
        .btn { padding: 12px; font-size: 16px; }
    }
    </style>
    '''

def encabezado_usuario():
    if 'traba' in session:
        return f'''
        <div style="text-align: center; background: rgba(44,62,80,0.85); color: white; padding: 15px; margin-bottom: 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.2);">
            <h1 style="margin: 0; font-size: 24px; font-weight: 600;">{session["traba"]}</h1>
            <p style="margin: 8px 0 0; opacity: 0.95; font-size: 15px;">
                Sesión activa | Fecha: {session.get("fecha", "—")}
            </p>
        </div>
        '''
    return ''

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
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f'SELECT id FROM {tabla} WHERE id = ? AND traba = ?', (id_registro, traba))
    existe = cursor.fetchone()
    conn.close()
    return existe is not None

# === SERVIR LOGO ===
@app.route("/logo")
def logo():
    return send_from_directory(os.getcwd(), "OIP.png")

# === INICIALIZACIÓN DE BASE DE DATOS ===
def init_db():
    if not os.path.exists(DB):
        conn = get_db_connection()
        cursor = conn.cursor()
        # ... (igual que tu script original, omitido por brevedad)
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
        # ... (igual que tu script, omitido)
        pass

# === (TODAS TUS RUTAS EXISTENTES: bienvenida, registro, menú, gallos, etc.) ===
# [Se mantienen exactamente igual, omitidas para no alargar el código]

# === RUTAS NUEVAS Y ACTUALIZADAS DE CRUCE INBREEDING ===

@app.route('/cruce-inbreeding')
@proteger_ruta
def cruce_inbreeding():
    traba = session['traba']
    conn = get_db_connection()
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
body{{background:#01030a; color:white; overflow-x:hidden;}}
.container{{width:95%; max-width:650px; margin:40px auto; background:rgba(255,255,255,0.06); border-radius:20px; padding:25px; backdrop-filter:blur(10px); box-shadow:0 0 30px rgba(0,255,255,0.4); position:relative; z-index:2;}}
header{{display:flex; justify-content:space-between; align-items:center; margin-bottom:25px; flex-wrap:wrap; gap:15px;}}
h1{{font-size:1.8rem; color:#00ffff; text-shadow:0 0 10px #00ffff;}}
.subtitle{{font-size:0.85rem; color:#bbb;}}
.logo{{width:80px; height:auto; filter:drop-shadow(0 0 6px #00ffff);}}

.form-group{{margin-bottom:20px;}}
label{{font-weight:600; color:#00e6ff; margin-bottom:6px; display:block; font-size:15px;}}
input, select, textarea{{width:100%; padding:12px; border-radius:10px; border:none; outline:none; background:rgba(255,255,255,0.08); color:white; transition:0.3s; font-size:16px;}}
input:focus, select:focus, textarea:focus{{background:rgba(0,255,255,0.15); transform:scale(1.01);}}
select option{{background-color:#0a0a0a; color:white;}}

button{{width:100%; padding:14px; border:none; border-radius:10px; background:linear-gradient(135deg,#00ffff,#008cff); color:#041428; font-size:1.1rem; font-weight:bold; cursor:pointer; transition:0.3s;}}
button:hover{{transform:translateY(-3px); box-shadow:0 6px 20px rgba(0,255,255,0.5);}}

.resultado{{margin-top:25px; background:rgba(0,0,0,0.4); padding:15px; border-radius:12px; border:1px solid rgba(0,255,255,0.3); text-align:center; color:#00ffff;}}
footer{{text-align:center; color:#888; font-size:0.8rem; margin-top:25px;}}

canvas{{position:fixed; top:0; left:0; width:100%; height:100%; z-index:-1;}}
</style>
</head>
<body>
<canvas id="bg"></canvas>

<div class="container">
<header>
<div>
<h1>GFRD Cruce Inbreeding</h1>
<p class="subtitle">Sistema moderno • Año 2026</p>
</div>
<img src="/logo" alt="Logo GFRD" class="logo">
</header>

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
<select name="generacion" required onchange="actualizarPorcentaje()">
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
</form>

<footer>© 2026 GFRD — Todos los derechos reservados</footer>
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

function actualizarPorcentaje(){{
  // El porcentaje se calcula en backend, pero aquí se puede mostrar una previsualización
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

        # ✅ Validar que ambos gallos pertenezcan a la traba
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM individuos WHERE id IN (?, ?) AND traba = ?', (gallo1_id, gallo2_id, traba))
        if len(cursor.fetchall()) != 2:
            raise ValueError("Uno o ambos gallos no pertenecen a tu traba.")

        # ✅ Calcular porcentaje automáticamente
        porcentajes = {1: 25, 2: 37.5, 3: 50, 4: 62.5, 5: 75, 6: 87.5}
        porcentaje = porcentajes.get(generacion, 25)

        # ✅ Subir foto si existe
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
        cruce_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # ✅ Mensaje con tipo + porcentaje
        mensaje = f"✅ ¡Cruce registrado!<br><strong>Tipo:</strong> {tipo}<br><strong>Generación {generacion}</strong> ({porcentaje}%)"
        estilo_mensaje = "color:#00ffff; text-shadow:0 0 10px #00ffff;"
        btn_style = "background:linear-gradient(135deg,#00ffff,#008cff); color:#041428;"

    except Exception as e:
        mensaje = f"❌ Error: {str(e)}"
        estilo_mensaje = "color:#ff6b6b;"
        btn_style = "background:#c0392b; color:white;"

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
body{{background:#01030a; color:white; overflow:hidden;}}
.container{{width:90%; max-width:600px; margin:50px auto; background:rgba(255,255,255,0.05); border-radius:20px; padding:30px; backdrop-filter:blur(8px); box-shadow:0 0 25px rgba(0,255,255,0.3);}}
.resultado{{margin-top:25px; background:rgba(0,0,0,0.5); padding:20px; border-radius:12px; border:1px solid rgba(0,255,255,0.2); text-align:center; {estilo_mensaje}}}
button{{width:100%; padding:14px; border:none; border-radius:10px; {btn_style}; font-size:1.1rem; font-weight:bold; cursor:pointer; transition:0.3s; margin-top:20px;}}
button:hover{{transform:translateY(-3px); box-shadow:0 4px 15px rgba(0,255,255,0.4);}}
canvas{{position:fixed; top:0; left:0; width:100%; height:100%; z-index:-1;}}
</style>
</head>
<body>
<canvas id="bg"></canvas>
<div class="container">
<div class="resultado"><h2>Resultado</h2><p>{mensaje}</p></div>
<a href="/cruce-inbreeding"><button>🔄 Registrar otro cruce</button></a>
<a href="/lista-cruces"><button style="background:linear-gradient(135deg,#ff7a18,#f6c84c); color:#041428;">📋 Ver mis cruces</button></a>
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

# === LISTA DE CRUCES ===
@app.route('/lista-cruces')
@proteger_ruta
def lista_cruces():
    traba = session['traba']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT c.id, c.tipo, c.generacion, c.porcentaje, c.fecha, c.notas, c.foto,
               i1.placa_traba as placa1, i1.nombre as nombre1,
               i2.placa_traba as placa2, i2.nombre as nombre2
        FROM cruces c
        JOIN individuos i1 ON c.individuo1_id = i1.id
        JOIN individuos i2 ON c.individuo2_id = i2.id
        WHERE c.traba = ?
        ORDER BY c.id DESC
    ''', (traba,))
    cruces = cursor.fetchall()
    conn.close()

    cruces_html = ""
    for c in cruces:
        foto_html = f'<img src="/uploads/{c["foto"]}" width="60" style="border-radius:4px;">' if c["foto"] else "—"
        cruces_html += f'''
        <tr>
            <td>{foto_html}</td>
            <td>{c["tipo"]}</td>
            <td>G{c["generacion"]} ({c["porcentaje"]}%)</td>
            <td>{c["placa1"]} - {c["placa2"]}</td>
            <td>{c["fecha"] or "—"}</td>
            <td>
                <a href="/arbol-cruce/{c['id']}" class="btn-ghost">🌳</a>
                <a href="/editar-foto-cruce/{c['id']}" class="btn-ghost">🖼️</a>
            </td>
        </tr>
        '''

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>GalloFino - Mis Cruces</title>
        {estilos_globales()}
    </head>
    <body>
        {encabezado_usuario()}
        <div class="container">
            <h2 style="color: #ff7a18; text-align: center;">📋 Mis Cruces Inbreeding</h2>
            <table>
                <thead>
                    <tr>
                        <th>Foto</th>
                        <th>Tipo</th>
                        <th>Generación</th>
                        <th>Gallos</th>
                        <th>Fecha</th>
                        <th>Acciones</th>
                    </tr>
                </thead>
                <tbody>
                    {cruces_html}
                </tbody>
            </table>
            <div style="text-align:center; margin-top:20px;">
                <a href="/cruce-inbreeding" class="btn">🔁 Registrar nuevo cruce</a>
                <a href="/menu" class="btn" style="background:#7f8c8d;">🏠 Menú</a>
            </div>
        </div>
    </body>
    </html>
    """

# === ÁRBOL DEL CRUCE ===
@app.route('/arbol-cruce/<int:id>')
@proteger_ruta
def arbol_cruce(id):
    if not verificar_pertenencia(id, 'cruces'):
        return '<script>alert("❌ No tienes permiso."); window.location="/lista-cruces";</script>'
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT c.tipo, c.generacion, c.porcentaje, c.foto,
               i1.placa_traba as placa1, i1.nombre as nombre1, i1.foto as foto1,
               i2.placa_traba as placa2, i2.nombre as nombre2, i2.foto as foto2
        FROM cruces c
        JOIN individuos i1 ON c.individuo1_id = i1.id
        JOIN individuos i2 ON c.individuo2_id = i2.id
        WHERE c.id = ?
    ''', (id,))
    cruce = cursor.fetchone()
    conn.close()

    if not cruce:
        return '<script>alert("❌ Cruce no encontrado."); window.location="/lista-cruces";</script>'

    foto1 = f'<img src="/uploads/{cruce["foto1"]}" width="80" style="border-radius:8px;">' if cruce["foto1"] else "—"
    foto2 = f'<img src="/uploads/{cruce["foto2"]}" width="80" style="border-radius:8px;">' if cruce["foto2"] else "—"

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>GalloFino - Árbol Cruce</title>
        {estilos_globales()}
        <style>
            .arbol-card {{
                background: rgba(0,0,0,0.2);
                border-radius: 12px;
                padding: 20px;
                margin: 15px 0;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        {encabezado_usuario()}
        <div class="container">
            <h2 style="text-align:center; color:#00ffff;">🌳 Árbol del Cruce #{id}</h2>
            <div class="arbol-card">
                <h3 style="color:#f6c84c;">{cruce['tipo']} • Gen {cruce['generacion']} ({cruce['porcentaje']}%)</h3>
                <div style="display:flex; justify-content:space-around; flex-wrap:wrap; gap:20px; margin:20px 0;">
                    <div>{foto1}<br><strong>{cruce['placa1']}</strong><br>{cruce['nombre1'] or '—'}</div>
                    <div><strong>+</strong></div>
                    <div>{foto2}<br><strong>{cruce['placa2']}</strong><br>{cruce['nombre2'] or '—'}</div>
                </div>
                {f'<div><img src="/uploads/{cruce["foto"]}" width="120" style="border-radius:8px; margin-top:10px;"></div>' if cruce["foto"] else ""}
            </div>
            <div style="text-align:center;">
                <a href="/lista-cruces" class="btn">← Volver</a>
            </div>
        </div>
    </body>
    </html>
    """

# === EDITAR SOLO LA FOTO DEL CRUCE ===
@app.route('/editar-foto-cruce/<int:id>')
@proteger_ruta
def editar_foto_cruce(id):
    if not verificar_pertenencia(id, 'cruces'):
        return '<script>alert("❌ No tienes permiso."); window.location="/lista-cruces";</script>'
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>GalloFino - Editar Foto</title>
        {estilos_globales()}
    </head>
    <body>
        {encabezado_usuario()}
        <div class="container">
            <h2 style="text-align:center;">🖼️ Editar Foto del Cruce #{id}</h2>
            <form method="POST" action="/actualizar-foto-cruce/{id}" enctype="multipart/form-data" style="max-width:500px; margin:0 auto;">
                <label>Nueva foto:</label>
                <input type="file" name="foto" accept="image/*" required>
                <button type="submit" class="btn" style="margin-top:15px;">✅ Actualizar Foto</button>
                <a href="/lista-cruces" class="btn" style="background:#7f8c8d; margin-top:10px;">Cancelar</a>
            </form>
        </div>
    </body>
    </html>
    """

@app.route('/actualizar-foto-cruce/<int:id>', methods=['POST'])
@proteger_ruta
def actualizar_foto_cruce(id):
    if not verificar_pertenencia(id, 'cruces'):
        return jsonify({"error": "No tienes permiso"}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Eliminar foto anterior si existe
        cursor.execute('SELECT foto FROM cruces WHERE id = ? AND traba = ?', (id, session['traba']))
        row = cursor.fetchone()
        if row and row['foto']:
            old_path = os.path.join(app.config['UPLOAD_FOLDER'], row['foto'])
            if os.path.exists(old_path):
                os.remove(old_path)

        # Guardar nueva foto
        if 'foto' not in request.files:
            raise ValueError("No se envió archivo")
        file = request.files['foto']
        if file.filename == '':
            raise ValueError("Archivo vacío")
        if not allowed_file(file.filename):
            raise ValueError("Formato no permitido")
        fname = secure_filename(f"cruce_{id}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))

        cursor.execute('UPDATE cruces SET foto = ? WHERE id = ? AND traba = ?', (fname, id, session['traba']))
        conn.commit()
        conn.close()
        return f"""
        <!DOCTYPE html>
        <html>
        <head>{estilos_globales()}</head>
        <body>
            {encabezado_usuario()}
            <div class="container" style="text-align:center;">
                <h3>✅ Foto actualizada</h3>
                <a href="/lista-cruces" class="btn">Ver cruces</a>
            </div>
        </body>
        </html>
        """
    except Exception as e:
        return f"""
        <!DOCTYPE html>
        <html>
        <head>{estilos_globales()}</head>
        <body>
            {encabezado_usuario()}
            <div class="container" style="text-align:center;">
                <h3>❌ Error: {str(e)}</h3>
                <a href="/editar-foto-cruce/{id}" class="btn">← Reintentar</a>
            </div>
        </body>
        </html>
        """

# === BÚSQUEDA DE CRUCES POR GENERACIÓN ===
@app.route('/buscar-cruce', methods=['GET', 'POST'])
@proteger_ruta
def buscar_cruce():
    if request.method == 'POST':
        generacion = request.form.get('generacion')
        if not generacion:
            return redirect(url_for('buscar_cruce'))
        traba = session['traba']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.id, c.tipo, c.generacion, c.porcentaje, c.fecha,
                   i1.placa_traba as placa1, i2.placa_traba as placa2
            FROM cruces c
            JOIN individuos i1 ON c.individuo1_id = i1.id
            JOIN individuos i2 ON c.individuo2_id = i2.id
            WHERE c.traba = ? AND c.generacion = ?
            ORDER BY c.id DESC
        ''', (traba, int(generacion)))
        resultados = cursor.fetchall()
        conn.close()
        return f"""
        <!DOCTYPE html>
        <html>
        <head>{estilos_globales()}</head>
        <body>
            {encabezado_usuario()}
            <div class="container">
                <h2 style="text-align:center;">🔍 Resultados - Generación {generacion}</h2>
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Tipo</th>
                            <th>Porcentaje</th>
                            <th>Gallos</th>
                            <th>Acciones</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(f'<tr><td>{r["id"]}</td><td>{r["tipo"]}</td><td>{r["porcentaje"]}%</td><td>{r["placa1"]} - {r["placa2"]}</td><td><a href="/arbol-cruce/{r["id"]}" class="btn-ghost">🌳</a></td></tr>' for r in resultados)}
                    </tbody>
                </table>
                <div style="text-align:center; margin-top:20px;">
                    <a href="/buscar-cruce" class="btn">← Nueva búsqueda</a>
                </div>
            </div>
        </body>
        </html>
        """
    return f"""
    <!DOCTYPE html>
    <html>
    <head>{estilos_globales()}</head>
    <body>
        {encabezado_usuario()}
        <div class="container" style="max-width:500px; margin:40px auto;">
            <h2 style="text-align:center;">🔍 Buscar Cruce por Generación</h2>
            <form method="POST">
                <label>Generación:</label>
                <select name="generacion" required class="btn-ghost">
                    <option value="">-- Selecciona --</option>
                    <option value="1">1 (25%)</option>
                    <option value="2">2 (37.5%)</option>
                    <option value="3">3 (50%)</option>
                    <option value="4">4 (62.5%)</option>
                    <option value="5">5 (75%)</option>
                    <option value="6">6 (87.5%)</option>
                </select>
                <button type="submit" class="btn" style="margin-top:15px;">Buscar</button>
            </form>
        </div>
    </body>
    </html>
    """

# === MENÚ PRINCIPAL ACTUALIZADO ===
# (En tu ruta `/menu`, añade enlaces a `/lista-cruces` y `/buscar-cruce`)

# === RESTO DEL SCRIPT (igual que el original) ===
# [Tus rutas de gallos, backup, etc., se mantienen]

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
