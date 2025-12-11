_numb = "1234567890"
_alph = "qwertyuiopasdfghjklñzxcvbnm"
_acen = "áéíóúÁÉÍÓÚüÜ"
_poin = ":;,.!?¡¿()%"
_email = "@_."


formularios_dict = {
    "login": {
        "rut": [7, 12, _numb + "-k"],
        "contrasena": [4, 20, _alph + _numb + "_@"]
    },
    "contactanos": {
        "asunto": [5, 100, _alph + _numb + " "],
        "motivo": [3, 30, _alph],
        "medio_de_contacto": [3, 10, _alph],
        "contacto": [4, 100, _alph + _numb + _email + "+ "],
        "mensaje": [20, 1000, _alph + _numb + _acen + _poin + _email + " "]
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
"""