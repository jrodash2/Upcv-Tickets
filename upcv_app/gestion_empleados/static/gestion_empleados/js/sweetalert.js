(function () {
  "use strict";

  function tema() {
    var estilos = window.getComputedStyle(document.body);
    return {
      background: estilos.backgroundColor,
      color: estilos.color,
      buttonsStyling: false,
      customClass: {
        confirmButton: "btn btn-primary mx-1",
        cancelButton: "btn btn-light mx-1",
        popup: "gestion-swal-popup",
      },
    };
  }

  function mostrar(opciones) {
    if (typeof window.Swal === "undefined") {
      console.error("SweetAlert2 no está disponible.");
      return Promise.resolve({ isConfirmed: false });
    }
    return window.Swal.fire(Object.assign({}, tema(), opciones));
  }

  function mostrarCola(mensajes, indice) {
    indice = indice || 0;
    if (indice >= mensajes.length) return;
    mostrar({
      icon: mensajes[indice].icon,
      title: mensajes[indice].title,
      text: mensajes[indice].text,
      confirmButtonText: "Aceptar",
    }).then(function () {
      mostrarCola(mensajes, indice + 1);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("form[data-confirm-stage]").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        if (form.dataset.confirmed === "true") return;
        // Degradación segura: si el recurso de SweetAlert2 no cargara, no se
        // bloquea la transición POST nativa del formulario.
        if (typeof window.Swal === "undefined") {
          console.error("SweetAlert2 no está disponible; se enviará el formulario sin interceptarlo.");
          return;
        }
        event.preventDefault();
        if (form.dataset.confirmationPending === "true") return;
        form.dataset.confirmationPending = "true";
        mostrar({
          title: form.dataset.confirmTitle || "¿Desea continuar?",
          text: form.dataset.confirmText || "Confirme esta acción para continuar.",
          icon: "question",
          showCancelButton: true,
          confirmButtonText: form.dataset.confirmButton || "Sí, continuar",
          cancelButtonText: "Cancelar",
          reverseButtons: true,
          focusCancel: true,
        }).then(function (resultado) {
          if (resultado.isConfirmed) {
            form.dataset.confirmed = "true";
            form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(function (control) {
              control.disabled = true;
            });
            form.submit();
          } else {
            delete form.dataset.confirmationPending;
          }
        });
      });
    });
  });

  window.GestionSwal = { mostrar: mostrar, mostrarCola: mostrarCola };
})();
