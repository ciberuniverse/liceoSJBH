from pymongo import MongoClient, UpdateOne, UpdateMany
from xhtml2pdf import pisa
from bson.objectid import ObjectId # Importar ObjectId
from datetime import datetime
from hashlib import blake2b
from form_validator import formularios_dict
import io, os, json, unicodedata
import pandas as pd


if "herna" not in os.getcwd():
    HOST = MongoClient(os.environ.get("HOST"))
    SECRET_KEY = os.environ.get("SECRET_KEY")
else:
    HOST = MongoClient("mongodb://localhost:27017/")
    SECRET_KEY = "324535542d953171e82ff39f647e41baeb53ce0b11f127a8da2fce199f5fd8955c368f1db7c7b1cb32abc6e236bb96d5cd85d65812a7506036fb362c47344ddf"
    
    
BDD = HOST["colegio"]

ROOT_DIR = os.getcwd()
TEMPLATES_DIR = os.path.join(ROOT_DIR, "static", "informes_templates")
MEDIA_DIR = os.path.join(ROOT_DIR, "static", "media")

estudiantes = BDD["estudiantes"] ######### ES DONDE ESTAN LOS USUARIOS
talleres = BDD["talleres"]
noticias = BDD["noticias"]
contacto = BDD["contacto"]
cursos = BDD["cursos"]
notas = BDD["notas"]
eventos = BDD["eventos"]

NOT_ALLOWED = r";$&|{}[]<>\"'\\`"


##################### Funciones auxiliares

def verificar_estado_de_peticion(resultado) -> dict:
    
    if resultado["codigo"] == 200:
        return resultado["mensaje"]
    
    return resultado

def json_de_mensaje(codigo: int, resultado_o_mensaje: str = None) -> dict:
    """Crea un json con el formato: { 'codigo': 000, 'mensaje': 'resultado o mensaje de error' }"""
    
    errores = {
        402: "Error formulario incompleto o corrupto.",
        403: "Acceso denegado. No tienes permisos suficientes.",
        404: "Recurso no encontrado.",
        500: "Error interno del servidor.",
        503: "Servicio no disponible temporalmente."
    }


    if not resultado_o_mensaje:
        resultado_o_mensaje = errores[codigo]

    if codigo == 500:
        print(f"\033[1;30;41m  ERRROR {codigo}: {resultado_o_mensaje}  \033[0m")

    return {"codigo": codigo, "mensaje": resultado_o_mensaje}

def obtener_fecha() -> str:
    """Obtiene la fecha actual."""
    return str(datetime.today().strftime("%d-%m-%Y"))

def no_sql(formulario: dict) -> dict:
    """Encargado de verificar longitud y sanitizacion adecuada."""

    keys_ = formulario.keys()

    for key in keys_:

        if any(char_ in formulario[key] for char_ in NOT_ALLOWED):
            return json_de_mensaje(500, "ERROR: Estas inyectando parametros no permitidos en la consulta.")
    
    return json_de_mensaje(200, "Exito.")

def obtener_path_normalizado(cadena_str: str) -> str:
    """Normaliza los path de Imagenes a '/'."""
    return cadena_str.replace("\\", "/")

def verificar_campos_vacios(json_: dict) -> dict:
    """Verifica que los campos no esten vacios."""

    dict_keys = json_.keys()

    for key in dict_keys:
        
        if json_[key] == "":
            return json_de_mensaje(500, "No puedes enviar formularios con datos vacios.")

    return json_de_mensaje(200, "Todo bien")

def guardar_imagen(seccion: str, name_frontend: str, formulario_file) -> dict:
    """
    seccion: Carpeta en la que se guardara la imagen.\n
    name_frontend: Como se llama el campo que envia la imagen al backend.\n
    formulario_file: El request.form de flask.
    """

    if name_frontend not in formulario_file:
        return json_de_mensaje(404, "No existe imagen que subir.")
    
    archivo = formulario_file[name_frontend]
    if not archivo or not archivo.filename:
        return json_de_mensaje(404, "")

    if seccion not in os.listdir(MEDIA_DIR):
        os.mkdir(os.path.join(MEDIA_DIR, seccion))

    ruta = os.path.join(MEDIA_DIR, seccion, archivo.filename)
    ruta_de_retorno = os.path.join("static", "media", seccion, archivo.filename)

    archivo.save(ruta)

    return json_de_mensaje(200, ruta_de_retorno)

def cifrar_contrasena(str_contrasena: str) -> str:
    return blake2b(str_contrasena.encode("utf-8")).hexdigest()

def obtener_navbar(session_cookie: dict, rutas_rol: dict, redirect: bool = False, verbose: bool = True) -> list | str:
    """
    Obtiene las rutas del usuario en base al cargo almacenado en su cookie:\n
    "informacion": {"cargo": "estudiante"}
    \n\n
    Retorna un dict con la informacion de las urtas para\n
    las navbar y redirecciones.\n

    Si redirect es True, se le redireccionara a la primera ruta\n
    del rol asignado. Es decir, rutas[0].
    """
    cargo = session_cookie["informacion"]["cargo"]
    rutas_rol_user = rutas_rol["rol"][cargo]

    if redirect:
        return rutas_rol_user[0]
    
    elif verbose:
        
        #descrip = {x: rutas_rol["navbar"][x] for x in rutas_rol_user}
        descrip = {x: rutas_rol["private"][x] for x in rutas_rol_user}
        
        return descrip

    return rutas_rol_user

###############################################
######## CLASES DE SEPARACION DE LOGICA

class Informes_pdf:

    @staticmethod
    def leer_plantilla_html(nombre_plantilla: str) -> dict:
        try:
            ruta_plantilla = obtener_path_normalizado(TEMPLATES_DIR) + "/" + nombre_plantilla + ".html"
            print(ruta_plantilla)
            with open(ruta_plantilla, "r", encoding="UTF-8") as leer_plantilla:
                return json_de_mensaje(200, leer_plantilla.read())
        
        except:
            return json_de_mensaje(500, f"ERROR: No se logro leer la plantilla {nombre_plantilla}.")
        
    @staticmethod
    def generar_pdf(plantilla_html: str, nombre_archivo: str) -> dict:
        
        buffer_en_memoria = io.BytesIO()

        try:
            nombre_archivo = "static/informes/" + nombre_archivo + ".pdf"

            with open(nombre_archivo, "wb") as archivo_pdf:
                
                pisa.CreatePDF(
                    io.StringIO(plantilla_html),
                    dest = buffer_en_memoria
                )

            buffer_en_memoria.seek(0)

        except:
            return json_de_mensaje(500, "ERROR: No se logro generar el informe correctamente.")

        return json_de_mensaje(200, buffer_en_memoria)

    @staticmethod
    def generar_pase_de_salida(plantilla_nombre: str, formulario: dict) -> dict:

        plantilla_pase = Informes_pdf.leer_plantilla_html(plantilla_nombre)
        if plantilla_pase["codigo"] != 200:
            return plantilla_pase
        
        resultado_seguridad = Security.claves_existentes(["nombre_apoderado", "rut_apoderado", "rut_estudiante", "hora_salida", "curso_estudiante"], formulario)
        if not resultado_seguridad:
            return json_de_mensaje(404, "Estas enviando un formulario incompleto.")

        plantilla: str = plantilla_pase["mensaje"]

        #### Modifica la variable de la plantilla por cada key en el formulario
        # los nombres de las variables en el formulario son iguales que en la plantilla
        for key in formulario:
            plantilla = plantilla.replace(key, formulario[key])

        return Informes_pdf.generar_pdf(plantilla, "xd")
        ######## GENERAR UNA PLANTILLA

    @staticmethod
    def generar_certificado_alumno_regular(plantilla_nombre: str, formulario: dict) -> dict:

        plantilla_str = Informes_pdf.leer_plantilla_html(plantilla_nombre)
        if plantilla_str["codigo"] != 200:
            return plantilla_str
        
        informacion_rut = General.obtener_informacion_rut(formulario["rut_estudiante"])
        if informacion_rut["codigo"] != 200:
            return informacion_rut
        
        formulario["nombre_estudiante"] = informacion_rut["mensaje"]["nombres"] + " " + informacion_rut["mensaje"]["apellidos"]
        formulario["fecha_actual"] = obtener_fecha()
        formulario["ano_actual"] = formulario["fecha_actual"].split("-")[2]
        
        ###### CURSO ACTUAL AUN EN PRUEBA
        formulario["curso_estudiante"] = informacion_rut["mensaje"]["desc_grado"] + " " + informacion_rut["mensaje"]["letra_curso"]


        ############### ESTAS CLAVES DEBEN DE ESTAR SI O SI PARA EL INFORME
        resultado_seguridad = Security.claves_existentes(
            ["telefono_colegio", "direccion_colegio", "nombre_estudiante", "rut_estudiante", "fecha_actual", "ano_actual", "curso_estudiante"],
            formulario
        )
        if not resultado_seguridad:
            return resultado_seguridad
        
        plantilla: str = plantilla_str["mensaje"]
        for key in formulario:
            plantilla = plantilla.replace(key, formulario[key])

        resultado_certificado = Informes_pdf.generar_pdf(plantilla, "xd")
        if resultado_certificado["codigo"] != 200:
            return resultado_certificado
        
        return resultado_certificado

