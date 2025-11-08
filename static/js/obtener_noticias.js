const LICEO = "Liceo San Juan Bautista de Hualqui"
const IDs = ["nombre_liceo_titulo", "nombre_liceo_banner", "nombre_liceo_footer"]

async function obtener_noticia() {

  try {
    const hora_actual = Date.now(); // Tiempo actual en milisegundos
    const hora_limite = localStorage.getItem("hora_limite"); // Recupera el límite guardado

    if (!hora_limite || Number(hora_limite) < hora_actual) {

        const buffer = hora_actual + 300000; // Suma 5 minutos (300.000 ms)
        localStorage.setItem("hora_limite", buffer.toString()); // Guarda el nuevo límite

    } else {

        const json_info = JSON.parse(localStorage.getItem("alerta"))

        document.getElementById("slides").innerHTML = `

          <article class="slide" aria-hidden="false">
            <div class="slide-media"
              style="background-image:linear-gradient(135deg,#e6f0ff,#fff);display:flex;align-items:center;justify-content:center">
              <svg width="120" height="120" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M3 7h18M3 12h18M3 17h18" stroke="#0b6cff" stroke-width="1.6" stroke-linecap="round">
                </path>
              </svg>
            </div>

            <div class="slide-content">
              <div class="kicker">Publicado el ${json_info.fecha_publicacion}</div>
              <h2>${json_info.titulo}</h2>

              <p>${json_info.descripcion}</p>
              <a class="btn" href="#noticias">Leer noticia</a>
            </div>
          </article>
        `
        return
    }

    // Crear un local storage que guarde las solicitudes por minuto en cache de localstorage
    
    const noticias = await fetch("/urgente")
    const json_info = await noticias.json()
    

    if (!JSON.stringify(json_info).includes("titulo")) {
        localStorage.removeItem("alerta")
        return
    }

    localStorage.setItem("alerta", JSON.stringify(json_info))

    document.getElementById("slides").innerHTML = `
          <article class="slide" aria-hidden="false">
            <div class="slide-media"
              style="background-image:linear-gradient(135deg,#e6f0ff,#fff);display:flex;align-items:center;justify-content:center">
              <svg width="120" height="120" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M3 7h18M3 12h18M3 17h18" stroke="#0b6cff" stroke-width="1.6" stroke-linecap="round">
                </path>
              </svg>
            </div>

            <div class="slide-content">
              <div class="kicker">Publicado el ${json_info.fecha_publicacion}</div>
              <h2>${json_info.titulo}</h2>

              <p>${json_info.descripcion}</p>
              <a class="btn" href="#noticias">Leer noticia</a>
            </div>
          </article>
    `
  } catch {
    console.log("ERROR: No hay ninguna noticia en la base de datos.")
  }
}

window.addEventListener("load", () => {

    /* Encargado de agregar el nombre del liceo dentro de la pagina web
    for (id of IDs) {
        document.getElementById(id).innerHTML = LICEO
    }
    */
    obtener_noticia()
})
