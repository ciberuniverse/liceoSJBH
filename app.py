import bdd
from flask import Flask, render_template, session, request, redirect, url_for, Response

app = Flask(__name__)
app.secret_key = bdd.SECRET_KEY

RUTAS = bdd.Users.leer_routes(True)
PERSONALIZACION_WEB = bdd.Settings.leer_settings(True)

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

########################################### SECCION PUBLICA

@app.route("/home", methods = ["GET"])
def home():

    noticias_list = bdd.Public.listar_noticias_home()

    if noticias_list["codigo"] != 200:
        return render_template("home.html")
    
    return render_template("home.html", noticias = noticias_list["mensaje"])

@app.route("/logout", methods = ["GET"])
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/contactanos", methods = ["POST", "GET"])
def contactanos():

    if request.method == "POST":

        if "accion" not in request.form:
            return "error"

        if request.form["accion"] == "contactar":
            
            mensaje = request.form.to_dict()
            mensaje.pop("accion")
            
            respuesta = bdd.Public.nuevo_mensaje(mensaje)

        return redirect(url_for("contactanos", codigo = respuesta["codigo"], mensaje = respuesta["mensaje"]))

    ###################### Seccion GET

    return render_template("contacto/contacto.html")

@app.route("/login", methods = ["POST", "GET"])
def login():
    
    # Si es que el metodo de acceso es port se realiza una comprobacion del usuario y contraseña
    # si es que esta correcto, se guarda en la sesion la informacion del usuario y se utiliza para
    # redirigirle al panel correspondiente
    # 
    # Como se ve lo que devuelve la bdd
    # {"codigo": 000, "mensaje": "resultados o mensaje de error"}
    if request.method == "POST":

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
        cargo = session["informacion"]["cargo"]

        ##### Se obtienen las rutas del cargo asignado en routes.json y se redirige a la primera.
        return redirect(url_for(RUTAS["rol"][cargo][0]))

    ################# Seccion de metodo GET

    # Se verifica si tiene una sesion iniciada, si no es asi se redirige al login. En el caso contrario
    # se le redirige al cargo que tenga asociado en la sesion

    if not session:
        return render_template("login.html")

    cargo = session["informacion"]["cargo"]

    return redirect(url_for(RUTAS["rol"][cargo][0]))

@app.route("/micuenta", methods = ["POST", "GET"]) ########### GENERAL PARA T0DO AQUEL LOGEADO
def micuenta():

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

            resultado = bdd.Users.reestablecer_contrasena(formulario["rut"], formulario["contrasena"])

        return redirect(url_for("micuenta", codigo = resultado["codigo"], mensaje = resultado["mensaje"]))

    ################### ZONA GET

    informacion_rut = bdd.General.obtener_informacion_rut(session["informacion"]["rut"])
    
    if informacion_rut["codigo"] != 200:
        return render_template("micuenta.html", error = informacion_rut, rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]])

    return render_template("micuenta.html", informacion = informacion_rut, rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]])

@app.route("/seccion_de_noticias", methods = ["GET"])
def seccion_de_noticias():

    resultados = bdd.Public.obtener_ultimas_noticias()

    if resultados["codigo"] != 200:
        return render_template("secciones/seccion_de_noticias.html", error = resultados)

    return render_template("secciones/seccion_de_noticias.html", noticias = resultados["mensaje"])
    
@app.route("/talleres", methods = ["GET"])
def talleres():

    resultado_taller = bdd.General.todos_los_talleres()

    if resultado_taller["codigo"] != 200:
        return render_template("secciones/talleres.html", error = resultado_taller)

    return render_template("secciones/talleres.html", talleres = resultado_taller["mensaje"])

############################### Rutas panel del administrador
@app.route("/administrador", methods = ["POST", "GET"])
def administrador():

    if request.method == "POST":

        if request.form["accion"] == "crear":
            resultado = bdd.Administrador.crear_usuario(request.form.to_dict())

        return redirect(url_for("administrador", codigo = resultado["codigo"], mensaje = resultado["mensaje"]))

    ################# Seccion de metodo GET

    roles = RUTAS["rol"].keys()
    cursos = bdd.General.todos_los_cursos()
    if cursos["codigo"] != 200:
        cursos = [{"curso": "No disponible", "_id": "0", "alumnos": 0}]

    cursos = cursos["mensaje"]

    # Usar el url para cambiar de acciones a utlizar pero no cambiar de direccion. es decir cambiar solo la plantilla
    return render_template("administrador/administrador.html",
        cursos = cursos,
        roles = roles,
        rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]]
    )