class Apoderado:

    @staticmethod
    def buscar_hijos(rut: str, apoderado_only: bool = False) -> dict:
        """
        Debido a posibles errores de cambios, se implemento\n
        un parametro opcional con False por defecto. Permitinedo\n
        buscar cargas de cualquier cargo sin excepcion si se mantiene de esa forma.
        """

        resultado_rut = General.obtener_informacion_rut(rut)
        if resultado_rut["codigo"] != 200:
            return resultado_rut
        
        if "carga_apoderado" not in resultado_rut["mensaje"]:
            return json_de_mensaje(200, resultado_rut)
        
        match_ = {
            "rut": rut
        }

        if apoderado_only:
            match_.setdefault("cargo", "apoderado")

        try:
            resultado_cargas = list(estudiantes.aggregate([
                {"$match": match_},
                {"$lookup": {
                    "from": "estudiantes",                
                    "localField": "carga_apoderado",
                    "foreignField": "rut",          
                    "as": "cargas"              
                }},
                {"$project": {"_id": 0, "contrasena": 0, "cargas._id": 0, "cargas.contrasena": 0}}
            ]))

        except:
            return json_de_mensaje(500, "ERROR: No se logro obtener informacion de tus cargas.")
        

        if not resultado_cargas:
            return json_de_mensaje(404, "No se logro encontrar ningun resultado asociado a tu rut.")
        
        resultado_cargas = resultado_cargas[0]

        # Se le agrega a la informacion del alummno la informacion del taller inscrito
        for carga in resultado_cargas["cargas"]:

            resultado_promedio_carga = General.calcular_promedios_materias_y_final(carga)
            if resultado_promedio_carga["codigo"] == 200:
                carga["materias"]["promedios"] = resultado_promedio_carga["mensaje"]

            if "taller" not in carga:
                continue
            
            taller_info = General.obtener_informacion_taller(carga["taller"])
            posicion = resultado_cargas["cargas"].index(carga)
            
            # Si no se logro obtener informacion del taller se borra para que el frontend muestre no encntrado
            if taller_info["codigo"] != 200:
                carga.pop("taller")

            # En el caso contrario, se envia la informacion del taller en el que su hijo se encuentra.
            else:            
                carga["taller"] = taller_info["mensaje"]

            resultado_cargas["cargas"][posicion] = carga

        return json_de_mensaje(200, resultado_cargas)

    @staticmethod
    def asignar_pase(rut_apoderado: str, datos_pase: dict) -> dict:

        informacion_rut = General.obtener_informacion_rut(datos_pase["rut_estudiante"])   
        if informacion_rut["codigo"] != 200:
            return informacion_rut

        ########## MODIFICACION DE INFORMACION PARA GENERAR EL PDF
        datos_pase.pop("accion")
        datos_pase["fecha_actual"] = obtener_fecha()
        datos_pase["nombre_estudiante"] = str(informacion_rut["mensaje"]["nombres"] + " " + informacion_rut["mensaje"]["apellidos"]).upper()
        ###### CURSO ACTUAL AUN EN PRUEBA
        datos_pase["curso_estudiante"] = informacion_rut["mensaje"]["desc_grado"] + " " + informacion_rut["mensaje"]["letra_curso"]


        print(datos_pase)
        # EL SPLIT DA COMO RESULTADO DOS VARIABLES QUE MODIFICAN LO FALTANTE
        datos_pase["fecha_retiro"], datos_pase["hora_salida"] = datos_pase["hora_salida"].split("T")
        try:
            modificacion_apoderados = estudiantes.update_one({"rut": rut_apoderado}, {"$push": {"retiro_alumno": datos_pase}})

        except:
            return json_de_mensaje(500, "ERROR: No se logro modificar la modificacion de apoderados.")
        
        if not modificacion_apoderados:
            return json_de_mensaje(404, "No se encontro ningun rut para asociar el pase.")
        
        return json_de_mensaje(200, f"El pase del apoderado con rut {rut_apoderado} esta disponible en su seccion de /mistramites.")

    @staticmethod
    def obtener_pases(rut_apoderado: str) -> dict:

        informacion_apoderado = General.obtener_informacion_rut(rut_apoderado)
        if informacion_apoderado["codigo"] != 200:
            return informacion_apoderado
        
        if "retiro_alumno" not in informacion_apoderado["mensaje"]:
            return json_de_mensaje(404, "No tiene ninguna solicitud de retiro para generar.")
        
        return json_de_mensaje(200, sorted(informacion_apoderado["mensaje"]["retiro_alumno"], key=lambda x: x["fecha_actual"], reverse=True))

class Security:

    alph = "qwertyuiopasdfghjklñzxcvbnm"
    num = "1234567890"
    url = ":/?&=%+"

    spc = "@_"
    # EL RETORNO ''''''''''''FALSE SIEMPRE ES NEGATIVO ES DECIR SIEMPRE HAY ALGO MAL
    @staticmethod
    def re_search(allowed: str, min_len: int, max_len: int, string_: str) -> bool:
        """
        allowed: Parametros permitidos en el campo.\n
        string _: Campo a analizar.\n
        min_len: Minima longitud del campo.\n
        max_len: Maxima longitud del campo.
        """

        str_len = len(string_)
        string_ = string_.lower()

        if str_len < min_len:
            return False

        if str_len > max_len:
            return False

        if any(x not in allowed for x in string_):
            return False

        return True
    
    @staticmethod
    def claves_existentes(claves: list, formulario: dict) -> bool:

        if any(key not in formulario for key in claves):
            return False
        
        return True

    @staticmethod
    def form_validator(formulario_name: str, formulario_validar: dict) -> dict:

        restricciones = formularios_dict.get(formulario_name)
        if not restricciones:
            return json_de_mensaje(500, "El programador no sabe cuales son sus propios formularios xd.")
        
        for campo, validator in restricciones.items():
            
            if campo not in formulario_validar:
                return json_de_mensaje(402, f"Campo '{campo}' faltante.")
            
            valor_validar = str(formulario_validar[campo]).lower()
            
            if len(valor_validar) < validator[0]:
                return json_de_mensaje(402, f"Campo '{campo}' demasiado corto.")
            
            if len(valor_validar) > validator[1]:
                return json_de_mensaje(402, f"Campo '{campo}' demasiado largo.")
            
            if any(char_ not in validator[2] for char_ in valor_validar):
                return json_de_mensaje(402, f"Campo '{campo}' contiene caracteres inválidos.")
            
        return json_de_mensaje(200, "Ok.")

    @staticmethod
    def leer_copia_seguridad(ruta_archivo: str) -> bytes:

        with open(ruta_archivo, "rb") as respaldo_b:
            respaldo_ = respaldo_b.read()

        return {"path": ruta_archivo, "bytes": respaldo_}
    
    @staticmethod
    def guardar_copia_seguridad(leer_dict: dict) -> None:

        print(f"COPIA DE SEGURIDAD REALIZADA EXITOSAMENTE DE {leer_dict['path']}")
        with open(leer_dict["path"], "wb") as respaldo_save:
            respaldo_save.write(leer_dict["bytes"])
    
    @staticmethod
    def str_to_json(form_input: str) -> dict:

        try:
            str_ = json.loads(form_input)
        
        except:
            return json_de_mensaje(402, "El formato del JSON en STR es incompatible para darle formato.")
        
        return json_de_mensaje(200, str_)

    @staticmethod
    def str_to_float(valor_float_str: str) -> float:

        # Tomar solo los primeros 3 caracteres
        raw = valor_float_str[:3]

        # Filtrar solo números
        new_valor = "".join([c for c in raw if c.isdigit()])

        long_str = len(new_valor)

        if not new_valor or long_str < 1:
            json_de_mensaje(500, "ESTAN ENVIANDO UN FORMULARIO CON STR SIN NUMEROS")
            return 1.0

        if long_str == 1:
            numero_retorno = float(new_valor)
        
        if long_str == 2 or long_str == 3:
            numero_retorno = float(new_valor[0] + "." + new_valor[1])

        if numero_retorno > 7 or numero_retorno < 1:
            return float(1.0)
        
        return numero_retorno

    @staticmethod
    def leer_normalizar_base_datos(excel_form_files: bytes, campo_form_frontend: str = "excel", nombres_keys: list = None) -> list[dict]:

        guardar_xml = guardar_imagen("nominas", campo_form_frontend, excel_form_files)
        if guardar_xml["codigo"] != 200:
            return guardar_xml
        
        archivo_xls = guardar_xml["mensaje"]
        print("Archivo usado como base de la base de datos: ", archivo_xls)

        ##################### Se lee el xls o html ya que en la practica el archivo que se sube es un xml



        try:
            tablas = pd.read_html(archivo_xls)
            
            if not tablas:
                raise ValueError("No se encontraron tablas")

            df = tablas[0]

            if nombres_keys:
                df.columns = nombres_keys

            df = df.dropna(how="all") ### Se borran las tablas vacias

            bdd_json = df.to_json(
                orient="records",
                indent=2,
                force_ascii=False
            )

            """
            excel_leyendo = pd.read_html(archivo_xls)
            bdd_json = excel_leyendo[0].to_json(
                indent = 2,
                orient = "records",
                force_ascii = False
            )"""

        except Exception as err:
            return json_de_mensaje(500, f"ERROR: Se a producido un error al intentar leer el archivo. Por favor contacta con soporte tecnico: {err}")

        bdd_json: dict = json.loads(bdd_json)
        normalizacion = []

        ######################## Se normaliza la base de datos quitando todos los caracteres especiales 
        for obj_ in bdd_json:

            try:
                obj_tmp = {}
                for key, value in obj_.items():

                    key_normal = unicodedata.normalize("NFKD", key).lower().replace(" ", "_")
                    key_normal = "".join([c for c in key_normal if not unicodedata.combining(c)])

                    for char_ in key_normal:

                        if char_ not in "qwertyuiopasdfghjklñzxcvbnm_":
                            key_normal = key_normal.replace(char_, "")

                    value_normal = value

                    if type(value) == str:
                        value_normal = unicodedata.normalize("NFKD", value)
                        
                    
                    obj_tmp.setdefault(key_normal, value_normal)
            
            except Exception as err:
                return json_de_mensaje(500, f"ERROR: No se logro normalizar la base de datos: {err}")
            
            normalizacion.append(obj_tmp)
        print(normalizacion)
        return json_de_mensaje(200, normalizacion)

    @staticmethod
    def validar_accion_form(formulario_validar: dict, posibles_acciones: list[str] = ["nuevo_ano", "crear_usuario"]) -> str:
        if "accion" not in formulario_validar:
            return json_de_mensaje(402)
        
        accion = formulario_validar["accion"]
        for x in posibles_acciones:

            if x == accion:
                return json_de_mensaje(200, accion)

        return json_de_mensaje(402)

class Users:
    """
    Clase encargada de almacenar las acciones a realizar para designar, leer, y modificar\n
    roles y rutas accesibles de la pagina web.
    """
    @staticmethod
    def guardar_routes(new_routes_dict) -> dict:

        path_r = "settings/routes.json"
        emergency = Security.leer_copia_seguridad(path_r)

        try:
            with open(path_r, "w", encoding="UTF-8") as save_json:
                json.dump(new_routes_dict, save_json, ensure_ascii=False, indent=2)
        
        except:
            Security.guardar_copia_seguridad(emergency)
            return json_de_mensaje(500, "ERROR: No se logro guardar la nueva version de roles.")
        
        return json_de_mensaje(200, "Ok.")

    @staticmethod
    def leer_routes(globa_l: bool = False) -> dict:
        """
        Funcion encargada de leer las rutas actuales, con los roles asignados.\n
        globa_l: Es un bool, cuando esta activado, se devuelve el json sin validar.
        """

        path = "settings/routes.json"
        
        if globa_l:
            with open(path, "r") as read_json:
                return json.loads(read_json.read())

        try:

            with open(path, "r") as read_json:
                result_routes = json.loads(read_json.read())
        
        except:
            return json_de_mensaje(500, "ERROR: Formato incompatible del archivo routes.json.")
        
        return json_de_mensaje(200, result_routes)
    
    @staticmethod
    def crear_rol(formulario: dict) -> dict:

        # Se verifica que contenga todos los campos del formulario
        campos_ = ["nombre_rol", "routes"]
        if any(x not in campos_ for x in formulario):
            return json_de_mensaje(404, "ERROR: Faltan parametros de consulta en tu consulta.")
    
        routes = formulario["routes"].split(",")
        nombre_rol = formulario["nombre_rol"].lower()

        routes_now = Users.leer_routes()

        if routes_now["codigo"] != 200:
            return routes_now

        routes_now = routes_now["mensaje"]
        all_private_routes = routes_now["private"].keys()


        # Se verifica que contenga rutas validas para asociar
        if any(route not in all_private_routes for route in routes):
            return json_de_mensaje(500, "Estas inyectando rutas inexistentes.")

        routes_now["rol"].setdefault(nombre_rol, routes)
        
        resultado_guardar = Users.guardar_routes(routes_now)
        if resultado_guardar["codigo"] != 200:
            return resultado_guardar

        return json_de_mensaje(200, f"Rol {nombre_rol} creado exitosamente.")

    @staticmethod
    def buscar_usuarios(filtro_valor: str, filtro: str):

        try:
            filtro_resultado = list(estudiantes.find(
                {
                    filtro: filtro_valor
                },

                {
                    "_id": 0, "cursos_asignados": 0, "taller_asignado": 0, "taller": 0, "curso_actual": 0, "lista_taller": 0
                }

            ))

        except:
            return json_de_mensaje(500, "ERROR: La base de datos no esta respondiendo como deberia a tu peticion.")
        
        if not filtro_resultado:
            return json_de_mensaje(404, "No se logro encontrar referencia alguna al usuario buscado.")
        
        return json_de_mensaje(200, filtro_resultado)

    @staticmethod
    def reestablecer_contrasena(rut: str, contrasena_nueva: str) -> dict:

        try:
            resultado = estudiantes.update_one({"rut": rut}, {"$set": {"contrasena": cifrar_contrasena(contrasena_nueva)}})
        
        except:
            return json_de_mensaje(500, "ERROR: Ocurrio un error inesperado al intentar modificar la contraseña del usuario.")
        
        if not resultado.acknowledged:
            return json_de_mensaje(404, "No se logro modificar la contraseña del usuario.")
        
        return json_de_mensaje(200, "Contraseña del usuario modificada correctamente.")

    @staticmethod
    def usuario_habilitado(rut: str, habilitado: bool):

        accion = "$unset" if habilitado else "$set"

        try:

            resultado = estudiantes.update_one({"rut": rut}, {accion: {
                "deshabilitado": True
            }})

        except:
            return json_de_mensaje(500, "ERROR: Ocurrio un error interno que no se logro modificar el estado del usuario.")
        
        if not resultado.acknowledged:
            return json_de_mensaje(404, "No se logro modificar el estado del usuario.")
        
        return json_de_mensaje(200, "Estado del usuario modificado exitosamente.")

