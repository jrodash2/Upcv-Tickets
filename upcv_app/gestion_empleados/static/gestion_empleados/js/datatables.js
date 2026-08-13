document.addEventListener("DOMContentLoaded", function () {
  if (typeof simpleDatatables === "undefined") return;
  document.querySelectorAll("table.gestion-datatable").forEach(function (table) {
    if (!table.dataset.datatableReady) {
      new simpleDatatables.DataTable(table, {
        labels: {
          placeholder: "Buscar...",
          perPage: "registros por página",
          noRows: "No hay registros",
          info: "Mostrando {start} a {end} de {rows} registros"
        }
      });
      table.dataset.datatableReady = "true";
    }
  });
});
