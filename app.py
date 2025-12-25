import bdd, server_settings
from flask_caching import Cache
import api_.calendario as calendario_api
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import Flask, render_template, session, request, redirect, url_for, send_file, Response

app = Flask(__name__)
app.secret_key = server_settings.SECRET_KEY

app.config.update(
    SESSION_COOKIE_HTTPONLY = True, # Anti xss para evitar inject de js
    SESSION_COOKIE_SECURE = True, # Solo https
    SESSION_COOKIE_SAMESITE = "Lax" # Solo desde mi dominio xd
)

app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

app.config['CACHE_TYPE'] = 'RedisCache'
app.config['CACHE_REDIS_URL'] = server_settings.REDIS_URI
app.config['CACHE_DEFAULT_TIMEOUT'] = server_settings.CACHE_TIMEOUT

def limiter_funcion():

    if "informacion" not in session:
        return get_remote_address()
    
    if "rut" not in session:
        return get_remote_address()

    return session["informacion"]["rut"]

cachear = Cache(app)
limitador = Limiter(
    app=app,
    key_func=limiter_funcion,
    storage_uri=server_settings.REDIS_URI
)

RUTAS = bdd.Users.leer_routes(True)
PERSONALIZACION_WEB = bdd.Settings.leer_settings(True)

#########################

@app.errorhandler(429)
def ratelimit_handler(e): # Aquí rediriges a otra ruta cuando se excede el límite
    return render_template(
        "error.html",
        codigo = 429,
        mensaje = "excediendo en el numero de consultas a este sitio por minuto. Espera un momento antes de continuar.",
        excepcion = e
    )

@app.errorhandler(413)
def too_large(e):
    return render_template(
        "error.html",
        codigo = 413,
        mensaje = "excediendo en el peso del archivo que deseas subir. Intenta con otro mas liviano.",
        excepcion = e
    )

#########################

@app.context_processor
def context():
    return PERSONALIZACION_WEB

# SECCION ENCARGADA DE INICIAR SESION POR CARGOS
@app.before_request
def limitar_acceso():

    # Static, esta pensado para verificar los recursos que llevan un .jpg .png u otros
    STATIC = request.url.replace(request.url_root, "")

    if "." in STATIC:
        return

    # Creamos la URL para validar si tiene permisos para entrar en la seccion
    URL = request.endpoint

    if all(ruta != URL for ruta in RUTAS["public"]):

        if not session:
            return redirect(url_for("login"))
        
        if all(ruta_permitida != URL for ruta_permitida in RUTAS["rol"][session["informacion"]["cargo"]]):
            return redirect(url_for("login"))

        print("TODO BIEN")

@app.after_request
def safe_headers(response):
    """Funcion encargada de responder con headers seguros"""

    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"

    return response

########################################### SECCION PUBLICA

@app.route("/home", methods = ["GET"])
@limitador.limit("30/minute")
@cachear.cached(timeout=300)
def home():

    noticias_list = bdd.Public.listar_noticias_home()
    print(noticias_list)
    
    if noticias_list["codigo"] != 200:
        noticias_list["mensaje"] = ""
    
    todos_los_eventos = bdd.General.todos_los_eventos()

    if todos_los_eventos["codigo"] != 200:
        todos_los_eventos = [{"fecha_evento": "12-12-2025", "titulo": "Ejemplo de Evento", "descripcion": "Esta descripcion es de ejemplo."}]    
    else:
        todos_los_eventos = todos_los_eventos["mensaje"]

    calendario_codigo = calendario_api.actualizar_calendario(todos_los_eventos)
    
    return render_template("home.html", noticias = noticias_list["mensaje"], codigo_calendario = calendario_codigo)

@app.route("/nuestra_historia", methods = ["GET"]) ### Pagina estatica
@cachear.cached(timeout=300)
def nuestra_historia():
    return render_template("secciones/nuestra_historia.html")

@app.route("/logout", methods = ["GET"])
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/contactanos", methods = ["POST", "GET"])
def contactanos():

    if request.method == "POST":

        if "accion" not in request.form:
            error = bdd.json_de_mensaje(402)
            return redirect(url_for("contactanos", codigo = error["codigo"], mensaje = error["mensaje"]))
    
        if request.form["accion"] == "contactar":
            
            mensaje = request.form.to_dict()
            mensaje.pop("accion")
            
            respuesta = bdd.Public.nuevo_mensaje(mensaje)

        return redirect(url_for("contactanos", codigo = respuesta["codigo"], mensaje = respuesta["mensaje"]))

    ###################### Seccion GET

    return render_template("contacto/contacto.html")

@app.route("/login", methods = ["POST", "GET"])
@limitador.limit("5/minute")
def login():
    
    # Si es que el metodo de acceso es port se realiza una comprobacion del usuario y contraseña
    # si es que esta correcto, se guarda en la sesion la informacion del usuario y se utiliza para
    # redirigirle al panel correspondiente
    # 
    # Como se ve lo que devuelve la bdd
    # {"codigo": 000, "mensaje": "resultados o mensaje de error"}
    if request.method == "POST":

        validar_campos = bdd.Security.form_validator("login", request.form)
        if validar_campos["codigo"] != 200:
            return redirect(url_for("login", codigo = validar_campos["codigo"], mensaje = validar_campos["mensaje"]))

        ## Cuando empleemos la base de datos corregir esta seccion creando una cookie mas elaborada
        cookies = bdd.Public.iniciar_sesion(request.form["rut"], request.form["contrasena"])

        if cookies["codigo"] != 200:
            return redirect(url_for("login", codigo = cookies["codigo"], mensaje = cookies["mensaje"]))

        ######## Si el usuario esta deshabilitado por alguna razon se redirige al error
        if "deshabilitado" in cookies["mensaje"]:
            return render_template("error.html")

        if cookies["mensaje"]["cargo"] not in RUTAS["rol"]:
            return str(
                {
                    "error": 402,
                    "mensaje": "GRAVE: CONTACTA A UN ADMINISTRADOR, Y SOLICITA QUE TE ASIGNE UN ROL EXISTENTE."
                }
            )

        session["informacion"] = cookies["mensaje"]

        ##### Se obtienen las rutas del cargo asignado en routes.json y se redirige a la primera.
        return redirect(url_for(bdd.obtener_navbar(session, RUTAS, True)))

    ################# Seccion de metodo GET

    # Se verifica si tiene una sesion iniciada, si no es asi se redirige al login. En el caso contrario
    # se le redirige al cargo que tenga asociado en la sesion

    if not session:
        return render_template("login.html")

    return redirect(url_for(bdd.obtener_navbar(session, RUTAS, True)))

