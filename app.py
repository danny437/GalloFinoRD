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
app.secret_key = 'clave_secreta_para_gallos_2025_mejor_cambiala'
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

def estilos_globales():
    return '''
    <style>
    /* ===== ESTILOS GLOBALES - GalloFino v2 ===== */
    body {
        font-family: 'Segoe UI', Arial, sans-serif;
        background: #041428;
        color: #e6f3ff;
        margin: 0;
        padding: 0;
    }
    .container {
        max-width: 1200px;
        margin: 0 auto;
        padding: 20px;
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
    .btn:hover, button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 0 #c4600d;
    }
    .btn:active, button:active {
        transform: translateY(1px);
        box-shadow: 0 2px 0 #c4600d;
    }
    .btn-ghost, .ghost {
        background: transparent;
        border: 1px solid rgba(255,255,255,0.06);
        color: #cfe6ff;
        padding: 8px 16px;
        border-radius: 8px;
        cursor: pointer;
        transition: background 0.2s, transform 0.1s;
    }
    .btn-ghost:hover {
        background: rgba(255,255,255,0.04);
        transform: scale(1.02);
    }
    input, select, textarea {
        width: 100%;
        padding: 10px;
        margin: 6px 0 12px;
        border-radius: 8px;
        border: 1px solid rgba(255,255,255,0.04);
        background: rgba(0,0,0,0.2);
        color: white;
        box-sizing: border-box;
    }
    input:focus, select:focus, textarea:focus {
        outline: none;
        border-color: #f6c84c;
        box-shadow: 0 0 0 2px rgba(246, 200, 76, 0.3);
    }
    table {
        width: 100%;
        border-collapse: collapse;
        margin: 20px 0;
        background: rgba(0,0,0,0.15);
        border-radius: 10px;
        overflow: hidden;
    }
    th, td {
        padding: 12px;
        text-align: left;
        border-bottom: 1px solid rgba(255,255,255,0.05);
    }
    th {
        background: rgba(0,0,0,0.25);
        color: #f6c84c;
    }
    tr:hover {
        background: rgba(255,255,255,0.03);
    }
    a {
        color: #3498db;
        text-decoration: none;
        transition: color 0.2s;
    }
    a:hover {
        color: #f6c84c;
        text-decoration: underline;
    }
    .card {
        background: linear-gradient(180deg, rgba(255,255,255,0.01), rgba(0,0,0,0.06));
        border-radius: 12px;
        padding: 16px;
        margin: 12px 0;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    </style>
    '''

def encabezado_usuario():
    if 'traba' in session:
        return f'''
        <div style="text-align: center; background: rgba(44,62,80,0.7); color: white; padding: 15px; margin-bottom: 25px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.2);">
            <h1 style="margin: 0; font-size: 26px; font-weight: 600;">{session["traba"]}</h1>
            <p style="margin: 8px 0 0; opacity: 0.95; font-size: 16px;">
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
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute(f'SELECT id FROM {tabla} WHERE id = ? AND traba = ?', (id_registro, traba))
    existe = cursor.fetchone()
    conn.close()
    return existe is not None

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
            FOREIGN KEY(individuo1_id) REFERENCES individuos(id),
            FOREIGN KEY(individuo2_id) REFERENCES individuos(id)
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
        try:
            cursor.execute('''CREATE TABLE cruces (
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
                FOREIGN KEY(individuo1_id) REFERENCES individuos(id),
                FOREIGN KEY(individuo2_id) REFERENCES individuos(id)
            )''')
        except: pass
        conn.commit()
        conn.close()

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# =============== INICIO DE SESIÓN ===============
@app.route('/')
def bienvenida():
    if 'traba' in session:
        return redirect(url_for('menu_principal'))
    fecha_actual = datetime.now().strftime('%Y-%m-%d')
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>GalloFino - Inicio</title>
        <style>
            body {{
                margin: 0; padding: 0; min-height: 100vh;
                background: url("/static/fondo.png") center/cover no-repeat fixed;
                font-family: 'Segoe UI', sans-serif;
                display: flex; justify-content: center; align-items: center; color: white;
            }}
            .welcome-card {{
                background: rgba(0,0,0,0.65); backdrop-filter: blur(4px);
                padding: 40px; border-radius: 16px; text-align: center;
                max-width: 500px; box-shadow: 0 10px 30px rgba(0,0,0,0.4);
            }}
            .form-container input {{
                width: 100%; padding: 12px; margin: 8px 0 15px;
                border-radius: 8px; border: 1px solid rgba(255,255,255,0.2);
                background: rgba(0,0,0,0.3); color: white; font-size: 16px;
            }}
            .submit-btn {{
                background: #3498db; color: white; border: none; padding: 14px;
                font-size: 18px; font-weight: bold; border-radius: 8px;
                width: 100%; cursor: pointer;
            }}
        </style>
    </head>
    <body>
        <div class="welcome-card">
            <h1>🐓 GalloFino</h1>
            <p>Sistema Profesional de Gestión Genética</p>
            <div class="form-container">
                <form method="POST" action="/registrar-traba">
                    <input type="text" name="nombre" required placeholder="Nombre">
                    <input type="text" name="apellido" required placeholder="Apellido">
                    <input type="text" name="traba" required placeholder="Nombre de la Traba">
                    <input type="password" name="contraseña" required placeholder="Contraseña">
                    <input type="date" name="fecha" value="{fecha_actual}">
                    <button type="submit" class="submit-btn">✅ Registrarme</button>
                </form>
                <p style="margin-top: 20px; font-size: 14px;">¿Ya tienes cuenta?</p>
                <form method="POST" action="/iniciar-sesion">
                    <input type="text" name="traba" required placeholder="Nombre de la Traba">
                    <input type="password" name="contraseña" required placeholder="Contraseña">
                    <button type="submit" style="background:#2ecc71;" class="submit-btn">🔑 Iniciar Sesión</button>
                </form>
            </div>
        </div>
    </body>
    </html>
    '''

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

