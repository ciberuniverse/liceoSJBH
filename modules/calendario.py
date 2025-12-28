import calendar
import datetime

fecha_actual = str(datetime.datetime.now().strftime("%d-%m-%Y"))

buttons = """
<button class="cal-prev" onclick='mostrar_mes("volver")'>‹</button>
<button class="cal-next" onclick='mostrar_mes("siguiente")'>›</button>
"""

js = """
<script>
let mes_actual = int_mes_actual

document.addEventListener("DOMContentLoaded", () => {
  const container = document.querySelector(".calendar-scroll");
  if (!container) return;

  // coger todas las tablas month (en el orden del DOM)
  const monthEls = Array.from(container.querySelectorAll("table.month"));
  if (!monthEls.length) return;

  // detectar cuál venía visible por inline style (block) si existe
  let initialEl = monthEls.find(m => (m.getAttribute("style") || "").includes("display") && (m.style.display === "block" || m.getAttribute("style").includes("display: block")));
  // fallback: mes actual del sistema (1-12) si no se detecta
  if (!initialEl) {
    const now = new Date();
    const idx = Math.max(0, Math.min(monthEls.length - 1, now.getMonth())); // 0-based
    initialEl = monthEls[idx];
  }

  // quitar atributos style inline para evitar conflictos, y reset clases
  monthEls.forEach(m => {
    m.removeAttribute("style");
    m.classList.remove("is-active");
  });

  // activar inicial
  initialEl.classList.add("is-active");

  // establecer mes_actual global (1..N) usando el id si existe 'mes_01' etc.
  let mes_actual = (() => {
    const id = initialEl.id || "";
    const match = id.match(/mes_(\d+)/);
    if (match) return parseInt(match[1], 10);
    // si no hay id, usar índice+1
    return monthEls.indexOf(initialEl) + 1;
  })();
  window.mes_actual = mes_actual;

  // exportar mostrar_mes global para tus botones inline onclick
  window.mostrar_mes = function(volver_siguiente) {
    const max = monthEls.length;
    const oldIndex = mes_actual - 1;
    if (volver_siguiente === "siguiente") {
      if (mes_actual >= max) return;
      mes_actual++;
    } else if (volver_siguiente === "volver") {
      if (mes_actual <= 1) return;
      mes_actual--;
    } else return;

    // swap clases (sin tocar display)
    monthEls[oldIndex].classList.remove("is-active");
    monthEls[mes_actual - 1].classList.add("is-active");
    // update global
    window.mes_actual = mes_actual;
  };

  // --- Modal: inyectar element en body ---
  const modal = document.createElement("div");
  modal.id = "calendarModal";
  modal.className = "calendar-modal";
  modal.innerHTML = `
    <div class="calendar-modal-content" role="dialog" aria-modal="true">
      <div class="calendar-modal-title" id="modalTitle"></div>
      <div class="calendar-modal-desc" id="modalDesc"></div>
      <button class="calendar-modal-close" id="modalClose">Cerrar</button>
    </div>
  `;
  document.body.appendChild(modal);

  const modalTitle = modal.querySelector("#modalTitle");
  const modalDesc = modal.querySelector("#modalDesc");
  const modalClose = modal.querySelector("#modalClose");

  const openModal = (title, desc) => {
    modalTitle.textContent = title || "";
    modalDesc.textContent = desc || "";
    modal.classList.add("active");
    // lock scroll
    document.documentElement.style.overflow = "hidden";
  };
  const closeModal = () => {
    modal.classList.remove("active");
    document.documentElement.style.overflow = "";
  };

  modalClose.addEventListener("click", closeModal);
  modal.addEventListener("click", (e) => { if (e.target === modal) closeModal(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

  // enlazar clicks en eventos existentes
  container.querySelectorAll(".calendar-event").forEach(ev => {
    ev.addEventListener("click", (e) => {
      e.stopPropagation();
      const t = ev.querySelector(".event-title")?.textContent?.trim() || "";
      const d = ev.querySelector(".event-desc")?.textContent?.trim() || "";
      openModal(t, d);
    });
  });
});

</script>
"""

