from flask import Flask, render_template, request, redirect, url_for, flash
import os

app = Flask(__name__)
app.secret_key = "gallofino_secret_key"

# ==============================
# RUTAS PRINCIPALES
# ==============================

@app.route('/')
def inicio():
    return render_template('inicio.html')

@app.route('/menu')
def menu():
    return render_template('menu.html')

@app.route('/lista')
def lista():
    gallos = [
        {"placa": "GF001", "nombre": "Fino Dorado", "raza": "Combatiente", "edad": "2 años"},
        {"placa": "GF002", "nombre": "Negro Bravo", "raza": "Cubanito", "edad": "3 años"},
    ]
    return render_template('lista.html', gallos=gallos)

@app.route('/cruce_inbreeding', methods=['GET', 'POST'])
def cruce_inbreeding():
    if request.method == 'POST':
        gallo1 = request.form.get('gallo1')
        gallo2 = request.form.get('gallo2')
        flash(f"Cruce registrado entre {gallo1} y {gallo2}.", "success")
        return redirect(url_for('menu'))
    return render_template('cruce_inbreeding.html')

@app.route('/buscar', methods=['GET', 'POST'])
def buscar():
    query = request.args.get('query', '')
    resultados = []
    if query:
        resultados = [
            {"nombre": "Fino Dorado", "raza": "Combatiente", "color": "Rojo"},
            {"nombre": "Negro Bravo", "raza": "Cubanito", "color": "Negro"},
        ]
    return render_template('resultados_busqueda.html', resultados=resultados, query=query)

@app.route('/registro_exitoso')
def registro_exitoso():
    return render_template('registro_exitoso.html')

@app.route('/error')
def error():
    return render_template('error.html')

@app.route('/eliminar_gallo/<int:id>')
def eliminar_gallo(id):
    flash(f"Gallo con ID {id} eliminado correctamente.", "success")
    return redirect(url_for('lista'))

@app.route('/editar_gallo/<int:id>', methods=['GET', 'POST'])
def editar_gallo(id):
    if request.method == 'POST':
        flash("Datos actualizados correctamente.", "success")
        return redirect(url_for('lista'))
    return render_template('editar_gallo.html', id=id)

# ==============================
# CONFIGURACIÓN DE EJECUCIÓN
# ==============================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