@app.route("/administrador_mensajes", methods = ["POST", "GET"])
def administrador_mensajes():
    # Obtener listado de mensajes (se usa tanto en GET como en POST)
    resultado = bdd.Administrador.listar_mensajes(0)

    if resultado["codigo"] != 200:
        return render_template("administrador/contacto.html", error=resultado, rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]])

    # POST: marcar mensaje como visto
    if request.method == "POST":
        if request.form.get("accion") == "visto":
            id_contacto = request.form.get("id_de_contacto")
            respuesta = bdd.Administrador.marcar_mensaje_como_visto(id_contacto)

            if respuesta["codigo"] != 200:
                return render_template("administrador/contacto.html", contactos=resultado["mensaje"], error=respuesta, rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]])

            return render_template("administrador/contacto.html", contactos=resultado["mensaje"], exito=respuesta, rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]])

    # GET: mostrar listado de mensajes
    return render_template("administrador/contacto.html", contactos=resultado["mensaje"], rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]])

@app.route("/administrador_mensajes_vistos", methods = ["POST", "GET"])
def administrador_mensajes_vistos():
    resultado_lista_mensajes = bdd.Administrador.listar_mensajes(1) # Si en el futuro hay queja por repeticion de mensajes es por esto
    
    if resultado_lista_mensajes["codigo"] != 200:
        return render_template("administrador/contacto.html", error = resultado_lista_mensajes, rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]])

    if request.method == "POST":

        if request.form["accion"] == "eliminar":            
            respuesta_eliminacion = bdd.Administrador.eliminar_mensaje(request.form["id_de_contacto"])

        if respuesta_eliminacion["codigo"] != 200:
            
            return render_template("administrador/contacto.html",
                error = respuesta_eliminacion,
                rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]]
            )
        
        if resultado_lista_mensajes["codigo"] != 200:

            return render_template("administrador/contacto.html",
                error = resultado_lista_mensajes,
                exito = respuesta_eliminacion,
                rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]]
            )
        
        return render_template("administrador/contacto.html",
            contactos_vistos = resultado_lista_mensajes["mensaje"],
            exito = respuesta_eliminacion,
            rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]]
        )

    ################################### Seccion GET

    return render_template("administrador/contacto.html", contactos_vistos = resultado_lista_mensajes["mensaje"], rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]])

@app.route("/administrador_crear_taller", methods = ["POST", "GET"])
def administrador_crear_taller():

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
        rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]]
    )

@app.route("/administrar_taller_estudiantes", methods = ["POST", "GET"])
def administrar_taller_estudiantes():

    if request.method == "POST":

        accion = request.form["accion"]

        # Todo esto funciona en la misma plantilla, dependiendo de lo que se responda la plantilla reacciona y se devuelven
        # ciertos datos dependiendo de la accion

        if accion == "buscar_taller":

            resultado_taller = bdd.General.obtener_informacion_taller(request.form["taller"])

            return render_template("administrador/aceptar_usuarios_taller.html",
                buscar_taller = True,
                taller = resultado_taller["mensaje"],
                cargo = session["informacion"]["cargo"]
            )
        
        if accion == "inscribir_alumnos":

            data_alumnos = request.form.to_dict()
            data_alumnos.pop("accion")

            resultado_asignacion = bdd.Administrador.aceptar_alumnos(data_alumnos)
            
            return redirect(url_for("administrar_taller_estudiantes",
                codigo = resultado_asignacion["codigo"],
                mensaje = resultado_asignacion["mensaje"])
            )


        if accion == "quitar_del_taller":
            
            data_alumnos = request.form.to_dict()
            data_alumnos.pop("accion")

            resultado_quitar_del_taller = bdd.Administrador.quitar_alumnos_del_taller(data_alumnos)

            return redirect(url_for("administrar_taller_estudiantes", codigo = resultado_quitar_del_taller["codigo"], mensaje = resultado_quitar_del_taller["mensaje"]))

        if accion == "deshabilitar_taller":

            resultado = bdd.Administrador.deshabilitar_taller(request.form["id_taller"])

            return redirect(url_for("administrar_taller_estudiantes", codigo = resultado["codigo"], mensaje = resultado["mensaje"]))

        if accion == "habilitar_taller":

            resultado = bdd.Administrador.habilitar_taller(request.form["id_taller"])

            return redirect(url_for("administrar_taller_estudiantes", codigo = resultado["codigo"], mensaje = resultado["mensaje"]))

    ############## ZONA GET

    talleres_resultado = bdd.General.todos_los_talleres()

    if talleres_resultado["codigo"] != 200:
        return render_template("administrador/aceptar_usuarios_taller.html", error = talleres_resultado, rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]])

    return render_template("administrador/aceptar_usuarios_taller.html", get = True, talleres = talleres_resultado["mensaje"], rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]])

