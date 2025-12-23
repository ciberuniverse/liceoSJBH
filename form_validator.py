_numb = "1234567890"
_alph = "qwertyuiopasdfghjklñzxcvbnm "
_acen = "áéíóúÁÉÍÓÚüÜ"
_poin = ":;,.!?¡¿()%"
_email = "@_."

rut_allowed = [7, 14, _numb + "-k"]

formularios_dict = {
    "login": {
        "rut": rut_allowed,
        "contrasena": [4, 20, _alph + _numb + "_@"]
    },
    "contactanos": {
        "asunto": [5, 100, _alph + _numb],
        "motivo": [3, 30, _alph],
        "medio_de_contacto": [3, 10, _alph],
        "contacto": [4, 100, _alph + _numb + _email + "+"],
        "mensaje": [20, 1000, _alph + _numb + _acen + _poin + _email]
    },
    "crear_taller": {
        "nombre": [10, 100, _alph + _numb + _acen + _poin],
        "descripcion": [5, 1000, _alph + _numb + _acen + _poin + _email],
        "cupos": [1, 4, _numb],
        "horarios": [3, 100, _alph + _numb + _poin + _acen],
        "profesor_rut": rut_allowed
    },
    "crear_evento": {
        "fecha_evento": [1, 12, _numb + "-" ],
        "titulo": [3, 40, _alph + _numb + _acen + _poin],
        "descripcion": [3, 500, _alph + _numb + _acen + _poin + _email],
    },
    "anotacion_alumno": {
        "rut_alumno": rut_allowed,
        "materia_alumno": [3, 50, _alph],
        "asunto": [4, 100, _alph + _numb],
        "descripcion": [5, 500, _alph + _numb + _acen + _poin + _email],
    },
    "crear_usuario": {
        "nombres": [5, 100, _alph + _acen],
        "apellidos": [5, 100, _alph + _acen],
        "rut": rut_allowed,
        "cargo": [5, 30, _alph],
    }
}
"""
Diccionario que define las reglas de validación para los formularios del programa.

Estructura:
"nombre_formulario": {
    "nombre_campo": [
        0: longitud mínima permitida,
        1: longitud máxima permitida,
        2: conjunto de caracteres válidos
    ]
}

Ejemplo:
"login": {
    "usuario": [4, 10, __numb + __alph + "__@"]
}

Por algun motivo no se pueden validar los saltos de linea.
"""