class Settings:
    """
    Esta clase se enfoca en la configuracion del sitio\n
    a diferencia de las demas esta se efectua de manera local\n
    modificando el archivo settings.json de la carpeta settings.
    """
    @staticmethod
    def modificar_template_base(formulario: dict) -> dict:

        
        try:
            json_new = {
                "nombre_colegio": formulario["nombre_colegio"],
                "lema_colegio": formulario["lema_colegio"],
                "nombre_director": formulario["nombre_director"],

                "redes_sociales": [
                    {"facebook": formulario["facebook"]},
                    {"youtube": formulario["youtube"]},
                    {"twitter": formulario["twitter"]},
                    {"instagram": formulario["instagram"]}
                ],

                "correo_colegio": formulario["correo_colegio"],
                "direccion_colegio": formulario["direccion_colegio"],
                "telefono_colegio": formulario["telefono_colegio"],
                "calendario_colegio": formulario["calendario_colegio"]
            }
        
        except:
            return json_de_mensaje(500, "ERROR: No se logro adaptar la consulta. Faltan parametros.")

        try:
            with open("settings/settings.json", "w", encoding="UTF-8") as save_new:
                json.dump(json_new, save_new, ensure_ascii=False, indent=2)

        except:
            return json_de_mensaje(500, "ERROR: No se logro guardar el nuevo contenido del archivo settings.json")

        return json_de_mensaje(200, "Datos actualizados. Los cambios se veran reflejados una vez reinicado el servidor.")

    @staticmethod
    def leer_settings(globa_l: bool = False):

        path_sett = "settings/settings.json"
        if globa_l:
            with open(path_sett, "r", encoding="UTF-8") as leer_sett:
                return json.loads(leer_sett.read())
            
        try:
            with open(path_sett, "r", encoding="UTF-8") as leer_sett:
                resultado_sett = json.loads(leer_sett.read())
        except:
            return json_de_mensaje(500, "ERROR: No se logro abrir el archivo settings/settings.json formato incompatible.")
        
        return json_de_mensaje(200, resultado_sett)

class General:
    """
    Esta clase contiene todas las funciones que son de utilidad\n
    para mas de una clase.
    """

    def obtener_nombre_de_inscritos_taller(lista_ruts) -> dict:

        alumno_retornar = []

        try:
            resultado_estudiantes = list(estudiantes.find({"rut": {"$in": lista_ruts}}, {"_id": 0, "rut": 1, "nombres": 1, "apellidos": 1, "nota_taller": 1}))

        except:
            return json_de_mensaje(500, "ERROR: No logramos extraer los nombres y apellidos de los alumnos inscritos.")

        if not resultado_estudiantes:
            return json_de_mensaje(404, "ERROR: No se encontraron ruts con el formato indicado.")
        
        for inscrito in resultado_estudiantes:

            nombre = inscrito["nombres"] + " " + inscrito["apellidos"]
            rut = inscrito["rut"]

            inscrito_tmp = {
                "nombre": nombre,
                "rut": rut
            }

            # Esto se encarga de devolver las notas de los alumnos
            if "nota_taller" in inscrito:
                inscrito_tmp.setdefault("nota_taller", inscrito["nota_taller"])

            alumno_retornar.append(inscrito_tmp)

        return json_de_mensaje(200, alumno_retornar)

    def listar_profesores() -> dict:
        
        try:
            resultado = list(estudiantes.find({"cargo": "profesor"}))
        
        except:
            return json_de_mensaje(500, "Error, no se logro obtener el listado de profesores.")
        
        if not resultado:
            return json_de_mensaje(404, "No se logro encontrar ningun profesor en la base de datos.")
        
        return json_de_mensaje(200, resultado)

    def obtener_informacion_taller(id_del_taller: str) -> dict:
        """Obtiene informacion del taller: Inscritos, Profesor, etc."""

        try:
            resultado = list(talleres.find({"_id": ObjectId(id_del_taller)}))
        
        except:
            return json_de_mensaje(500, "Ocurrio un error en donde no se logro obtener la informacion del taller por el _id.")
        
        if not resultado:
            return json_de_mensaje(404, "No se encontro ningun taller asociado al id seleccionado.")
        
        # En caso de existir alumnos inscritos o en espera, se obtendran sus nombres apellidos y ruts para realizar una edicion mas profecional
        # desde el panel de administracion

        if "inscritos" in resultado[0]:

            informacion_estudiantes_insc = list(estudiantes.find(
                {"rut": {"$in": resultado[0]["inscritos"]}}, {"_id": 0, "nombres": 1, "apellidos": 1, "rut": 1}
            ))

            # Se limpia la lista que esta en inscritos (es tipo list)
            resultado[0]["inscritos"] = []

            for estudiante in informacion_estudiantes_insc:

                resultado[0]["inscritos"].append({"nombre": estudiante["nombres"] + " " + estudiante["apellidos"], "rut": estudiante["rut"]})

        if "lista_espera" in resultado[0]:

            informacion_estudiante_espera = list(estudiantes.find(
                {"rut": {"$in": resultado[0]["lista_espera"]}}, {"_id": 0, "nombres": 1, "apellidos": 1, "rut": 1}
            ))

            # Se limpia la lista que esta en inscritos (es tipo list)
            resultado[0]["lista_espera"] = []
            for estudiante in informacion_estudiante_espera:
                resultado[0]["lista_espera"].append({"nombre": estudiante["nombres"] + " " + estudiante["apellidos"], "rut": estudiante["rut"]})

        resultado[0]["_id"] = str(resultado[0]["_id"])

        return json_de_mensaje(200, resultado[0])

    def todos_los_talleres() -> dict:

        try:
            resultado = list(talleres.find({"deshabilitado": {"$exists": False}}))
        except:
            return json_de_mensaje(500, "Ocurrio un error al buscar en la base de datos.")

        if resultado:
            return json_de_mensaje(200, resultado)

        return json_de_mensaje(404, "No se logro encontrar ningun taller en la base de datos.")

    def todos_los_cursos() -> dict:

        try:
            resp_ = list(cursos.find({}, {"_id": 1, "curso": 1, "alumnos": 1}))
        
        except:
            return json_de_mensaje(500, "Ocurrio un error en la base de datos que no se logro obtener los cursos.")

        if not resp_:
            return json_de_mensaje(404, "No se logro obtener la informacion de los cursos.")

        res_return = []

        for obj_ in resp_:

            if "alumnos" not in obj_:
                continue

            obj_['alumnos'] = len(obj_['alumnos'])
            res_return.append(obj_)

        if not res_return:
            return json_de_mensaje(404, "No se logro obtener la informacion de los cursos.")

        return json_de_mensaje(200, res_return)
    
    def todos_los_eventos() -> dict:
        
        try:
            resultado = list(eventos.find({}))
        
        except Exception as err:
            return json_de_mensaje(500, f"ERROR: No se logro listar los eventos existentes.")

        if not resultado:
            return json_de_mensaje(404)
        
        return json_de_mensaje(200, resultado)

    def obtener_informacion_rut(rut: str) -> dict:

        try:
            resultado = list(estudiantes.find({"rut": rut}))

        except:
            return json_de_mensaje(500, "No se logro obtener informacion del rut por un error.")
        
        if not resultado:
            return json_de_mensaje(404, "No se encontro el rut en la bdd.")

        return json_de_mensaje(200, resultado[0])

    @staticmethod
    def profesores_asignados(profesores_existentes: dict, curso_info: dict) -> dict:
        
        if profesores_existentes["codigo"] != 200:
            return profesores_existentes

        if "materias" not in curso_info["mensaje"]:
            return json_de_mensaje(404, "No se encontraron materias en el curso.")
        
        profesores_existentes: list = profesores_existentes["mensaje"]
        curso_info: dict = curso_info["mensaje"]
        
        profesores_asignados = [ x for x in curso_info["materias"] ]
        profesores_asignados_rt = []
        
        for profesor in profesores_existentes:

            if profesor["rut"] not in profesores_asignados:
                continue
                        
            informacion_profesor = {

                "_id": str(profesor["_id"]),
                "nombres": profesor["nombres"],
                "apellidos": profesor["apellidos"],
                "rut": profesor["rut"],
                "materia": curso_info["materias"][profesor["rut"]]
            }

            profesores_asignados_rt.append(informacion_profesor)
        
        return json_de_mensaje(200, profesores_asignados_rt)

    @staticmethod
    def obtener_informacion_curso(id_curso: str) -> dict:
        
        try:
            resultado_curso = list(cursos.aggregate([
                {"$match": {"_id": ObjectId(id_curso)}},
                {"$lookup": {
                    "from": "estudiantes",                
                    "localField": "alumnos",
                    "foreignField": "rut",          
                    "as": "alumnos_curso"              
                }},
                {"$project": {"_id": 0, "alumnos_curso._id": 0, "alumnos_curso.contrasena": 0 }}
            ]))


        except Exception as err:
            return json_de_mensaje(500, f"ERROR: No se logro obtener informacion de los cursos. {err}")
        
        if not resultado_curso:
            return json_de_mensaje(404, "No se logro encontrar ningun curso asociado al id.")


        return json_de_mensaje(200, resultado_curso[0])

    @staticmethod
    def obtener_informacion_rut_personalizado(rut: str, no_listar_key: list) -> dict:

        no_listar = {key: 0 for key in no_listar_key}

        try:
            resultado_list = list(estudiantes.find({"rut": rut}, no_listar))
        
        except:
            return json_de_mensaje(500, "ERROR: No logramos extraer la informacion de la bdd.")
        
        if not resultado_list:
            return json_de_mensaje(404, f"No se logro encontrar ningun resultado asociado al rut {rut}")

        return json_de_mensaje(200, resultado_list[0])

    @staticmethod
    def calcular_promedios_materias_y_final(informacion_estudiante: str | dict, rut: bool = False) -> dict:

        ######## Si es que necesitamos obtener la informacion del usuario por su rut
        if rut:

            resultado = General.obtener_informacion_rut(informacion_estudiante)
            if resultado["codigo"] != 200:
                return resultado
            

            if "materias" not in resultado["mensaje"]:
                return json_de_mensaje(404, "No hay materias a que calcular el promedio.")
            
            alumno_materias = resultado["mensaje"]["materias"]

        ######3 Si no se usa la variable que es dict
        else:

            if "materias" not in informacion_estudiante:
                return json_de_mensaje(404, "No hay materias a que calcular el promedio.")
            
            alumno_materias = informacion_estudiante["materias"]

        materias_promedio = []
        calc_promedio_final = []

        try:
            for materia, info_materia in alumno_materias.items(): 

                notas = []
                
                for nota in info_materia["notas"]:
                    notas.append(nota["nota"])

                promedio_final_materia = round(sum(notas) / len(notas), 1)

                calc_promedio_final.append(promedio_final_materia)
                materias_promedio.append({materia: promedio_final_materia})

            promedio_final = round(sum(calc_promedio_final) / len(calc_promedio_final), 1)       

            print(f"Promedio Final Alumno: {promedio_final} =>>> {materias_promedio}")
            
            info_retorno = {
                "materias_promedio": materias_promedio,
                "promedio_final": promedio_final
            }
        
        except Exception as err:
            return json_de_mensaje(500, f"ERROR: No se logro calcular el promedio del alumno: {err}")

        return json_de_mensaje(200, info_retorno)

