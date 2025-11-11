import json


"""En caso de no leer el archivo correctamente se usara este archivo."""
PERSONALIZACION_WEB = {
    "nombre_colegio": "Liceo San Juan Bautista De Hualqui",
    "lema_colegio": "Construyendo tu futuro",
    
    "redes_sociales": [
        {"facebook": ""},
        {"youtube": ""},
        {"twitter": ""},
        {"instagram": ""}
    ]
}

try:
    with open("settings/settings.json", "r", encoding="UTF-8") as settings_info:
        PERSONALIZACION_WEB = json.loads(settings_info.read())

except:
    print("ERROR: No se logro leer el archivo settings.json")

MIGRANDO = False

# Acciones y/o paginas que pueden visitar los cargos de la bdd
# Ejemplo: Un noticiero solo puede acceder a la pagina de noticias/ y noticiero/
RUTAS_DE_USUARIOS = {

    "estudiante": [
        "estudiante", 
        "taller_estudiante",
    ],
    
    "administrador": [
        "administrador",
        "administrador_mensajes",
        "administrador_mensajes_vistos",
        "administrador_crear_taller",
        "administrar_taller_estudiantes",
        "administrar_pagina",
    ],
    
    "noticiero": [
        "noticiero",
        "noticias",
    ],
    
    "profesor": [
        "profesor",
        "profesor_taller",
    ]
}

# Rutas publicas permitidas sin autenticacion
RUTAS_PUBLICAS = [
    "home", "logout", "contactanos", "login", "seccion_de_noticias", "urgente", "profesor_jefe_crear", "talleres"
]

