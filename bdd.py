from pymongo import MongoClient
from bson.objectid import ObjectId # Importar ObjectId
from datetime import datetime

import os

if "herna" not in os.getcwd():
    HOST = MongoClient(os.environ.get("HOST"))
else:
    HOST = MongoClient("mongodb://localhost:27017/")
    
BDD = HOST["colegio"]

ROOT_DIR = os.getcwd() 
MEDIA_DIR = os.path.join(ROOT_DIR, "static", "media")

estudiantes = BDD["estudiantes"]
talleres = BDD["talleres"]
noticias = BDD["noticias"]
contacto = BDD["contacto"]
cursos = BDD["cursos"]
notas = BDD["notas"]

NOT_ALLOWED = ";$&|{}[]<>\"'\\`"


##################### Funciones auxiliares

def verificar_estado_de_peticion(resultado) -> dict:
    
    if resultado["codigo"] == 200:
        return resultado["mensaje"]
    
    return resultado

def json_de_mensaje(codigo, resultado_o_mensaje) -> dict:
    """Crea un json con el formato: { 'codigo': 000, 'mensaje': 'resultado o mensaje de error' }"""
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

def obtener_path_normalizado(cadena_str: str) -> dict:
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

##########################################

class General():
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

    def obtener_informacion_rut(rut: str) -> dict:
        """Obtiene informacion del rut (Todo)."""

        try:
            resultado = list(estudiantes.find({"rut": rut}))

        except:
            return json_de_mensaje(500, "No se logro obtener informacion del rut por un error.")
        
        if not resultado:
            return json_de_mensaje(404, "No se encontro el rut en la bdd.")
        print(resultado[0])
        return json_de_mensaje(200, resultado[0])

class Administrador():
    """
    Clase contenedora de todas las funciones activas que\n
    utiliza y accede el Administrador.
    """

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

        try:
            resultados = estudiantes.insert_one(informacion_json)
        except:
            json_de_mensaje(500, "No se logro crear un nuevo usuario por un error.")
        
        if not resultados.acknowledged:
            return json_de_mensaje(400, "La base de datos no completo el registro.")
        
        return json_de_mensaje(200, f"Se ha agregado al usuario {informacion_json['rut']} con cargo {informacion_json['cargo']} exitosamente.")

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

class Profesor():
    """
    Funciones que utiliza el perfil de Profesor y sus dependencias.
    """

    def listar_cursos_de_profesor(rut_de_profesor) -> dict:
        
        try:
            respuesta = list(estudiantes.find({"cargo": "profesor", "rut": rut_de_profesor}, {"cursos_asignados": 1}))

        except:
            return json_de_mensaje(500, "Error, no se logro obtener la lista desde la base de datos.")
        
        if not respuesta:
            return json_de_mensaje(404, f"No se logro encontrar ningun curso asociado al rut {rut_de_profesor}.")
        
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

class Noticiero():
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

class Estudiante():
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
    
class Public():
    """
    Acciones/funciones que se utilizan de manera publica.
    """

    def nuevo_mensaje(informacion_del_contacto: dict) -> dict:

        no_sql_st = no_sql(informacion_del_contacto)

        if no_sql_st["codigo"] != 200:
            return no_sql_st

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

        no_sql_str = no_sql({"usuario": usuario, "contrasena": contrasena})

        if no_sql_str["codigo"] != 200:
            return no_sql_str

        try:
            resultado = list(estudiantes.find({"rut": usuario, "contrasena": contrasena}, {"_id": 0, "contrasena": 0, "cursos_asignados": 0, "taller_asignado": 0, "taller": 0}))
        except:
            return json_de_mensaje(500, "Ocurrio un error al buscar en la base de datos un usuario o contraseña.")
        
        if not resultado:
            return json_de_mensaje(404, "Usuario o contraseña no coinciden con ninguna en la base de datos.")

        return json_de_mensaje(200, resultado[0])

#################### Seccion Profesor Jefe -- NO INCLUIDO YA QUE SE USA EDUPLAN

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

    profesor_resultado = asignar_curso_a_profesor(resultado.inserted_id, profesores_rut)

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

def asignar_curso_a_profesor(id_curso, ruts):

    try:
        respuesta = estudiantes.update_many({"rut": {"$in": ruts}}, {"$push": {"cursos_asignados": ObjectId(id_curso)}})
    
    except:
        return json_de_mensaje(500, "No se logro asignar el curso a los profesores.")
    
    if not respuesta.acknowledged:
        return json_de_mensaje(404, "No se encontraron todos los profesores a asignar el curso.")
    
    return json_de_mensaje(200, "Se asigno el curso correctamente a los profesores.")
