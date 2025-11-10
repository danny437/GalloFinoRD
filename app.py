from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "tu_clave_secreta"
UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Crear carpeta si no existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Simulación de datos
gallos = []

@app.route("/")
def inicio():
    from datetime import date
    fecha_actual = date.today().isoformat()
    return render_template("inicio.html", fecha_actual=fecha_actual)

@app.route("/menu")
def menu_principal():
    return render_template("menu.html")

@app.route("/registrar_traba", methods=["POST"])
def registrar_traba():
    flash("Usuario registrado con éxito", "success")
    return redirect(url_for("inicio"))

@app.route("/lista_gallos")
def lista_gallos():
    return render_template("lista.html", gallos=gallos)

@app.route("/buscar")
def buscar():
    return render_template("resultados_busqueda.html", resultados=[])

@app.route("/cerrar_sesion")
def cerrar_sesion():
    flash("Sesión cerrada", "success")
    return redirect(url_for("inicio"))

@app.route("/download/<filename>")
def download_file(filename):
    return send_from_directory("backups", filename)

@app.route("/backup", methods=["POST"])
def backup():
    # Simulación de backup
    os.makedirs("backups", exist_ok=True)
    filename = "backup_demo.txt"
    with open(f"backups/{filename}", "w") as f:
        f.write("Backup de datos")
    return {"mensaje": "Backup creado", "archivo": filename}

if __name__ == "__main__":
    app.run(debug=True)