@app.route("/micuenta", methods = ["POST", "GET"]) ########### GENERAL PARA T0DO AQUEL LOGEADO
def micuenta():
    rutas_permitidas_usuario = bdd.obtener_navbar(session, RUTAS)

    if not session or "informacion" not in session:
        return redirect(url_for("login", codigo = 402, mensaje="Acceso denegado: necesitas iniciar sesión para continuar"))

    if request.method == "POST":

        formulario = request.form.to_dict()

        if "accion" not in formulario:
            return redirect(url_for("micuenta", codigo = 404, mensaje = "ERROR: Estas enviando un formulario inconcluso."))

        if formulario["accion"] == "modificar_contrasena":

            # Verificamos que todos los campos necesarios para utilizar el api sean correctos
            resultado_contrasena = bdd.Security.claves_existentes(["rut", "contrasena"], formulario)
            if not resultado_contrasena:
                return redirect(url_for("micuenta",
                    codigo = resultado_contrasena["codigo"],
                    mensaje = resultado_contrasena["mensaje"]
                ))

            # Se utiliza la validacion del formulario de login para verificar que no esten inyectando caracteres rancios
            resultado_contrasena = bdd.Security.form_validator("login", formulario)
            if resultado_contrasena["codigo"] != 200:
                return redirect(url_for("micuenta",
                    codigo = resultado_contrasena["codigo"],
                    mensaje = resultado_contrasena["mensaje"]
                ))

            resultado = bdd.Users.reestablecer_contrasena(formulario["rut"], formulario["contrasena"])

        return redirect(url_for("micuenta", codigo = resultado["codigo"], mensaje = resultado["mensaje"]))

    ################### ZONA GET

    informacion_rut = bdd.General.obtener_informacion_rut(session["informacion"]["rut"])
    
    if informacion_rut["codigo"] != 200:
        return render_template(
            "micuenta.html",
            error = informacion_rut,
            rutas_permitidas = rutas_permitidas_usuario
        )

    return render_template(
        "micuenta.html",
        informacion = informacion_rut,
        rutas_permitidas = rutas_permitidas_usuario
    )

@app.route("/seccion_de_noticias", methods = ["GET"])
@cachear.cached(timeout=300)
def seccion_de_noticias():

    resultados = bdd.Public.obtener_ultimas_noticias()

    if resultados["codigo"] != 200:
        return render_template("secciones/seccion_de_noticias.html", error = resultados)

    return render_template("secciones/seccion_de_noticias.html", noticias = resultados["mensaje"])
    
@app.route("/talleres", methods = ["GET"])
@cachear.cached(timeout=300)
def talleres():

    resultado_taller = bdd.General.todos_los_talleres()

    if resultado_taller["codigo"] != 200:
        return render_template("secciones/talleres.html", error = resultado_taller)

    return render_template("secciones/talleres.html", talleres = resultado_taller["mensaje"])

############################### Rutas panel del administrador
@app.route("/administrador", methods = ["POST", "GET"])
def administrador():

    rutas_permitidas_usuario = bdd.obtener_navbar(session, RUTAS)

    if request.method == "POST":
        formulario_dict = request.form.to_dict()

        accion_in = bdd.Security.validar_accion_form(formulario_dict, ["crear"])
        if accion_in["codigo"] != 200:
            return redirect(url_for("administrador", codigo = accion_in["codigo"], mensaje = accion_in["mensaje"]))
    
        if request.form["accion"] == "crear":
            resultado = bdd.Administrador.crear_usuario(request.form.to_dict())

        return redirect(url_for("administrador", codigo = resultado["codigo"], mensaje = resultado["mensaje"]))

    ################# Seccion de metodo GET

    roles = RUTAS["rol"].keys()
    cursos = bdd.General.todos_los_cursos()
    if cursos["codigo"] != 200:
        cursos = [{"curso": "No disponible", "_id": "0", "alumnos": 0}]
    
    else:
        cursos = cursos["mensaje"]

    # Usar el url para cambiar de acciones a utlizar pero no cambiar de direccion. es decir cambiar solo la plantilla
    return render_template("administrador/administrador.html",
        cursos = cursos,
        roles = roles,
        rutas_permitidas = rutas_permitidas_usuario
    )

@app.route("/administrador_mensajes", methods = ["POST", "GET"])
def administrador_mensajes():
    # Obtener listado de mensajes (se usa tanto en GET como en POST)
    rutas_permitidas_usuario = bdd.obtener_navbar(session, RUTAS)
    resultado = bdd.Administrador.listar_mensajes(0)

    if resultado["codigo"] != 200:
        
        return render_template(
            "administrador/contacto.html",
            error=resultado,
            rutas_permitidas = rutas_permitidas_usuario
        )

    # POST: marcar mensaje como visto
    if request.method == "POST":

        if request.form.get("accion") == "visto":
            id_contacto = request.form.get("id_de_contacto")
            respuesta = bdd.Administrador.marcar_mensaje_como_visto(id_contacto)

            if respuesta["codigo"] != 200:
                return render_template(
                    "administrador/contacto.html",
                    contactos = resultado["mensaje"],
                    error = respuesta,
                    rutas_permitidas = rutas_permitidas_usuario
                )

            return render_template(
                "administrador/contacto.html",
                contactos = resultado["mensaje"],
                exito = respuesta,
                rutas_permitidas = rutas_permitidas_usuario
            )

    # GET: mostrar listado de mensajes
    return render_template(
        "administrador/contacto.html",
        contactos = resultado["mensaje"],
        rutas_permitidas = rutas_permitidas_usuario
    )