# =============== MENÚ PRINCIPAL ===============
@app.route('/menu')
@proteger_ruta
def menu_principal():
    html_content = encabezado_usuario() + '''
    <div class="container" style="text-align: center;">
        <h2>Menú Principal</h2>
        <div style="display: flex; flex-wrap: wrap; gap: 15px; justify-content: center; margin: 20px 0;">
            <a href="/formulario-gallo" class="btn">🐓 Registrar Gallo</a>
            <a href="/cruce-inbreeding" class="btn">🔁 Cruce Inbreeding</a>
            <a href="/lista" class="btn">📋 Mis Gallos</a>
            <a href="/buscar" class="btn">🔍 Buscar</a>
            <a href="/exportar" class="btn">📤 Exportar</a>
            <button onclick="crearBackup()" class="btn">💾 Respaldo</button>
        </div>
        <a href="/cerrar-sesion" class="btn" style="background: #7f8c8d;">Cerrar Sesión</a>
        <div id="mensaje-backup" style="margin-top: 15px; min-height: 24px; color: #2c3e50; font-weight: bold;"></div>
    </div>
    <script>
    function crearBackup() {
        fetch("/backup", { method: "POST" })
            .then(r => r.json())
            .then(d => {
                if (d.error) {
                    document.getElementById("mensaje-backup").innerHTML = `<span style="color:#e74c3c;">❌ ${d.error}</span>`;
                } else {
                    document.getElementById("mensaje-backup").innerHTML = `<span style="color:#27ae60;">${d.mensaje}</span>`;
                    window.location.href = "/download/" + d.archivo;
                }
            });
    }
    </script>
    '''
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>GalloFino - Menú</title>
        {estilos_globales()}
    </head>
    <body>
        {html_content}
    </body>
    </html>
    '''

# =============== REGISTRO DE GALLO ===============
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
        <div style="flex: 1; min-width: 300px; background: {color_fondo}; padding: 15px; border-radius: 10px;">
            <h3 style="color: {color_titulo}; text-align: center;">{titulo}</h3>
            <label>Placa de Traba:</label>
            <input type="text" name="{prefijo}_placa_traba" autocomplete="off" {req_attr} class="btn-ghost" style="background: rgba(0,0,0,0.3); color: white;">
            <label>Placa Regional (opcional):</label>
            <input type="text" name="{prefijo}_placa_regional" autocomplete="off" class="btn-ghost" style="background: rgba(0,0,0,0.3); color: white;">
            <label>N° Pelea:</label>
            <input type="text" name="{prefijo}_n_pelea" autocomplete="off" class="btn-ghost" style="background: rgba(0,0,0,0.3); color: white;">
            <label>Nombre del ejemplar:</label>
            <input type="text" name="{prefijo}_nombre" autocomplete="off" class="btn-ghost" style="background: rgba(0,0,0,0.3); color: white;">
            <label>Raza:</label>
            <select name="{prefijo}_raza" {req_attr} class="btn-ghost" style="background: rgba(0,0,0,0.3); color: white;">{razas_html}</select>
            <label>Color:</label>
            <input type="text" name="{prefijo}_color" autocomplete="off" {req_attr} class="btn-ghost" style="background: rgba(0,0,0,0.3); color: white;">
            <label>Apariencia:</label>
            <div style="margin:5px 0;">{ap_html}</div>
            <label>Foto (opcional):</label>
            <input type="file" name="{prefijo}_foto" accept="image/*" class="btn-ghost">
        </div>
        '''
    html = encabezado_usuario() + f'''
    <div class="container">
        <h2 style="text-align: center; color: #3498db;">🐓 Registrar Gallo (Opcional: Progenitores y Abuelos)</h2>
        <form method="POST" action="/registrar-gallo" enctype="multipart/form-data" style="max-width: 1200px; margin: 0 auto; padding: 20px; background: rgba(0,0,0,0.15); border-radius: 12px;">
            <div style="display: flex; gap: 15px; flex-wrap: wrap;">
                {columna("A. Gallo (Obligatorio)", "gallo", "rgba(232,244,252,0.2)", "#2980b9", required=True)}
                {columna("B. Madre (Opcional)", "madre", "rgba(253,239,242,0.2)", "#c0392b", required=False)}
                {columna("C. Padre (Opcional)", "padre", "rgba(235,245,235,0.2)", "#27ae60", required=False)}
            </div>
            <div style="display: flex; gap: 15px; flex-wrap: wrap; margin-top: 20px;">
                {columna("D. Abuelo Materno (Opcional)", "ab_materno", "rgba(253,242,233,0.2)", "#e67e22", required=False)}
                {columna("E. Abuelo Paterno (Opcional)", "ab_paterno", "rgba(232,248,245,0.2)", "#1abc9c", required=False)}
            </div>
            <div style="text-align: center; margin-top: 20px;">
                <button type="submit" class="btn">✅ Registrar Gallo</button>
                <a href="/menu" class="btn" style="background: #3498db; margin-left: 15px;">← Menú</a>
            </div>
        </form>
    </div>
    '''
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>GalloFino - Registrar Gallo</title>
        {estilos_globales()}
    </head>
    <body>
        {html}
    </body>
    </html>
    '''

@app.route('/registrar-gallo', methods=['POST'])
@proteger_ruta
def registrar_gallo():
    traba = session['traba']
    conn = sqlite3.connect(DB)
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
                fname = secure_filename(f"{prefijo[0]}_{placa}_{file.filename}")
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
        ab_materno_id = guardar_individuo('ab_materno') if madre_id else None
        ab_paterno_id = guardar_individuo('ab_paterno') if padre_id else None
        if madre_id is not None or padre_id is not None:
            cursor.execute('''
            INSERT INTO progenitores (individuo_id, madre_id, padre_id)
            VALUES (?, ?, ?)
            ''', (gallo_id, madre_id, padre_id))
        if madre_id and ab_materno_id:
            cursor.execute('''
            INSERT INTO progenitores (individuo_id, padre_id)
            VALUES (?, ?)
            ''', (madre_id, ab_materno_id))
        if padre_id and ab_paterno_id:
            cursor.execute('''
            INSERT INTO progenitores (individuo_id, padre_id)
            VALUES (?, ?)
            ''', (padre_id, ab_paterno_id))
        conn.commit()
        conn.close()
        return f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>GalloFino - Éxito</title>
            {estilos_globales()}
        </head>
        <body>
            {encabezado_usuario()}
            <div class="container">✅ ¡Gallo registrado! <a href="/lista" class="btn">Ver lista</a></div>
        </body>
        </html>
        '''
    except Exception as e:
        conn.close()
        return f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>GalloFino - Error</title>
            {estilos_globales()}
        </head>
        <body>
            {encabezado_usuario()}
            <div class="container">❌ Error: {str(e)} <a href="/formulario-gallo" class="btn">← Volver</a></div>
        </body>
        </html>
        '''

# =============== LISTA DE GALLOS ===============
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
    html_content = encabezado_usuario() + '<div class="container">'
    html_content += '<h2 style="color: #c0392b; text-align: center; margin-bottom: 20px;">📋 Mis Gallos</h2>'
    html_content += '<table>'
    html_content += '''
        <thead>
            <tr>
                <th>Foto</th>
                <th>Placa Traba</th>
                <th>Placa Regional</th>
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
    '''
    for g in gallos:
        nombre_mostrar = g['nombre'] or g['placa_traba']
        placa_traba = g['placa_traba'] or "—"
        placa_regional = g['placa_regional'] or "—"
        n_pelea = g['n_pelea'] or "—"
        foto_html = f'<img src="/uploads/{g["foto"]}" width="60" style="border-radius:4px; display: block; margin: 0 auto;">' if g["foto"] else "—"
        madre_txt = g['madre_placa'] or "—"
        padre_txt = g['padre_placa'] or "—"
        html_content += f'''
        <tr>
            <td>{foto_html}</td>
            <td>{placa_traba}</td>
            <td>{placa_regional}</td>
            <td>{nombre_mostrar}</td>
            <td>{g['raza']}</td>
            <td>{g['apariencia']}</td>
            <td>{n_pelea}</td>
            <td>{madre_txt}</td>
            <td>{padre_txt}</td>
            <td>
                <a href="/arbol/{g['id']}" class="btn-ghost">🌳 Árbol</a>
                <a href="/editar-gallo/{g['id']}" class="btn-ghost">✏️</a>
                <a href="/eliminar-gallo/{g['id']}" class="btn-ghost">🗑️</a>
            </td>
        </tr>
        '''
    html_content += '</tbody></table><div style="text-align:center; margin-top: 20px;"><a href="/menu" class="btn">← Menú</a></div></div>'
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>GalloFino - Mis Gallos</title>
        {estilos_globales()}
    </head>
    <body>
        {html_content}
    </body>
    </html>
    '''

