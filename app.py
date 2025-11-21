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
from functools import wraps

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

def init_db():
    if not os.path.exists(DB):
        conn = sqlite3.connect(DB)
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE trabas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_traba TEXT UNIQUE NOT NULL,
            nombre_completo TEXT NOT NULL,
            correo TEXT UNIQUE NOT NULL
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
        if 'correo' not in cols_trabas:
            try:
                cursor.execute("ALTER TABLE trabas ADD COLUMN correo TEXT UNIQUE")
            except:
                pass
        conn.commit()
        conn.close()

def proteger_ruta(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'traba' not in session:
            return redirect(url_for('bienvenida'))
        return f(*args, **kwargs)
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

@app.route('/registrar-traba', methods=['POST'])
def registrar_traba():
    nombre = request.form.get('nombre', '').strip()
    apellido = request.form.get('apellido', '').strip()
    traba = request.form.get('traba', '').strip()
    correo = request.form.get('correo', '').strip().lower()
    if not nombre or not apellido or not traba or not correo:
        return '<script>alert("❌ Todos los campos son obligatorios."); window.location="/";</script>'
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id FROM trabas WHERE nombre_traba = ? OR correo = ?', (traba, correo))
        if cursor.fetchone():
            conn.close()
            return '<script>alert("❌ Nombre de traba o correo ya registrado."); window.location="/";</script>'
        nombre_completo = f"{nombre} {apellido}".strip()
        cursor.execute('''
            INSERT INTO trabas (nombre_traba, nombre_completo, correo)
            VALUES (?, ?, ?)
        ''', (traba, nombre_completo, correo))
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
        alert("✅ Código enviado a tu correo.\\
(Verifica la consola del servidor si estás en desarrollo)");
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
<input type="email" name="correo" required placeholder="Correo Electrónico">
<input type="date" name="fecha" value="{fecha_actual}">
<button type="submit">✅ Registrarme</button>
</form>
<p style="margin-top: 20px; font-size: 14px;">¿Ya tienes cuenta?</p>
<form method="POST" action="/solicitar-otp">
<input type="email" name="correo" required placeholder="Correo Electrónico">
<button style="background:linear-gradient(135deg,#2ecc71,#3498db);">🔐 Enviar código</button>
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

@proteger_ruta
@app.route('/menu')
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

# → El resto del archivo (formulario-gallo, registrar-gallo, cruce, lista, etc.) permanece **exactamente igual** a tu archivo original.
# Solo asegúrate de que **todas las rutas protegidas usen @proteger_ruta arriba de @app.route**.

@proteger_ruta
@app.route('/formulario-gallo')
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

# =============== REGISTRAR-GALLO Y DEMÁS RUTAS ===============
# → Copia y pega **el resto de tu código original** a partir de aquí,
# pero asegúrate de que **cada ruta protegida tenga este orden**:

@proteger_ruta
@app.route('/registrar-gallo', methods=['POST'])
def registrar_gallo():
    pass

@proteger_ruta
@app.route('/cruce-inbreeding')
def cruce_inbreeding():
    # ... (tu código original)
    pass

@proteger_ruta
@app.route('/lista')
def lista_gallos():
    # ... (tu código original)
    pass

# ... y así con todas las rutas protegidas

@app.route('/cerrar-sesion')
def cerrar_sesion():
    session.clear()
    return redirect(url_for('bienvenida'))

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