@app.route("/administrador_mensajes_vistos", methods = ["POST", "GET"])
def administrador_mensajes_vistos():

    rutas_permitidas_usuario = bdd.obtener_navbar(session, RUTAS)
    resultado_lista_mensajes = bdd.Administrador.listar_mensajes(1) # Si en el futuro hay queja por repeticion de mensajes es por esto
    
    if resultado_lista_mensajes["codigo"] != 200:
        return render_template(
            "administrador/contacto.html",
            error = resultado_lista_mensajes,
            rutas_permitidas = rutas_permitidas_usuario
        )

    if request.method == "POST":

        if request.form["accion"] == "eliminar":            
            respuesta_eliminacion = bdd.Administrador.eliminar_mensaje(request.form["id_de_contacto"])

        if respuesta_eliminacion["codigo"] != 200:
            
            return render_template("administrador/contacto.html",
                error = respuesta_eliminacion,
                rutas_permitidas = rutas_permitidas_usuario
            )
        
        if resultado_lista_mensajes["codigo"] != 200:

            return render_template("administrador/contacto.html",
                error = resultado_lista_mensajes,
                exito = respuesta_eliminacion,
                rutas_permitidas = rutas_permitidas_usuario
            )
        
        return render_template("administrador/contacto.html",
            contactos_vistos = resultado_lista_mensajes["mensaje"],
            exito = respuesta_eliminacion,
            rutas_permitidas = rutas_permitidas_usuario
        )

    ################################### Seccion GET

    return render_template(
        "administrador/contacto.html",
        contactos_vistos = resultado_lista_mensajes["mensaje"],
        rutas_permitidas = rutas_permitidas_usuario
    )

@app.route("/administrador_crear_taller", methods = ["POST", "GET"])
def administrador_crear_taller():

    rutas_permitidas_usuario = bdd.obtener_navbar(session, RUTAS)

    if request.method == "POST":

        if request.form["accion"] == "crear_taller":

            informacion_nuevo_taller = request.form.to_dict()
            informacion_nuevo_taller.pop("accion")

            resultado = bdd.Administrador.crear_taller(informacion_nuevo_taller)

        return redirect(url_for("administrador_crear_taller", codigo = resultado["codigo"], mensaje = resultado["mensaje"]))

    ########### ZONA GET

    resultado_profesores = bdd.Administrador.listar_profesores_talleristas()

    if resultado_profesores["codigo"] != 200:
        return redirect(url_for("administrador_crear_taller",
            codigo = resultado["codigo"],
            mensaje = resultado["mensaje"])
        )

    return render_template("administrador/crear_taller.html",
        profesores = resultado_profesores["mensaje"],
        rutas_permitidas = rutas_permitidas_usuario
    )

@app.route("/administrar_taller_estudiantes", methods = ["POST", "GET"])
def administrar_taller_estudiantes():

    rutas_permitidas_usuario = bdd.obtener_navbar(session, RUTAS)
    cache_key = "talleres_lista"
    
    if request.method == "POST":

        accion = request.form["accion"]

        # Todo esto funciona en la misma plantilla, dependiendo de lo que se responda la plantilla reacciona y se devuelven
        # ciertos datos dependiendo de la accion

        if accion == "buscar_taller":

            resultado_taller = bdd.General.obtener_informacion_taller(request.form["taller"])

            return render_template("administrador/aceptar_usuarios_taller.html",
                buscar_taller = True,
                taller = resultado_taller["mensaje"],
                cargo = session["informacion"]["cargo"],

                rutas_permitidas = rutas_permitidas_usuario
            )
        
        if accion == "inscribir_alumnos":

            data_alumnos = request.form.to_dict()
            data_alumnos.pop("accion")

            resultado_asignacion = bdd.Administrador.aceptar_alumnos(data_alumnos)

            ######### Se borra la cache de talleres lista
            cachear.delete(cache_key)
            
            return redirect(url_for("administrar_taller_estudiantes",
                codigo = resultado_asignacion["codigo"],
                mensaje = resultado_asignacion["mensaje"])
            )


        if accion == "quitar_del_taller":
            
            data_alumnos = request.form.to_dict()
            data_alumnos.pop("accion")
            
            ########## Borramos la cache de los talleres
            cachear.delete(cache_key)

            resultado_quitar_del_taller = bdd.Administrador.quitar_alumnos_del_taller(data_alumnos)

            return redirect(url_for("administrar_taller_estudiantes", codigo = resultado_quitar_del_taller["codigo"], mensaje = resultado_quitar_del_taller["mensaje"]))

        if accion == "deshabilitar_taller":


            resultado = bdd.Administrador.deshabilitar_taller(request.form["id_taller"])
            ########## Borramos la cache de los talleres
            cachear.delete(cache_key)

            return redirect(url_for("administrar_taller_estudiantes", codigo = resultado["codigo"], mensaje = resultado["mensaje"]))

        if accion == "habilitar_taller":

            resultado = bdd.Administrador.habilitar_taller(request.form["id_taller"])
            ########## Borramos la cache de los talleres
            cachear.delete(cache_key)

            return redirect(url_for("administrar_taller_estudiantes", codigo = resultado["codigo"], mensaje = resultado["mensaje"]))

    ############## ZONA GET

    ########## Verificamos el Cache los talleres
    talleres_resultado = cachear.get(cache_key)

    if talleres_resultado:
        return render_template(
            "administrador/aceptar_usuarios_taller.html",
            get = True,
            talleres = talleres_resultado["mensaje"],
            rutas_permitidas = rutas_permitidas_usuario
        )

    talleres_resultado = bdd.General.todos_los_talleres()

    if talleres_resultado["codigo"] != 200:
        return render_template(
            "administrador/aceptar_usuarios_taller.html",
            error = talleres_resultado,
            rutas_permitidas = rutas_permitidas_usuario
        )
    
    # En caso de no haber se actualiza o se cachea
    cachear.set(cache_key, talleres_resultado, timeout=300)

    return render_template(
        "administrador/aceptar_usuarios_taller.html",
        get = True,
        talleres = talleres_resultado["mensaje"],
        rutas_permitidas = rutas_permitidas_usuario
    )

