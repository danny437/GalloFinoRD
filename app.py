# app.py
from flask import Flask, request, session, redirect, url_for, send_from_directory, jsonify, render_template
import sqlite3
import os
import csv
import io
import shutil
import zipfile
from datetime import datetime
from werkzeug.utils import secure_filename
import secrets

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
    # ... (igual que en tu archivo original)
    # (código de init_db completo aquí)
    pass  # <-- reemplaza con tu código original

def proteger_ruta(f):
    # ... (igual que en tu archivo)
    pass

def verificar_pertenencia(id_registro, tabla):
    # ... (igual que en tu archivo)
    pass

# Rutas de autenticación
@app.route('/registrar-traba', methods=['POST'])
def registrar_traba():
    # ... lógica igual, pero redirige o renderiza plantillas
    pass

@app.route('/solicitar-otp', methods=['POST'])
def solicitar_otp():
    # ... igual
    pass

@app.route('/verificar-otp', methods=['GET', 'POST'])
def verificar_otp():
    # Aquí usamos render_template para GET, y lógica para POST
    if request.method == 'GET':
        correo = request.args.get('correo', '').strip()
        if not correo:
            return redirect(url_for('bienvenida'))
        return render_template('verificar_otp.html', correo=correo)
    else:
        # ... lógica de verificación
        pass

# Rutas principales
@app.route('/')
def bienvenida():
    if 'traba' in session:
        return redirect(url_for('menu_principal'))
    fecha_actual = datetime.now().strftime('%Y-%m-%d')
    return render_template('inicio.html', fecha_actual=fecha_actual)

@app.route('/menu')
@proteger_ruta
def menu_principal():
    return render_template('menu.html', traba=session['traba'])

@app.route('/formulario-gallo')
@proteger_ruta
def formulario_gallo():
    traba = session['traba']
    razas = RAZAS
    apariencias = ['Crestarosa', 'Cocolo', 'Tuceperne', 'Pava', 'Moton']
    
    def columna_html(titulo, prefijo, color_fondo, color_titulo, required=False):
        req_attr = "required" if required else ""
        req_radio = "required" if required else ""
        ap_html = ''.join([f'<label><input type="radio" name="{prefijo}_apariencia" value="{a}" {req_radio}> {a}</label><br>' for a in apariencias])
        razas_html = ''.join([f'<option value="{r}">{r}</option>' for r in razas])
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

    return render_template('registrar_gallo.html',
        traba=traba,
        columna_gallo=columna_html("A. Gallo (Obligatorio)", "gallo", "rgba(232,244,252,0.2)", "#2980b9", required=True),
        columna_madre=columna_html("B. Madre (Opcional)", "madre", "rgba(253,239,242,0.2)", "#c0392b"),
        columna_padre=columna_html("C. Padre (Opcional)", "padre", "rgba(235,245,235,0.2)", "#27ae60"),
        columna_ab_materno=columna_html("D. Abuelo Materno (Opcional)", "ab_materno", "rgba(253,242,233,0.2)", "#e67e22"),
        columna_ab_paterno=columna_html("E. Abuelo Paterno (Opcional)", "ab_paterno", "rgba(232,248,245,0.2)", "#1abc9c")
    )

# === Todas las demás rutas: igual lógica, pero usando render_template ===

@app.route('/registrar-gallo', methods=['POST'])
@proteger_ruta
def registrar_gallo():
    # ... tu lógica igual
    try:
        # ... registro exitoso
        return render_template('registro_exitoso.html')
    except Exception as e:
        return render_template('error.html', mensaje=str(e))

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
    return render_template('cruce_inbreeding.html', gallos=gallos)

@app.route('/buscar', methods=['GET', 'POST'])
@proteger_ruta
def buscar():
    if request.method == 'POST':
        # ... lógica de búsqueda
        return render_template('resultados_busqueda.html', resultados=resultados)
    else:
        return render_template('buscar.html')

@app.route('/lista')
@proteger_ruta
def lista_gallos():
    mensaje_exito = request.args.get('exito', '')
    traba = session['traba']
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    # ... consulta
    gallos = cursor.fetchall()
    conn.close()
    return render_template('lista.html', traba=traba, gallos=gallos, mensaje_exito=mensaje_exito)

@app.route('/editar-gallo/<int:id>')
@proteger_ruta
def editar_gallo(id):
    # ... lógica
    return render_template('editar_gallo.html', gallo=gallo, todos_gallos=todos_gallos, progen=progen, RAZAS=RAZAS, apariencias=apariencias)

@app.route('/eliminar-gallo/<int:id>')
@proteger_ruta
def eliminar_gallo(id):
    # ... confirmación
    return render_template('eliminar_gallo.html', placa_traba=gallo[0])

@app.route('/arbol/<int:id>')
@proteger_ruta
def arbol_genealogico(id):
    # ... lógica recursiva
    return render_template('arbol.html', gallo=gallo, madre=madre, padre=padre, abuelos=abuelos)

# Rutas de utilidad
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route("/logo")
def logo():
    return send_from_directory("static/imgs", "OIP.png")

@app.route('/backup', methods=['POST'])
@proteger_ruta
def crear_backup_manual():
    # ... igual
    pass

@app.route('/download/<filename>')
@proteger_ruta
def descargar_backup(filename):
    # ... igual
    pass

@app.route('/cerrar-sesion')
def cerrar_sesion():
    session.clear()
    return redirect(url_for('bienvenida'))

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