@app.route("/administrar_pagina", methods = ["POST", "GET"]) ######### USA PERSONALIZACION_WEB EN GLOBAL
def administrar_pagina():
    global PERSONALIZACION_WEB
    
    if request.method == "POST":

        formulario = request.form.to_dict()
        respuesta_modificar = bdd.Settings.modificar_template_base(formulario)

        if respuesta_modificar["codigo"] == 200:
            PERSONALIZACION_WEB = bdd.Settings.leer_settings(True)

        return redirect(url_for("administrar_pagina", codigo = respuesta_modificar["codigo"], mensaje = respuesta_modificar["mensaje"]))

    ################ ZONA GET
    
    return render_template("administrador/administrar_pagina.html", rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]])

@app.route("/crear_roles", methods = ["GET", "POST"]) ######### USA RUTAS EN GLOBAL
def crear_roles():
    global RUTAS

    if request.method == "POST":
        
        formulario = request.form.to_dict()

        resultado_crear_roles = bdd.Users.crear_rol(formulario)

        if resultado_crear_roles["codigo"] == 200:
            RUTAS = bdd.Users.leer_routes(True)

        return redirect(url_for("crear_roles", codigo = resultado_crear_roles["codigo"], mensaje = resultado_crear_roles["mensaje"]))

    ###################### ZONA GET

    routes_get = bdd.Users.leer_routes()

    if routes_get["codigo"] != 200:
        return render_template("administrador/crear_roles", error = routes_get, rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]])

    return render_template("administrador/crear_roles.html", routes = routes_get, rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]])

@app.route("/administrar_usuarios", methods = ["POST", "GET"])
def administrar_usuarios():

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
                    plantilla = "resultado_buscar"
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

        return redirect(url_for("administrar_usuarios", codigo = resultado["codigo"], mensaje = resultado["mensaje"]))


    ################# Zona GET

    return render_template("administrador/administrar_usuarios.html", get = True, cargos = RUTAS["rol"], rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]])

@app.route("/crear_curso", methods = ["POST", "GET"])
def crear_curso():

    if request.method == "POST":
        
        formulario_ = request.form.to_dict()
        if "accion" not in formulario_:
            return redirect(url_for("crear_curso", codigo = 500, mensaje = "ERROR: Formulario incompleto o corrupto."))

        if formulario_["accion"] == "crear_curso":
            resultado = bdd.Administrador.crear_curso(formulario_)

        return redirect(url_for("crear_curso", codigo = resultado["codigo"], mensaje = resultado["mensaje"]))

    profesores = bdd.General.listar_profesores()
    if profesores["codigo"] != 200:
        return profesores
    
    return render_template("administrador/crear_curso.html", profesores = profesores["mensaje"])

############################### Rutas de panel del noticiero