@app.route("/administrar_pagina", methods = ["POST", "GET"]) ######### USA PERSONALIZACION_WEB EN GLOBAL
def administrar_pagina():
    global PERSONALIZACION_WEB
    
    rutas_permitidas_usuario = bdd.obtener_navbar(session, RUTAS)

    if request.method == "POST":

        formulario = request.form.to_dict()
        
        if "accion" not in formulario:
            return redirect(url_for("administrar_pagina", codigo = 402, mensaje = "ERROR: Estas enviando un formulario corrupto o invalido."))
  
        if formulario["accion"] == "modificar_base":
            respuesta_modificar = bdd.Settings.modificar_template_base(formulario)

            if respuesta_modificar["codigo"] == 200:
                PERSONALIZACION_WEB = bdd.Settings.leer_settings(True)
        
        elif formulario["accion"] == "nuevo_ano":
            respuesta_modificar = bdd.Administrador.nuevo_ano(request.files)
            cachear.clear()
        
        elif formulario["accion"] == "subir_profesores":
            respuesta_modificar = bdd.Administrador.subir_profesores(request.files)

            if respuesta_modificar["codigo"] == 200:
                print(respuesta_modificar["mensaje"])
            cachear.clear()

        return redirect(url_for("administrar_pagina", codigo = respuesta_modificar["codigo"], mensaje = respuesta_modificar["mensaje"]))

    ################ ZONA GET
    
    return render_template(
        "administrador/administrar_pagina.html",
        rutas_permitidas = rutas_permitidas_usuario
    )

@app.route("/crear_roles", methods = ["GET", "POST"]) ######### USA RUTAS EN GLOBAL
def crear_roles():
    global RUTAS
    rutas_permitidas_usuario = bdd.obtener_navbar(session, RUTAS)

    if request.method == "POST":
        
        formulario = request.form.to_dict()

        resultado_crear_roles = bdd.Users.crear_rol(formulario)

        if resultado_crear_roles["codigo"] == 200:
            RUTAS = bdd.Users.leer_routes(True)

        return redirect(url_for("crear_roles", codigo = resultado_crear_roles["codigo"], mensaje = resultado_crear_roles["mensaje"]))

    ###################### ZONA GET

    routes_get = bdd.Users.leer_routes()

    if routes_get["codigo"] != 200:
        return render_template(
            "administrador/crear_roles",
            error = routes_get,
            rutas_permitidas = rutas_permitidas_usuario
        )

    return render_template(
        "administrador/crear_roles.html",
        routes = routes_get["mensaje"],
        rutas_permitidas = rutas_permitidas_usuario
    )

@app.route("/administrar_usuarios", methods = ["POST", "GET"])
def administrar_usuarios():

    rutas_permitidas_usuario = bdd.obtener_navbar(session, RUTAS)


    if request.method == "POST":

        formulario = request.form.to_dict()
        
        if "accion" not in formulario:
            return redirect(url_for("administrar_usuarios", codigo = 500, mensaje = "ERROR: Formulario incompleto o corrupto."))

        if formulario["accion"] == "buscar":

            if not bdd.Security.claves_existentes(["filtro_valor", "filtro"], formulario):
                return redirect(url_for("administrar_usuarios", codigo = 500, mensaje = "ERROR: Formulario incompleto o corrupto."))

            resultado = bdd.Users.buscar_usuarios(formulario["filtro_valor"], formulario["filtro"])

            if resultado["codigo"] == 200:
                return render_template("administrador/administrar_usuarios.html",
                    usuarios = resultado["mensaje"],
                    plantilla = "resultado_buscar",

                    cargos = RUTAS["rol"],
                    rutas_permitidas = rutas_permitidas_usuario
                )

        if formulario["accion"] == "reestablecer_contrasena":

            if "rut" not in formulario:
                return redirect(url_for("administrar_usuarios", codigo = 500, mensaje = "ERROR: Formulario incompleto o corrupto."))
            
            resultado = bdd.Users.reestablecer_contrasena(formulario["rut"], "liceohualqui2025")

        if formulario["accion"] == "habilitar_usuario":
            
            if "rut" not in formulario:
                return redirect(url_for("administrar_usuarios", codigo = 500, mensaje = "ERROR: Formulario incompleto o corrupto."))
            
            resultado = bdd.Users.usuario_habilitado(formulario["rut"], True)

        if formulario["accion"] == "deshabilitar_usuario":
            
            if "rut" not in formulario:
                return redirect(url_for("administrar_usuarios", codigo = 500, mensaje = "ERROR: Formulario incompleto o corrupto."))
            
            resultado = bdd.Users.usuario_habilitado(formulario["rut"], False)

        if formulario["accion"] == "eliminar_usuario":
            
            if "rut" not in formulario:
                return redirect(url_for("administrar_usuarios", codigo = 500, mensaje = "ERROR: Formulario incompleto o corrupto."))
            
            resultado = bdd.Administrador.eliminar_usuario(formulario["rut"])

        return redirect(url_for("administrar_usuarios", codigo = resultado["codigo"], mensaje = resultado["mensaje"]))


    ################# Zona GET

    return render_template(
        "administrador/administrar_usuarios.html",
        
        cargos = RUTAS["rol"],
        rutas_permitidas = rutas_permitidas_usuario
    )