class Administrador:
    """
    Clase contenedora de todas las funciones activas que\n
    utiliza y accede el Administrador.
    """
    @staticmethod
    def asignar_materias_a_profesores(formulario_json: dict):
        
        formulario_json.pop("accion")

        seguridad_ = Security.claves_existentes(["curso_informacion", "curso_id"], formulario_json)
        if not seguridad_:
            return json_de_mensaje(402, "Estas enviando un formulario incompleto o corrupto.")
        
        curso_id = formulario_json["curso_id"]
        try:
            informacion_curso = json.loads(formulario_json["curso_informacion"])
        
        except:
            return json_de_mensaje(500, "No se logro leer adecuadamente el objeto enviado.")
        
        ################## Se verifica que los ruts existan
        try:

            profesores_ruts = list(informacion_curso["materias"].keys())
            resultado = list(estudiantes.find({"rut": {"$in": profesores_ruts}}, {"_id": 0,"rut": 1}))

        except:
            return json_de_mensaje(500, "ERROR: No se logro buscar la informacion solicitada.")
        
        if not resultado:
            return json_de_mensaje(404, "No se logro encontrar ninguna informacion asociada a los ruts de profesores y estudiantes.")
        
        resultado_tmp = str(resultado)
        for rut_vf in profesores_ruts:
            
            if rut_vf in resultado_tmp:
                continue
            
            return json_de_mensaje(404, f"El rut {rut_vf} no se encuentra en la base de datos.")


        ########## SE OBTIENEN LOS ANTIGUOS PROFESORES
        resultado_curso_info = General.obtener_informacion_curso(curso_id)
        if resultado_curso_info["codigo"] != 200:
            return resultado_curso_info

        resultado_curso_info = resultado_curso_info["mensaje"]

        ##################################
        # Se le da formato a la consulta para mongo db
        informacion_curso["materias"] = { x:informacion_curso["materias"][x] for x in informacion_curso["materias"] }
        # PUEDEN HABER ERRORES A FUTURO CON LA LINEA DE ARRIBA

        ########################## VALIDACION PARA EVITAR SOBRECARGA DE DATOS O CRASHEOS INESPERADOS
        key_check: str; value_check: str
        for key_check, value_check in informacion_curso["materias"].items():
            
            # VERIFICA QUE EL NOMBBRE DE LA MATERIA CONTENGA UNICAMENTE CARCTERES ALFABETICOS
            if all(palabra.isalpha() for palabra in value_check.split(" ")):
                continue

            return json_de_mensaje(402, f"Estas enviando una materia con caracteres que no son alfabeticos: {value_check}.")

        #######################


        materias_format = {
            "materias": informacion_curso["materias"]
        }

        try:
            ######### las materias se sobreeescriben ya que en teoria siempre se envian los mismos desde el formulario
            asignar_materias = cursos.update_one({"_id": ObjectId(curso_id)}, {"$set": materias_format})
        except:
            return json_de_mensaje(500, "ERROR: Ocurrio un error al intentar crear el curso.")
        
        if not asignar_materias.acknowledged:
            return json_de_mensaje(404, "No se logro insertar completamente el curso.")

        ###############################

        seguridad_json = Security.claves_existentes(["materias"], informacion_curso)
        if not seguridad_json:
            return json_de_mensaje(402, "Estas enviando un formulario incompleto o corrupto.")

        asignar_curso_profesores = profesores_ruts.copy()

        if "materias" in resultado_curso_info:

            profesores_pre_changes = [ x for x in resultado_curso_info["materias"] ]

            eliminar_curso_adm = []

            # Itera la lista de profesores antes de la modificacion (profesores antiguos)
            for profesor_ in profesores_pre_changes:

                # Si el antiguo profesor ya no esta en la nueva lista se agrega para borrar
                if profesor_ not in profesores_ruts:
                    eliminar_curso_adm.append(profesor_)
                    continue
                
                # En caso de que este tanto en antigua como la nueva se borrara de las listas
                # para evitar duplicados
                idx = asignar_curso_profesores.index(profesor_)
                asignar_curso_profesores.pop(idx)

            
            if len(eliminar_curso_adm) >= 1:

                print(f"Desasignar profesores del curso: {eliminar_curso_adm}.")
                resultado_desasignar = Administrador.asignar_curso_a_profesor(
                    id_curso = curso_id,
                    ruts = eliminar_curso_adm,
                    unset = True
                )

                if resultado_desasignar["codigo"] != 200:
                    return resultado_desasignar

        ########### SE LE ASIGNAN LOS CURSOS A LOS PROFESORES NUEVOS

        if len(asignar_curso_profesores) >= 1:

            resultado_asignar_profesor = Administrador.asignar_curso_a_profesor(
                id_curso = curso_id,
                ruts = asignar_curso_profesores
            )

            if resultado_asignar_profesor["codigo"] != 200:
                return resultado_asignar_profesor
            
        return json_de_mensaje(200, "Profesores asignados al curso correctamente.")

    @staticmethod
    def asignar_curso_a_profesor(id_curso: str, ruts: list, unset: bool = False) -> dict:

        accion = "$pull" if unset else "$push"
        word = "elimino" if unset else "asigno"

        try:
            respuesta = estudiantes.update_many({"rut": {"$in": ruts}}, {accion: {"cursos_asignados": ObjectId(id_curso)}})
        
        except:
            return json_de_mensaje(500, f"No se logro {word} el curso a los profesores.")
        
        if not respuesta.acknowledged:
            return json_de_mensaje(404, f"No se encontraron todos los profesores a {word} el curso.")
        
        return json_de_mensaje(200, f"Se {word} el curso correctamente a los profesores.")

    @staticmethod
    def crear_curso(formulario_json: dict):
        
        formulario_json.pop("accion")

        seguridad_ = Security.claves_existentes(["grado_curso", "letra_curso", "curso_informacion"], formulario_json)
        if not seguridad_:
            return json_de_mensaje(402, "Estas enviando un formulario incompleto o corrupto.")
        
        try:
            informacion_curso = json.loads(formulario_json["curso_informacion"])
        
        except:
            return json_de_mensaje(500, "No se logro leer adecuadamente el objeto enviado.")
        
        seguridad_json = Security.claves_existentes(["materias", "alumnos"], informacion_curso)
        if not seguridad_json:
            return json_de_mensaje(402, "Estas enviando un formulario incompleto o corrupto.")
        
        if not informacion_curso["alumnos"]:
            return json_de_mensaje(402, "No hay ningun alumno asignado a este curso.")
        
        ################ SE VERIFICAN LOS RUTS QUE EXISTAN
        
        verificar_ruts = list(informacion_curso["materias"].keys())
        profesores_ruts = verificar_ruts.copy()

        verificar_ruts.extend(informacion_curso["alumnos"])

        try:
            resultado = list(estudiantes.find({"rut": {"$in": verificar_ruts}}, {"_id": 0,"rut": 1}))

        except:
            return json_de_mensaje(500, "ERROR: No se logro buscar la informacion solicitada.")
        
        if not resultado:
            return json_de_mensaje(404, "No se logro encontrar ninguna informacion asociada a los ruts de profesores y estudiantes.")
        
        resultado_tmp = str(resultado)
        for rut_vf in verificar_ruts:
            
            if rut_vf in resultado_tmp:
                continue
            
            return json_de_mensaje(404, f"El rut {rut_vf} no se encuentra en la base de datos.")

        ################## 
        # Se le da formato a la consulta para mongo db
        informacion_curso["materias"] = { x:informacion_curso["materias"][x] for x in informacion_curso["materias"] }
        ################################## PUEDEN HABER ERRORES A FUTURO CON LA LINEA DE ARRIBA

        curso_format = {
            "curso": str(formulario_json["grado_curso"] + "°" + formulario_json["letra_curso"]).lower(),
            "materias": informacion_curso["materias"],
            "alumnos": informacion_curso["alumnos"]
        }

        try:
            curso_creado = cursos.insert_one(curso_format)
        except:
            return json_de_mensaje(500, "ERROR: Ocurrio un error al intentar crear el curso.")
        
        if not curso_creado.acknowledged:
            return json_de_mensaje(404, "No se logro insertar completamente el curso.")
        
        resultado_asignar_alumno = asignar_curso_a_alumno(
            ruts = curso_format["alumnos"],
            id_curso = curso_creado.inserted_id
        )
        if resultado_asignar_alumno["codigo"] != 200:
            return resultado_asignar_alumno
        
        resultado_asignar_profesor = Administrador.asignar_curso_a_profesor(
            id_curso = curso_creado.inserted_id,
            ruts = profesores_ruts
        )
        if resultado_asignar_profesor["codigo"] != 200:
            return resultado_asignar_profesor
        return json_de_mensaje(200, "Curso creado exitosamente.")

    @staticmethod
    def asignar_curso_alumno(ruts: list, curso_id: ObjectId) -> dict:
        
        try:
            resultado = estudiantes.update_many({"rut": {"$in": ruts}, "cargo": "estudiante"}, {"$set": {"curso_actual": ObjectId(curso_id)}})

        except:
            return json_de_mensaje(500, "ERROR: No se logro asignar el curso a los estudiantes.")
        
        if not resultado.acknowledged:
            return json_de_mensaje(404, "No se les logro asignar el curso a todos.")
        
        return json_de_mensaje(200, "Se les asigno el curso correctamente a los estudiantes.")
    
    @staticmethod
    def asignar_curso_profesores(ruts: list, curso_id: ObjectId) -> dict:

        try:
            resultado = estudiantes.update_many({"rut": {"$in": ruts}}, {"$push": {"cursos_asignados": curso_id}})
        
        except:
            return json_de_mensaje(500, "ERROR: No se logro asignar el curso a los profesores.")
        
        if not resultado.acknowledged:
            return json_de_mensaje(404, "No se les logro asignar el curso a todos.")
        
        return json_de_mensaje(200, "Se les asigno el curso correctamente a los profesores.")

    def listar_profesores_talleristas() -> dict:

        try:
            profesores = list(estudiantes.find({"cargo": {"$in": ["profesor", "tallerista"]}}, {"_id": 0, "nombres": 1, "apellidos": 1, "rut": 1}))

        except:
            return json_de_mensaje(500, "Error al intentar obtener profesores y talleristas.")
        
        if not profesores:
            return json_de_mensaje(404, "No se lograron encontrar profesores.")
        
        return json_de_mensaje(200, profesores)

    def crear_usuario(informacion_json: dict) -> dict:
        
        informacion_json.pop("accion") # Se borra del diccionario la accion a realizar que envia el formulario
        no_sql_st = no_sql(informacion_json)

        if no_sql_st["codigo"] != 200:
            return no_sql_st

        if "contrasena" in informacion_json:
            informacion_json["contrasena"] = cifrar_contrasena(informacion_json["contrasena"])

        #### Si es que tiene alguna carga se le agregara
        if "carga_apoderado" in informacion_json and informacion_json["carga_apoderado"]:

            informacion_json["carga_apoderado"] = informacion_json["carga_apoderado"].split(",")

            ############## verificacion de existencia de usuarios
            try:
                coincidencia_ruts = list(estudiantes.find({"rut": {"$in": informacion_json["carga_apoderado"]}, "cargo": "estudiante"}))

            except:
                return json_de_mensaje(500, "ERROR: Fallo al intentar buscar coincidencias en el rut de cargas.")
            
            if not coincidencia_ruts:
                return json_de_mensaje(404, "No se logro encontrar ningun rut REAL para asociar a este apoderado.")
            
            ########### Asignacion de apoderado a estudiantes

            try:
                asignar_apoderado_a_estudiante = estudiantes.update_many({"rut": {"$in": informacion_json["carga_apoderado"]}, "cargo": "estudiante"}, {"$set": {"apoderado": informacion_json["rut"]}})
            
            except:
                return json_de_mensaje(500, "ERROR: No se logro asignar el apoderado a los estudiantes.")
            
            if not asignar_apoderado_a_estudiante.acknowledged:
                return json_de_mensaje(404, "No se lograron asignar el apoderado a uno o mas estudiantes.")
            

        #################

        if informacion_json["cargo"] == "estudiante":

            if "curso_id" in informacion_json:
                curso = informacion_json["curso_id"]
                informacion_json.pop("curso_id")
                
                # Se guarda en un formato con la clave correcta y se envia
                informacion_json["curso_actual"] = ObjectId(curso)

        try:
            resultados = estudiantes.insert_one(informacion_json)
        except:
            json_de_mensaje(500, "No se logro crear un nuevo usuario por un error.")

        if informacion_json["cargo"] == "estudiante":

            estudiante_curso = Administrador.asignar_estudiante_a_curso(
                rut_estudiante = informacion_json["rut"],
                id_curso = curso
            )

            if estudiante_curso["codigo"] != 200:
                return estudiante_curso
        
        if not resultados.acknowledged:
            return json_de_mensaje(400, "La base de datos no completo el registro.")
        
        return json_de_mensaje(200, f"Se ha agregado al usuario {informacion_json['rut']} con cargo {informacion_json['cargo']} exitosamente.")

    @staticmethod
    def asignar_estudiante_a_curso(rut_estudiante: str, id_curso: str) -> dict:

        try:
            resultado = cursos.update_one({"_id": ObjectId(id_curso)}, {"$push": {"alumnos": rut_estudiante}})

        except:
            return json_de_mensaje(500, "ERROR: No se logro asignar el estudiante al curso.")
        
        if not resultado.acknowledged:
            return json_de_mensaje(404, "No se logro encontrar el curso para agregar el alumno.")
        
        return json_de_mensaje(200, "Alumno agregado exitosamente.")

    def quitar_alumnos_del_taller(data_form: dict) -> dict:

        rsp_check = verificar_campos_vacios(data_form)
        if rsp_check["codigo"] != 200:
            return rsp_check

        if type(data_form["alumnos_rut"]) == str:
            data_form["alumnos_rut"] = data_form["alumnos_rut"].split(",")

        total_de_alumnos = len(data_form["alumnos_rut"])

        if total_de_alumnos <= 0:
            return json_de_mensaje(500, "Estas intentando borrar ?? 0 o menos XD.")

        try:
            respuesta_taller = talleres.update_one(
                {
                    "_id": ObjectId(data_form["id_taller"])},

                {
                    "$pull": {"inscritos": {"$in": data_form["alumnos_rut"]}}, # Los eliminamos de la lista del taller
                    "$inc": {"cupos": total_de_alumnos}
                }
            )
        
        except:
            return json_de_mensaje(500, "FATAL: No se logro eliminar los ruts desde la bdd.")
        
        if not respuesta_taller.acknowledged:
            return json_de_mensaje(404, "No se logro eliminar algun rut de la lista de alumnos a eliminar del taller.")
        
        # En esta seccion se elimina la coneccion que se tiene el taller con el alumno
        # asi mismo tambien se eliminara la lista de asistencia a este, preguntar si se debe dejar asi o no.
        try:
            respuesta_alumno = estudiantes.update_many({"rut": {"$in": data_form["alumnos_rut"]}}, {"$unset": {"taller": "xd", "lista_taller": "xd"}})

        except:
            return json_de_mensaje(500, "FATAL: Se logro eliminar el registro del taller pero no del alumno.")

        if not respuesta_alumno.acknowledged:
            return json_de_mensaje(404, "No se logro eliminar algun registro del alumno.")

        return json_de_mensaje(200, "Alumnos eliminados del taller exitosamente.")  

    def desasignar_taller_profesor(rut_profesor: str) -> dict:
        """Quita la capacidad de administrar el taller al tallerista."""

        try:
            resultado_taller = estudiantes.update_one({"rut": rut_profesor}, {"$unset": {"taller_asignado": "xd"}})

        except:
            return json_de_mensaje(500, "ERROR: No se logro quitar el rol de tallerista al profesor asignado.")

        if not resultado_taller.acknowledged:
            return json_de_mensaje(404, "No se logro encontrar al rut asociado al tallerista.")

        return json_de_mensaje(200, "Tallersita desligado del taller exitosamente.")

    def habilitar_taller(id_taller: str) -> dict:

        try:
            resultado = talleres.update_one({"_id": ObjectId(id_taller)}, {"$unset": {"deshabilitado": "xd"}})

        except:
            return json_de_mensaje(500, "ERROR: No se logro actualizar a habilitado el taller.")

        if not resultado.acknowledged:
            return json_de_mensaje(404, "No se encontro el taller a actualizar a habilitado.")
        
        return json_de_mensaje(200, "El taller se a establecido como habilitado.")

    def deshabilitar_taller(id_taller: str) -> dict:
        """Le asigna el campo "deshabilitado" a un taller para evitar que se muestre en listados. No se elimina de la base de datos."""
        informacion_taller = General.obtener_informacion_taller(id_taller)

        # Verifica si la respuesta al obtener el taller fue exitosa (código 200). Si no, retorna el error recibido.
        if informacion_taller["codigo"] != 200:
            return informacion_taller


        # Si el taller tiene alumnos inscritos, se procede a quitarlos del taller.
        if "inscritos" in informacion_taller["mensaje"] and len(informacion_taller["mensaje"]["inscritos"]) != 0:    
            # Se extraen los RUT de los alumnos inscritos.
            alumnos_rut = [x["rut"] for x in informacion_taller["mensaje"]["inscritos"]]

            # Se llama a la función que quita a los alumnos del taller.
            alumnos_quitados = Administrador.quitar_alumnos_del_taller({"alumnos_rut": alumnos_rut, "id_taller": id_taller})
            
            # Si hubo un error al quitar alumnos, se retorna dicho error.
            if alumnos_quitados["codigo"] != 200:
                return alumnos_quitados

        # Si hay un profesor asignado al taller, se procede a desasignarlo.
        if "profesor_rut" in informacion_taller["mensaje"] and informacion_taller["mensaje"]["profesor_rut"] != "":
            # Se llama a la función que desasigna al profesor del taller.
            profesor_resultado = Administrador.desasignar_taller_profesor(informacion_taller["mensaje"]["profesor_rut"])
            
            # Si hubo un error al desasignar al profesor, se retorna dicho error.
            if profesor_resultado["codigo"] != 200:
                return profesor_resultado

        # Intenta actualizar el documento del taller en la base de datos, marcándolo como deshabilitado.
        try:
            resultado_des = talleres.update_one({"_id": ObjectId(id_taller)}, {"$set": {"deshabilitado": True}})
        except:
            # Si ocurre una excepción durante la actualización, se retorna un error 500.
            return json_de_mensaje(500, "ERROR: No se logró deshabilitar el taller.")

        # Verifica si la operación fue reconocida por MongoDB. Si no, retorna error 404.
        if not resultado_des.acknowledged:
            return json_de_mensaje(404, "No se logró modificar el estado del taller.")

        # Si todo fue exitoso, retorna un mensaje de éxito.
        return json_de_mensaje(200, "Taller deshabilitado correctamente.")

    def aceptar_alumnos(data_form: dict) -> dict:
        
        rsp_check = verificar_campos_vacios(data_form)
        if rsp_check["codigo"] != 200:
            return rsp_check
        
        data_form["alumnos_rut"] = data_form["alumnos_rut"].split(",")
        total_de_alumnos = len(data_form["alumnos_rut"])

        # Si hay mas alumnos de los cupos suficientes se retorna error.
        if int(data_form["cupos"]) - total_de_alumnos < 0:
            return json_de_mensaje(500, "No hay suficientes cupos para todos.")

        try:
            resultado = talleres.update_one(
                {
                    "_id": ObjectId(data_form["id_taller"])}, # Modificamos el taller con el id asignado
                {
                    "$pull": {"lista_espera": {"$in": data_form["alumnos_rut"]}}, # Los borramos de la lista_espera
                    "$push": {"inscritos": {"$each": data_form["alumnos_rut"]}}, # Insertamos dentro de inscritos
                    "$inc": {"cupos": -total_de_alumnos}
                }
            )

        except:
            return json_de_mensaje(500, "ERROR FATAL: No se logro modificar la base de datos del taller designado.")
        
        if not resultado.acknowledged:
            return json_de_mensaje(404, "No se logro modificar correctamente el taller.")
        
        try:
            resultado_alumnos = estudiantes.update_many({"rut": {"$in": data_form["alumnos_rut"]}}, {"$set": {"taller": ObjectId(data_form["id_taller"])}})
        
        except:
            return json_de_mensaje(500, "ERROR FATAL: No se logro asignar los talleres a los alumnos.")
        
        if not resultado_alumnos.acknowledged:
            return json_de_mensaje(404, "No se logro modificar todos completamente por lo que no se asigno completamente.")
        
        return json_de_mensaje(200, "Taller asignado correctamente a los alumnos seleccionados.")

    def crear_taller(informacion_taller: dict) -> dict:
        
        no_sql_st = no_sql(informacion_taller)

        if no_sql_st["codigo"] != 200:
            return no_sql_st
        
        respuesta_validacion = Security.form_validator("crear_taller", informacion_taller)
        if respuesta_validacion["codigo"] != 200:
            return respuesta_validacion

        # El dict trae los cupos como numeros en str por eso se tienen que transformar
        informacion_taller["cupos"] = int(informacion_taller["cupos"])

        informacion_profesor = General.obtener_informacion_rut(informacion_taller["profesor_rut"])
        
        if informacion_profesor["codigo"] != 200:
            return json_de_mensaje(500, "Esta ocurriendo un error que no permite asociar el rut del tallerista o profesor al taller.")
        
        informacion_taller["profesor_nombre"] = informacion_profesor["mensaje"]["nombres"] + " " + informacion_profesor["mensaje"]["apellidos"]

        try:
            respuesta = talleres.insert_one(informacion_taller)
        
        except:
            return json_de_mensaje(500, "ERROR: No se logro crear ningun taller.")

        if not respuesta.acknowledged:
            return json_de_mensaje(404, "No se logro encontrar donde insertar el nuevo taller.")
        
        # Agregar control de errores a todos los procesos con la BDD y limpieza y contencion de campos
        profesor_asignar_taller = estudiantes.update_one({"rut": informacion_taller["profesor_rut"]}, {"$set": {"taller_asignado": respuesta.inserted_id}})
        
        if not profesor_asignar_taller.acknowledged:
            return json_de_mensaje(404, "No se logro encontrar el rut del profesor a asignar el taller.")

        return json_de_mensaje(200, "Taller creado exitosamente.")

    def marcar_mensaje_como_visto(id_del_mensaje: str) -> dict:

        try:
            respuesta = contacto.update_one({"_id": ObjectId(id_del_mensaje)}, {"$set": {"visto": True}})
        except:
            return json_de_mensaje(500, "Ocurrio un error. No se logro marcar como visto a la solicitud de mensaje.")
        
        if not respuesta.acknowledged:
            return json_de_mensaje(404, "No se logro encontrar el id a marcar como visto.")

        return json_de_mensaje(200, "Se marco como visto correctamente.")

    def eliminar_mensaje(id_del_mensaje: str) -> dict:

        try:
            respuesta = contacto.delete_one({"_id": ObjectId(id_del_mensaje)})
        
        except:
            return json_de_mensaje(500, "Ocurrio un error al intentar eliminar el mensaje.")
        
        if not respuesta.acknowledged:
            return json_de_mensaje(404, "No se logro encontrar el id a eliminar en la base de datos.")
        
        return json_de_mensaje(200, f"El ID {id_del_mensaje} ha sido eliminado correctamente.")

    def listar_mensajes(vistos: int) -> dict:
        """Listar mensajes aun no leidos: 0, Marcar los leidos: 1"""

        try:
            resultado = list(contacto.find({"visto": {"$exists": vistos}})) # Devuelve solamente los que aun no se han visto
        except:
            return json_de_mensaje(500, "Ocurrio un error inesperado obteniendo los mensajes.")

        if not resultado:
            return json_de_mensaje(404, "No se logro encontrar ninguna persona a contactar.")
        
        return json_de_mensaje(200, resultado)

    def subir_profesores(excel_form_files: bytes) -> dict:

        profesores_columnas = [
            "rut",
            "dv",
            "apellido_paterno",
            "apellido_materno",
            "nombres",
            "sexo",
            "fecha_nacimiento",
            "estado_civil",
            "direccion",
            "telefono",
            "celular",
            "email",
            "cargo",
            "col_14",
            "col_15",
            "col_16",
            "direccion_completa",
            "estado"
        ]

        normalizado = Security.leer_normalizar_base_datos(
            excel_form_files = excel_form_files,
            nombres_keys = profesores_columnas
        )

        if normalizado["codigo"] != 200:
            return normalizado
        
        normalizado: list = normalizado["mensaje"]
        normalizado.pop(0) ######### Se borra la plantilla 0 es decir los nombres mal hechos del XLS

        try:
            profesores = []
            for profesor in normalizado:
                profesor: dict

                profesor_tmp = {}

                profesor_tmp["rut"] = profesor["rut"] + "-" + profesor["dv"]
                profesor_tmp["contrasena"] = cifrar_contrasena(profesor_tmp["rut"][:4])
                profesor_tmp["nombres"] = profesor["nombres"]
                profesor_tmp["apellidos"] = (profesor["apellido_paterno"] or "") + " " + (profesor["apellido_materno"] or "")
                profesor_tmp["cargo"] = "profesor"

                profesores.append(profesor_tmp)

        except Exception as err:
            return json_de_mensaje(500, f"ERROR: No se esta normalizando correctamente la integracion del excel a JSON: {err}")
        
        try:
            result_del = estudiantes.delete_many({"cargo": "profesor"})
            if not result_del.acknowledged:
                return json_de_mensaje(500, "No se estan borrando los profesores antiguos de la base de datos.")
            
            result_add = estudiantes.insert_many(profesores)
            if not result_add.acknowledged:
                return json_de_mensaje(500, "No se estan insertando los nuevos profesores en la base de datos.")
        
        except Exception as err:
            return json_de_mensaje(500, f"ERROR: El codigo no se esta comportando de la manera adecuada: {err}")
    
        return json_de_mensaje(200, f"La base de datos de profesores a sido renovada.")

        ########################## LOGICA DE COMPATIBILIDAD CON PROFESORES XD

    def nuevo_ano(excel_form_files: bytes) -> dict:

        ############## Se lee y se retorna la base de datos ya limpia -- en keys -- y sanitizada
        normalizacion = Security.leer_normalizar_base_datos(excel_form_files)
        if normalizacion["codigo"] != 200:
            return normalizacion
        
        normalizacion = normalizacion["mensaje"]

        ######################################## COMPATIBILIZA LA BDD PARA LAS COLECCIONES DE ALUMNOS
        bdd_estudiantes = []
        bdd_cursos = {}

        for estudiante_nrm in normalizacion:

            estudiante_tmp = {}
            for key, value in estudiante_nrm.items():

                
                """
                ESTA SECCION SE MOVIO HACIA Security.normalizar_base_datos()
                for char_ in key:

                    if char_ not in "qwertyuiopasdfghjklñzxcvbnm_":
                        key = key.replace(char_, "")"""


                if key in ["run", "digito_ver"]:

                    if "rut" in estudiante_tmp:
                        continue

                    value = str(estudiante_nrm["run"]) + "-" + str(estudiante_nrm["digito_ver"])
                    estudiante_tmp.setdefault("rut", value)

                    ############################### Contraseña plataforma
                    contrasena = value[:4]
                    contrasena = cifrar_contrasena(contrasena)

                    estudiante_tmp.setdefault("contrasena", contrasena)

                    ############################### Se le asigna el cargo estudiante

                    estudiante_tmp.setdefault("cargo", "estudiante")

                    ############ Se verifica que los campos necesarios para realizar la creacion o agregacion del curso existan
                    if any(x not in estudiante_nrm for x in ["desc_grado", "letra_curso", "cod_grado"]):
                        print(f"El rut {value} no tiene todos los parametros para ser incluido en un curso.")
                        continue

                    curso_str = estudiante_nrm.get("desc_grado")
                    curso_letra = estudiante_nrm.get("letra_curso")

                    curso = curso_str + " " + curso_letra

                    if curso not in bdd_cursos:
                        bdd_cursos.setdefault(curso, {"alumnos": []})

                    bdd_cursos[curso]["alumnos"].append(value)

                
                elif key in ["apellido_materno", "apellido_paterno"]:

                    if "apellidos" in estudiante_tmp:
                        continue
                    
                    apellido_paterno = estudiante_nrm.get("apellido_paterno")
                    apellido_materno = estudiante_nrm.get("apellido_materno")

                    value = (apellido_paterno or "") + " " + (apellido_materno or "")
                

                    estudiante_tmp.setdefault("apellidos", value)

                else:
                    estudiante_tmp.setdefault(key, value)

            bdd_estudiantes.append(estudiante_tmp)


        ####################### Se normaliza el objeto de los cursos para su subida correctamente

        cursos_upload = []
        for curso_ in bdd_cursos:

            json_curso = {
                "curso": curso_,
                "alumnos": bdd_cursos[curso_]["alumnos"]
            }

            cursos_upload.append(json_curso)

        
        try:

            ########## SE BORRAN TODOS LOS EVENTOS
            eventos.delete_many({})

            ########## SE BORRAN TODOS LOS CURSOS Y ESTUDIANTES
            cursos.delete_many({})
            estudiantes.delete_many({"cargo": "estudiante"})
            
            ########## SE LE BORRAN LOS CURSOS ASIGNADOS A LOS PROFESORES
            estudiantes.update_many({"cursos_asignados": {"$exists": 1}}, {"$unset": {"cursos_asignados": ""}})

            ########## SE INSERTAN LOS NUEVOS CURSOS EN LA PLATAFORMA Y BASE DE DATOS
            resultado_cursos_id = cursos.insert_many(cursos_upload)

            ########## SE INSERTAN LOS NUEVOS ESTUDIANTES
            estudiantes.insert_many(bdd_estudiantes)

            ########## SE USAN LOS IDS RECIEN INSERTADOS de CURSOS PARA OBTENER LA LISTA DE ALIMNOS A SU VEZ INSERTARLES LOS DOCUMENTOS
            cursos_creados = list(cursos.find({"_id": {"$in": resultado_cursos_id.inserted_ids}}))            
            operaciones_actualizar_estudiantes = []

            for curso_creado in cursos_creados:
                
                operaciones_actualizar_estudiantes.append(
                    UpdateMany(
                        {"rut": {"$in": curso_creado["alumnos"]}},
                        {"$set": {"curso_actual": curso_creado["_id"]}}
                    )
                )

            ########## SE EJECUTA EL ACTUALIZAR DOCUMENTOS SOBRE LOS ESTUDIANTES
            estudiantes.bulk_write(operaciones_actualizar_estudiantes)

        except Exception as err:
            return json_de_mensaje(500, f"ERROR: La base de datos no esta siendo procesada. {err}")

        return json_de_mensaje(200, "Nuevo año asignado correctamente. Porfavor asigna los profesores.")

    def crear_evento(formulario_crear_evento: dict) -> dict:

        valido_ = Security.form_validator("crear_evento", formulario_crear_evento)
        if valido_["codigo"] != 200:
            return valido_
        

        fecha_evento = formulario_crear_evento["fecha_evento"]
        titulo = formulario_crear_evento["titulo"]
        descripcion = formulario_crear_evento["descripcion"]        

        fecha_evento = datetime.strptime(fecha_evento, "%Y-%m-%d")
        fecha_evento = fecha_evento.strftime("%d-%m-%Y")

        creacion_evento_format: dict = {
            "fecha_evento": fecha_evento,
            "titulo": titulo,
            "descripcion": descripcion
        }

        try:
            resultado = eventos.insert_one(creacion_evento_format)
        
        except Exception as err:
            return json_de_mensaje(500, f"ERROR: No se logro insertar el evento de manera adecuada: {err}")

        if not resultado.acknowledged:
            return json_de_mensaje(404, "ERROR: No se logro insertar el nuevo evento en la base de datos.")
        
        return json_de_mensaje(200, "Evento creado e insertado en la base de datos correctamente.")