@app.route("/noticiero", methods = ["POST", "GET"])
def noticiero():

    if request.method == "POST":

        if request.form["accion"] == "crear_alerta":
            resultado = bdd.Noticiero.crear_alerta(request.form["titulo"], request.form["descripcion"])

        if request.form["accion"] == "crear_noticia":
            resultado = bdd.Noticiero.crear_noticia(request.form["titulo"], request.form["descripcion"], request.files)
            # Agregar imagen

        ########################################
        # TALLARIN CODIGO: LO AGREGE TIEMPO DESPUES
        ########################################
        if request.form["accion"] == "listar_alertas":
            resultado = bdd.Noticiero.listar_alertas()

            if resultado["codigo"] == 200:
                return render_template("noticiero/noticias.html", resultados = resultado["mensaje"], rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]])

        if request.form["accion"] == "listar_noticias":
            resultado = bdd.Noticiero.listar_noticias()

            if resultado["codigo"] == 200:            
                return render_template("noticiero/noticias.html", resultados = resultado["mensaje"], rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]])

        if request.form["accion"] == "eliminar_noti":
            resultado = bdd.Noticiero.eliminar_noticia(request.form["id_noticia"])
        
        if request.form["accion"] == "modificar_noti":
            resultado = bdd.Noticiero.modificar_noticia(request.form, request.files)

        ########################################
        
        # Esto redirige a la pagina principal de noticiero con el codigo de error
        return redirect(url_for("noticiero", codigo = resultado["codigo"], mensaje = resultado["mensaje"]))

    return render_template("noticiero/noticiero.html", rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]])

################### API NOTICIAS OBTENER LA ULTIMA NOTICIA URGENTE
@app.route("/urgente")
def urgente():

    resultado = bdd.Public.obtener_ultima_alerta()

    if resultado["codigo"] != 200:
        return resultado
    
    return resultado["mensaje"]

############################### Rutas de panel del profesor

@app.route("/profesor", methods = ["POST", "GET"])
def profesor():

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
            return render_template("profesor/administrar_curso.html", informacion_curso = respuesta["mensaje"], rut_profesor = session["informacion"]["rut"])

        if formulario["accion"] == "subir_notas":
            respuesta = bdd.Profesor.asignar_notas(formulario)

        if formulario["accion"] == "pasar_lista":
            respuesta = bdd.Profesor.pasar_lista(formulario)
        
        print(respuesta)

        return redirect(url_for("profesor", codigo = respuesta["codigo"], mensaje = respuesta["mensaje"]))




    #################### Seccion GET
    lista_cursos = bdd.Profesor.listar_cursos_de_profesor(session["informacion"]["rut"])

    if lista_cursos["codigo"] != 200:
        return redirect(url_for("administrar_taller_estudiantes", codigo = lista_cursos["codigo"], mensaje = lista_cursos["mensaje"]))

    return render_template("profesor/profesor.html", informacion_profesor = lista_cursos["mensaje"], rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]])

@app.route("/profesor_taller", methods = ["POST", "GET"])
def profesor_taller():
    # Se obtiene el taller asignado al profesor usando su RUT desde la sesión
    profesor_taller = bdd.Profesor.listar_taller_de_profesor(session["informacion"]["rut"])

    # Si hubo un error al obtener el taller, se muestra la plantilla con el mensaje de error
    if profesor_taller["codigo"] != 200:
        return render_template("profesor/profesor_taller.html", error = profesor_taller, rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]])

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
    return render_template("profesor/profesor_taller.html", taller = profesor_taller["mensaje"], rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]])

@app.route("/profesor_jefe_crear", methods = ["POST", "GET"])
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

    ############### ZONA GET

    informacion_perfil = bdd.Estudiante.resumen_de_mi_perfil(session["informacion"]["rut"])
    
    if informacion_perfil["codigo"] != 200:
        
        return render_template("estudiante/estudiante.html",
            error = informacion_perfil,
            rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]]
        )


    return render_template("estudiante/estudiante.html", perfil = informacion_perfil["mensaje"], rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]])

@app.route("/taller_estudiante", methods = ["POST", "GET"])
def taller_estudiante():

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
        return render_template("estudiante/talleres.html", in_taller = True, informacion_rut = verificacion_taller["mensaje"], rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]])

    # Si el usuario esta esta en un taller o da error
    if verificacion_taller["codigo"] != 200:
        return render_template("estudiante/talleres.html", error = verificacion_taller, rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]])
    
    #######################################

    resultado = bdd.General.todos_los_talleres()

    if resultado["codigo"] != 200:
        return render_template("estudiante/talleres.html", error = resultado) # Esto redirige a una pagina de error

    return render_template("estudiante/talleres.html", not_in_taller = True, talleres = resultado["mensaje"], rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]])

############################### Ruta plataforma Apoderado