@app.route("/asignar_profesores_a_cursos", methods = ["POST", "GET"])
def asignar_profesores_a_cursos():

    rutas_permitidas_usuario = bdd.obtener_navbar(session, RUTAS)

    if request.method == "POST":
    
        formulario_ = request.form.to_dict()
        if "accion" not in formulario_:
            return redirect(url_for(
                "asignar_profesores_a_cursos",
                codigo = 500,
                mensaje = "ERROR: Formulario incompleto o corrupto."
            ))

        if formulario_["accion"] == "asignar_materias":

            if "curso" not in formulario_:
                return redirect(url_for("asignar_profesores_a_cursos", codigo = 402, mensaje = "Estas enviando un formulario invalido o corrupto."))
            
            curso_id = formulario_["curso"]

            curso_informacion = bdd.General.obtener_informacion_curso(curso_id)
            if curso_informacion["codigo"] != 200:
                return redirect(url_for("asignar_profesores_a_cursos", codigo = curso_informacion["codigo"], mensaje = curso_informacion["mensaje"]))

            ########### LISTA DE PROFESORES
            cache_key = "listar_profesores"

            # Obtenemos la cache
            profesores = cachear.get(cache_key)
        
            # Si tiene se retornan los daatos con la cache
            if profesores:
                
                ########### Se obtiene la informacion de los profesores y se le adjunta al documento del curso
                profesores_asig = bdd.General.profesores_asignados(profesores, curso_informacion)
                if profesores_asig["codigo"] == 200:
                    curso_informacion["mensaje"]["profesores_asignados"] = profesores_asig["mensaje"]

                return render_template(
                    "administrador/asignar_profesores_a_cursos.html",
                    asignar = True,

                    ########## Informacion para el template
                    profesores = profesores["mensaje"],
                    curso = curso_informacion["mensaje"],
                    curso_id = curso_id,
                    rutas_permitidas = rutas_permitidas_usuario
                )

            # En caso de no, se actualiza y se retornan con los valores de la BDD externa
            profesores = bdd.General.listar_profesores()
            
            if profesores["codigo"] != 200:
                return redirect(url_for(
                    "asignar_profesores_a_cursos",
                    codigo = profesores["codigo"],
                    mensaje = profesores["mensaje"]
                ))
            
            cachear.set(cache_key, profesores)

            ########### Se obtiene la informacion de los profesores y se le adjunta al documento del curso
            profesores_asig = bdd.General.profesores_asignados(profesores, curso_informacion)
            if profesores_asig["codigo"] == 200:
                curso_informacion["mensaje"]["profesores_asignados"] = profesores_asig["mensaje"]

            return render_template(
                "administrador/asignar_profesores_a_cursos.html",
                asignar = True,
                
                ########## Informacion para el template
                profesores = profesores["mensaje"],
                curso = curso_informacion["mensaje"],
                curso_id = curso_id,
                rutas_permitidas = rutas_permitidas_usuario
            )

        elif formulario_["accion"] == "asignar_profesores_a_cursos":
            resultado = bdd.Administrador.asignar_materias_a_profesores(formulario_)

        return redirect(url_for("asignar_profesores_a_cursos", codigo = resultado["codigo"], mensaje = resultado["mensaje"]))

    ########### Se intenta obtener el cache desde los archivos
    cache_key_cursos = "todos_los_cursos"
    cursos = cachear.get(cache_key_cursos)

    # Si existe se retorna eso
    if cursos:
        print("CACHEEEEEEEEEEEEE")
        return render_template(
            "administrador/asignar_profesores_a_cursos.html",
            principal = True,
            ######## DATA NECESARIA PARA LA SECCION PRINCIPAL
            cursos = cursos["mensaje"],
            rutas_permitidas = rutas_permitidas_usuario
        )

    # De no ser asi se obtiene el valor y se guarda en la cache
    cursos = bdd.General.todos_los_cursos()

    if cursos["codigo"] != 200:

        return render_template(
            "administrador/asignar_profesores_a_cursos.html",
            error = cursos,
            rutas_permitidas = rutas_permitidas_usuario
        )
    
    # Se guarda en cache
    cachear.set(cache_key_cursos, cursos, timeout=300)

    return render_template(
        "administrador/asignar_profesores_a_cursos.html",
        principal = True,
        ######## DATA NECESARIA PARA LA SECCION PRINCIPAL
        cursos = cursos["mensaje"],
        rutas_permitidas = rutas_permitidas_usuario

    )

@app.route("/crear_evento", methods = ["POST", "GET"])
def crear_evento():

    rutas_permitidas_usuario = bdd.obtener_navbar(session, RUTAS)

    if request.method == "POST":
        
        formulario_ = request.form.to_dict()
        acciones = [
            "crear_evento"
        ]

        accion = bdd.Security.validar_accion_form(formulario_, acciones)
        if accion["codigo"] != 200:
            return redirect(url_for("crear_evento", codigo = accion["codigo"], mensaje = accion["codigo"]))
        
        accion = accion["mensaje"]

        if accion == "crear_evento":
            resultado = bdd.Administrador.crear_evento(formulario_)

        return redirect(url_for("crear_evento", codigo = resultado["codigo"], mensaje = resultado["mensaje"]))

    ############### ZONA GET

    return render_template("administrador/crear_evento.html", rutas_permitidas = rutas_permitidas_usuario)

############################### Rutas de panel del noticiero

@app.route("/noticiero", methods = ["POST", "GET"])
def noticiero():

    rutas_permitidas_usuario = bdd.obtener_navbar(session, RUTAS)

    if request.method == "POST":

        if request.form["accion"] == "crear_alerta":
            resultado = bdd.Noticiero.crear_alerta(
                request.form["titulo"],
                request.form["descripcion"]
            )

        if request.form["accion"] == "crear_noticia":
            resultado = bdd.Noticiero.crear_noticia(
                request.form["titulo"],
                request.form["descripcion"],
                request.files
            )

        ########################################
        # TALLARIN CODIGO: LO AGREGE TIEMPO DESPUES
        ########################################
        if request.form["accion"] == "listar_alertas":
            resultado = bdd.Noticiero.listar_alertas()

            if resultado["codigo"] == 200:
                return render_template(
                    "noticiero/noticias.html",
                    resultados = resultado["mensaje"],
                    rutas_permitidas = rutas_permitidas_usuario
                )

        if request.form["accion"] == "listar_noticias":
            resultado = bdd.Noticiero.listar_noticias()

            if resultado["codigo"] == 200:            
                return render_template(
                    "noticiero/noticias.html",
                    resultados = resultado["mensaje"],
                    rutas_permitidas = rutas_permitidas_usuario
                )

        if request.form["accion"] == "eliminar_noti":
            resultado = bdd.Noticiero.eliminar_noticia(request.form["id_noticia"])
        
        if request.form["accion"] == "modificar_noti":
            resultado = bdd.Noticiero.modificar_noticia(request.form, request.files)

        ########################################
        
        # Esto redirige a la pagina principal de noticiero con el codigo de error
        return redirect(url_for("noticiero", codigo = resultado["codigo"], mensaje = resultado["mensaje"]))

    return render_template("noticiero/noticiero.html", rutas_permitidas = rutas_permitidas_usuario)

