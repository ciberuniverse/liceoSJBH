from pymongo import MongoClient
from datetime import datetime
from bson.objectid import ObjectId

# =============================
# Conexión a la base de datos
# =============================
client = MongoClient("mongodb://localhost:27017/")
db = client["colegio"]

estudiantes = db["estudiantes"]
talleres = db["talleres"]
noticias = db["noticias"]
contacto = db["contacto"]

# =============================
# Función Auxiliar para fechas
# =============================
def hoy():
    return datetime.today().strftime("%d-%m-%Y")


# ======================================
#   INSERTAR ESTUDIANTES DE PRUEBA
# ======================================
estudiantes_prueba = [
    {
        "rut": "11111111-1",
        "nombres": "Juan",
        "apellidos": "Pérez",
        "cargo": "estudiante",
        "contrasena": "1234",
        "taller": "",
        "lista_taller": []
    },
    {
        "rut": "22222222-2",
        "nombres": "María",
        "apellidos": "González",
        "cargo": "estudiante",
        "contrasena": "1234",
        "taller": "",
        "lista_taller": []
    },
    {
        "rut": "33333333-3",
        "nombres": "Pedro",
        "apellidos": "Soto",
        "cargo": "profesor",
        "contrasena": "1234",
        "cursos_asignados": [],
        "taller_asignado": ""
    },
    {
        "rut": "44444444-4",
        "nombres": "Ana",
        "apellidos": "Martínez",
        "cargo": "tallerista",
        "contrasena": "1234",
        "taller_asignado": ""
    },
    {
        "rut": "55555555-5",
        "nombres": "Luis",
        "apellidos": "Reyes",
        "cargo": "estudiante",
        "contrasena": "1234",
        "taller": "",
        "lista_taller": []
    }
]

estudiantes.insert_many(estudiantes_prueba)
print("[OK] 5 estudiantes insertados.")


# ======================================
#   INSERTAR TALLERES DE PRUEBA
# ======================================
talleres_prueba = [
    {
        "nombre": "Taller de Música",
        "descripcion": "Aprender guitarra y piano.",
        "profesor_rut": "33333333-3",
        "profesor_nombre": "Pedro Soto",
        "cupos": 10,
        "inscritos": [],
        "lista_espera": []
    },
    {
        "nombre": "Taller de Pintura",
        "descripcion": "Técnicas de pintura acrílica.",
        "profesor_rut": "44444444-4",
        "profesor_nombre": "Ana Martínez",
        "cupos": 12,
        "inscritos": [],
        "lista_espera": []
    },
    {
        "nombre": "Taller de Robótica",
        "descripcion": "Arduino, sensores, electrónica básica.",
        "profesor_rut": "",
        "profesor_nombre": "",
        "cupos": 8,
        "inscritos": [],
        "lista_espera": []
    },
    {
        "nombre": "Taller de Fútbol",
        "descripcion": "Entrenamiento físico y táctico.",
        "profesor_rut": "",
        "profesor_nombre": "",
        "cupos": 20,
        "inscritos": [],
        "lista_espera": []
    },
    {
        "nombre": "Taller de Inglés Conversacional",
        "descripcion": "Práctica de conversación.",
        "profesor_rut": "",
        "profesor_nombre": "",
        "cupos": 15,
        "inscritos": [],
        "lista_espera": []
    }
]

talleres.insert_many(talleres_prueba)
print("[OK] 5 talleres insertados.")


# ======================================
#   INSERTAR NOTICIAS DE PRUEBA
# ======================================
noticias_prueba = [
    {
        "titulo": "Bienvenida al Año Escolar",
        "descripcion": "El colegio da inicio al nuevo año académico.",
        "imagen": "",
        "fecha_publicacion": hoy(),
        "tipo": "noticia"
    },
    {
        "titulo": "Nuevo Taller de Robótica",
        "descripcion": "Se abre el taller de robótica para estudiantes.",
        "imagen": "",
        "fecha_publicacion": hoy(),
        "tipo": "noticia"
    },
    {
        "titulo": "Simulacro de Emergencia",
        "descripcion": "El colegio realizará un simulacro este viernes.",
        "imagen": "",
        "fecha_publicacion": hoy(),
        "tipo": "alerta"
    },
    {
        "titulo": "Reunión de Apoderados",
        "descripcion": "Reunión destinada a informar horarios y reglamentos.",
        "imagen": "",
        "fecha_publicacion": hoy(),
        "tipo": "noticia"
    },
    {
        "titulo": "Talleres Extraprogramáticos",
        "descripcion": "Revisa los talleres disponibles este semestre.",
        "imagen": "",
        "fecha_publicacion": hoy(),
        "tipo": "noticia"
    }
]

noticias.insert_many(noticias_prueba)
print("[OK] 5 noticias/alertas insertadas.")


# ======================================
#   INSERTAR MENSAJES DE CONTACTO DE PRUEBA
# ======================================
contacto_prueba = [
    {"nombre": "Sofía", "correo": "sofia@example.com", "mensaje": "Consulta sobre matrícula", "visto": False},
    {"nombre": "Tomás", "correo": "tomas@example.com", "mensaje": "Solicitud de reunión", "visto": False},
    {"nombre": "Carla", "correo": "carla@example.com", "mensaje": "Problema con acceso a plataforma", "visto": False},
    {"nombre": "Diego", "correo": "diego@example.com", "mensaje": "Dudas sobre taller", "visto": True},
    {"nombre": "Isabel", "correo": "isabel@example.com", "mensaje": "Felicitaciones al equipo docente", "visto": True}
]

contacto.insert_many(contacto_prueba)
print("[OK] 5 mensajes de contacto insertados.")

print("\n===== SEEDING COMPLETADO =====")