# =============== ÁRBOL GENEALÓGICO ===============
@app.route('/arbol/<int:id>')
@proteger_ruta
def arbol_genealogico(id):
    traba = session['traba']
    def get_individuo(ind_id):
        if not ind_id:
            return None
        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM individuos WHERE id = ? AND traba = ?', (ind_id, traba))
        row = cursor.fetchone()
        conn.close()
        return row
    def get_progenitores(ind_id):
        if not ind_id:
            return None, None
        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT madre_id, padre_id FROM progenitores WHERE individuo_id = ?', (ind_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return row['madre_id'], row['padre_id']
        return None, None
    gallo = get_individuo(id)
    if not gallo:
        return f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>GalloFino - Error</title>
            {estilos_globales()}
        </head>
        <body>
            {encabezado_usuario()}
            <div class="container">❌ No encontrado. <a href="/lista" class="btn">← Volver</a></div>
        </body>
        </html>
        '''
    madre_id, padre_id = get_progenitores(id)
    madre = get_individuo(madre_id)
    padre = get_individuo(padre_id)
    abuelos = []
    if madre_id:
        ab_madre_id, ab_padre_id = get_progenitores(madre_id)
        abuelos.append(get_individuo(ab_madre_id))
        abuelos.append(get_individuo(ab_padre_id))
    else:
        abuelos.extend([None, None])
    if padre_id:
        ab_madre_id, ab_padre_id = get_progenitores(padre_id)
        abuelos.append(get_individuo(ab_madre_id))
        abuelos.append(get_individuo(ab_padre_id))
    else:
        abuelos.extend([None, None])
    def detalle_card(ind, title, color):
        if not ind:
            return f'''
            <div class="card" style="background: #f8f9fa; color: #6c757d; text-align: center;">
                <strong>{title}</strong><br><em>— Sin datos —</em>
            </div>
            '''
        nombre = ind['nombre'] or "—"
        placa_traba = ind['placa_traba'] or "—"
        placa_regional = ind['placa_regional'] or "—"
        n_pelea = ind['n_pelea'] or "—"
        raza = ind['raza'] or "—"
        color_val = ind['color'] or "—"
        apariencia = ind['apariencia'] or "—"
        foto_url = f"/uploads/{ind['foto']}" if ind['foto'] else None
        foto_html = f'<img src="{foto_url}" style="width: 80px; height: 80px; object-fit: cover; border-radius: 8px; margin-right: 15px;">' if foto_url else '<div style="width: 80px; height: 80px; background: #e9ecef; border-radius: 8px; margin-right: 15px;"></div>'
        return f'''
        <div class="card" style="background: {color}; color: white;">
            <h3 style="margin: 0 0 12px; text-align: center;">{title}</h3>
            <div style="display: flex; align-items: flex-start;">
                {foto_html}
                <div style="flex: 1;">
                    <p style="margin: 4px 0;"><strong>Nombre:</strong> {nombre}</p>
                    <p style="margin: 4px 0;"><strong>Placa Traba:</strong> {placa_traba}</p>
                    <p style="margin: 4px 0;"><strong>Placa Regional:</strong> {placa_regional}</p>
                    <p style="margin: 4px 0;"><strong>N° Pelea:</strong> {n_pelea}</p>
                    <p style="margin: 4px 0;"><strong>Raza:</strong> {raza}</p>
                    <p style="margin: 4px 0;"><strong>Color:</strong> {color_val}</p>
                    <p style="margin: 4px 0;"><strong>Apariencia:</strong> {apariencia}</p>
                </div>
            </div>
        </div>
        '''
    html_content = encabezado_usuario() + f'''
    <div class="container">
        <div style="max-width: 900px; margin: 0 auto; background: rgba(0,0,0,0.15); padding: 25px; border-radius: 12px;">
            <h2 style="text-align: center; color: #2c3e50;">🌳 Árbol Genealógico</h2>
            {detalle_card(gallo, '🐓 Gallo', '#3498db')}
            <h3 style="text-align: center; margin: 25px 0 15px; color: #2c3e50;"> Padres </h3>
            <div style="display: flex; flex-wrap: wrap; gap: 15px; justify-content: space-between;">
                <div style="flex: 1; min-width: 250px;">{detalle_card(madre, '👩 Madre', '#e74c3c')}</div>
                <div style="flex: 1; min-width: 250px;">{detalle_card(padre, '🐓 Padre', '#27ae60')}</div>
            </div>
            <h3 style="text-align: center; margin: 25px 0 15px; color: #2c3e50;"> Abuelos </h3>
            <div style="display: flex; flex-wrap: wrap; gap: 15px; justify-content: space-between;">
                <div style="flex: 1; min-width: 200px;">{detalle_card(abuelos[0], '👵 Abuela Materna', '#e67e22')}</div>
                <div style="flex: 1; min-width: 200px;">{detalle_card(abuelos[1], '👴 Abuelo Materno', '#e67e22')}</div>
                <div style="flex: 1; min-width: 200px;">{detalle_card(abuelos[2], '👵 Abuela Paterna', '#1abc9c')}</div>
                <div style="flex: 1; min-width: 200px;">{detalle_card(abuelos[3], '👴 Abuelo Paterno', '#1abc9c')}</div>
            </div>
            <div style="text-align: center; margin-top: 25px;">
                <a href="/lista" class="btn" style="background: #3498db;">← Volver a la lista</a>
            </div>
        </div>
    </div>
    '''
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>GalloFino - Árbol</title>
        {estilos_globales()}
    </head>
    <body>
        {html_content}
    </body>
    </html>
    '''

