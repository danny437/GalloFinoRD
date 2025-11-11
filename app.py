from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = "gallofino_secret_key"

# ========================
# RUTAS PRINCIPALES
# ========================

@app.route('/')
def inicio():
    return render_template('inicio.html')

@app.route('/menu')
def menu():
    return render_template('menu.html')

@app.route('/lista')
def lista():
    # Ejemplo: puedes reemplazar esto con datos reales más adelante
    gallos = [
        {"nombre": "Fino Dorado", "raza": "Combatiente", "edad": "2 años"},
        {"nombre": "Gallo Negro", "raza": "Cubanito", "edad": "3 años"},
    ]
    return render_template('lista.html', gallos=gallos)

@app.route('/registro_exitoso')
def registro_exitoso():
    return render_template('registro_exitoso.html')

@app.route('/error')
def error():
    return render_template('error.html')

# =========================
# FORMULARIOS Y PROCESOS
# =========================

@app.route('/editar_gallo/<int:id>', methods=['GET', 'POST'])
def editar_gallo(id):
    if request.method == 'POST':
        flash("Datos del gallo actualizados correctamente.", "success")
        return redirect(url_for('lista'))
    return render_template('editar_gallo.html', id=id)

@app.route('/eliminar_gallo/<int:id>', methods=['POST'])
def eliminar_gallo(id):
    flash(f"Gallo con ID {id} eliminado correctamente.", "success")
    return redirect(url_for('lista'))

@app.route('/cruce_inbreeding', methods=['GET', 'POST'])
def cruce_inbreeding():
    if request.method == 'POST':
        gallo1 = request.form.get('gallo1')
        gallo2 = request.form.get('gallo2')
        flash(f"Cruce registrado entre {gallo1} y {gallo2}.", "success")
        return redirect(url_for('menu'))
    return render_template('cruce_inbreeding.html')

@app.route('/buscar', methods=['GET'])
def buscar():
    query = request.args.get('query', '')
    resultados = []
    if query:
        resultados = [
            {"nombre": "Fino Dorado", "raza": "Combatiente", "edad": "2 años"},
            {"nombre": "Gallo Negro", "raza": "Cubanito", "edad": "3 años"},
        ]
    return render_template('resultados_busqueda.html', query=query, resultados=resultados)

# =========================
# CONFIGURACIÓN Y EJECUCIÓN
# =========================
if __name__ == '__main__':
    app.run(debug=True)


