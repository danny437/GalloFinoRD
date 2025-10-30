from flask import Flask, request, render_template_string, Response, session, redirect, url_for, send_from_directory, jsonify, send_file
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
import re

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or 'clave_secreta_para_gallos_2025_mejor_cambiala'
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

def encabezado_usuario():
    estilos_globales = '''
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
    if 'traba' in session:
        return estilos_globales + f'''
        <div style="text-align: center; background: rgba(44,62,80,0.7); color: white; padding: 15px; margin-bottom: 25px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.2);">
            <h1 style="margin: 0; font-size: 26px; font-weight: 600;">{session["traba"]}</h1>
            <p style="margin: 8px 0 0; opacity: 0.95; font-size: 16px;">
                Sesión activa | Fecha: {session.get("fecha", "—")}
            </p>
        </div>
        '''
    return estilos_globales

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
            email TEXT UNIQUE NOT NULL,
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
            individuo1_id INTEGER NOT NULL,
            individuo2_id INTEGER NOT NULL,
            generacion INTEGER NOT NULL,
            fecha TEXT,
            notas TEXT,
            foto TEXT,
            descendiente_id INTEGER,
            FOREIGN KEY(individuo1_id) REFERENCES individuos(id),
            FOREIGN KEY(individuo2_id) REFERENCES individuos(id),
            FOREIGN KEY(descendiente_id) REFERENCES individuos(id)
        )
        ''')
        conn.commit()
        conn.close()
    else:
        conn = sqlite3.connect(DB)
        cursor = conn.cursor()
        cols = [col[1] for col in cursor.execute("PRAGMA table_info(trabas)").fetchall()]
        if 'email' not in cols:
            try:
                cursor.execute("ALTER TABLE trabas ADD COLUMN email TEXT UNIQUE")
            except: pass
        cols_ind = [col[1] for col in cursor.execute("PRAGMA table_info(individuos)").fetchall()]
        for col in ['placa_regional', 'nombre', 'n_pelea', 'nacimiento', 'foto']:
            if col not in cols_ind:
                try:
                    cursor.execute(f"ALTER TABLE individuos ADD COLUMN {col} TEXT")
                except: pass
        try:
            cursor.execute('''CREATE TABLE progenitores (...)''')
        except: pass
        try:
            cursor.execute('''CREATE TABLE cruces (...)''')
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
                    <input type="text" name="traba" required placeholder="Nombre de la Traba">
                    <input type="text" name="nombre" required placeholder="Nombre del Usuario">
                    <input type="text" name="apellido" required placeholder="Apellido del Usuario">
                    <input type="email" name="email" required placeholder="Correo Electrónico">
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
    email = request.form.get('email', '').strip().lower()
    contraseña = request.form.get('contraseña', '').strip()
    if not (nombre and apellido and traba and email and contraseña):
        return '<script>alert("❌ Completa todos los campos."); window.location="/";</script>'
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return '<script>alert("❌ Correo inválido."); window.location="/";</script>'
    try:
        conn = sqlite3.connect(DB)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM trabas WHERE nombre_traba = ? OR email = ?', (traba, email))
        if cursor.fetchone():
            return '<script>alert("❌ La traba o el correo ya existen."); window.location="/";</script>'
        contraseña_hash = generate_password_hash(contraseña)
        cursor.execute('''
        INSERT INTO trabas (nombre_traba, nombre_completo, email, contraseña_hash)
        VALUES (?, ?, ?, ?)
        ''', (traba, f"{nombre} {apellido}", email, contraseña_hash))
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
            <a href="/cruce-inbreeding" class="btn">🔁 Cruce Avanzado</a>
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
            <label>N° Pelea:</label>
            <input type="text" name="{prefijo}_n_pelea" autocomplete="off" class="btn-ghost" style="background: rgba(0,0,0,0.3); color: white;" placeholder="Ej: 12">
            <label>Placa Regional (opcional):</label>
            <input type="text" name="{prefijo}_placa_regional" autocomplete="off" class="btn-ghost" style="background: rgba(0,0,0,0.3); color: white;">
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
        n_pelea = request.form.get(f'{prefijo}_n_pelea') or None
        placa_regional = request.form.get(f'{prefijo}_placa_regional') or None
        nombre = request.form.get(f'{prefijo}_nombre') or None
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
        return encabezado_usuario() + '<div class="container">✅ ¡Gallo registrado! <a href="/lista" class="btn">Ver lista</a></div>'
    except Exception as e:
        conn.close()
        return encabezado_usuario() + f'<div class="container">❌ Error: {str(e)} <a href="/formulario-gallo" class="btn">← Volver</a></div>'

