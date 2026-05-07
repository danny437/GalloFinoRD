# 🐓 GalloFinoRD
> Sistema Profesional de Gestión Genética y Registro de Cruces

Aplicación web moderna desarrollada en Flask para el control genealógico, registro de individuos, cruces inbreeding/linebreeding, gestión de placas y respaldos de datos. Diseñada para criadores que requieren trazabilidad, organización y seguridad en su manejo genético.

---

## ✨ Características Principales
- 📝 Registro y edición de gallos con carga de fotos
- 🌳 Árbol genealógico automático (3 generaciones + hijos)
- 🔁 Registro de cruces con cálculo de consanguinidad (Padre-Hija, Hermanos, Abuelo-Nieta, etc.)
- 🔍 Búsqueda inteligente por placa, nombre o color
- 📥 Importación masiva de datos vía CSV
- 📤 Exportación de registros y respaldos automáticos en ZIP
- 🔐 Autenticación segura con OTP, sesiones protegidas y hashing de contraseñas
- 🛡️ Validación de imágenes reales, protección CSRF y claves foráneas activas

---

## 🛠️ Stack Tecnológico
| Capa | Tecnología |
|------|------------|
| **Backend** | Python 3.10+ / Flask 3.0 |
| **Base de Datos** | SQLite (con migraciones automáticas) |
| **Servidor** | Gunicorn (producción) |
| **Frontend** | HTML5, CSS3, Vanilla JS (responsive) |
| **Seguridad** | Flask-WTF (CSRF), Werkzeug (hashing), Pillow (validación de imágenes) |

---

## 📦 Instalación y Ejecución Local

### 1. Clonar el repositorio
```bash
git clone https://github.com/danny437/GalloFinoRD.git
cd GalloFinoRD