# =============== BÚSQUEDA ===============
@app.route('/buscar', methods=['GET', 'POST'])
@proteger_ruta
def buscar():
    if request.method == 'POST':
        termino = request.form.get('termino', '').strip()
        if not termino:
            return f'''
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>GalloFino - Búsqueda</title>
                {estilos_globales()}
            </head>
            <body>
                {encabezado_usuario()}
                <div class="container">❌ Ingresa un término. <a href="/buscar">← Volver</a></div>
            </body>
            </html>
            '''
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
        if resultados:
            primer_resultado = resultados[0]
            if primer_resultado['tipo'] == 'gallo':
                nombre_mostrar = primer_resultado['nombre'] or primer_resultado['placa_traba']
                foto_html = f'<div style="text-align:center; margin:10px;"><img src="/uploads/{primer_resultado["foto"]}" width="150" style="border-radius:8px;"></div>' if primer_resultado["foto"] else ""
                padre_placa = primer_resultado['padre_placa'] or "—"
                madre_placa = primer_resultado['madre_placa'] or "—"
                return f'''
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>GalloFino - Resultado</title>
                    {estilos_globales()}
                </head>
                <body>
                    {encabezado_usuario()}
                    <div class="container">
                        <div style="max-width: 700px; margin: 0 auto; background: rgba(0,0,0,0.2); padding: 20px; border-radius: 8px;">
                            <h2 style="color: #27ae60; text-align: center;">✅ Gallo Encontrado</h2>
                            {foto_html}
                            <p><strong>Nombre:</strong> {nombre_mostrar}</p>
                            <p><strong>Placa Traba:</strong> {primer_resultado['placa_traba']}</p>
                            <p><strong>Placa Regional:</strong> {primer_resultado['placa_regional'] or '—'}</p>
                            <p><strong>Raza:</strong> {primer_resultado['raza']}</p>
                            <p><strong>Color:</strong> {primer_resultado['color']}</p>
                            <p><strong>Apariencia:</strong> {primer_resultado['apariencia']}</p>
                            <h3 style="color: #3498db;">👩 Madre</h3>
                            <p><strong>Placa Traba:</strong> {madre_placa}</p>
                            <h3 style="color: #3498db;">🐓 Padre</h3>
                            <p><strong>Placa Traba:</strong> {padre_placa}</p>
                            <button onclick="mostrarArbolSimplificado('{primer_resultado['placa_traba']}', '{padre_placa}', '{madre_placa}')" 
                                    class="btn" style="margin: 15px 0 10px;">
                                🌳 Árbol Simplificado
                            </button>
                            <br>
                            <a href="/menu" class="btn" style="background: #3498db; margin-top:15px;">🏠 Menú Principal</a>
                        </div>
                    </div>
                    <script>
                    function mostrarArbolSimplificado(cria, padre, madre) {{
                        const modal = document.createElement('div');
                        modal.id = 'modal-arbol';
                        modal.innerHTML = `
                            <div class="card" style="max-width:500px; margin:20px auto;">
                                <h3 style="text-align:center;">🌳 Árbol del Gallo</h3>
                                <p><strong>Padre:</strong> ${{padre}}</p>
                                <p><strong>Madre:</strong> ${{madre}}</p>
                                <p><strong>Cría:</strong> ${{cria}}</p>
                                <div style="text-align:center; margin-top:15px;">
                                    <button onclick="document.getElementById('modal-arbol').remove()" class="btn" style="background:#c0392b;">
                                        Cerrar
                                    </button>
                                </div>
                            </div>
                        `;
                        document.body.appendChild(modal);
                    }}
                    </script>
                </body>
                </html>
                '''
            else:
                return f'''
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>GalloFino - Cruce</title>
                    {estilos_globales()}
                </head>
                <body>
                    {encabezado_usuario()}
                    <div class="container">
                        <div style="max-width: 700px; margin: 0 auto; background: rgba(0,0,0,0.2); padding: 20px; border-radius: 8px;">
                            <h2 style="color: #27ae60; text-align: center;">✅ Cruce Encontrado</h2>
                            <p><strong>Tipo:</strong> {primer_resultado['tipo']}</p>
                            <p><strong>Generación:</strong> {primer_resultado['generacion']} ({primer_resultado['porcentaje']}%)</p>
                            <p><strong>Gallo 1:</strong> {primer_resultado['placa1']} - {primer_resultado['nombre1'] or '—'}</p>
                            <p><strong>Gallo 2:</strong> {primer_resultado['placa2']} - {primer_resultado['nombre2'] or '—'}</p>
                            <p><strong>Fecha:</strong> {primer_resultado['fecha'] or '—'}</p>
                            <p><strong>Notas:</strong> {primer_resultado['notas'] or '—'}</p>
                            <a href="/menu" class="btn" style="background: #3498db; margin-top:15px;">🏠 Menú Principal</a>
                        </div>
                    </div>
                </body>
                </html>
                '''
        else:
            return f'''
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>GalloFino - No encontrado</title>
                {estilos_globales()}
            </head>
            <body>
                {encabezado_usuario()}
                <div class="container" style="text-align:center; max-width:600px; margin:50px auto;">
                    <h3>😔 Lo sentimos</h3>
                    <p>No se encontró ningún gallo ni cruce con los términos: <strong>{termino}</strong>.</p>
                    <a href="/menu" class="btn" style="background:#e74c3c;">← Volver al Menú</a>
                </div>
            </body>
            </html>
            '''
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>GalloFino - Buscar</title>
        {estilos_globales()}
    </head>
    <body>
        {encabezado_usuario()}
        <div class="container">
            <div style="max-width: 600px; margin: 40px auto; background: rgba(0,0,0,0.2); padding: 25px; border-radius: 10px;">
                <h2 style="text-align: center; color: #f39c12;">🔍 Buscar Gallo o Cruce</h2>
                <form method="POST">
                    <label>Término (placa, nombre, color o tipo de cruce):</label>
                    <input type="text" name="termino" required class="btn-ghost" style="background: rgba(0,0,0,0.3); color: white;">
                    <div style="text-align:center; margin-top:20px;">
                        <button type="submit" class="btn">🔎 Buscar</button>
                        <br><br>
                        <a href="/menu" class="btn" style="background: #3498db;">← Menú</a>
                    </div>
                </form>
            </div>
        </div>
    </body>
    </html>
    '''

# =============== EXPORTAR ===============
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

# =============== EDITAR / ELIMINAR ===============
@app.route('/editar-gallo/<int:id>')
@proteger_ruta
def editar_gallo(id):
    if not verificar_pertenencia(id, 'individuos'):
        return f'''
        <!DOCTYPE html>
        <html>
        <head>{estilos_globales()}</head>
        <body>{encabezado_usuario()}<div class="container">❌ No tienes permiso. <a href="/lista" class="btn">← Volver</a></div></body>
        </html>
        '''
    traba = session['traba']
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM individuos WHERE id = ?', (id,))
    gallo = cursor.fetchone()
    if not gallo:
        conn.close()
        return f'''
        <!DOCTYPE html>
        <html>
        <head>{estilos_globales()}</head>
        <body>{encabezado_usuario()}<div class="container">❌ Gallo no encontrado. <a href="/lista" class="btn">← Volver</a></div></body>
        </html>
        '''
    # Obtener madre y padre actuales
    cursor.execute('SELECT madre_id, padre_id FROM progenitores WHERE individuo_id = ?', (id,))
    progen = cursor.fetchone()
    madre_actual = progen['madre_id'] if progen else None
    padre_actual = progen['padre_id'] if progen else None
    # Obtener lista de todos los gallos de la traba (excluyendo al actual)
    cursor.execute('SELECT id, placa_traba, nombre, raza FROM individuos WHERE traba = ? AND id != ? ORDER BY placa_traba', (traba, id))
    todos_gallos = cursor.fetchall()
    conn.close()
    razas_html = ''.join([f'<option value="{r}" {"selected" if r == gallo["raza"] else ""}>{r}</option>' for r in RAZAS])
    apariencias = ['Crestarosa', 'Cocolo', 'Tuceperne', 'Pava', 'Moton']
    apariencias_html = ''.join([f'<label><input type="radio" name="apariencia" value="{a}" {"checked" if a == gallo["apariencia"] else ""}> {a}</label><br>' for a in apariencias])
    # Opciones para madre y padre
    opciones_gallos = ''.join([
        f'<option value="{g["id"]}" {"selected" if g["id"] == madre_actual else ""}>{g["placa_traba"]} ({g["raza"]}) - {g["nombre"] or "Sin nombre"}</option>'
        for g in todos_gallos
    ])
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>GalloFino - Editar</title>
        {estilos_globales()}
    </head>
    <body>
        {encabezado_usuario()}
        <div class="container">
            <h2 style="text-align: center; color: #3498db;">✏️ Editar Gallo</h2>
            <form method="POST" action="/actualizar-gallo/{id}" enctype="multipart/form-data" style="max-width: 700px; margin: 0 auto; padding: 20px; background: rgba(0,0,0,0.15); border-radius: 8px;">
                <label>Placa de Traba:</label>
                <input type="text" name="placa_traba" value="{gallo['placa_traba']}" required class="btn-ghost" style="background: rgba(0,0,0,0.3); color: white;">
                <label>Placa Regional (opcional):</label>
                <input type="text" name="placa_regional" value="{gallo['placa_regional'] or ''}" class="btn-ghost" style="background: rgba(0,0,0,0.3); color: white;">
                <label>N° Pelea:</label>
                <input type="text" name="n_pelea" value="{gallo['n_pelea'] or ''}" class="btn-ghost" style="background: rgba(0,0,0,0.3); color: white;" placeholder="Ej: 12">
                <label>Nombre del ejemplar:</label>
                <input type="text" name="nombre" value="{gallo['nombre'] or ''}" class="btn-ghost" style="background: rgba(0,0,0,0.3); color: white;">
                <label>Raza:</label>
                <select name="raza" required class="btn-ghost" style="background: rgba(0,0,0,0.3); color: white;">{razas_html}</select>
                <label>Color:</label>
                <input type="text" name="color" value="{gallo['color']}" required class="btn-ghost" style="background: rgba(0,0,0,0.3); color: white;">
                <label>Apariencia:</label>
                <div style="margin:5px 0;">{apariencias_html}</div>
                <label>Foto actual:</label>
                <div style="margin:10px 0;">{f'<img src="/uploads/{gallo["foto"]}" width="100" style="border-radius:4px;">' if gallo["foto"] else "—"}</div>
                <label>Nueva foto (opcional):</label>
                <input type="file" name="foto" accept="image/*" class="btn-ghost">
                
                <!-- Nuevos campos: Madre y Padre -->
                <label style="margin-top: 15px;">Madre (opcional):</label>
                <select name="madre_id" class="btn-ghost" style="background: rgba(0,0,0,0.3); color: white;">
                    <option value="">-- Ninguna --</option>
                    {opciones_gallos}
                </select>
                <label style="margin-top: 15px;">Padre (opcional):</label>
                <select name="padre_id" class="btn-ghost" style="background: rgba(0,0,0,0.3); color: white;">
                    <option value="">-- Ninguno --</option>
                    {opciones_gallos}
                </select>
                
                <button type="submit" class="btn" style="margin-top: 25px;">✅ Actualizar</button>
                <a href="/lista" class="btn" style="background: #c0392b; margin-top: 15px;">← Cancelar</a>
            </form>
        </div>
    </body>
    </html>
    '''

