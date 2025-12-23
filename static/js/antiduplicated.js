
document.addEventListener('DOMContentLoaded', function () {

    document.addEventListener('submit', function (e) {
        const form = e.target;
        if (!(form instanceof HTMLFormElement)) return;

        // event.submitter es el botón que disparó el submit (soportado en navegadores modernos)
        const submitter = e.submitter || form.querySelector('button[type="submit"], input[type="submit"]');

        if (!submitter) return;

        // Si ya está deshabilitado, prevenir envío adicional
        if (submitter.hidden) {
            e.preventDefault();
            return;
        }

        // Deshabilitar y marcar accesibilidad
        submitter.hidden = true;
        submitter.setAttribute('aria-busy', 'true');
    });

});