class Profesor:
    """
    Funciones que utiliza el perfil de Profesor y sus dependencias.
    """
    @staticmethod
    def listar_cursos_de_profesor(rut_de_profesor) -> dict:
        
        try:
            respuesta = list(estudiantes.aggregate([
                {"$match": {"rut": rut_de_profesor}},
                {"$lookup": {
                    "from": "cursos",                
                    "localField": "cursos_asignados",
                    "foreignField": "_id",          
                    "as": "cursos_informacion"              
                }},
                {"$project": {
                    "_id": 0,
                    "contrasena": 0,
                    "cursos_asignados": 0,
                    "cursos_informacion.alumnos": 0,
                }}
            ]))

        except:
            return json_de_mensaje(500, "Error: No se logro obtener la lista desde la base de datos.")
        
        if not respuesta:
            return json_de_mensaje(404, f"No se logro encontrar ningun curso asociado al rut {rut_de_profesor}.")
        
        respuesta = respuesta[0]
        for curso in respuesta["cursos_informacion"]:

            if "materias" not in curso:
                continue

            if rut_de_profesor not in curso["materias"]:
                continue

            idx = respuesta["cursos_informacion"].index(curso)
            respuesta["cursos_informacion"][idx]["_id"] = str(respuesta["cursos_informacion"][idx]["_id"])

            try:
                respuesta["cursos_informacion"][idx]["materias"] = {rut_de_profesor: curso["materias"][rut_de_profesor]}

            except:
                json_de_mensaje(500, "Borrando curso sin rut")
            

        return json_de_mensaje(200, respuesta)

    def listar_taller_de_profesor(rut_de_profesor) -> dict:

        try:
            taller_asignado_id = General.obtener_informacion_rut(rut_de_profesor)

        except:
            return json_de_mensaje(500, "Error: BDD no respondio al buscar profesor a cargo del taller por rut.")
        
        if taller_asignado_id["codigo"] != 200:
            return taller_asignado_id
        
        if "taller_asignado" not in taller_asignado_id["mensaje"]:
            return json_de_mensaje(404, "No te encuentras a cargo de ningun taller.")
        
        try:
            resultado = list(talleres.find({"_id": taller_asignado_id["mensaje"]["taller_asignado"]}))

        except:
            return json_de_mensaje(500, "ERROR: No se logro encontrar nignun id de taller asociado a tu rut.")
        
        if not resultado:
            return json_de_mensaje(404, "No estas a cargo de ningun taller.")

        if "inscritos" in resultado[0] and resultado[0]["inscritos"]:
            
            nombres_alumnos = General.obtener_nombre_de_inscritos_taller(resultado[0]["inscritos"])
            
            if nombres_alumnos["codigo"] != 200:
                return nombres_alumnos
                
            resultado[0]["inscritos"] = nombres_alumnos["mensaje"]

        return json_de_mensaje(200, resultado[0])

    """Falta asignar una validacion de notas decimales y que no esten vacias"""
    def asignar_nota_taller(data_form: dict) -> dict:

        chk_keys = data_form.keys()
        error = False
        error_ruts = []

        for key in chk_keys:

            nota: str = data_form[key]
            rut: str = key.replace("alumno_rut_nota_", "")

            if "alumno_rut_nota_" not in key:
                continue

            if not nota:
                error = True
                error_ruts.append(rut)
                continue

            # AGREGAR VALIDACION DE NUMEROS DECIMALES
            
            try:
                estudiantes.update_one({"rut": rut}, {"$set": {"nota_taller": nota}})

            except:
                error = True
                error_ruts.append(rut)
            
        if error:
            return json_de_mensaje(500, f"No se logro asignar la nota correctamente a {len(error_ruts)} alumnos. Ruts de los alumnos: {','.join(error_ruts)}")

        return json_de_mensaje(200, "Se asigno la nota correctamente al alumno")

    def pasar_lista_taller(data_form: dict) -> dict:
        """Les asigna la fecha exacta en la que asistieron los estudiantes al taller. Lista."""

        if data_form["alumnos_rut"] == "":
            return json_de_mensaje(404, "No se pueden entregar formularios vacios.")

        alumnos_rut = data_form["alumnos_rut"].split(",")
        fecha_lista = obtener_fecha()

        try:
            resultado = estudiantes.update_many(
                {
                    "rut": {"$in": alumnos_rut}}, # Modificamos el taller con el id asignado
                {
                    "$push": {"lista_taller": fecha_lista}, # Insertamos dentro de inscritos
                }
            )
        
        except:
            return json_de_mensaje(500, "ERROR: No logramos dejar presente a los alumnos asistentes.")
        
        if not resultado.acknowledged:
            return json_de_mensaje(404, "No se logro dejar a todos presentes.")
        
        return json_de_mensaje(200, f"Los {len(alumnos_rut)} estudiantes han quedado presentes en la fecha {fecha_lista}.")

    def asignar_notas(data_form: dict) -> dict:

        data_form.pop("accion")

        resultado_seguridad = Security.claves_existentes(
            claves = ["payload_json"],
            formulario = data_form
        )
        if not resultado_seguridad:
            return json_de_mensaje(402, "El formato de tu formulario no cumple con lo esperado.")
        
        ##########
        materia_notas = Security.str_to_json(data_form["payload_json"])
        if materia_notas["codigo"] != 200:
            return materia_notas
        
        materia_notas = materia_notas["mensaje"]

        resultado_check = Security.claves_existentes(["materia", "notas"], materia_notas)
        if not resultado_check:
            return json_de_mensaje(402, "El formato de tu formulario no cumple con lo esperado.")
        
        nombre_materia = materia_notas["materia"]
        nombre_evaluacion = materia_notas["notas"]["nombre_prueba"]

        if "notas_alumnos" not in materia_notas["notas"]:
            return json_de_mensaje(402, "El formato de tu formulario no cumple con lo esperado.")
        
        notas_alumnos: list = materia_notas["notas"]["notas_alumnos"]

        operacion_actualizar = []
        for obj_tmp in notas_alumnos:

            for rut, nota in obj_tmp.items():

                operacion_actualizar.append(
                    UpdateOne(
                        {"rut": rut},
                        {"$push": {f"materias.{nombre_materia}.notas": {"nombre_evaluacion": nombre_evaluacion, "nota": Security.str_to_float(nota)}}}
                    )
                )

        try:
            respuesta_ = estudiantes.bulk_write(operacion_actualizar)
        except Exception as err:
            return json_de_mensaje(500, f"Oucrrio un error inesperado. Contactar al administrador o encargado de informatica. Linea 1306. {err}")
        
        if not respuesta_.acknowledged:
            return json_de_mensaje(404, "No se logro modificar a los estudiantes del curso sus notas.")
        
        return json_de_mensaje(200, "Notas asignadas a los alumnos correctamente.")

    def pasar_lista(data_form: dict) -> dict:

        data_form.pop("accion")

        if "payload_json" not in data_form:
            return json_de_mensaje(402, "El formulario que estas enviando esta incompleto o corrupto.")
        
        resultado_json = Security.str_to_json(data_form["payload_json"])
        if resultado_json["codigo"] != 200:
            return resultado_json
        
        resultado_json = resultado_json["mensaje"] #### ESTO ES PORQUE RETORNA UN DICT CON CODIGO Y MENSAJE
        resultado_sec = Security.claves_existentes(["materia", "alumnos_presentes"], resultado_json)
        if not resultado_sec:
            return json_de_mensaje(402, "Estas enviando un json incompleto.")
        
        materia = resultado_json["materia"]
        alumnos_presentes = resultado_json["alumnos_presentes"]

        if not alumnos_presentes:
            return json_de_mensaje(402, "Estas enviando una lista de estudiantes vacia.")

        operacion_actualizar = []
        fecha_actual = obtener_fecha()
        
        try:
            for alumno in alumnos_presentes:

                operacion_actualizar.append(
                    UpdateOne(
                        {"rut": alumno},
                        {"$push": {
                            f"materias.{materia}.asistencia": fecha_actual}}
                    )
                )

        except Exception as err:
            return json_de_mensaje(500, f"Ocurrio un error: {err}.")

        try:
            respuesta_ = estudiantes.bulk_write(operacion_actualizar)
        except Exception as err:
            return json_de_mensaje(500, f"Oucrrio un error inesperado. Contactar al administrador o encargado de informatica. Linea 1306. {err}")
        
        if not respuesta_.acknowledged:
            return json_de_mensaje(404, "No se logro modificar a los estudiantes del curso sus notas.")
        

        return json_de_mensaje(200, f"Se ha dejado presentes a un total de {len(alumnos_presentes)} en {materia}.")

