/* =====================================================================
   CasaMuebles — logica del frontend
   - POST /api/chat      -> burbujas de chat con el asistente
   - POST /api/contacto  -> envio del formulario de contacto
   - FAB flotante que abre un chat compacto
   ===================================================================== */

(function () {
  "use strict";

  /* ---------------------------- Helpers ---------------------------- */
  const $ = (sel) => document.querySelector(sel);

  function crearBurbuja(texto, tipo, meta) {
    const div = document.createElement("div");
    div.className = "bubble bubble--" + tipo;
    div.textContent = texto;
    if (meta) {
      const small = document.createElement("span");
      small.className = "bubble__meta";
      small.textContent = meta;
      div.appendChild(small);
    }
    return div;
  }

  function burbujaEscribiendo() {
    const div = document.createElement("div");
    div.className = "bubble bubble--bot bubble--typing";
    div.append(document.createElement("span"), document.createElement("span"), document.createElement("span"));
    return div;
  }

  /** POST JSON contra la API y devuelve el objeto parseado (lanza si falla). */
  async function postJSON(url, payload) {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      throw new Error(data.detail || "Error " + resp.status);
    }
    return data;
  }

  /* =====================================================================
     CHAT PRINCIPAL (seccion #asistente)
     ===================================================================== */
  const log = $("#chatLog");
  const form = $("#chatForm");
  const input = $("#chatInput");
  const sendBtn = $("#chatSend");
  const clearBtn = $("#chatClear");
  const chipsBox = $("#chatChips");

  async function enviarMensaje(texto) {
    texto = (texto || "").trim();
    if (!texto) return;

    log.appendChild(crearBurbuja(texto, "user"));
    input.value = "";
    log.scrollTop = log.scrollHeight;

    const typing = burbujaEscribiendo();
    log.appendChild(typing);
    log.scrollTop = log.scrollHeight;
    sendBtn.disabled = true;

    try {
      const data = await postJSON("/api/chat", { message: texto });
      typing.remove();

      // Metadatos: confianza y si la consulta cae dentro del FAQ.
      const meta = data.relevante
        ? "Coincidencia con el FAQ · confianza " + data.confianza
        : "Sin coincidencia en el FAQ · tema fuera de alcance";

      log.appendChild(crearBurbuja(data.respuesta, "bot", meta));
    } catch (err) {
      typing.remove();
      log.appendChild(
        crearBurbuja("No pude conectar con el servidor. Revisa que la API este corriendo y reintenta.", "error")
      );
      console.error("Error en /api/chat:", err);
    } finally {
      sendBtn.disabled = false;
      log.scrollTop = log.scrollHeight;
      input.focus();
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    enviarMensaje(input.value);
  });

  clearBtn.addEventListener("click", () => {
    log.innerHTML = "";
    log.appendChild(crearBurbuja("Conversacion reiniciada. ¿Que te gustaria saber?", "bot"));
  });

  /* Carga sugerencias desde /api/faq (degradacion silenciosa si falla) */
  async function cargarSugerencias() {
    try {
      const resp = await fetch("/api/faq");
      const data = await resp.json();
      (data.preguntas || []).slice(0, 5).forEach((p) => {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "chip";
        chip.textContent = p.pregunta;
        chip.addEventListener("click", () => enviarMensaje(p.pregunta));
        chipsBox.appendChild(chip);
      });
    } catch (err) {
      console.warn("No se pudieron cargar las sugerencias:", err);
    }
  }

  /* =====================================================================
     CHAT FLOTANTE (FAB)
     ===================================================================== */
  const fab = $("#chatFab");
  const mini = $("#chatMini");
  const miniLog = $("#chatMiniLog");
  const miniForm = $("#chatMiniForm");
  const miniInput = $("#chatMiniInput");
  const miniClose = $("#chatMiniClose");

  function abrirMini() {
    mini.classList.add("is-open");
    mini.setAttribute("aria-hidden", "false");
    fab.style.display = "none";
    miniInput.focus();
  }

  function cerrarMini() {
    mini.classList.remove("is-open");
    mini.setAttribute("aria-hidden", "true");
    fab.style.display = "";
  }

  fab.addEventListener("click", abrirMini);
  miniClose.addEventListener("click", cerrarMini);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && mini.classList.contains("is-open")) cerrarMini();
  });

  miniForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const texto = miniInput.value.trim();
    if (!texto) return;

    miniLog.appendChild(crearBurbuja(texto, "user"));
    miniInput.value = "";
    miniLog.scrollTop = miniLog.scrollHeight;

    const typing = burbujaEscribiendo();
    miniLog.appendChild(typing);
    miniLog.scrollTop = miniLog.scrollHeight;

    try {
      const data = await postJSON("/api/chat", { message: texto });
      typing.remove();
      miniLog.appendChild(crearBurbuja(data.respuesta, "bot"));
    } catch (err) {
      typing.remove();
      miniLog.appendChild(crearBurbuja("No se pudo conectar con la API.", "error"));
      console.error("Error en /api/chat (mini):", err);
    } finally {
      miniLog.scrollTop = miniLog.scrollHeight;
      miniInput.focus();
    }
  });

  /* =====================================================================
     FORMULARIO DE CONTACTO
     ===================================================================== */
  const formContacto = $("#formContacto");
  const contactoMsg = $("#contactoMsg");
  const contactoSend = $("#contactoSend");

  formContacto.addEventListener("submit", async (e) => {
    e.preventDefault();
    contactoMsg.className = "form-contacto__msg";
    contactoMsg.textContent = "";

    const nombre = $("#nombre").value.trim();
    const email = $("#email").value.trim();
    const mensaje = $("#mensaje").value.trim();

    // Validacion minima en el cliente (el backend tambien valida).
    if (nombre.length < 2) {
      mostrarContacto("Ingresa un nombre de al menos 2 caracteres.", false);
      return;
    }
    if (!/^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$/.test(email)) {
      mostrarContacto("El email no tiene un formato valido.", false);
      return;
    }
    if (mensaje.length < 10) {
      mostrarContacto("El mensaje debe tener al menos 10 caracteres.", false);
      return;
    }

    contactoSend.disabled = true;
    contactoSend.textContent = "Enviando...";

    try {
      const data = await postJSON("/api/contacto", {
        nombre: nombre,
        email: email,
        mensaje: mensaje,
        categoria: $("#categoria").value, // campo trampa anti-spam
      });
      mostrarContacto("✓ " + data.mensaje, true);
      formContacto.reset();
    } catch (err) {
      mostrarContacto("Error: " + err.message, false);
    } finally {
      contactoSend.disabled = false;
      contactoSend.textContent = "Enviar consulta";
    }
  });

  function mostrarContacto(texto, ok) {
    contactoMsg.textContent = texto;
    contactoMsg.className = "form-contacto__msg " + (ok ? "ok" : "error");
  }

  /* ---------------------------- Init ---------------------------- */
  cargarSugerencias();
})();