@app.route('/actualizar-gallo/<int:id>', methods=['POST'])
@proteger_ruta
def actualizar_gallo(id):
    if not verificar_pertenencia(id, 'individuos'):
        return f'''
        <!DOCTYPE html>
        <html>
        <head>{estilos_globales()}</head>
        <body>{encabezado_usuario()}<div class="container">❌ No tienes permiso. <a href="/lista" class="btn">← Volver</a></div></body>
        </html>
        '''
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
        # Actualizar datos del gallo
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
        # Actualizar progenitores
        cursor.execute('SELECT 1 FROM progenitores WHERE individuo_id = ?', (id,))
        if cursor.fetchone():
            # Ya existe → actualizar
            cursor.execute('''
                UPDATE progenitores SET madre_id = ?, padre_id = ? WHERE individuo_id = ?
            ''', (madre_id, padre_id, id))
        else:
            # No existe → insertar
            cursor.execute('''
                INSERT INTO progenitores (individuo_id, madre_id, padre_id)
                VALUES (?, ?, ?)
            ''', (id, madre_id, padre_id))
        conn.commit()
        conn.close()
        return f'''
        <!DOCTYPE html>
        <html>
        <head>{estilos_globales()}</head>
        <body>{encabezado_usuario()}<div class="container">✅ ¡Gallo actualizado! <a href="/lista" class="btn">Ver lista</a></div></body>
        </html>
        '''
    except Exception as e:
        return f'''
        <!DOCTYPE html>
        <html>
        <head>{estilos_globales()}</head>
        <body>{encabezado_usuario()}<div class="container">❌ Error: {str(e)} <a href="/editar-gallo/{id}" class="btn">← Volver</a></div></body>
        </html>
        '''
