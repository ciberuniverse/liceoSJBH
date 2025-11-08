NOMBRE_LICEO = "LICEO SAN JUAN BAUTISTA DE HUALQUI"
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

