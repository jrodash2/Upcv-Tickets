/* global bootstrap, Swal */
(() => {
  'use strict';
  const root = document.getElementById('solicitud-admin');
  if (!root) return;
  const el = id => document.getElementById(id);
  const selects = Array.from(root.querySelectorAll('[data-componente]'));
  const navToggle = el('admin-nav-toggle');
  const backdrop = el('admin-nav-backdrop');
  const sidebar = document.querySelector('.sidebar-wrapper');
  sidebar?.querySelectorAll('.sidebar-submenu a').forEach(link => {
    if (!link.title) link.title = link.textContent.trim();
  });
  const mobile = window.matchMedia('(max-width: 991.98px)');
  function syncNavigation() {
    const open = mobile.matches ? document.body.classList.contains('admin-nav-open') : !document.body.classList.contains('admin-nav-collapsed');
    navToggle.setAttribute('aria-expanded', String(open));
    backdrop.hidden = !mobile.matches || !open;
    if (sidebar) sidebar.inert = !open;
  }
  function closeNavigation() {
    document.body.classList.remove('admin-nav-open');
    syncNavigation();
    navToggle.focus();
  }
  navToggle.addEventListener('click', () => {
    document.body.classList.toggle(mobile.matches ? 'admin-nav-open' : 'admin-nav-collapsed');
    syncNavigation();
    if (mobile.matches && document.body.classList.contains('admin-nav-open')) sidebar?.querySelector('a[aria-current]')?.focus();
  });
  backdrop.addEventListener('click', closeNavigation);
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && document.body.classList.contains('admin-nav-open')) closeNavigation();
  });
  mobile.addEventListener('change', () => {
    document.body.classList.remove('admin-nav-open');
    syncNavigation();
  });
  syncNavigation();
  const modalNode = el('editar-modal');
  const modal = bootstrap.Modal.getOrCreateInstance(modalNode);
  let current = null, sequence = 0, searchAbort = null, historyAbort = null;
  let historyPage = 1, retry = null, saving = false;
  const dateTime = value => new Date(value).toLocaleString('es-GT');
  const endpoint = (name, id) => root.dataset[name].replace('/0/', `/${id}/`);
  const show = (node, visible) => node.classList.toggle('d-none', !visible);
  const text = (id, value) => { el(id).textContent = value || ''; };
  const notify = async (message, icon = 'info') => {
    if (window.Swal) await Swal.fire({text: message, icon, confirmButtonText: 'Aceptar'});
    else window.alert(message);
  };
  async function request(url, options = {}) {
    let response;
    try {
      response = await fetch(url, {credentials: 'same-origin', ...options});
    } catch (err) {
      if (err.name === 'AbortError') throw err;
      throw new Error('No fue posible conectar. Compruebe la conexión e intente nuevamente.');
    }
    let data;
    try { data = await response.json(); }
    catch (_) { throw new Error('Respuesta no válida o sesión vencida. Actualice la página e intente nuevamente.'); }
    if (!response.ok || !data.success) {
      const err = new Error(data.error || 'No fue posible completar la operación.');
      err.code = data.code;
      throw err;
    }
    return data;
  }
  function resetSelect(index) {
    selects[index].replaceChildren(new Option('Seleccione…', ''));
    selects[index].disabled = true;
  }
  function hideDetail() {
    current = null;
    historyAbort?.abort();
    show(el('detalle-card'), false);
    show(el('historial-card'), false);
    modal.hide();
  }
  async function search(work, retryWork) {
    const ticket = ++sequence;
    searchAbort?.abort();
    searchAbort = new AbortController();
    hideDetail();
    text('busqueda-status', 'Consultando…');
    show(el('busqueda-loading'), true);
    show(el('reintentar-busqueda'), false);
    retry = retryWork;
    try {
      await work(searchAbort.signal, () => ticket === sequence);
    } catch (err) {
      if (ticket !== sequence || err.name === 'AbortError') return;
      text('busqueda-status', err.message);
      show(el('reintentar-busqueda'), true);
    } finally {
      if (ticket === sequence) show(el('busqueda-loading'), false);
    }
  }
  function parameters(count) {
    const params = new URLSearchParams();
    selects.slice(0, count).forEach(s => params.set(s.dataset.componente, s.value));
    return params;
  }
  async function loadOptions(index) {
    for (let i = index; i < selects.length; i++) resetSelect(i);
    await search(async (signal, active) => {
      const params = parameters(index);
      params.set('nivel', selects[index].dataset.componente);
      const data = await request(`${root.dataset.opciones}?${params}`, {signal});
      if (!active()) return;
      data.opciones.forEach(o => selects[index].add(new Option(o.label, o.value)));
      selects[index].disabled = !data.opciones.length;
      text('busqueda-status', data.opciones.length ? 'Seleccione una opción para continuar.' : 'No hay coincidencias para esta selección.');
      if (index === 0) text('historicos-aviso', data.historicos ? `${data.historicos} correlativo(s) con otro formato: utilice la consulta histórica exacta.` : 'También puede consultar un correlativo completo por su valor exacto.');
    }, () => loadOptions(index));
  }
  function addRow(body, values) {
    const row = document.createElement('tr');
    values.forEach(value => {
      const cell = document.createElement('td');
      cell.className = 'text-break';
      cell.textContent = value ?? '—';
      row.append(cell);
    });
    body.append(row);
  }
  function rows(id, items, mapper) {
    const body = el(id);
    body.replaceChildren();
    items.forEach(item => addRow(body, mapper(item)));
    if (!items.length) {
      const cell = document.createElement('td');
      cell.colSpan = body.closest('table').querySelectorAll('thead th').length;
      cell.textContent = 'Sin registros.';
      const row = document.createElement('tr'); row.append(cell); body.append(row);
    }
  }
  function renderDetail(data) {
    current = data;
    text('detalle-correlativo', data.correlativo);
    text('detalle-descripcion', data.descripcion);
    text('restriccion-estado', data.restriccion_estado);
    const general = el('detalle-general'); general.replaceChildren();
    [['Fecha de solicitud', dateTime(data.fecha_hora)], ['Estado actual', data.estado_label],
      ['Usuario solicitante', data.usuario], ['Departamento', data.departamento],
      ['Sección', data.seccion], ['Prioridad', data.prioridad]].forEach(([label, value]) => {
      const term = document.createElement('dt'); term.className = 'col-sm-4 col-lg-2'; term.textContent = label;
      const detail = document.createElement('dd'); detail.className = 'col-sm-8 col-lg-4 text-break';
      if (label === 'Estado actual') {
        const badge = document.createElement('span'); badge.className = `badge ${data.estado_badge}`;
        badge.textContent = value; detail.append(badge);
      } else detail.textContent = value;
      general.append(term, detail);
    });
    rows('detalle-insumos', data.insumos, i => [i.codigo, `${i.nombre} / ${i.presentacion}`, i.cantidad, i.caracteristicas, i.especiales]);
    rows('detalle-servicios', data.servicios, s => [s.nombre, s.cantidad, s.caracteristicas, s.observacion]);
    show(el('detalle-card'), true); show(el('historial-card'), true);
    loadHistory(1);
  }
  async function loadDetail(params) {
    await search(async (signal, active) => {
      const data = await request(`${root.dataset.detalle}?${params}`, {signal});
      if (!active()) return;
      renderDetail(data.solicitud);
      text('busqueda-status', 'Solicitud encontrada.');
    }, () => loadDetail(params));
  }
  async function loadHistory(page) {
    if (!current) return;
    const id = current.id;
    historyAbort?.abort(); historyAbort = new AbortController();
    const signal = historyAbort.signal;
    text('historial-status', 'Cargando historial…');
    show(el('historial-reintentar'), false);
    el('historial-anterior').disabled = true; el('historial-siguiente').disabled = true;
    try {
      const data = await request(`${endpoint('historial', id)}?page=${page}`, {signal});
      if (signal.aborted || current?.id !== id) return;
      historyPage = data.page;
      rows('historial-rows', data.registros, r => [dateTime(r.fecha), r.usuario, r.campo,
        r.campo === 'Fecha de solicitud' ? dateTime(r.anterior) : r.anterior,
        r.campo === 'Fecha de solicitud' ? dateTime(r.nuevo) : r.nuevo]);
      text('historial-status', data.registros.length ? '' : 'No hay modificaciones administrativas registradas.');
      text('historial-page', `Página ${data.page} de ${data.pages}`);
      el('historial-anterior').disabled = data.page <= 1;
      el('historial-siguiente').disabled = data.page >= data.pages;
    } catch (err) {
      if (signal.aborted || current?.id !== id) return;
      text('historial-status', err.message);
      show(el('historial-reintentar'), true);
    }
  }
  selects.forEach((select, index) => select.addEventListener('change', () => {
    if (saving) return;
    el('historico-codigo').value = '';
    for (let i = index + 1; i < selects.length; i++) resetSelect(i);
    if (!select.value) {
      ++sequence; searchAbort?.abort(); hideDetail();
      show(el('busqueda-loading'), false); show(el('reintentar-busqueda'), false);
      text('busqueda-status', 'Seleccione una opción para continuar.');
    } else if (index < selects.length - 1) loadOptions(index + 1);
    else loadDetail(parameters(selects.length));
  }));
  el('historico-form').addEventListener('submit', event => {
    event.preventDefault();
    if (saving || !event.target.reportValidity()) return;
    selects.forEach((_, i) => resetSelect(i));
    loadDetail(new URLSearchParams({historico: el('historico-codigo').value}));
  });
  el('limpiar-busqueda').addEventListener('click', () => {
    if (saving) return;
    el('historico-codigo').value = '';
    loadOptions(0);
  });
  el('reintentar-busqueda').addEventListener('click', () => retry?.());
  el('historial-anterior').addEventListener('click', () => loadHistory(historyPage - 1));
  el('historial-siguiente').addEventListener('click', () => loadHistory(historyPage + 1));
  el('historial-reintentar').addEventListener('click', () => loadHistory(historyPage));
  el('editar-solicitud').addEventListener('click', () => {
    if (!current) return;
    text('editar-correlativo', current.correlativo);
    text('editar-error', '');
    el('editar-fecha').value = current.fecha_solicitud;
    el('editar-estado').replaceChildren(...current.estados_permitidos.map(e => new Option(e.label, e.value)));
    el('editar-estado').value = current.estado;
    modal.show();
  });
  el('editar-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (!current || saving || !event.target.reportValidity()) return;
    if (el('editar-fecha').value === current.fecha_solicitud && el('editar-estado').value === current.estado) {
      text('editar-error', 'No hay cambios para guardar.'); return;
    }
    saving = true;
    const selected = current;
    const buttons = Array.from(modalNode.querySelectorAll('button, input, select'));
    // Capture antes de deshabilitar controles: FormData excluye los campos deshabilitados.
    const body = new FormData(event.target); body.set('version', selected.version);
    buttons.forEach(button => { button.disabled = true; });
    try {
      const confirmed = window.Swal ? (await Swal.fire({title: '¿Guardar los cambios?',
        text: `Solicitud ${selected.correlativo}. Se registrará la modificación en el historial.`,
        icon: 'warning', showCancelButton: true, confirmButtonText: 'Guardar cambios', cancelButtonText: 'Cancelar'})).isConfirmed
        : window.confirm('¿Guardar los cambios y registrar la modificación?');
      if (!confirmed) return;
      const data = await request(endpoint('actualizar', selected.id), {method: 'POST', body,
        headers: {'X-CSRFToken': body.get('csrfmiddlewaretoken')}});
      modal.hide();
      await notify(data.message, data.changed ? 'success' : 'info');
      await loadDetail(new URLSearchParams({historico: selected.correlativo}));
    } catch (err) {
      text('editar-error', err.message);
      if (err.code === 'stale') {
        modal.hide();
        await notify(err.message, 'warning');
        await loadDetail(new URLSearchParams({historico: selected.correlativo}));
      }
    } finally {
      buttons.forEach(button => { button.disabled = false; });
      saving = false;
    }
  });
  loadOptions(0);
})();