template_json = """
>
  str_dia
  <div class="calendar-event">
    <span class="event-title">string_titulo</span>
    <span class="event-desc">string_descripcion</span>
  </div>
</td>
"""
def __retornar_html_dia(dia, evento_descripcion: dict):
    return_json = template_json.replace("str_dia", dia).replace("string_titulo", evento_descripcion["titulo"]).replace("string_descripcion", evento_descripcion["descripcion"])
    return return_json

def __espanol_calendario(calendario_str: str) -> str:

    dic_espn = {
        "Mon": "Lunes",
        "Tue": "Martes",
        "Wed": "Miercoles",
        "Thu": "Jueves",
        "Fri": "Viernes",
        "Sat": "Sabado",
        "Sun": "Domingo",
        "January": "Enero",
        "February": "Febrero",
        "March": "Marzo",
        "April": "Abril",
        "May": "Mayo",
        "June": "Junio",
        "July": "Julio",
        "August": "Agosto",
        "September": "Septiembre",
        "October": "Octubre",
        "November": "Noviembre",
        "December": "Diciembre"
    }

    for ingles, espanol in dic_espn.items():
        calendario_str = calendario_str.replace(ingles, espanol)

    return calendario_str

def actualizar_calendario(eventos_list: dict = [{"_id": "tmp", "fecha_evento": "22-11-2025", "titulo": "test", "descripcion": "test"}]) -> str:
    global js

    ano_actual = fecha_actual.split("-")[2]
    calendario_html = calendar.HTMLCalendar().formatyear(theyear=2025, width=5).split("</table>")

    count_mes = 0
    calendario_save = []
    ###### Se itera cada mes dentro de las tablas html retornadas por la libreria calendar
    for mes in calendario_html:

        ##### Si el mes contiene menos de 400 caracteres se asume que no contiene datos del mes y se salta
        if len(mes) < 400:
            continue
        
        ##### Se le suma un mes a nuestro contador
        count_mes += 1

        ##### Se itera cada evento guardado por el momento en un dict.
        fecha_evento: str; detalles: dict

        for evento in eventos_list:

          fecha_evento = evento["fecha_evento"]
          titulo = evento["titulo"]
          descripcion = evento["descripcion"]

          detalles = {
            "titulo": titulo,
            "descripcion": descripcion
          }

          dia_evento, mes_evento, ano_evento = fecha_evento.split("-") # Queda como [12, 12, 2025]
          if count_mes < 10:
              count_mes_str = "0" + str(count_mes)
          
          else:
              count_mes_str = str(count_mes)

          if count_mes_str != mes_evento or ano_evento != ano_actual:
              continue

          #### De coincidir el mes con el año se reemplazara la fecha con un html
          # Dejando en claro el evento asignado
          if int(dia_evento) < 10:
              dia_evento = str(int(dia_evento))
          
          close_dia: str = ">" + dia_evento + "</td>"
          """Variable utilizada para reemplazar de forma correcta la informacion en el html."""

          evento_comlpemento = __retornar_html_dia(dia_evento, detalles)
          mes = mes.replace(close_dia, evento_comlpemento)

        ################## INCLUCION CORRECTA PARA VISUALIZAR EL CALENDARIO
        display = "none"
        if "-" + count_mes_str + "-" in fecha_actual:
            display = "block"
    
        #replace_var = f'class="month" id="mes_{count_mes_str}" style="display: {display};"'
        replace_var = f'><table id="mes_{count_mes_str}" style="display: {display};"'

        mes = mes.replace('><table', replace_var)
        calendario_save.append(mes + "</table>")

    js = js.replace("int_mes_actual", count_mes_str)
    calendario_save = "\n".join(calendario_save)
    calendario_save = __espanol_calendario(calendario_save)

    calendario_save = buttons + '<div class="calendar-scroll">\n' + calendario_save + "</div>\n" + js
    return calendario_save

