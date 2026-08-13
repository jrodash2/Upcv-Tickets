document.addEventListener("DOMContentLoaded", function () {
  const sede = document.getElementById("id_sede");
  const puesto = document.getElementById("id_puesto");
  const crearPuestoSede = document.getElementById("id_puesto-rapido-sede");
  if (!sede || !puesto) return;

  const endpoint = puesto.dataset.puestosUrl;
  const setPlaceholder = (texto) => {
    puesto.innerHTML = "";
    const option = document.createElement("option");
    option.value = "";
    option.textContent = texto;
    puesto.appendChild(option);
  };

  async function cargarPuestos(conservarSeleccion) {
    const anterior = conservarSeleccion ? puesto.value : "";
    if (!sede.value) {
      setPlaceholder("Seleccione primero una sede");
      puesto.disabled = true;
      if (crearPuestoSede) crearPuestoSede.value = "";
      return;
    }
    puesto.disabled = true;
    setPlaceholder("Cargando puestos...");
    try {
      const response = await fetch(`${endpoint}?sede_id=${encodeURIComponent(sede.value)}`, {
        headers: { "X-Requested-With": "XMLHttpRequest" }
      });
      if (!response.ok) throw new Error("No fue posible consultar los puestos");
      const puestos = await response.json();
      setPlaceholder(puestos.length ? "Seleccione un puesto" : "No hay puestos registrados para esta sede");
      puestos.forEach(({ id, nombre }) => puesto.add(new Option(nombre, id)));
      if (anterior && puestos.some(({ id }) => String(id) === String(anterior))) puesto.value = anterior;
      if (crearPuestoSede) crearPuestoSede.value = sede.value;
    } catch (error) {
      setPlaceholder("No fue posible cargar los puestos");
    } finally {
      puesto.disabled = false;
    }
  }

  sede.addEventListener("change", () => cargarPuestos(false));
  cargarPuestos(true);
});