################### API NOTICIAS OBTENER LA ULTIMA NOTICIA URGENTE
@app.route("/urgente")
@cachear.cached(timeout=300)
def urgente():

    resultado = bdd.Public.obtener_ultima_alerta()

    if resultado["codigo"] != 200:
        return resultado
    
    return resultado["mensaje"]

############################### Rutas de panel del profesor

@app.route("/profesor", methods = ["POST", "GET"])
def profesor():

    rutas_permitidas_usuario = bdd.obtener_navbar(session, RUTAS)

    if request.method == "POST":
        
        formulario = request.form.to_dict()
        if "accion" not in formulario:
            return redirect(url_for("profesor", codigo = 402, mensaje = "Estas enviando un formulario corrupto o incompleto."))
        
        if formulario["accion"] == "administrar_curso":

            if "id_curso" not in formulario:
                return redirect(url_for("profesor", codigo = 402, mensaje = "Estas enviando un formulario corrupto o incompleto."))
            
            respuesta = bdd.General.obtener_informacion_curso(formulario["id_curso"])
            if respuesta["codigo"] != 200:
                return redirect(url_for("profesor", codigo = respuesta["codigo"], mensaje = respuesta["mensaje"]))
            
            #print(respuesta)
            return render_template(
                "profesor/administrar_curso.html",
                informacion_curso = respuesta["mensaje"],
                rut_profesor = session["informacion"]["rut"],
                rutas_permitidas = rutas_permitidas_usuario
            )

        elif formulario["accion"] == "subir_notas":
            respuesta = bdd.Profesor.asignar_notas(formulario)

        elif formulario["accion"] == "pasar_lista":
            respuesta = bdd.Profesor.pasar_lista(formulario)
        
        elif formulario["accion"] == "anotacion_alumno":
            respuesta = bdd.Profesor.anotacion_alumno(formulario)

        return redirect(url_for("profesor", codigo = respuesta["codigo"], mensaje = respuesta["mensaje"]))

    #################### Seccion GET
    rut_profesor = session["informacion"]["rut"]
    cache_key = rut_profesor + "_cursos"

    ########## Verificamos la cache
    lista_cursos = cachear.get(cache_key)
    print(lista_cursos)

    if lista_cursos:
        return render_template(
            "profesor/profesor.html",
            informacion_profesor = lista_cursos["mensaje"],
            rutas_permitidas = rutas_permitidas_usuario
        )

    lista_cursos = bdd.Profesor.listar_cursos_de_profesor(rut_profesor)

    if lista_cursos["codigo"] != 200:
        return redirect(url_for("administrar_taller_estudiantes", codigo = lista_cursos["codigo"], mensaje = lista_cursos["mensaje"]))

    ########## Si no existe la cache se setea o actualiza pasado el tiempo
    cachear.set(cache_key, lista_cursos, timeout=300)

    return render_template(
        "profesor/profesor.html",
        informacion_profesor = lista_cursos["mensaje"],
        rutas_permitidas = rutas_permitidas_usuario
    )

@app.route("/profesor_taller", methods = ["POST", "GET"])
def profesor_taller():

    rutas_permitidas_usuario = bdd.obtener_navbar(session, RUTAS)

    # Se obtiene el taller asignado al profesor usando su RUT desde la sesión
    profesor_taller = bdd.Profesor.listar_taller_de_profesor(session["informacion"]["rut"])

    # Si hubo un error al obtener el taller, se muestra la plantilla con el mensaje de error
    if profesor_taller["codigo"] != 200:
        return render_template(
            "profesor/profesor_taller.html",
            error = profesor_taller,
            rutas_permitidas = rutas_permitidas_usuario
        )

    # Si el método es POST, se procesan acciones enviadas desde el formulario
    if request.method == "POST":
        # Se convierte el formulario en un diccionario manipulable
        formulario_web = request.form.to_dict()

        # Si la acción es "lista", se registra la asistencia del taller
        if request.form["accion"] == "lista":
            formulario_web.pop("accion")  # Se elimina la clave 'accion' para no interferir con la lógica de backend
            resultado = bdd.Profesor.pasar_lista_taller(formulario_web)  # Se envía la lista al backend

        # Si la acción es "nota", se asignan notas a los alumnos del taller
        if request.form["accion"] == "nota":
            formulario_web.pop("accion")
            resultado = bdd.Profesor.asignar_nota_taller(formulario_web)

        # Luego de ejecutar la acción, se redirige a la misma vista con el resultado como parámetros GET
        return redirect(url_for("profesor_taller", codigo = resultado["codigo"], mensaje = resultado["mensaje"]))

    # Si el método es GET, se muestra la plantilla con los datos del taller
    return render_template(
        "profesor/profesor_taller.html",
        taller = profesor_taller["mensaje"],
        rutas_permitidas = rutas_permitidas_usuario
    )

@app.route("/profesor_jefe_crear", methods = ["POST", "GET"]) ############ NO SE ESTA USANDO
def profesor_jefe_crear():

    if request.method == "POST":

        if request.form["accion"] == "crear_curso":

            data = request.form.to_dict()
            data.pop("accion")

            #nombre_jefe = session["informacion"]["nombres"] + " " + session["informacion"]["apellidos"]
            nombre_jefe = "TEMPORAL"
            rut_jefe = "TEMPORAL"
            #rut_jefe = session["informacion"]["rut"]

            respuesta = bdd.crear_curso_jefe(data, nombre_jefe, rut_jefe)

            return redirect(url_for("administrar_taller_estudiantes", codigo = respuesta["codigo"], mensaje = respuesta["mensaje"]))

    ##################### Seccion GET

    resultado_profesores = bdd.General.listar_profesores()

    if resultado_profesores["codigo"] != 200:
        return render_template("profesor/jefe/crear.html", error = resultado_profesores, rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]])

    return render_template("profesor/jefe/crear.html", profesores = resultado_profesores["mensaje"], rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]])

