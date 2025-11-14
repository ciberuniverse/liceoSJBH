import bdd
from flask import Flask, render_template, session, request, redirect, url_for

app = Flask(__name__)
app.secret_key = "xd"

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

#########################

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


        session["informacion"] = cookies["mensaje"]
        cargo = session["informacion"]["cargo"]

        if "estudiante" == cargo:
            return redirect(url_for("estudiante"))

        if "profesor" == cargo:
            return redirect(url_for("profesor"))
        
        if "noticiero" == cargo:
            return redirect(url_for("noticiero"))
        
        if "administrador" == cargo:
            return redirect(url_for("administrador"))
        
        return "error no logro obtener ninguna respuesta para este caso"

    ################# Seccion de metodo GET

    # Se verifica si tiene una sesion iniciada, si no es asi se redirige al login. En el caso contrario
    # se le redirige al cargo que tenga asociado en la sesion

    if not session:
        return render_template("login.html")

    cargo = session["informacion"]["cargo"]

    if "estudiante" == cargo:
        return redirect(url_for("estudiante"))

    if "profesor" == cargo:
        return redirect(url_for("profesor"))
    
    if "noticiero" == cargo:
        return redirect(url_for("noticiero"))
    
    if "administrador" == cargo:
        return redirect(url_for("administrador"))

    return "error no logro obtener ninguna respuesta para este caso"

############################### Seccion de noticias
@app.route("/seccion_de_noticias", methods = ["GET"])
def seccion_de_noticias():

    resultados = bdd.Public.obtener_ultimas_noticias()

    if resultados["codigo"] != 200:
        return render_template("secciones/seccion_de_noticias.html", error = resultados)

    return render_template("secciones/seccion_de_noticias.html", noticias = resultados["mensaje"])
    
############################### Taller seccion estatica publica
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

    # Usar el url para cambiar de acciones a utlizar pero no cambiar de direccion. es decir cambiar solo la plantilla
    return render_template("administrador/administrador.html", roles = roles)

@app.route("/administrador_mensajes", methods = ["POST", "GET"])
def administrador_mensajes():
    # Obtener listado de mensajes (se usa tanto en GET como en POST)
    resultado = bdd.Administrador.listar_mensajes(0)

    if resultado["codigo"] != 200:
        return render_template("administrador/contacto.html", error=resultado)

    # POST: marcar mensaje como visto
    if request.method == "POST":
        if request.form.get("accion") == "visto":
            id_contacto = request.form.get("id_de_contacto")
            respuesta = bdd.Administrador.marcar_mensaje_como_visto(id_contacto)

            if respuesta["codigo"] != 200:
                return render_template("administrador/contacto.html", contactos=resultado["mensaje"], error=respuesta)

            return render_template("administrador/contacto.html", contactos=resultado["mensaje"], exito=respuesta)

    # GET: mostrar listado de mensajes
    return render_template("administrador/contacto.html", contactos=resultado["mensaje"])

@app.route("/administrador_mensajes_vistos", methods = ["POST", "GET"])
def administrador_mensajes_vistos():
    resultado_lista_mensajes = bdd.Administrador.listar_mensajes(1) # Si en el futuro hay queja por repeticion de mensajes es por esto
    
    if resultado_lista_mensajes["codigo"] != 200:
        return render_template("administrador/contacto.html", error = resultado_lista_mensajes)

    if request.method == "POST":

        if request.form["accion"] == "eliminar":            
            respuesta_eliminacion = bdd.Administrador.eliminar_mensaje(request.form["id_de_contacto"])

        if respuesta_eliminacion["codigo"] != 200:
            return render_template("administrador/contacto.html", error = respuesta_eliminacion)
        
        if resultado_lista_mensajes["codigo"] != 200:
            return render_template("administrador/contacto.html", error = resultado_lista_mensajes, exito = respuesta_eliminacion)
        
        return render_template("administrador/contacto.html", contactos_vistos = resultado_lista_mensajes["mensaje"], exito = respuesta_eliminacion)

    ################################### Seccion GET

    return render_template("administrador/contacto.html", contactos_vistos = resultado_lista_mensajes["mensaje"])

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
        return redirect(url_for("administrador_crear_taller", codigo = resultado["codigo"], mensaje = resultado["mensaje"]))

    return render_template("administrador/crear_taller.html", profesores = resultado_profesores["mensaje"])