class Noticiero:
    """Funciones que corresponden al uso del Noticiero."""

    def listar_alertas() -> dict:

        try:
            resultados = list(noticias.find({"tipo": "alerta"}))
        except:
            return json_de_mensaje(500, "Ocurrio un error al tratar de obtener las alertas.")
        
        if not resultados:
            return json_de_mensaje(404, "No se logro encontrar ninguna alerta en la base de datos.")
        
        return json_de_mensaje(200, resultados)

    def listar_noticias() -> dict:

        try:
            resultados = list(noticias.find({"tipo": "noticia"}))
        except:
            return json_de_mensaje(500, "Ocurrio un error al tratar de obtener las noticias.")
        
        if not resultados:
            return json_de_mensaje(404, "No se logro encontrar ninguna noticia en la base de datos.")
        
        return json_de_mensaje(200, resultados)

    def crear_noticia(titulo, descripcion, request_file_form) -> dict:

        fecha = obtener_fecha()
        query_insert = {
            "titulo": titulo,
            "descripcion": descripcion,
            "imagen": "",
            "fecha_publicacion": fecha,
            "tipo": "noticia"
            }

        no_sql_st = no_sql(query_insert)

        if no_sql_st["codigo"] != 200:
            return no_sql_st

        resultado_imagen = guardar_imagen("noticias", "imagen", request_file_form)

        if resultado_imagen["codigo"] == 200:
            query_insert["imagen"] = obtener_path_normalizado(resultado_imagen["mensaje"])

        try:
            resultado = noticias.insert_one(query_insert)
        
        except:
            return json_de_mensaje(500, "Ocurrio un error donde no se logro insertar la noticia.")
        
        if not resultado.acknowledged:
            return json_de_mensaje(500, "No se logro insertar la noticia segun la base de datos.")
        
        return json_de_mensaje(200, "La noticia se ha insertado con exito.")

    def crear_alerta(titulo, descripcion) -> dict:

        no_sql_st = no_sql({"titulo": titulo, "descripcion": descripcion})

        if no_sql_st["codigo"] != 200:
            return no_sql_st

        try:
            fecha = obtener_fecha()
            resultado = noticias.insert_one({"titulo": titulo, "fecha_publicacion": fecha, "descripcion": descripcion, "tipo": "alerta"})
        except:
            return json_de_mensaje(500, "Ocurre un error que impide la creacion de alertas.")

        if not resultado.acknowledged:
            return json_de_mensaje(500, "Error interno de la base de datos. No se logro insertar la noticia.")

        return json_de_mensaje(200, "Noticia de tipo alerta creada exitosamente.")

    def eliminar_noticia(id_noticia) -> dict:

        try:
            resultado = noticias.delete_one({"_id": ObjectId(id_noticia)})
        except:
            return json_de_mensaje(500, "No se logro eliminar la noticia producto de un error en el sistema.")
        
        if not resultado.acknowledged:
            return json_de_mensaje(404, "La base de datos no borro la noticia del sitema.")

        return json_de_mensaje(200, "La noticia se borro correctamente.")

    def modificar_noticia(informacion_en_dict: dict, files_en_dict: dict) -> dict:
        
        set_query = {
            "titulo": informacion_en_dict["titulo"],
            "descripcion": informacion_en_dict["descripcion"]
        }

        no_sql_st = no_sql(set_query)

        if no_sql_st["codigo"] != 200:
            return no_sql_st
        
        resultado_guardar = guardar_imagen("noticias", "imagen", files_en_dict)

        if resultado_guardar["codigo"] == 200:
            set_query.setdefault("imagen", resultado_guardar["mensaje"])

        try:
            resultado = noticias.update_one({"_id": ObjectId(informacion_en_dict["id_noticia"])},
                {"$set": set_query})
        except:
            return json_de_mensaje(500, "Un error ocurrio y no se logro modificar la noticia correctamente.")
        
        if not resultado.acknowledged:
            return json_de_mensaje(400, "La base de datos no encontro la noticia a modificar.")

        return json_de_mensaje(200, "La noticia se ha modificado correctamente.")

