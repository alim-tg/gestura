const GESTURES = {
  Open_Palm: ["🖐", "Открытая ладонь"],
  Closed_Fist: ["✊", "Кулак"],
  Pointing_Up: ["☝️", "Указательный вверх"],
  Thumb_Up: ["👍", "Палец вверх"],
  Thumb_Down: ["👎", "Палец вниз"],
  Victory: ["✌️", "Victory"],
  ILoveYou: ["🤟", "I love you"],
  Pinch: ["🤏", "Щипок"],
  swipe_left: ["⬅️", "Свайп влево"],
  swipe_right: ["➡️", "Свайп вправо"],
  swipe_up: ["⬆️", "Свайп вверх"],
  swipe_down: ["⬇️", "Свайп вниз"],
  hand_enter: ["👋", "Рука появилась"],
  hand_leave: ["💨", "Рука ушла"],
  None: ["·", "Нет жеста"],
};
const HIDDEN_IN_LEGEND = ["None", "hand_enter", "hand_leave"];
const COLORS = ["#4cc9f0", "#f72585", "#b8f35d", "#ffb703"];
const SIDES = { Left: "Левая", Right: "Правая" };
const MAX_EVENTS = 80;

const $ = (id) => document.getElementById(id);
const label = (name) => GESTURES[name] || ["•", name];
const color = (id) => COLORS[(id - 1) % COLORS.length];
let legendKey = null;

function renderLegend(configured) {
  const key = configured.join("|");
  if (key === legendKey) return;
  legendKey = key;
  $("legend").innerHTML = Object.entries(GESTURES)
    .filter(([name]) => !HIDDEN_IN_LEGEND.includes(name))
    .map(([name, [icon, text]]) => `
      <li>
        <span class="icon">${icon}</span>
        <span>${text}</span>
        <code>${name}</code>
        ${configured.includes(name) ? '<span class="tag">action</span>' : "<span></span>"}
      </li>`)
    .join("");
}

function renderHands(hands) {
  $("count").textContent = `рук: ${hands.length}`;
  if (!hands.length) {
    $("hands").innerHTML = '<p class="empty">Покажите руку в камеру</p>';
    return;
  }
  $("hands").innerHTML = hands.map((h) => {
    const [icon, text] = label(h.gesture);
    const raw = h.moving
      ? '<span class="raw moving">в движении, жесты не распознаются</span>'
      : h.raw !== h.gesture ? `<span class="raw">сейчас: ${label(h.raw)[1]}</span>` : "";
    const score = h.gesture === "None" ? 0 : Math.round(h.score * 100);
    return `
      <article class="hand" style="--c:${color(h.id)}">
        <div class="hand-head">
          <span class="dot"></span>#${h.id} · ${SIDES[h.hand] || h.hand}
          <span class="pos">x ${h.x.toFixed(2)} · y ${h.y.toFixed(2)} · ${h.age}s</span>
        </div>
        <div class="gesture">
          <span class="big">${icon}</span>
          <div><div class="name">${text}</div>${raw}</div>
          <span class="score">${score ? score + "%" : ""}</span>
        </div>
        <div class="bar"><span style="width:${score}%"></span></div>
      </article>`;
  }).join("");
}

function renderEvents(events) {
  const list = $("events");
  for (const e of events) {
    const li = document.createElement("li");
    li.className = `event ${e.type}`;
    const time = new Date(e.ts * 1000).toLocaleTimeString("ru-RU");
    if (e.type === "action") {
      const failed = !/^2\d\d$/.test(e.status);
      li.innerHTML = `<time>${time}</time><span class="icon">⚡</span><span>${label(e.name)[1]} → <b class="${failed ? "fail" : "done"}">${e.status}</b></span><span></span>`;
    } else {
      const [icon, text] = label(e.name);
      li.innerHTML = `<time>${time}</time><span class="icon">${icon}</span><span>${text}</span><span class="who" style="--c:${color(e.track)}">#${e.track}</span>`;
    }
    list.prepend(li);
  }
  while (list.children.length > MAX_EVENTS) list.lastChild.remove();
}

function renderState(s) {
  const on = s.camera === "on";
  $("camera").textContent = on ? `камера ${s.width}×${s.height}` : "камера выкл";
  $("camera").className = `pill ${on ? "ok" : "bad"}`;
  $("fps").textContent = `${Math.round(s.fps)} fps · камера ${Math.round(s.cameraFps)}`;
  $("fps").title = "обработка / камера";
  $("error").hidden = !s.error;
  $("error").textContent = s.error || "";
  renderHands(s.hands);
  renderLegend(s.actions);
  for (const input of document.querySelectorAll("[data-overlay]")) {
    input.checked = s.overlay[input.dataset.overlay];
  }
}

function connect() {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ws.onopen = () => {
    $("link").textContent = "online";
    $("link").className = "pill ok";
    $("events").innerHTML = "";
    $("stream").src = `/stream.mjpg?t=${Date.now()}`;
  };
  ws.onmessage = (message) => {
    const data = JSON.parse(message.data);
    renderState(data.state);
    renderEvents(data.events);
  };
  ws.onclose = () => {
    $("link").textContent = "offline";
    $("link").className = "pill bad";
    setTimeout(connect, 1500);
  };
}

for (const input of document.querySelectorAll("[data-overlay]")) {
  input.addEventListener("change", () => fetch("/api/overlay", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ [input.dataset.overlay]: input.checked }),
  }));
}

connect();
