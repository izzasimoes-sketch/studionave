// Cena em pixel art de cada módulo: a sessão principal no comando e os subagentes nas estações.
// Tudo é desenhado com retângulos; não há imagens externas.
(function () {
  const W = 192, H = 108;
  const SKIN = ["#F1C27D", "#E0AC69", "#C68642", "#8D5524", "#FFDBAC"];
  const HAIR = ["#2B1B12", "#5A3825", "#A0522D", "#D9A441", "#1F1F2E", "#7A7A85"];
  const SUITS = ["#26A69A", "#EF6C00", "#42A5F5", "#EC407A", "#9CCC65", "#FFCA28", "#8D6E63",
                 "#AB47BC", "#26C6DA", "#D4E157", "#FF7043", "#5C6BC0"];
  // Tipos nativos do Claude Code têm cor fixa; os seus agentes recebem uma cor pelo nome.
  const KNOWN = { "Explore": "#26A69A", "Plan": "#EF6C00", "general-purpose": "#42A5F5",
                  "claude-code-guide": "#EC407A", "statusline-setup": "#8D6E63" };
  const STATE_SCREEN = { trabalhando: "#81C995", delegando: "#D0BCFF", aguardando: "#FFB95C", orfa: "#F2B8B5" };
  // Estações dos subagentes (x, y = base da mesa). O comandante fica no centro.
  const SEATS = [[34, 62], [158, 62], [70, 52], [122, 52], [34, 96], [158, 96]];
  const CAPTAIN = [96, 92];

  function hash(text) {
    let h = 2166136261;
    for (const ch of String(text)) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
    return h >>> 0;
  }
  function mix(h) { h ^= h >>> 16; h = Math.imul(h, 0x45d9f3b); h ^= h >>> 16; return h >>> 0; }
  function suitColor(kind) { return kind === "principal" ? "#6750A4" : (KNOWN[kind] || SUITS[mix(hash(kind)) % SUITS.length]); }

  function rect(ctx, x, y, w, h, color) { ctx.fillStyle = color; ctx.fillRect(Math.round(x), Math.round(y), w, h); }

  function drawBackdrop(ctx, t, seed) {
    // Janela panorâmica com estrelas em movimento.
    rect(ctx, 0, 0, W, 30, "#07061a");
    for (let i = 0; i < 40; i++) {
      const s = hash(seed + ":" + i);
      const speed = 1 + (s % 3);
      const x = (W - ((s % 997) + t * speed * 0.012) % (W + 4)) | 0;
      const y = 2 + (s >> 8) % 24;
      rect(ctx, x, y, 1, 1, speed === 3 ? "#FFFFFF" : speed === 2 ? "#B9B2D9" : "#5E5A7E");
    }
    const planetX = 150 - (t * 0.0008) % 30;
    rect(ctx, planetX, 8, 10, 10, "#3B2F6B");
    rect(ctx, planetX + 1, 9, 6, 3, "#5B4A9B");
    for (let x = 0; x < W; x += 48) rect(ctx, x, 0, 3, 30, "#2C2840");
    rect(ctx, 0, 28, W, 3, "#3A3552");
    // Piso metálico.
    for (let y = 31; y < H; y += 8) {
      for (let x = 0; x < W; x += 16) {
        const shade = ((x / 16 + y / 8) | 0) % 2 ? "#1C1A2A" : "#211F31";
        rect(ctx, x, y, 16, 8, shade);
        rect(ctx, x, y, 16, 1, "#2A2740");
      }
    }
  }

  function drawPerson(ctx, x, y, run, t) {
    const seed = hash(run.chave);
    const bob = (run.estado === "trabalhando" || run.estado === "delegando") && Math.floor((t + seed % 400) / 280) % 2 ? 1 : 0;
    const top = y - 22 + bob;
    const skin = SKIN[seed % SKIN.length], hair = HAIR[(seed >> 4) % HAIR.length], suit = suitColor(run.tipo);
    rect(ctx, x - 4, top, 8, 2, hair);           // cabelo
    rect(ctx, x - 4, top + 2, 8, 5, skin);       // rosto
    rect(ctx, x - 4, top + 2, 1, 3, hair);
    rect(ctx, x + 3, top + 2, 1, 3, hair);
    const blink = Math.floor((t + seed) / 120) % 30 === 0;
    if (!blink) { rect(ctx, x - 2, top + 4, 1, 1, "#1D1B20"); rect(ctx, x + 1, top + 4, 1, 1, "#1D1B20"); }
    rect(ctx, x - 5, top + 7, 10, 7, suit);      // tronco
    rect(ctx, x - 1, top + 7, 2, 2, "#FFFFFF");  // gola
    if (run.tipo === "principal") rect(ctx, x + 2, top + 9, 2, 1, "#FFCA28"); // insígnia do comandante
    const typing = run.estado === "trabalhando" && Math.floor((t + seed) / 140) % 2;
    rect(ctx, x - 7, top + 8 + (typing ? 1 : 0), 2, 5, suit);
    rect(ctx, x + 5, top + 8 + (typing ? 0 : 1), 2, 5, suit);
  }

  function drawDesk(ctx, x, y, run, t, big) {
    const w = big ? 30 : 22;
    const on = run && run.estado !== "concluida";
    const screen = run ? STATE_SCREEN[run.estado] : null;
    rect(ctx, x - 5, y - 14, 10, 7, "#2D2B3D");                 // monitor
    if (on && screen) {
      const blinkOff = run.estado === "orfa" && Math.floor(t / 400) % 2;
      rect(ctx, x - 4, y - 13, 8, 5, blinkOff ? "#3A1C1C" : "#0F1A12");
      if (!blinkOff) {
        const seed = hash(run.chave);
        for (let row = 0; row < 2; row++) {
          const len = run.estado === "trabalhando"
            ? 2 + (hash(seed + ":" + row + ":" + Math.floor(t / 220)) % 5)
            : 6 - row * 3;
          rect(ctx, x - 3, y - 12 + row * 2, len, 1, screen);
        }
      }
    } else {
      rect(ctx, x - 4, y - 13, 8, 5, "#151420");
    }
    rect(ctx, x - w / 2, y - 7, w, 6, "#4A4560");                // mesa
    rect(ctx, x - w / 2, y - 7, w, 1, "#6B6585");
    rect(ctx, x - w / 2 + 1, y - 1, 2, 3, "#2D2B3D");
    rect(ctx, x + w / 2 - 3, y - 1, 2, 3, "#2D2B3D");
  }

  function drawBubble(ctx, x, y, kind, t) {
    const color = kind === "alerta" ? "#F2B8B5" : "#F5EFF7";
    rect(ctx, x - 5, y - 7, 11, 6, color);
    rect(ctx, x - 1, y - 1, 2, 2, color);
    if (kind === "alerta") {
      rect(ctx, x, y - 6, 1, 3, "#8C1D18");
      rect(ctx, x, y - 2, 1, 1, "#8C1D18");
    } else {
      const n = 1 + Math.floor(t / 400) % 3;
      for (let i = 0; i < n; i++) rect(ctx, x - 3 + i * 3, y - 4, 1, 1, "#322F35");
    }
  }

  function drawLink(ctx, from, to, t) {
    // Linha pontilhada animada do comandante até a estação delegada.
    const steps = Math.max(Math.abs(to[0] - from[0]), Math.abs(to[1] - from[1]));
    const phase = Math.floor(t / 90) % 4;
    for (let i = 0; i <= steps; i += 2) {
      if (((i / 2) | 0) % 4 === phase) continue;
      const x = from[0] + (to[0] - from[0]) * (i / steps);
      const y = from[1] + (to[1] - from[1]) * (i / steps);
      rect(ctx, x, y, 1, 1, "#D0BCFF");
    }
  }

  function render(ctx, session, t) {
    ctx.clearRect(0, 0, W, H);
    drawBackdrop(ctx, t, session.chave);
    const crew = session.subagentes.slice()
      .sort((a, b) => (b.estado !== "concluida") - (a.estado !== "concluida") || a.inicio.localeCompare(b.inicio))
      .slice(0, SEATS.length);
    const hits = [];
    crew.forEach((run, i) => {
      const [x, y] = SEATS[i];
      if (run.estado === "trabalhando" && session.estado === "delegando") drawLink(ctx, [CAPTAIN[0], CAPTAIN[1] - 18], [x, y - 12], t);
    });
    // Estações vazias completam a sala.
    SEATS.slice(crew.length).forEach(([x, y]) => drawDesk(ctx, x, y, null, t, false));
    const people = crew.map((run, i) => ({ run, x: SEATS[i][0], y: SEATS[i][1] }));
    people.push({ run: session, x: CAPTAIN[0], y: CAPTAIN[1], captain: true });
    people.sort((a, b) => a.y - b.y);
    for (const p of people) {
      const present = p.run.estado !== "concluida";
      if (present) drawPerson(ctx, p.x, p.y - 6, p.run, t);
      drawDesk(ctx, p.x, p.y, p.run, t, p.captain);
      if (p.run.estado === "aguardando") drawBubble(ctx, p.x + 6, p.y - 28, "espera", t);
      if (p.run.estado === "orfa") drawBubble(ctx, p.x + 6, p.y - 28, "alerta", t);
      hits.push({ x: p.x - 12, y: p.y - 30, w: 24, h: 32, run: p.run });
    }
    return hits;
  }

  window.Pixel = { W, H, render, suitColor };
})();
