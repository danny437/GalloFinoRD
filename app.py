import os
import sqlite3
import csv
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from flask import (
    Flask, request, session, redirect, url_for,
    render_template, send_from_directory, jsonify, send_file
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'clave_secreta_para_gallos_2025_mejor_cambiala')
app.config.update(
    DB='gallos.db',
    UPLOAD_FOLDER='uploads',
    BACKUPS_FOLDER='backups',
    ALLOWED_EXTENSIONS={'png', 'jpg', 'jpeg', 'gif'},
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16 MB
)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['BACKUPS_FOLDER'], exist_ok=True)

RAZAS = [
    "Hatch", "Sweater", "Kelso", "Grey", "Albany",
    "Radio", "Asil (Aseel)", "Shamo", "Spanish", "Peruvian"
]
TABLAS_PERMITIDAS = {'individuos', 'cruces'}
APARIENCIAS = ['Crestarosa', 'Cocolo', 'Tuceperne', 'Pava', 'Moton']
PORCENTAJES = {1: 25, 2: 37.5, 3: 50, 4: 62.5, 5: 75, 6: 87.5}


def get_db():
    conn = sqlite3.connect(app.config['DB'])
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    db_path = app.config['DB']
    if not os.path.exists(db_path):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE trabas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_traba TEXT UNIQUE NOT NULL,
            nombre_completo TEXT NOT NULL,
            contraseña_hash TEXT NOT NULL,
            email TEXT
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


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def proteger_ruta(f):
    def wrapper(*args, **kwargs):
        if 'traba' not in session:
            return redirect(url_for('bienvenida'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper


def verificar_pertenencia(id_registro, tabla):
    if tabla not in TABLAS_PERMITIDAS:
        return False
    traba = session['traba']
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM ? WHERE id = ? AND traba = ?', (tabla, id_registro, traba))
    existe = cursor.fetchone()
    conn.close()
    return bool(existe)


# ------------------ RUTAS ------------------

@app.route('/logo')
def logo():
    return send_from_directory(os.getcwd(), "OIP.png")


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/')
def bienvenida():
    if 'traba' in session:
        return redirect(url_for('menu_principal'))
    return render_template('inicio.html', fecha_actual=datetime.now().strftime('%Y-%m-%d'))


@app.route('/registrar-traba', methods=['POST'])
def registrar_traba():
    nombre = request.form['nombre']
    apellido = request.form['apellido']
    traba = request.form['traba']
    contraseña = request.form['contraseña']
    nombre_completo = f"{nombre} {apellido}"
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO trabas (nombre_traba, nombre_completo, contraseña_hash) VALUES (?, ?, ?)",
            (traba, nombre_completo, generate_password_hash(contraseña))
        )
        conn.commit()
        session['traba'] = traba
        return redirect(url_for('menu_principal'))
    except sqlite3.IntegrityError:
        conn.close()
        return render_template('error.html', error="Nombre de traba ya registrado.")
    except Exception as e:
        conn.close()
        return render_template('error.html', error=str(e))
    finally:
        conn.close()


@app.route('/iniciar-sesion', methods=['POST'])
def iniciar_sesion():
    traba = request.form['traba']
    contraseña = request.form['contraseña']
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT contraseña_hash FROM trabas WHERE nombre_traba = ?", (traba,))
    row = cursor.fetchone()
    conn.close()
    if row and check_password_hash(row[0], contraseña):
        session['traba'] = traba
        return redirect(url_for('menu_principal'))
    else:
        return render_template('error.html', error="Traba o contraseña incorrectos.")


@app.route('/menu')
@proteger_ruta
def menu_principal():
    return render_template('menu.html')


@app.route('/formulario-gallo')
@proteger_ruta
def formulario_gallo():
    return render_template('registrar_gallo.html', razas=RAZAS, apariencias=APARIENCIAS)


@app.route('/registrar-gallo', methods=['POST'])
@proteger_ruta
def registrar_gallo():
    traba = session['traba']
    conn = get_db()
    cursor = conn.cursor()

    def guardar_individuo(prefijo, es_gallo=False):
        placa = request.form.get(f'{prefijo}_placa_traba')
        if not placa:
            return None if not es_gallo else None
        if es_gallo and not placa:
            raise ValueError("Placa del gallo es obligatoria.")
        placa_regional = request.form.get(f'{prefijo}_placa_regional')
        nombre = request.form.get(f'{prefijo}_nombre')
        n_pelea = request.form.get(f'{prefijo}_n_pelea')
        raza = request.form.get(f'{prefijo}_raza')
        color = request.form.get(f'{prefijo}_color')
        apariencia = request.form.get(f'{prefijo}_apariencia')

        if es_gallo and (not raza or not color or not apariencia):
            raise ValueError("Raza, color y apariencia son obligatorios para el gallo.")
        if not es_gallo and (not raza or not color or not apariencia):
            return None

        foto = None
        if f'{prefijo}_foto' in request.files:
            file = request.files[f'{prefijo}_foto']
            if file and file.filename != '' and allowed_file(file.filename):
                safe_placa = secure_filename(placa)
                fname = f"{safe_placa}_{secure_filename(file.filename)}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], fname)
                file.save(file_path)
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

        if madre_id or padre_id:
            cursor.execute('INSERT INTO progenitores (individuo_id, madre_id, padre_id) VALUES (?, ?, ?)',
                           (gallo_id, madre_id, padre_id))
        if madre_id and ab_materno_id:
            cursor.execute('INSERT INTO progenitores (individuo_id, padre_id) VALUES (?, ?)', (madre_id, ab_materno_id))
        if padre_id and ab_paterno_id:
            cursor.execute('INSERT INTO progenitores (individuo_id, padre_id) VALUES (?, ?)', (padre_id, ab_paterno_id))

        conn.commit()
        return render_template('registro_exitoso.html', tipo='gallo')
    except Exception as e:
        conn.rollback()
        return render_template('error.html', error=str(e))
    finally:
        conn.close()


@app.route('/backup', methods=['POST'])
@proteger_ruta
def crear_backup_manual():
    try:
        timestamp = datetime.now()
        fecha_archivo = timestamp.strftime("%Y%m%d_%H%M%S")
        temp_dir = f"temp_backup_{fecha_archivo}"
        os.makedirs(temp_dir, exist_ok=True)

        shutil.copy2(app.config['DB'], os.path.join(temp_dir, "gallos.db"))
        if os.path.exists(app.config['UPLOAD_FOLDER']):
            shutil.copytree(app.config['UPLOAD_FOLDER'], os.path.join(temp_dir, "uploads"), dirs_exist_ok=True)

        zip_filename = f"gallofino_backup_{fecha_archivo}.zip"
        zip_path = os.path.join(app.config['BACKUPS_FOLDER'], zip_filename)

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(temp_dir):
                for f in files:
                    full_path = os.path.join(root, f)
                    arcname = os.path.relpath(full_path, temp_dir)
                    zf.write(full_path, arcname)

        shutil.rmtree(temp_dir)
        mensaje = f"Copia de seguridad creada el {timestamp.strftime('%d/%m/%Y %H:%M')}."
        return jsonify({"mensaje": mensaje, "archivo": zip_filename})
    except Exception as e:
        if 'temp_dir' in locals() and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return jsonify({"error": str(e)}), 500


@app.route('/download/<filename>')
@proteger_ruta
def descargar_backup(filename):
    ruta = Path(app.config['BACKUPS_FOLDER']) / filename
    if not ruta.is_file() or ".." in str(ruta) or not filename.endswith('.zip'):
        return "Archivo no válido", 400
    return send_file(ruta, as_attachment=True)


@app.route('/cerrar-sesion')
def cerrar_sesion():
    session.clear()
    return redirect(url_for('bienvenida'))


# ------------------ MAIN ------------------

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