@app.route("/administrar_taller_estudiantes", methods = ["POST", "GET"])
def administrar_taller_estudiantes():

    if request.method == "POST":

        accion = request.form["accion"]

        # Todo esto funciona en la misma plantilla, dependiendo de lo que se responda la plantilla reacciona y se devuelven
        # ciertos datos dependiendo de la accion

        if accion == "buscar_taller":

            resultado_taller = bdd.General.obtener_informacion_taller(request.form["taller"])

            return render_template("administrador/aceptar_usuarios_taller.html", buscar_taller = True, taller = resultado_taller["mensaje"])
        
        if accion == "inscribir_alumnos":

            data_alumnos = request.form.to_dict()
            data_alumnos.pop("accion")

            resultado_asignacion = bdd.Administrador.aceptar_alumnos(data_alumnos)
            
            return redirect(url_for("administrar_taller_estudiantes", codigo = resultado_asignacion["codigo"], mensaje = resultado_asignacion["mensaje"]))


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
        return render_template("administrador/aceptar_usuarios_taller.html", error = talleres_resultado)

    return render_template("administrador/aceptar_usuarios_taller.html", get = True, talleres = talleres_resultado["mensaje"])

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
    
    return render_template("administrador/administrar_pagina.html")

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
        return render_template("administrador/crear_roles", error = routes_get)

    return render_template("administrador/crear_roles.html", routes = routes_get)


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

    return render_template("administrador/administrar_usuarios.html", get = True, cargos = RUTAS["rol"])

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
                return render_template("noticiero/noticias.html", resultados = resultado["mensaje"])

        if request.form["accion"] == "listar_noticias":
            resultado = bdd.Noticiero.listar_noticias()

            if resultado["codigo"] == 200:            
                return render_template("noticiero/noticias.html", resultados = resultado["mensaje"])

        if request.form["accion"] == "eliminar_noti":
            resultado = bdd.Noticiero.eliminar_noticia(request.form["id_noticia"])
        
        if request.form["accion"] == "modificar_noti":
            resultado = bdd.Noticiero.modificar_noticia(request.form, request.files)

        ########################################
        
        # Esto redirige a la pagina principal de noticiero con el codigo de error
        return redirect(url_for("noticiero", codigo = resultado["codigo"], mensaje = resultado["mensaje"]))

    return render_template("noticiero/noticiero.html")

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

    #################### Seccion GET

    lista_cursos = bdd.Profesor.listar_cursos_de_profesor(session["informacion"]["rut"])

    ############# USAR AGREGATE PARA OBTENER LOS RUTS DE LOS PARTICIPANTES del CURSO

    if lista_cursos["codigo"] != 200:
        return redirect(url_for("administrar_taller_estudiantes", codigo = lista_cursos["codigo"], mensaje = lista_cursos["mensaje"]))

    return render_template("profesor/profesor.html", cursos = lista_cursos["mensaje"])

@app.route("/profesor_taller", methods = ["POST", "GET"])
def profesor_taller():
    # Se obtiene el taller asignado al profesor usando su RUT desde la sesión
    profesor_taller = bdd.Profesor.listar_taller_de_profesor(session["informacion"]["rut"])

    # Si hubo un error al obtener el taller, se muestra la plantilla con el mensaje de error
    if profesor_taller["codigo"] != 200:
        return render_template("profesor/profesor_taller.html", error=profesor_taller)

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
        return redirect(url_for("profesor_taller", codigo=resultado["codigo"], mensaje=resultado["mensaje"]))

    # Si el método es GET, se muestra la plantilla con los datos del taller
    return render_template("profesor/profesor_taller.html", taller=profesor_taller["mensaje"])

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
        return render_template("profesor/jefe/crear.html", error = resultado_profesores)

    return render_template("profesor/jefe/crear.html", profesores = resultado_profesores["mensaje"])


############################### Rutas de panel del estudiante

@app.route("/estudiante", methods = ["POST", "GET"])
def estudiante():
    return render_template("estudiante/estudiante.html")

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
        return render_template("estudiante/talleres.html", in_taller = True, informacion_rut = verificacion_taller["mensaje"])

    # Si el usuario esta esta en un taller o da error
    if verificacion_taller["codigo"] != 200:
        return render_template("estudiante/talleres.html", error = verificacion_taller)
    
    #######################################

    resultado = bdd.General.todos_los_talleres()

    if resultado["codigo"] != 200:
        return render_template("estudiante/talleres.html", error = resultado) # Esto redirige a una pagina de error

    return render_template("estudiante/talleres.html", not_in_taller = True, talleres = resultado["mensaje"])

if __name__ == '__main__':
    app.run(debug=True)