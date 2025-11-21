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

# ✅ DECORADOR CORREGIDO (usa @wraps)
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

# ========== RUTAS (orden corregido: @proteger_ruta primero) ==========
@app.route('/')
def bienvenida():
    if 'traba' in session:
        return redirect(url_for('menu_principal'))
    fecha_actual = datetime.now().strftime('%Y-%m-%d')
    return f"""..."""  # (tu HTML de inicio, sin cambios)

@app.route('/registrar-traba', methods=['POST'])
def registrar_traba():
    # ... (sin cambios)

@app.route('/solicitar-otp', methods=['POST'])
def solicitar_otp():
    # ... (sin cambios)

@app.route('/verificar-otp')
def pagina_verificar_otp():
    # ... (sin cambios)

@app.route('/verificar-otp', methods=['POST'])
def verificar_otp():
    # ... (sin cambios)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route("/logo")
def logo():
    return send_from_directory(os.getcwd(), "OIP.png")

# ✅ TODAS LAS RUTAS PROTEGIDAS: @proteger_ruta arriba de @app.route
@proteger_ruta
@app.route('/menu')
def menu_principal():
    traba = session['traba']
    return f"""..."""  # (tu HTML del menú)

@proteger_ruta
@app.route('/formulario-gallo')
def formulario_gallo():
    # ... (tu código completo)

@proteger_ruta
@app.route('/registrar-gallo', methods=['POST'])
def registrar_gallo():
    # ... (tu código completo, sin cambios)

# → Repite el mismo patrón para las demás rutas protegidas:
@proteger_ruta
@app.route('/cruce-inbreeding')
def cruce_inbreeding():
    # ...

@proteger_ruta
@app.route('/registrar-cruce', methods=['POST'])
def registrar_cruce():
    # ...

@proteger_ruta
@app.route('/buscar', methods=['GET', 'POST'])
def buscar():
    # ...

@proteger_ruta
@app.route('/lista')
def lista_gallos():
    # ...

@proteger_ruta
@app.route('/exportar')
def exportar():
    # ...

@proteger_ruta
@app.route('/editar-gallo/<int:id>')
def editar_gallo(id):
    # ...

@proteger_ruta
@app.route('/actualizar-gallo/<int:id>', methods=['POST'])
def actualizar_gallo(id):
    # ...

@proteger_ruta
@app.route('/eliminar-gallo/<int:id>')
def eliminar_gallo(id):
    # ...

@proteger_ruta
@app.route('/confirmar-eliminar-gallo/<int:id>')
def confirmar_eliminar_gallo(id):
    # ...

@proteger_ruta
@app.route('/arbol/<int:id>')
def arbol_genealogico(id):
    # ...

@proteger_ruta
@app.route('/backup', methods=['POST'])
def crear_backup_manual():
    # ...

@proteger_ruta
@app.route('/download/<filename>')
def descargar_backup(filename):
    # ...

@app.route('/cerrar-sesion')
def cerrar_sesion():
    session.clear()
    return redirect(url_for('bienvenida'))

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