# =============== LISTA DE GALLOS (CON N° PELEA) ===============
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
    html = encabezado_usuario() + '<div class="container">'
    html += '<h2 style="color: #c0392b; text-align: center; margin-bottom: 20px;">📋 Mis Gallos</h2>'
    html += '<table>'
    html += '''
        <thead>
            <tr>
                <th>Foto</th>
                <th>Placa</th>
                <th>N° Pelea</th>
                <th>Nombre</th>
                <th>Raza</th>
                <th>Madre</th>
                <th>Padre</th>
                <th>Acciones</th>
            </tr>
        </thead>
        <tbody>
    '''
    for g in gallos:
        nombre_mostrar = g['nombre'] or g['placa_traba']
        placa_mostrar = g['placa_traba']
        n_pelea_mostrar = g['n_pelea'] or "—"
        foto_html = f'<img src="/uploads/{g["foto"]}" width="60" style="border-radius:4px; display: block; margin: 0 auto;">' if g["foto"] else "—"
        madre_txt = g['madre_placa'] or "—"
        padre_txt = g['padre_placa'] or "—"
        html += f'''
        <tr>
            <td>{foto_html}</td>
            <td>{placa_mostrar}</td>
            <td>{n_pelea_mostrar}</td>
            <td>{nombre_mostrar}</td>
            <td>{g['raza']}</td>
            <td>{madre_txt}</td>
            <td>{padre_txt}</td>
            <td>
                <a href="/arbol/{g['id']}" class="btn-ghost">🌳 Árbol</a>
                <a href="/editar-gallo/{g['id']}" class="btn-ghost">✏️</a>
                <a href="/eliminar-gallo/{g['id']}" class="btn-ghost">🗑️</a>
            </td>
        </tr>
        '''
    html += '</tbody></table><div style="text-align:center; margin-top: 20px;"><a href="/menu" class="btn">← Menú</a></div></div>'
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>GalloFino - Mis Gallos</title>
    </head>
    <body>
        {html}
    </body>
    </html>
    '''

# =============== ÁRBOL GENEALÓGICO (CON N° PELEA) ===============
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
        return encabezado_usuario() + '<div class="container">❌ No encontrado. <a href="/lista" class="btn">← Volver</a></div>'
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
        n_pelea = ind['n_pelea'] or "—"
        placa_regional = ind['placa_regional'] or "—"
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
                    <p style="margin: 4px 0;"><strong>N° Pelea:</strong> {n_pelea}</p>
                    <p style="margin: 4px 0;"><strong>Placa Regional:</strong> {placa_regional}</p>
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
    </head>
    <body>
        {html_content}
    </body>
    </html>
    '''

# =============== RESTO DE RUTAS (BUSCAR, EXPORTAR, EDITAR, ETC.) ===============
# (El resto del código es igual al original. Por brevedad, se omite aquí, pero debes mantenerlo.)

# Ejemplo: ruta de edición (para que también edite N° Pelea)
@app.route('/editar-gallo/<int:id>')
@proteger_ruta
def editar_gallo(id):
    if not verificar_pertenencia(id, 'individuos'):
        return encabezado_usuario() + '<div class="container">❌ No tienes permiso. <a href="/lista" class="btn">← Volver</a></div>'
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM individuos WHERE id = ?', (id,))
    gallo = cursor.fetchone()
    conn.close()
    if not gallo:
        return encabezado_usuario() + '<div class="container">❌ Gallo no encontrado. <a href="/lista" class="btn">← Volver</a></div>'
    razas_html = ''.join([f'<option value="{r}" {"selected" if r == gallo["raza"] else ""}>{r}</option>' for r in RAZAS])
    apariencias = ['Crestarosa', 'Cocolo', 'Tuceperne', 'Pava', 'Moton']
    apariencias_html = ''.join([f'<label><input type="radio" name="apariencia" value="{a}" {"checked" if a == gallo["apariencia"] else ""}> {a}</label><br>' for a in apariencias])
    return encabezado_usuario() + f'''
    <div class="container">
        <h2 style="text-align: center; color: #3498db;">✏️ Editar Gallo</h2>
        <form method="POST" action="/actualizar-gallo/{id}" enctype="multipart/form-data" style="max-width: 700px; margin: 0 auto; padding: 20px; background: rgba(0,0,0,0.15); border-radius: 8px;">
            <label>Placa de Traba:</label>
            <input type="text" name="placa_traba" value="{gallo['placa_traba']}" required class="btn-ghost" style="background: rgba(0,0,0,0.3); color: white;">
            <label>N° Pelea:</label>
            <input type="text" name="n_pelea" value="{gallo['n_pelea'] or ''}" class="btn-ghost" style="background: rgba(0,0,0,0.3); color: white;" placeholder="Ej: 12">
            <label>Placa Regional (opcional):</label>
            <input type="text" name="placa_regional" value="{gallo['placa_regional'] or ''}" class="btn-ghost" style="background: rgba(0,0,0,0.3); color: white;">
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
            <button type="submit" class="btn" style="margin-top: 20px;">✅ Actualizar</button>
            <a href="/lista" class="btn" style="background: #c0392b; margin-top: 15px;">← Cancelar</a>
        </form>
    </div>
    '''

@app.route('/actualizar-gallo/<int:id>', methods=['POST'])
@proteger_ruta
def actualizar_gallo(id):
    if not verificar_pertenencia(id, 'individuos'):
        return encabezado_usuario() + '<div class="container">❌ No tienes permiso. <a href="/lista" class="btn">← Volver</a></div>'
    traba = session['traba']
    placa_traba = request.form['placa_traba']
    n_pelea = request.form.get('n_pelea') or None
    placa_regional = request.form.get('placa_regional', None) or None
    nombre = request.form.get('nombre', None) or None
    raza = request.form['raza']
    color = request.form['color']
    apariencia = request.form['apariencia']
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
        conn.commit()
        conn.close()
        return encabezado_usuario() + '<div class="container">✅ ¡Gallo actualizado! <a href="/lista" class="btn">Ver lista</a></div>'
    except Exception as e:
        return encabezado_usuario() + f'<div class="container">❌ Error: {str(e)} <a href="/editar-gallo/{id}" class="btn">← Volver</a></div>'

# =============== RUTAS RESTANTES (buscar, exportar, backup, cruces, eliminar) ===============
# (Mantén exactamente como en tu archivo original Pasted_Text_1761681999852.txt)

# Por ejemplo, la ruta de exportar:
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

# =============== INICIAR ===============
if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