class Estudiante:
    """
    Funciones correspondientes al rol de\n
    Estudiante.
    """

    def inscripcion_de_taller(rut, id_taller) -> dict:

        no_sql_st = no_sql({"rut": rut, "id_taller": id_taller})

        if no_sql_st["codigo"] != 200:
            return no_sql_st


        ############## Verificar cupos
        try:
            respuesta_cupos = list(talleres.find({"_id": ObjectId(id_taller)}))

        except:
            return json_de_mensaje(500, "ERROR: No se logro obtener informacion del taller")
        
        if not respuesta_cupos:
            return json_de_mensaje(404, "No se logro encontrar ningun taller asociado al id seleccionado.")
        
        if respuesta_cupos[0]["cupos"] < 1:
            return json_de_mensaje(404, "Lo sentimos. No hay cupos disponibles para este taller.")

        ############## 


        try:
            respuesta_solicitud = talleres.update_one({"_id": ObjectId(id_taller)}, {"$push": {"lista_espera": rut}})

        except:
            return json_de_mensaje(500, "Ocurrio un error, no se logro solicitar el cupo en el taller.")
        
        if not respuesta_solicitud.acknowledged:
            return json_de_mensaje(404, "No se logro solicitar un cupo.")
        
        # Ver como contener posibles errores <====================
        resultado_espera = estudiantes.update_one({"rut": rut}, {"$set": {"taller": "espera"}})

        if not resultado_espera.acknowledged:
            return json_de_mensaje(404, "No se logro modificar su estado de espera en un taller.")

        return json_de_mensaje(200, "Usted a sido puesto en lista de espera para el taller.")

    def verificaicon_taller(rut: str) -> dict:
        """Funcion encargada de verificar el estado del alumno en su taller por rut."""

        try:
            resultado_taller_estudiante = list(estudiantes.find({"rut": rut}, {"_id": 0, "contrasena": 0}))

        except:
            return json_de_mensaje(500, "Error, no se logro verificar si estas en un taller o no.")
        
        if not resultado_taller_estudiante:
            return json_de_mensaje(404, "No se logro encontrar ningun estudiante asociado a tu rut.")
        
        # Si no existe taller en el diccionario es porque no existe asociado en ningun taller
        if "taller" not in resultado_taller_estudiante[0]:
            return json_de_mensaje(200, "El usuario no esta en ningun taller.")

        # Si esta en espera se le envia notificando que esta en espera
        if resultado_taller_estudiante[0]["taller"] == "espera":
            return json_de_mensaje(400, "No te puedes inscribir en un taller porque ya estas en espera.")

        ######################### Obtener informacion del taller tipo asistentes

        try:
            resultado_taller = General.obtener_informacion_taller(resultado_taller_estudiante[0]["taller"])

        except:
            return json_de_mensaje(500, "ERROR: No se logro obtener la informacion del taller.")
        
        if resultado_taller["codigo"] != 200:
            return resultado_taller
        
        resultado_taller_estudiante[0]["taller"] = resultado_taller["mensaje"]
        
        print(resultado_taller_estudiante[0])

        return json_de_mensaje(202, resultado_taller_estudiante[0])
    
    def resumen_de_mi_perfil(rut: str) -> dict:

        rut_informacion = General.obtener_informacion_rut(rut)
        if rut_informacion["codigo"] != 200:
            return rut_informacion    

        if "taller" in rut_informacion["mensaje"]:
            
            if rut_informacion["mensaje"]["taller"] != "espera":

                informacion_taller = General.obtener_informacion_taller(rut_informacion["mensaje"]["taller"])
                
                if informacion_taller["codigo"] != 200:
                    return informacion_taller

                rut_informacion["mensaje"]["taller"] = informacion_taller["mensaje"]
        
        if "apoderado" in rut_informacion["mensaje"]:
            apoderado_info = General.obtener_informacion_rut(rut_informacion["mensaje"]["apoderado"])
            
            if apoderado_info["codigo"] != 200:
                return apoderado_info

            rut_informacion["mensaje"]["apoderado"] = apoderado_info["mensaje"]
            

        print(rut_informacion["mensaje"])

        return json_de_mensaje(200, rut_informacion["mensaje"])

