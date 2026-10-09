// Interface do Studio Nave: consulta /api/estado a cada 4 segundos e desenha a sala e o painel.
(function () {
  const STATES = {
    trabalhando: { label: "Trabalhando", icon: "bolt" },
    delegando: { label: "Delegando", icon: "account_tree" },
    aguardando: { label: "Aguardando", icon: "hourglass_empty" },
    concluida: { label: "Concluída", icon: "check_circle" },
    orfa: { label: "Sem sinal", icon: "signal_disconnected" },
  };
  const $ = (id) => document.getElementById(id);
  const scenes = new Map(); // chave da sessão -> { canvas, ctx, session, hits }
  let hours = 12;
  let last = null;

  // ---------------------------------------------------------- utilidades
  function esc(text) {
    return String(text ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function ago(iso) {
    const s = Math.max(0, (Date.now() - Date.parse(iso)) / 1000);
    if (s < 60) return "agora";
    if (s < 3600) return `há ${Math.floor(s / 60)} min`;
    return `há ${Math.floor(s / 3600)} h ${Math.floor((s % 3600) / 60)} min`;
  }
  function duration(a, b) {
    const s = Math.max(0, (Date.parse(b) - Date.parse(a)) / 1000);
    if (s < 60) return `${Math.round(s)} s`;
    if (s < 3600) return `${Math.floor(s / 60)} min`;
    return `${Math.floor(s / 3600)} h ${Math.floor((s % 3600) / 60)} min`;
  }
  function chip(state) {
    const info = STATES[state] || { label: state };
    return `<span class="chip state state-${esc(state)}"><span class="dot"></span>${esc(info.label)}</span>`;
  }
  function agentName(run) { return run.tipo === "principal" ? "Sessão principal" : run.tipo; }

  // ---------------------------------------------------------- tema
  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    $("theme").querySelector("span").textContent = theme === "dark" ? "light_mode" : "dark_mode";
  }
  let saved = null;
  try { saved = localStorage.getItem("studionave-tema"); } catch (_) {}
  applyTheme(saved || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
  $("theme").addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    applyTheme(next);
    try { localStorage.setItem("studionave-tema", next); } catch (_) {}
  });

  // ---------------------------------------------------------- navegação
  document.querySelectorAll("[data-view]").forEach((button) => button.addEventListener("click", () => {
    document.querySelectorAll("[data-view]").forEach((b) => b.classList.toggle("selected", b === button));
    document.querySelectorAll(".view").forEach((v) => { v.hidden = v.id !== button.dataset.view; });
  }));
  document.querySelectorAll("[data-hours]").forEach((button) => button.addEventListener("click", () => {
    document.querySelectorAll("[data-hours]").forEach((b) => b.classList.toggle("selected", b === button));
    hours = Number(button.dataset.hours);
    refresh();
  }));

  $("legend").innerHTML = ["trabalhando", "delegando", "aguardando", "orfa"].map(chip).join("");

  // ---------------------------------------------------------- sala
  function moduleMarkup(session) {
    const kids = session.subagentes;
    const crew = kids.length
      ? kids.map((k) => `<span class="chip chip-outline" data-tip="${esc(k.tipo)} | ${esc(STATES[k.estado]?.label || k.estado)} | ${esc(duration(k.inicio, k.atualizado))}">
          <span class="swatch" style="background:${Pixel.suitColor(k.tipo)}"></span>${esc(k.tipo)}
          <span class="dot" style="background:var(--state-${esc(k.estado)})"></span></span>`).join("")
      : `<span class="body-medium muted">Nenhum subagente nesta sessão.</span>`;
    return `
      <div class="module-head">
        <div class="avatar"><span class="material-symbols-outlined">${STATES[session.estado]?.icon || "help"}</span></div>
        <div class="names"><h3>${esc(session.projeto)}</h3><p title="${esc(session.cwd)}">${esc(session.cwd || session.session_id)}</p></div>
        ${chip(session.estado)}
      </div>
      <canvas class="scene" width="${Pixel.W}" height="${Pixel.H}"></canvas>
      <div class="crew">
        <span class="chip chip-tonal"><span class="material-symbols-outlined">schedule</span>${esc(ago(session.inicio).replace("agora", "iniciada agora").replace(/^há/, "iniciada há"))}</span>
        ${crew}
      </div>`;
  }

  function renderRoom(data) {
    const container = $("modules");
    const wanted = new Set(data.sessoes.map((s) => s.chave));
    for (const [key, scene] of scenes) {
      if (!wanted.has(key)) { scene.el.remove(); scenes.delete(key); }
    }
    // Sessões ativas primeiro, depois as concluídas mais recentes.
    const ordered = data.sessoes.slice().sort((a, b) =>
      (b.estado !== "concluida") - (a.estado !== "concluida") || b.atualizado.localeCompare(a.atualizado));
    ordered.forEach((session) => {
      let scene = scenes.get(session.chave);
      if (!scene) {
        const el = document.createElement("article");
        el.className = "card module";
        scene = { el };
        scenes.set(session.chave, scene);
      }
      const signature = JSON.stringify([session.estado, session.projeto, session.subagentes.map((k) => [k.chave, k.estado])]) + ago(session.inicio);
      if (scene.signature !== signature) {
        scene.el.innerHTML = moduleMarkup(session);
        scene.canvas = scene.el.querySelector("canvas");
        scene.ctx = scene.canvas.getContext("2d");
        scene.signature = signature;
        attachTooltip(scene);
      }
      scene.session = session;
      scene.el.classList.toggle("ended", session.estado === "concluida");
      container.appendChild(scene.el); // reordena sem recriar
    });
    $("empty").hidden = data.sessoes.length > 0;
  }

  function attachTooltip(scene) {
    const tip = $("tooltip");
    scene.canvas.addEventListener("mousemove", (event) => {
      const box = scene.canvas.getBoundingClientRect();
      const x = (event.clientX - box.left) * Pixel.W / box.width;
      const y = (event.clientY - box.top) * Pixel.H / box.height;
      const hit = (scene.hits || []).find((h) => x >= h.x && x <= h.x + h.w && y >= h.y && y <= h.y + h.h);
      if (!hit) { tip.hidden = true; return; }
      const r = hit.run;
      tip.innerHTML = `<strong>${esc(agentName(r))}</strong><br>${esc(STATES[r.estado]?.label || r.estado)} | ${esc(duration(r.inicio, r.atualizado))}<br>Atualizado ${esc(ago(r.atualizado))}`;
      tip.style.left = `${event.clientX + 12}px`;
      tip.style.top = `${event.clientY + 12}px`;
      tip.hidden = false;
    });
    scene.canvas.addEventListener("mouseleave", () => { tip.hidden = true; });
    scene.el.querySelectorAll("[data-tip]").forEach((node) => {
      node.addEventListener("mousemove", (event) => {
        tip.textContent = node.dataset.tip;
        tip.style.left = `${event.clientX + 12}px`;
        tip.style.top = `${event.clientY + 12}px`;
        tip.hidden = false;
      });
      node.addEventListener("mouseleave", () => { tip.hidden = true; });
    });
  }

  let lastFrame = 0;
  function animate(now) {
    if (now - lastFrame > 90) {
      lastFrame = now;
      for (const scene of scenes.values()) {
        if (scene.ctx && scene.session) scene.hits = Pixel.render(scene.ctx, scene.session, now);
      }
    }
    requestAnimationFrame(animate);
  }
  requestAnimationFrame(animate);

  // ---------------------------------------------------------- painel
  function renderPanel(data) {
    $("stats").innerHTML = Object.entries(STATES).map(([state, info]) => `
      <div class="stat state-${state}">
        <div class="value">${data.contagem[state] || 0}</div>
        <div class="label"><span class="material-symbols-outlined" style="color:var(--c)">${info.icon}</span>${info.label}</div>
      </div>`).join("");
    const types = Object.entries(data.por_tipo).sort((a, b) => b[1] - a[1]);
    const max = Math.max(1, ...types.map(([, n]) => n));
    $("types").innerHTML = types.length
      ? types.map(([kind, n]) => `
        <div class="bar-row"><span>${esc(kind)}</span><span class="muted">${n}</span>
          <div class="bar-track"><div class="bar-fill" style="width:${(n / max) * 100}%;background:${Pixel.suitColor(kind)}"></div></div>
        </div>`).join("")
      : `<p class="body-medium muted">Nenhum subagente no período.</p>`;
    $("runs").innerHTML = data.execucoes.slice(0, 40).map((r) => `
      <tr><td>${esc(agentName(r))}</td><td>${esc(r.projeto)}</td><td>${chip(r.estado)}</td><td class="muted">${esc(ago(r.atualizado))}</td></tr>`).join("")
      || `<tr><td colspan="4" class="muted">Nada no período.</td></tr>`;
  }

  // ---------------------------------------------------------- ciclo
  async function refresh() {
    try {
      const response = await fetch(`/api/estado?horas=${hours}`, { cache: "no-store" });
      if (!response.ok) throw new Error(response.status);
      last = await response.json();
      $("offline").hidden = true;
      $("demo-chip").hidden = !last.demo;
      renderRoom(last);
      renderPanel(last);
    } catch (_) {
      $("offline").hidden = false;
    }
  }
  refresh();
  setInterval(refresh, 4000);
})();