@app.route("/apoderado", methods = ["GET", "POST"])
def apoderado():
    
    if request.method == "POST":

        formulario = request.form.to_dict()
        if "accion" not in formulario:
            return redirect(url_for("apoderado", codigo = 404, mensaje = "ERROR: Estas enviando formularios incompletos."))
        
        if "obtener_certificado" == formulario["accion"]:

            if "rut_estudiante" not in formulario:
                return redirect(url_for("apoderado", codigo = 404, mensaje = "ERROR: Estas enviando formularios incompletos."))

            ########## Le pasamos informacion actualizada directamente desde la variable global para evitar malos formatos
            formulario_certificado = {
                "telefono_colegio": PERSONALIZACION_WEB["telefono_colegio"],
                "direccion_colegio": PERSONALIZACION_WEB["direccion_colegio"],
                "nombre_director": PERSONALIZACION_WEB["nombre_director"],
                "rut_estudiante": formulario["rut_estudiante"]
            }

            resultado_alumno_reg = bdd.Informes_pdf.generar_certificado_alumno_regular("tmp_alumno_regular", formulario_certificado)

            if resultado_alumno_reg["codigo"] != 200:
                return redirect(url_for("apoderado", codigo = resultado_alumno_reg["codigo"], mensaje = resultado_alumno_reg["mensaje"]))

            return Response(
                resultado_alumno_reg["mensaje"],
                mimetype="application/pdf",
                headers={
                    "Content-Disposition": f"inline; filename=certificado_alumno_regular_{formulario['rut_estudiante']}.pdf"
                }
            )
    ############### ZONA GET

    rut_apoderado = session["informacion"]["rut"]
    resultado_apoderado = bdd.Apoderado.buscar_hijos(rut_apoderado)

    if resultado_apoderado["codigo"] != 200:
        return render_template("apoderado/principal_apoderado.html", error = resultado_apoderado)

    return render_template("apoderado/principal_apoderado.html", informacion_cargas = resultado_apoderado["mensaje"], rutas_permitidas = RUTAS["rol"][session["informacion"]["cargo"]])

@app.route("/retirar_alumno", methods = ["GET", "POST"])
def retirar_alumno():

    apoderado_informacion = {
        "nombre": session["informacion"]["nombres"] + " " + session["informacion"]["apellidos"],
        "rut": session["informacion"]["rut"]
    }

    if request.method == "POST":

        formulario = request.form.to_dict()

        if "accion" not in formulario:
            return redirect(url_for("retirar_alumno", codigo = 404, mensaje = "ERROR: Estas enviando un formulario incompleto."))
        
        if formulario["accion"] == "descargar_pase":
            
            # Envia el formulario que ya esta hecho por el inspector lo envia a la seccion de generar pase. Y genera el informe.
            resultado = bdd.Informes_pdf.generar_pase_de_salida("tmp_pase", formulario)

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
        return render_template("apoderado/retirar_alumno.html", error = pases_para_generar, informacion_apoderado = apoderado_informacion)

    return render_template("apoderado/retirar_alumno.html", pases = pases_para_generar["mensaje"], informacion_apoderado = apoderado_informacion) 

############################## Encargado de generar pases

@app.route("/generar_pase", methods = ["GET", "POST"])
def generar_pase():

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
            informacion_apoderado_cargas = bdd.Apoderado.buscar_hijos(rut_apoderado)

            if informacion_apoderado_cargas["codigo"] != 200:
                return redirect(url_for("generar_pase",
                    codigo = informacion_apoderado_cargas["codigo"],
                    mensaje = informacion_apoderado_cargas["mensaje"]
                ))
            
            return render_template("administrador/generar_pase_virtual.html",
                informacion_rut = informacion_apoderado_cargas["mensaje"],
                mostrar_info = True,

                informacion_encargado = informacion_encargado,
                db_documento = rut_apoderado
            )
            
        if formulario["accion"] == "generar_pase":

            resultado_pase = bdd.Apoderado.asignar_pase(formulario["rut_apoderado"], formulario)            
            return redirect(url_for("generar_pase", codigo = resultado_pase["codigo"], mensaje = resultado_pase["mensaje"]))

        
    return render_template("administrador/generar_pase_virtual.html", get = True, informacion_encargado = informacion_encargado)


if __name__ == '__main__':
    app.run(debug=True)