class Public:
    """
    Acciones/funciones que se utilizan de manera publica.
    """

    def nuevo_mensaje(informacion_del_contacto: dict) -> dict:

        validacion = Security.form_validator("contactanos", informacion_del_contacto)

        if validacion["codigo"] != 200:
            return validacion

        try:
            resultado = contacto.insert_one(informacion_del_contacto)
        except:
            return json_de_mensaje(500, "Ocurrio un error inesperado. Contacta con el administrador.")

        if not resultado.acknowledged:
            return json_de_mensaje(404, "No se encontro ningun lugar donde almacenar tus datos.")
        
        return json_de_mensaje(200, "Se ha enviado tu informacion de contacto. Pronto nos pondremos en contacto contigo.")

    def obtener_ultima_alerta() -> dict:

        try:
            resultados = list(noticias.aggregate([{"$match": {"tipo": "alerta"}}, {"$sort": {"_id": -1}}, {"$limit": 1}, {"$project": {"_id": 0, "tipo": 0}}]))
        except:
            return json_de_mensaje(500, "Ocurrio un error interno que no se logro obtener la ultima alerta.")
        
        if not resultados:
            return json_de_mensaje(404, "No se encontraron alertas que mostrar.")
        
        return json_de_mensaje(200, resultados[0])

    def obtener_ultimas_noticias() -> dict:

        try:
            resultados = list(noticias.aggregate([{"$match": {"tipo": "noticia"}}, {"$sort": {"_id": -1}}, {"$limit": 10}, {"$project": {"_id": 0}}]))
        
        except:
            json_de_mensaje(500, "Ocurrio un error, no se lograron obtener las noticias.")

        if not resultados:
            return json_de_mensaje(404, "No se logro encontrar ninguna noticia.")
        
        return json_de_mensaje(200, resultados)
    
    def listar_noticias_home() -> dict:
        """Retrona las noticias en formato de vista previa para el home."""

        try:
            resultado = list(noticias.aggregate([
                {"$match": {"tipo": "noticia"}},
                {"$sort": {"_id": -1}},
                {"$limit": 3},
                {"$project": {"_id": 0, "tipo": 0}}
            ]))

        except:
            return json_de_mensaje(500, "ERROR: No se logro obtener las ultimas 3 noticias.")
        
        if not resultado:
            return json_de_mensaje(404, "No se lograron encontrar las ultimas noticias.")
        
        # Formatea la descripcion a un limite de 48 caracteres para una vista adecuada en el frontend
        for noticia in resultado:

            inx = resultado.index(noticia)
            resultado[inx]["descripcion"] = noticia["descripcion"][:48] + " ..."

        return json_de_mensaje(200, resultado)

    def iniciar_sesion(usuario, contrasena) -> dict:
        """Se busca una coincidencia entre contraseñas en la base de datos"""

        # Esta linea es unicamente de DEBUG y developer. Una vez en la nuve se debera
        # crear un usuario administrador el cual tendra un rut asociado.

        valid = [
            Security.re_search(
                "1234567890-k",
                7, 12,
                usuario
            ),
            Security.re_search(
                Security.alph + Security.num + Security.spc,
                4, 20,
                contrasena
            )
        ]

        if not all(valid):
            return json_de_mensaje(402, "Estas enviando parametros o logitudes no permitidas.")

        no_sql_str = no_sql({"usuario": usuario, "contrasena": contrasena})

        if no_sql_str["codigo"] != 200:
            return no_sql_str

        try:
            resultado = list(estudiantes.find(
                {
                    "rut": usuario, 
                    "contrasena": cifrar_contrasena(contrasena)
                },
                ############## LO QUE ES SENSIBLE VA AQUI ABAJO, Y LO QUE CONTIENE OBJECTID 
                {
                    "_id": 0,
                    "contrasena": 0,
                    "cursos_asignados": 0,
                    "taller_asignado": 0,
                    "taller": 0,
                    "curso_actual": 0
                }
            ))

        except:
            return json_de_mensaje(500, "Ocurrio un error al buscar en la base de datos un usuario o contraseña.")
        
        if not resultado:
            return json_de_mensaje(404, "Usuario o contraseña no coinciden con ninguna en la base de datos.")

        return json_de_mensaje(200, resultado[0])

#################### Seccion Profesor Jefe -- NO INCLUIDO -- Ahora el ADMINISTRADOR crea cursos

def crear_curso_jefe(formulario: dict, profesor_jefe: str, profesor_jefe_rut: str) -> dict:
    
    alumnos_rut = formulario["alumnos_rut"]
    profesores_rut = formulario["profesores_rut"]

    # Primero se verifica si es que el navegador envio o no una lista, si no es asi se transforma a list
    if type(alumnos_rut) != list:
        alumnos_rut = alumnos_rut.split(",")
        formulario["alumnos_rut"] = alumnos_rut

    if type(profesores_rut) != list:
        profesores_rut = profesores_rut.split(",")
        formulario["profesores_rut"] = profesores_rut
        
    # Luego asignamos las claves de nombre del profesor y su rut para identificarlos dentro de la bdd
    formulario["profesor_jefe"] = profesor_jefe
    formulario["profesor_jefe_rut"] = profesor_jefe_rut
    
    # Finalmente realizamos el intento de insertar o crear un nuevo curso
    try:
        resultado = cursos.insert_one(formulario)

    except:
        return json_de_mensaje(500, "Error, no se logro crear el curso.")
    
    if not resultado.acknowledged:
        return json_de_mensaje(404, "No se logro encontrar donde almacenar el curso.")
    
    ####################### Asignar curso a alumno

    # Si todo sale bien se le asigna el nuevo curso a los alumnos en la lista
    alumnos_resultado = asignar_curso_a_alumno(resultado.inserted_id, alumnos_rut)

    if alumnos_resultado["codigo"] != 200:
        return alumnos_resultado
    
    #########################

    ######################### Asignar el curso al profesor

    profesor_resultado = Administrador.asignar_curso_a_profesor(resultado.inserted_id, profesores_rut)

    if profesor_resultado["codigo"] != 200:
        return profesor_resultado
    
    #########################

    return json_de_mensaje(200, f"El curso {formulario['curso']} {formulario['curso_letra']} fue creado exitosamente.")

def asignar_curso_a_alumno(id_curso, ruts):

    try:
        resultado = estudiantes.update_many({"rut": {"$in": ruts}}, {"$set": {"curso_actual": ObjectId(id_curso)}})
    except:
        return json_de_mensaje(500, "Ocurrio un error, no se logro asignar a los alumnos el curso.")
    
    if not resultado.acknowledged:
        return json_de_mensaje(404, "No se logro asignar completamente el curso a los alumnos.")
    
    return json_de_mensaje(200, "Se ha asignado el curso correctamente a los alumnos.")