@app.route('/eliminar-gallo/<int:id>')
@proteger_ruta
def eliminar_gallo(id):
    if not verificar_pertenencia(id, 'individuos'):
        return f'''
        <!DOCTYPE html>
        <html>
        <head>{estilos_globales()}</head>
        <body>{encabezado_usuario()}<div class="container">❌ No tienes permiso. <a href="/lista" class="btn">← Volver</a></div></body>
        </html>
        '''
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute('SELECT placa_traba FROM individuos WHERE id = ? AND traba = ?', (id, session['traba']))
    gallo = cursor.fetchone()
    conn.close()
    if not gallo:
        return f'''
        <!DOCTYPE html>
        <html>
        <head>{estilos_globales()}</head>
        <body>{encabezado_usuario()}<div class="container">❌ Gallo no encontrado. <a href="/lista" class="btn">← Volver</a></div></body>
        </html>
        '''
    return f'''
    <!DOCTYPE html>
    <html>
    <head>{estilos_globales()}</head>
    <body>
        {encabezado_usuario()}
        <div class="container">
            <div style="max-width: 500px; margin: 50px auto; padding: 30px; background: rgba(255,245,245,0.1); border-radius: 10px; text-align: center; border: 2px solid #e74c3c;">
                <h3 style="color: #c0392b;">⚠️ Confirmar Eliminación</h3>
                <p>¿Eliminar el gallo <strong>{gallo[0]}</strong>?</p>
                <p style="color: #e74c3c; font-size: 14px;">Esta acción no se puede deshacer.</p>
                <div style="margin-top: 20px;">
                    <a href="/confirmar-eliminar-gallo/{id}" class="btn" style="background: #c0392b;">✅ Sí, eliminar</a>
                    <a href="/lista" class="btn" style="background: #7f8c8d;">❌ Cancelar</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/confirmar-eliminar-gallo/<int:id>')
@proteger_ruta
def confirmar_eliminar_gallo(id):
    if not verificar_pertenencia(id, 'individuos'):
        return f'''
        <!DOCTYPE html>
        <html>
        <head>{estilos_globales()}</head>
        <body>{encabezado_usuario()}<div class="container">❌ No tienes permiso. <a href="/lista" class="btn">← Volver</a></div></body>
        </html>
        '''
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
        return f'''
        <!DOCTYPE html>
        <html>
        <head>{estilos_globales()}</head>
        <body>{encabezado_usuario()}<div class="container">🗑️ ¡Gallo eliminado! <a href="/lista" class="btn">Ver lista</a></div></body>
        </html>
        '''
    except Exception as e:
        return f'''
        <!DOCTYPE html>
        <html>
        <head>{estilos_globales()}</head>
        <body>{encabezado_usuario()}<div class="container">❌ Error: {str(e)} <a href="/lista" class="btn">← Volver</a></div></body>
        </html>
        '''

# =============== BACKUP ===============
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

# =============== CRUCE INBREEDING ===============
<p class="subtitle">Sistema moderno 2026 • GalloFino</p>
@app.route('/cruce-inbreeding')
@proteger_ruta
def cruce_inbreeding():
    traba = session['traba']
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT id, placa_traba, placa_regional, nombre, raza FROM individuos WHERE traba = ? ORDER BY placa_traba', (traba,))
    gallos = cursor.fetchall()
    opciones_gallos = ''.join([
        f'<option value="{g["id"]}">{g["placa_traba"]} ({g["raza"]}) - {g["nombre"] or "Sin nombre"}</option>'
        for g in gallos
    ])
    conn.close()
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Cruce Inbreeding - GalloFino</title>
        {estilos_globales()}
        <style>
            .form-container {{
                max-width: 800px;
                margin: 20px auto;
                padding: 20px;
                background: rgba(0,0,0,0.15);
                border-radius: 12px;
            }}
            .form-group {{
                margin: 15px 0;
            }}
            label {{
                display: block;
                margin-bottom: 5px;
                font-weight: bold;
                color: #f6c84c;
            }}
            select, input, textarea {{
                width: 100%;
                padding: 10px;
                margin: 5px 0;
                border-radius: 8px;
                border: 1px solid rgba(255,255,255,0.04);
                background: rgba(0,0,0,0.2);
                color: white;
                box-sizing: border-box;
            }}
        </style>
    </head>
    <body>
        {encabezado_usuario()}
        <div class="container">
            <h2 style="text-align:center; color:#ff7a18;">🔁 Registro de Cruce Inbreeding</h2>
            <div class="form-container">
                <form method="POST" action="/registrar-cruce">
                    <div class="form-group">
                        <label>Tipo de Cruce:</label>
                        <select name="tipo" required class="btn-ghost">
                            <option value="">-- Selecciona --</option>
                            <option value="Padre-Hija">Padre - Hija</option>
                            <option value="Madre-Hijo">Madre - Hijo</option>
                            <option value="Hermano-Hermana">Hermano - Hermana</option>
                            <option value="Medio-Hermanos">Medio Hermanos</option>
                            <option value="Tio-Sobrino">Tío - Sobrino</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Gallo 1 (ej. Padre):</label>
                        <select name="gallo1" required class="btn-ghost">
                            <option value="">-- Elige un gallo --</option>
                            {opciones_gallos}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Gallo 2 (ej. Hija):</label>
                        <select name="gallo2" required class="btn-ghost">
                            <option value="">-- Elige un gallo --</option>
                            {opciones_gallos}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Generación (1-6):</label>
                        <select name="generacion" required class="btn-ghost">
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
                        <label>Notas (opcional):</label>
                        <textarea name="notas" class="btn-ghost" rows="3"></textarea>
                    </div>
                    <button type="submit" class="btn" style="margin-top:15px;">✅ Registrar Cruce</button>
                </form>
            </div>
            <a href="/menu" class="btn" style="background:#7f8c8d; display:block; text-align:center; margin-top:20px;">
                🏠 Menú Principal
            </a>
        </div>
    </body>
    </html>
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
        porcentajes = {1: 25, 2: 37.5, 3: 50, 4: 62.5, 5: 75, 6: 87.5}
        porcentaje = porcentajes.get(generacion, 25)
        traba = session['traba']
        conn = sqlite3.connect(DB)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO cruces (traba, tipo, individuo1_id, individuo2_id, generacion, porcentaje, fecha, notas)
            VALUES (?, ?, ?, ?, ?, ?, date('now'), ?)
        ''', (traba, tipo, gallo1_id, gallo2_id, generacion, porcentaje, notas))
        conn.commit()
        conn.close()
        mensaje = "✅ Cruce registrado exitosamente."
    except Exception as e:
        mensaje = f"❌ Error: {str(e)}"
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Cruce Inbreeding - GalloFino</title>
        {estilos_globales()}
        <style>
            .mensaje {{
                text-align: center;
                padding: 20px;
                margin: 20px auto;
                max-width: 600px;
                border-radius: 12px;
                background: rgba(0,0,0,0.15);
            }}
            .mensaje.ok {{ color: #27ae60; }}
            .mensaje.error {{ color: #e74c3c; }}
        </style>
    </head>
    <body>
        {encabezado_usuario()}
        <div class="container">
            <div class="mensaje {'ok' if '✅' in mensaje else 'error'}">
                <h3>{mensaje}</h3>
                <a href="/cruce-inbreeding" class="btn">Regresar al formulario</a>
            </div>
        </div>
    </body>
    </html>
    '''

# =============== INICIAR ===============
if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)