############################### Rutas de panel del estudiante

@app.route("/estudiante", methods = ["POST", "GET"])
def estudiante():

    rutas_permitidas_usuario = bdd.obtener_navbar(session, RUTAS)

    ############### ZONA GET

    rut_estudiante = session["informacion"]["rut"]
    cache_key = rut_estudiante + "_perfil"

    ########## Verificamos que exista una posible cache
    informacion_perfil = cachear.get(cache_key)
    if informacion_perfil:

        return render_template(
            "estudiante/estudiante.html",
            perfil = informacion_perfil["mensaje"],
            rutas_permitidas = rutas_permitidas_usuario
        )

    informacion_perfil = bdd.Estudiante.resumen_de_mi_perfil(rut_estudiante)

    if informacion_perfil["codigo"] != 200:
        
        return render_template("estudiante/estudiante.html",
            error = informacion_perfil,
            rutas_permitidas = rutas_permitidas_usuario
        )
    
    ##### Se cachea de caso de no haberla tenido
    cachear.set(cache_key, informacion_perfil, timeout=300)

    return render_template(
        "estudiante/estudiante.html",
        perfil = informacion_perfil["mensaje"],
        rutas_permitidas = rutas_permitidas_usuario
    )

@app.route("/taller_estudiante", methods = ["POST", "GET"])
def taller_estudiante():

    rutas_permitidas_usuario = bdd.obtener_navbar(session, RUTAS)

    # Si el estudiante se quiere unir a un taller
    if request.method == "POST":

        rut_solicitante = session["informacion"]["rut"]
        id_taller = request.form["taller_id"]

        respuesta = bdd.Estudiante.inscripcion_de_taller(rut_solicitante, id_taller)

        return redirect(url_for("taller_estudiante", codigo = respuesta["codigo"], mensaje = respuesta["mensaje"]))

    ################# Seccion de metodo GET

    verificacion_taller = bdd.Estudiante.verificaicon_taller(session["informacion"]["rut"])

    # Si es que el estudiante ya tiene o esta en un taller
    if verificacion_taller["codigo"] == 202:
        return render_template(
            "estudiante/talleres.html",
            in_taller = True,
            informacion_rut = verificacion_taller["mensaje"],
            rutas_permitidas = rutas_permitidas_usuario
        )

    # Si el usuario esta esta en un taller o da error
    if verificacion_taller["codigo"] != 200:
        return render_template(
            "estudiante/talleres.html",
            error = verificacion_taller,
            rutas_permitidas = rutas_permitidas_usuario
        )
    
    #######################################

    cache_key = "talleres_lista"

    ########## Se verifica la existencia de cache
    resultado = cachear.get(cache_key)
    if resultado:
        return render_template(
            "estudiante/talleres.html",
            not_in_taller = True,
            talleres = resultado["mensaje"],
            rutas_permitidas = rutas_permitidas_usuario
        )


    resultado = bdd.General.todos_los_talleres()

    if resultado["codigo"] != 200:
        return render_template(
            "estudiante/talleres.html",
            error = resultado,
            rutas_permitidas = rutas_permitidas_usuario
        ) # Esto redirige a una pagina de error

    ########## Se cachea en caso de no existir
    cachear.set(cache_key, resultado, timeout=300)

    return render_template(
        "estudiante/talleres.html",
        not_in_taller = True,
        talleres = resultado["mensaje"],
        rutas_permitidas = rutas_permitidas_usuario
    )

############################### Ruta plataforma Apoderado

@app.route("/apoderado", methods = ["GET", "POST"])
@limitador.limit("5/minute")
def apoderado():
    
    rutas_permitidas_usuario = bdd.obtener_navbar(session, RUTAS)
    rut_apoderado = session["informacion"]["rut"]

    if request.method == "POST":

        formulario = request.form.to_dict()
        if "accion" not in formulario:
            return redirect(url_for("apoderado", codigo = 404, mensaje = "ERROR: Estas enviando formularios incompletos."))
        
        if "obtener_certificado" == formulario["accion"]:

            if "rut_estudiante" not in formulario:
                return redirect(url_for("apoderado", codigo = 404, mensaje = "ERROR: Estas enviando formularios incompletos."))

            cache_key = f"{rut_apoderado}_regular_{formulario['rut_estudiante']}"
            existe_cache = cachear.get(cache_key)

            # Si existe el pdf almacenado en disco se retorna la descarga
            if existe_cache:

                return send_file(
                    path_or_file = existe_cache,
                    mimetype = "application/pdf",
                    as_attachment = True,
                    download_name=f"certificado_alumno_regular_{formulario['rut_estudiante']}.pdf"

                )

            ######## Se obtiene el estado del uso de nuestro generador de pases
            # si esta disponible se usa si no esperar hasta que termine el otro usuario.
            key_cache_cola = "pdf_cola"
            lock = cachear.get(key_cache_cola)
            
            if lock:
                return redirect(
                    url_for(
                        "retirar_alumno",
                        codigo=400,
                        mensaje="Hay demasiados usuarios generando informes. Por favor, espere."
                    )
                )

            ########## Le pasamos informacion actualizada directamente desde la variable global para evitar malos formatos
            formulario_certificado = {
                "telefono_colegio": PERSONALIZACION_WEB["telefono_colegio"],
                "direccion_colegio": PERSONALIZACION_WEB["direccion_colegio"],
                "nombre_director": PERSONALIZACION_WEB["nombre_director"],
                "rut_estudiante": formulario["rut_estudiante"]
            }


            ############## Se agrego una cola para evitar cuellos de botella en la app
            cachear.set(key_cache_cola, True, timeout=20)
            try:
                # generar el PDF
                resultado_alumno_reg = bdd.Informes_pdf.generar_certificado_alumno_regular("tmp_alumno_regular", formulario_certificado)

            finally:
                # liberar el lock SIEMPRE
                cachear.delete(key_cache_cola)

            ############## 

            if resultado_alumno_reg["codigo"] != 200:
                return redirect(url_for("apoderado", codigo = resultado_alumno_reg["codigo"], mensaje = resultado_alumno_reg["mensaje"]))

            resultado_alumno_reg = resultado_alumno_reg["mensaje"]

            # Si es que retorna la url de descarga redirigir a la descarga
            cachear.set(cache_key, resultado_alumno_reg, timeout=0) # Se cachea indefinidamente hasta que se ejecute "nuevo ano"
            return send_file(
                path_or_file = resultado_alumno_reg,
                mimetype = "application/pdf",
                as_attachment = True,
                download_name=f"certificado_alumno_regular_{formulario['rut_estudiante']}.pdf"
            )

    ############### ZONA GET


    cache_key = rut_apoderado + "_perfil"

    ########## Cache de apoderado para su perfil
    resultado_apoderado = cachear.get(cache_key)
    
    if resultado_apoderado:
        return render_template(
            "apoderado/principal_apoderado.html",
            informacion_cargas = resultado_apoderado["mensaje"],
            rutas_permitidas = rutas_permitidas_usuario
        )

    resultado_apoderado = bdd.Apoderado.buscar_hijos(rut_apoderado)

    if resultado_apoderado["codigo"] != 200:
        return render_template(
            "apoderado/principal_apoderado.html",
            error = resultado_apoderado,
            rutas_permitidas = rutas_permitidas_usuario
        )

    ######### Guardar en cache el perfil
    cachear.set(cache_key, resultado_apoderado, timeout=300)
    return render_template(
        "apoderado/principal_apoderado.html",
        informacion_cargas = resultado_apoderado["mensaje"],
        rutas_permitidas = rutas_permitidas_usuario
    )

