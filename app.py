from flask import Flask, request, session, redirect, url_for, send_from_directory, render_template, jsonify
import sqlite3
import os
import secrets
from datetime import datetime
from werkzeug.utils import secure_filename
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

# === Rutas públicas ===

@app.route('/')
def bienvenida():
    if 'traba' in session:
        return redirect(url_for('menu_principal'))
    return render_template('inicio.html', fecha_actual=datetime.now().strftime('%Y-%m-%d'))

@app.route('/registrar-traba', methods=['POST'])
def registrar_traba():
    nombre = request.form.get('nombre', '').strip()
    apellido = request.form.get('apellido', '').strip()
    traba = request.form.get('traba', '').strip()
    correo = request.form.get('correo', '').strip().lower()
    if not nombre or not apellido or not traba or not correo:
        return render_template('error.html', mensaje="Todos los campos son obligatorios.")
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id FROM trabas WHERE nombre_traba = ? OR correo = ?', (traba, correo))
        if cursor.fetchone():
            conn.close()
            return render_template('error.html', mensaje="Nombre de traba o correo ya registrado.")
        nombre_completo = f"{nombre} {apellido}".strip()
        cursor.execute('INSERT INTO trabas (nombre_traba, nombre_completo, correo) VALUES (?, ?, ?)', (traba, nombre_completo, correo))
        conn.commit()
        conn.close()
        session['traba'] = traba
        return redirect(url_for('menu_principal'))
    except Exception as e:
        conn.close()
        return render_template('error.html', mensaje=str(e))

@app.route('/solicitar-otp', methods=['POST'])
def solicitar_otp():
    correo = request.form.get('correo', '').strip().lower()
    if not correo:
        return render_template('error.html', mensaje="Ingresa tu correo.")
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute('SELECT nombre_traba FROM trabas WHERE correo = ?', (correo,))
    traba_row = cursor.fetchone()
    conn.close()
    if not traba_row:
        return render_template('error.html', mensaje="Correo no registrado.")
    traba = traba_row[0]
    codigo = str(secrets.randbelow(1000000)).zfill(6)
    OTP_TEMP[correo] = {'codigo': codigo, 'traba': traba}
    print(f"\n📧 [OTP para {correo}]: {codigo}\n")
    return render_template('verificar_otp.html', correo=correo, mensaje="Código enviado (ver consola).")

@app.route('/verificar-otp', methods=['GET', 'POST'])
def verificar_otp():
    if request.method == 'GET':
        correo = request.args.get('correo', '').strip()
        if not correo:
            return redirect(url_for('bienvenida'))
        return render_template('verificar_otp.html', correo=correo)
    else:
        correo = request.form.get('correo', '').strip()
        codigo = request.form.get('codigo', '').strip()
        if not correo or not codigo:
            return redirect(url_for('bienvenida'))
        if correo in OTP_TEMP and OTP_TEMP[correo]['codigo'] == codigo:
            session['traba'] = OTP_TEMP[correo]['traba']
            del OTP_TEMP[correo]
            return redirect(url_for('menu_principal'))
        else:
            return render_template('error.html', mensaje="Código incorrecto o expirado.")

# === Rutas protegidas ===

@app.route('/menu')
@proteger_ruta
def menu_principal():
    return render_template('menu.html', traba=session['traba'])

@app.route('/formulario-gallo')
@proteger_ruta
def formulario_gallo():
    return render_template('registrar_gallo.html', traba=session['traba'], razas=RAZAS)

@app.route('/registrar-gallo', methods=['POST'])
@proteger_ruta
def registrar_gallo():
    traba = session['traba']
    try:
        conn = sqlite3.connect(DB)
        cursor = conn.cursor()

        def guardar_individuo(prefijo, es_gallo=False):
            placa = request.form.get(f'{prefijo}_placa_traba')
            if not placa:
                if es_gallo:
                    raise ValueError("La placa del gallo es obligatoria.")
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
                INSERT INTO progenitores (individuo_id, madre_id)
                VALUES (?, ?)
            ''', (madre_id, ab_materno_id))
        if padre_id and ab_paterno_id:
            cursor.execute('''
                INSERT INTO progenitores (individuo_id, padre_id)
                VALUES (?, ?)
            ''', (padre_id, ab_paterno_id))

        conn.commit()
        conn.close()
        return render_template('registro_exitoso.html', traba=traba)

    except Exception as e:
        try:
            conn.close()
        except:
            pass
        return render_template('error.html', mensaje=str(e))

@app.route('/buscar', methods=['GET', 'POST'])
@proteger_ruta
def buscar_gallo():
    traba = session['traba']
    if request.method == 'POST':
        termino = request.form.get('termino', '').strip()
        if not termino:
            return render_template('error.html', mensaje="Término de búsqueda vacío.")
        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, placa_traba, placa_regional, nombre, raza, color, apariencia, n_pelea, foto
            FROM individuos
            WHERE traba = ?
              AND (placa_traba LIKE ? OR nombre LIKE ? OR color LIKE ? OR raza LIKE ?)
            ORDER BY nombre, placa_traba
        ''', (traba, f'%{termino}%', f'%{termino}%', f'%{termino}%', f'%{termino}%'))
        resultados = cursor.fetchall()
        conn.close()
        return render_template('resultados_busqueda.html', resultados=resultados, termino=termino)
    else:
        return render_template('buscar.html')

@app.route('/lista')
@proteger_ruta
def lista_gallos():
    traba = session['traba']
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM individuos WHERE traba = ? ORDER BY nombre', (traba,))
    gallos = cursor.fetchall()
    conn.close()
    return render_template('lista.html', gallos=gallos, traba=traba)

@app.route('/cruce-inbreeding')
@proteger_ruta
def cruce_inbreeding():
    return render_template('cruce_inbreeding.html', traba=session['traba'])

@app.route('/cerrar-sesion')
def cerrar_sesion():
    session.clear()
    return redirect(url_for('bienvenida'))

# === Archivos estáticos y uploads ===

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.route("/logo")
def logo():
    return send_from_directory(os.getcwd(), "OIP.png")

# === Para Render ===
if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