@app.route("/retirar_alumno", methods = ["GET", "POST"])
@limitador.limit("3/minute")
def retirar_alumno():

    rutas_permitidas_usuario = bdd.obtener_navbar(session, RUTAS)

    apoderado_informacion = {
        "nombre": session["informacion"]["nombres"] + " " + session["informacion"]["apellidos"],
        "rut": session["informacion"]["rut"]
    }

    if request.method == "POST":

        formulario = request.form.to_dict()

        if "accion" not in formulario:
            return redirect(url_for("retirar_alumno", codigo = 404, mensaje = "ERROR: Estas enviando un formulario incompleto."))
        
        if formulario["accion"] == "descargar_pase":
            
            lock = cachear.get("pdf_cola")
            
            if lock:
                return redirect(
                    url_for(
                        "retirar_alumno",
                        codigo=400,
                        mensaje="Hay demasiados usuarios generando informes. Por favor, espere."
                    )
                )
            
            cachear.set("pdf_cola", True, timeout=20)
            try:
                # generar el PDF
                resultado = bdd.Informes_pdf.generar_pase_de_salida("tmp_pase", formulario)

            finally:
                # liberar el lock SIEMPRE
                cachear.delete("pdf_cola")

            if resultado["codigo"] == 200:
                return Response(
                    resultado["mensaje"],
                    mimetype="application/pdf",
                    headers={
                        "Content-Disposition": "inline; filename=pase_retiro.pdf"
                    }
                )

        return redirect(url_for("retirar_alumno", codigo = resultado["codigo"], mensaje = resultado["mensaje"]))

    ################### ZONA GET

    pases_para_generar = bdd.Apoderado.obtener_pases(session["informacion"]["rut"])
    if pases_para_generar["codigo"] != 200:
        return render_template(
            "apoderado/retirar_alumno.html",
            error = pases_para_generar,
            informacion_apoderado = apoderado_informacion,
            rutas_permitidas = rutas_permitidas_usuario
        )

    return render_template(
        "apoderado/retirar_alumno.html",
        pases = pases_para_generar["mensaje"],
        informacion_apoderado = apoderado_informacion,
        rutas_permitidas = rutas_permitidas_usuario
    )

############################## Encargado de generar pases

@app.route("/generar_pase", methods = ["GET", "POST"])
def generar_pase():

    rutas_permitidas_usuario = bdd.obtener_navbar(session, RUTAS)

    informacion_encargado = {
        "nombre": session["informacion"]["nombres"] + " " + session["informacion"]["apellidos"] + "Cargo: " + session["informacion"]["cargo"].capitalize(),
        "rut": session["informacion"]["rut"]
    }

    if request.method == "POST":

        formulario = request.form.to_dict()
        print("xd")
        if "accion" not in formulario:
            return redirect(url_for("generar_pase", codigo = 404, mensaje = "ERROR: Estas enviando un formulario incompleto."))

        if formulario["accion"] == "buscar_carga":
            
            if "rut" not in formulario:
                return redirect(url_for("generar_pase", codigo = 404, mensaje = "ERROR: Estas enviando un formulario incompleto."))

            rut_apoderado = request.form["rut"]
            informacion_apoderado_cargas = bdd.Apoderado.buscar_hijos(rut_apoderado, apoderado_only=True)
            print(informacion_apoderado_cargas)

            if informacion_apoderado_cargas["codigo"] != 200:
                return redirect(url_for("generar_pase",
                    codigo = informacion_apoderado_cargas["codigo"],
                    mensaje = informacion_apoderado_cargas["mensaje"]
                ))
            
            return render_template("administrador/generar_pase_virtual.html",
                informacion_rut = informacion_apoderado_cargas["mensaje"],
                mostrar_info = True,

                informacion_encargado = informacion_encargado,
                db_documento = rut_apoderado,

                rutas_permitidas = rutas_permitidas_usuario
            )
            
        if formulario["accion"] == "generar_pase":

            resultado_pase = bdd.Apoderado.asignar_pase(formulario["rut_apoderado"], formulario)            
            return redirect(url_for("generar_pase", codigo = resultado_pase["codigo"], mensaje = resultado_pase["mensaje"]))

        
    return render_template(
        "administrador/generar_pase_virtual.html",
        get = True,
        informacion_encargado = informacion_encargado,
        rutas_permitidas = rutas_permitidas_usuario
    )


if __name__ == '__main__':
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )