/**
 * Opportunity Scout — Floating Chat Widget v2
 * Embeddable on any page: <script src="https://your-app.vercel.app/widget.js"></script>
 * Optional attribute: data-api-url="https://your-app.vercel.app/api/chat"
 *
 * Global API:
 *   window.askAdvisor(promptText)  — open widget and send a prefilled message
 */
(function () {
  "use strict";

  // ── Config ────────────────────────────────────────────────────────────────
  const currentScript =
    document.currentScript ||
    (function () {
      const scripts = document.getElementsByTagName("script");
      return scripts[scripts.length - 1];
    })();

  const API_URL =
    (currentScript && currentScript.getAttribute("data-api-url")) ||
    "/api/chat";

  // Quick-starter prompt chips
  const CHIPS = [
    { label: "🔍 Paid CS Research", prompt: "Find me paid computer science research opportunities for undergraduates. I'm interested in AI and software engineering." },
    { label: "🌐 Remote Internships", prompt: "What remote internship opportunities are available for undergraduate students? I prefer fully remote positions." },
    { label: "🎓 Upcoming Scholarships", prompt: "Show me scholarships with upcoming deadlines in the next 2 months. I'm an undergraduate student." },
    { label: "⚡ Hackathons", prompt: "Are there any hackathons I can join right now? I'm interested in AI and web development." },
    { label: "🏆 Fellowships", prompt: "What prestigious fellowships are available for graduate students? I'm interested in research and policy." },
  ];

  // ── State ─────────────────────────────────────────────────────────────────
  let isOpen      = false;
  let isLoading   = false;
  let history     = [];
  let unreadCount = 0;
  let chipsShown  = true;

  // ── CSS ───────────────────────────────────────────────────────────────────
  const CSS = `
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    #osc-widget * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* ── Launcher bubble ── */
    #osc-bubble {
      position: fixed;
      bottom: 28px;
      right: 28px;
      width: 62px;
      height: 62px;
      border-radius: 50%;
      background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
      box-shadow: 0 8px 32px rgba(99, 102, 241, 0.55), 0 2px 8px rgba(0,0,0,0.3);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 2147483647;
      border: none;
      outline: none;
      transition: transform 0.25s cubic-bezier(0.34,1.56,0.64,1), box-shadow 0.2s ease;
      animation: oscPulse 3s ease-in-out infinite;
    }
    #osc-bubble:hover {
      transform: scale(1.12) translateY(-2px);
      box-shadow: 0 12px 48px rgba(99, 102, 241, 0.7), 0 4px 12px rgba(0,0,0,0.3);
    }
    #osc-bubble svg {
      width: 28px;
      height: 28px;
      fill: white;
      transition: transform 0.3s cubic-bezier(0.34,1.56,0.64,1);
    }
    #osc-bubble:hover svg { transform: scale(1.1); }

    #osc-unread {
      position: absolute;
      top: -4px;
      right: -4px;
      background: #ef4444;
      color: white;
      font-size: 10px;
      font-weight: 700;
      width: 20px;
      height: 20px;
      border-radius: 50%;
      display: none;
      align-items: center;
      justify-content: center;
      border: 2px solid #0f0f1f;
    }
    #osc-unread.visible { display: flex; }

    /* ── Chat panel ── */
    #osc-panel {
      position: fixed;
      bottom: 102px;
      right: 28px;
      width: 390px;
      max-width: calc(100vw - 32px);
      height: 580px;
      max-height: calc(100vh - 130px);
      border-radius: 24px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      z-index: 2147483646;
      /* Glassmorphism */
      background: rgba(10, 10, 30, 0.92);
      backdrop-filter: blur(24px) saturate(180%);
      -webkit-backdrop-filter: blur(24px) saturate(180%);
      border: 1px solid rgba(99, 102, 241, 0.25);
      box-shadow:
        0 32px 96px rgba(0, 0, 0, 0.7),
        0 0 0 1px rgba(255,255,255,0.04) inset,
        0 1px 0 rgba(255,255,255,0.08) inset;
      transform: scale(0.88) translateY(24px);
      opacity: 0;
      pointer-events: none;
      transform-origin: bottom right;
      transition: transform 0.35s cubic-bezier(0.34,1.56,0.64,1), opacity 0.25s ease;
    }
    #osc-panel.osc-open {
      transform: scale(1) translateY(0);
      opacity: 1;
      pointer-events: all;
    }

    /* ── Header ── */
    #osc-header {
      background: linear-gradient(135deg, #4338ca 0%, #6d28d9 100%);
      padding: 14px 16px;
      display: flex;
      align-items: center;
      gap: 10px;
      flex-shrink: 0;
      position: relative;
      overflow: hidden;
    }
    #osc-header::before {
      content: '';
      position: absolute;
      inset: 0;
      background: linear-gradient(135deg, rgba(255,255,255,0.08) 0%, transparent 60%);
      pointer-events: none;
    }
    #osc-avatar {
      width: 42px;
      height: 42px;
      border-radius: 50%;
      background: rgba(255,255,255,0.18);
      backdrop-filter: blur(8px);
      border: 2px solid rgba(255,255,255,0.25);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      flex-shrink: 0;
    }
    #osc-header-info { flex: 1; min-width: 0; }
    #osc-header-name { color: white; font-weight: 700; font-size: 15px; letter-spacing: -0.01em; }
    #osc-header-sub {
      color: rgba(255,255,255,0.7);
      font-size: 11.5px;
      display: flex;
      align-items: center;
      gap: 5px;
      margin-top: 2px;
    }
    #osc-status-dot {
      width: 7px; height: 7px;
      border-radius: 50%;
      background: #4ade80;
      animation: oscBlink 2s ease-in-out infinite;
      flex-shrink: 0;
    }
    #osc-close {
      background: rgba(255,255,255,0.15);
      border: none;
      border-radius: 50%;
      width: 30px; height: 30px;
      cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      color: white;
      font-size: 14px;
      line-height: 1;
      transition: background 0.2s;
      flex-shrink: 0;
    }
    #osc-close:hover { background: rgba(255,255,255,0.28); }

    /* ── Messages area ── */
    #osc-messages {
      flex: 1;
      overflow-y: auto;
      padding: 16px 14px;
      display: flex;
      flex-direction: column;
      gap: 10px;
      scroll-behavior: smooth;
    }
    #osc-messages::-webkit-scrollbar { width: 4px; }
    #osc-messages::-webkit-scrollbar-track { background: transparent; }
    #osc-messages::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 2px; }

    /* ── Message bubbles ── */
    .osc-msg {
      display: flex;
      gap: 8px;
      max-width: 92%;
      animation: oscFadeUp 0.3s ease;
    }
    .osc-msg.osc-user { align-self: flex-end; flex-direction: row-reverse; }
    .osc-msg.osc-bot  { align-self: flex-start; }

    .osc-msg-av {
      width: 28px; height: 28px;
      border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      font-size: 13px;
      flex-shrink: 0;
      margin-top: auto;
    }
    .osc-bot  .osc-msg-av { background: linear-gradient(135deg, #4338ca, #6d28d9); }
    .osc-user .osc-msg-av { background: rgba(255,255,255,0.08); }

    .osc-bubble {
      padding: 9px 13px;
      border-radius: 16px;
      font-size: 13.5px;
      line-height: 1.55;
      word-break: break-word;
    }
    .osc-bot  .osc-bubble {
      background: rgba(255,255,255,0.07);
      color: #e2e8f0;
      border-bottom-left-radius: 4px;
      border: 1px solid rgba(255,255,255,0.06);
    }
    .osc-user .osc-bubble {
      background: linear-gradient(135deg, #4338ca, #6d28d9);
      color: white;
      border-bottom-right-radius: 4px;
    }

    /* Markdown styles */
    .osc-bubble strong { font-weight: 700; color: #c4b5fd; }
    .osc-user .osc-bubble strong { color: rgba(255,255,255,0.9); }
    .osc-bubble em { font-style: italic; color: #a5b4fc; }
    .osc-bubble a { color: #818cf8; text-decoration: underline; text-underline-offset: 2px; }
    .osc-bubble code { background: rgba(99,102,241,0.2); padding: 1px 5px; border-radius: 4px; font-size: 12px; }
    .osc-bubble ul { padding-left: 16px; margin: 4px 0; }
    .osc-bubble ol { padding-left: 18px; margin: 4px 0; }
    .osc-bubble li { margin-bottom: 4px; }
    .osc-bubble h3 { color: #c4b5fd; font-size: 14px; font-weight: 700; margin: 8px 0 4px; }
    .osc-bubble hr { border: none; border-top: 1px solid rgba(255,255,255,0.1); margin: 8px 0; }
    .osc-bubble p { margin-bottom: 6px; }
    .osc-bubble p:last-child { margin-bottom: 0; }

    /* ── Typing indicator ── */
    .osc-typing-wrap {
      display: flex;
      gap: 8px;
      align-self: flex-start;
      animation: oscFadeUp 0.3s ease;
    }
    .osc-dots {
      display: flex;
      gap: 4px;
      align-items: center;
      padding: 10px 14px;
      background: rgba(255,255,255,0.07);
      border-radius: 16px;
      border-bottom-left-radius: 4px;
      border: 1px solid rgba(255,255,255,0.06);
    }
    .osc-dots span {
      width: 7px; height: 7px;
      background: #6366f1;
      border-radius: 50%;
      animation: oscBounce 1.2s ease-in-out infinite;
    }
    .osc-dots span:nth-child(2) { animation-delay: 0.15s; }
    .osc-dots span:nth-child(3) { animation-delay: 0.30s; }

    /* ── Quick-start chips ── */
    #osc-chips {
      padding: 10px 14px 6px;
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      flex-shrink: 0;
      border-top: 1px solid rgba(255,255,255,0.06);
    }
    #osc-chips-label {
      width: 100%;
      font-size: 10.5px;
      font-weight: 600;
      color: rgba(255,255,255,0.35);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: 2px;
    }
    .osc-chip {
      background: rgba(99,102,241,0.12);
      border: 1px solid rgba(99,102,241,0.25);
      color: #a5b4fc;
      font-size: 11.5px;
      font-weight: 500;
      padding: 5px 11px;
      border-radius: 20px;
      cursor: pointer;
      transition: background 0.2s, border-color 0.2s, transform 0.15s;
      white-space: nowrap;
    }
    .osc-chip:hover {
      background: rgba(99,102,241,0.22);
      border-color: rgba(99,102,241,0.5);
      transform: translateY(-1px);
    }

    /* ── Input footer ── */
    #osc-footer {
      padding: 10px 12px 12px;
      border-top: 1px solid rgba(255,255,255,0.06);
      display: flex;
      gap: 8px;
      align-items: flex-end;
      flex-shrink: 0;
      background: rgba(255,255,255,0.02);
    }
    #osc-input {
      flex: 1;
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 14px;
      color: #e2e8f0;
      font-size: 13.5px;
      padding: 10px 14px;
      outline: none;
      resize: none;
      max-height: 100px;
      min-height: 42px;
      line-height: 1.4;
      transition: border-color 0.2s, background 0.2s;
    }
    #osc-input::placeholder { color: rgba(255,255,255,0.25); }
    #osc-input:focus {
      border-color: rgba(99,102,241,0.5);
      background: rgba(255,255,255,0.09);
    }

    #osc-send {
      width: 42px; height: 42px;
      background: linear-gradient(135deg, #4338ca, #6d28d9);
      border: none;
      border-radius: 12px;
      cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      flex-shrink: 0;
      transition: opacity 0.2s, transform 0.15s;
      box-shadow: 0 4px 12px rgba(99,102,241,0.35);
    }
    #osc-send:hover { opacity: 0.92; transform: scale(1.05); }
    #osc-send:disabled { opacity: 0.35; cursor: not-allowed; transform: none; }
    #osc-send svg { width: 18px; height: 18px; fill: white; }

    #osc-powered {
      text-align: center;
      font-size: 10px;
      color: rgba(255,255,255,0.15);
      padding: 4px 0 8px;
      flex-shrink: 0;
    }
    #osc-powered a { color: rgba(99,102,241,0.5); text-decoration: none; }

    /* ── Keyframes ── */
    @keyframes oscPulse {
      0%,100% { box-shadow: 0 8px 32px rgba(99,102,241,0.55), 0 2px 8px rgba(0,0,0,0.3); }
      50%      { box-shadow: 0 8px 52px rgba(99,102,241,0.8), 0 2px 8px rgba(0,0,0,0.3); }
    }
    @keyframes oscBlink { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }
    @keyframes oscBounce { 0%,80%,100% { transform: translateY(0); } 40% { transform: translateY(-7px); } }
    @keyframes oscFadeUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

    @media (max-width: 440px) {
      #osc-panel  { width: calc(100vw - 16px); right: 8px; bottom: 90px; }
      #osc-bubble { right: 16px; bottom: 16px; }
    }
  `;

  // ── Markdown renderer ─────────────────────────────────────────────────────
  function renderMarkdown(text) {
    // Escape HTML
    function esc(s) {
      return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
    }

    let lines = text.split("\n");
    let html  = "";
    let inUl  = false, inOl = false;

    for (let i = 0; i < lines.length; i++) {
      let line = lines[i];

      // Headings
      if (/^### /.test(line)) { if (inUl) { html += "</ul>"; inUl=false; } if (inOl) { html += "</ol>"; inOl=false; } html += `<h3>${inline(esc(line.slice(4)))}</h3>`; continue; }
      if (/^## /.test(line))  { if (inUl) { html += "</ul>"; inUl=false; } if (inOl) { html += "</ol>"; inOl=false; } html += `<h3>${inline(esc(line.slice(3)))}</h3>`; continue; }

      // HR
      if (/^---+$/.test(line.trim())) { html += "<hr>"; continue; }

      // Unordered list
      if (/^[-•*] /.test(line)) {
        if (inOl) { html += "</ol>"; inOl=false; }
        if (!inUl) { html += "<ul>"; inUl=true; }
        html += `<li>${inline(esc(line.replace(/^[-•*] /, "")))}</li>`;
        continue;
      }

      // Ordered list
      if (/^\d+\. /.test(line)) {
        if (inUl) { html += "</ul>"; inUl=false; }
        if (!inOl) { html += "<ol>"; inOl=true; }
        html += `<li>${inline(esc(line.replace(/^\d+\. /, "")))}</li>`;
        continue;
      }

      // Close lists
      if (inUl) { html += "</ul>"; inUl=false; }
      if (inOl) { html += "</ol>"; inOl=false; }

      // Empty line = paragraph break
      if (!line.trim()) { html += "<br>"; continue; }

      html += `<p>${inline(esc(line))}</p>`;
    }

    if (inUl) html += "</ul>";
    if (inOl) html += "</ol>";
    return html;
  }

  function inline(s) {
    return s
      // Bold
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      // Italic
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      // Inline code
      .replace(/`(.+?)`/g, "<code>$1</code>")
      // Links [text](url)
      .replace(/\[(.+?)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
      // Bare URLs
      .replace(/(https?:\/\/[^\s<>"]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
  }

  // ── DOM construction ──────────────────────────────────────────────────────
  function buildWidget() {
    // Inject CSS
    const styleEl = document.createElement("style");
    styleEl.textContent = CSS;
    document.head.appendChild(styleEl);

    // Root wrapper
    const root = document.createElement("div");
    root.id = "osc-widget";
    document.body.appendChild(root);

    // ── Bubble ──
    const bubble = document.createElement("button");
    bubble.id = "osc-bubble";
    bubble.setAttribute("aria-label", "Open Opportunity Scout chat");
    bubble.innerHTML = ICON_CHAT;

    const unreadBadge = document.createElement("span");
    unreadBadge.id = "osc-unread";
    bubble.appendChild(unreadBadge);
    root.appendChild(bubble);

    // ── Panel ──
    const panel = document.createElement("div");
    panel.id = "osc-panel";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-modal", "true");
    panel.setAttribute("aria-label", "Opportunity Scout chat assistant");
    panel.innerHTML = `
      <div id="osc-header">
        <div id="osc-avatar">🎓</div>
        <div id="osc-header-info">
          <div id="osc-header-name">Opportunity Scout</div>
          <div id="osc-header-sub">
            <span id="osc-status-dot"></span>
            <span>24/7 Student Advisor · AI Powered</span>
          </div>
        </div>
        <button id="osc-close" aria-label="Close chat">✕</button>
      </div>

      <div id="osc-messages" role="log" aria-live="polite" aria-label="Chat messages"></div>

      <div id="osc-chips">
        <div id="osc-chips-label">Quick starters</div>
        ${CHIPS.map(c => `<button class="osc-chip" data-prompt="${c.prompt.replace(/"/g,'&quot;')}">${c.label}</button>`).join("")}
      </div>

      <div id="osc-footer">
        <textarea
          id="osc-input"
          placeholder="Ask about scholarships, internships, research…"
          rows="1"
          aria-label="Type your message"
        ></textarea>
        <button id="osc-send" aria-label="Send message" disabled>
          <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
        </button>
      </div>
      <div id="osc-powered">Powered by <a href="https://github.com/Jaiswal096/Student-opportunities-agents" target="_blank">Opportunity Scout</a></div>
    `;
    root.appendChild(panel);

    return { bubble, panel, unreadBadge };
  }

  // SVG icons
  const ICON_CHAT  = `<svg viewBox="0 0 24 24"><path d="M20 2H4C2.9 2 2 2.9 2 4v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 10H6v-2h12v2zm0-3H6V7h12v2z"/></svg>`;
  const ICON_CLOSE = `<svg viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" fill="white"/></svg>`;

  // ── Message rendering ─────────────────────────────────────────────────────
  function appendMessage(role, text, msgEl) {
    const wrap   = document.createElement("div");
    wrap.className = "osc-msg " + (role === "user" ? "osc-user" : "osc-bot");

    const av = document.createElement("div");
    av.className = "osc-msg-av";
    av.textContent = role === "user" ? "👤" : "🎓";

    const bub = document.createElement("div");
    bub.className = "osc-bubble";
    bub.innerHTML = renderMarkdown(text);

    wrap.appendChild(av);
    wrap.appendChild(bub);
    msgEl.appendChild(wrap);
    msgEl.scrollTop = msgEl.scrollHeight;
    return wrap;
  }

  function showTyping(msgEl) {
    const wrap = document.createElement("div");
    wrap.className = "osc-typing-wrap";
    wrap.id = "osc-typing";
    wrap.innerHTML = `
      <div class="osc-msg-av" style="background:linear-gradient(135deg,#4338ca,#6d28d9);width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:13px;">🎓</div>
      <div class="osc-dots"><span></span><span></span><span></span></div>
    `;
    msgEl.appendChild(wrap);
    msgEl.scrollTop = msgEl.scrollHeight;
    return wrap;
  }

  function removeTyping() {
    const el = document.getElementById("osc-typing");
    if (el) el.remove();
  }

  // ── API ───────────────────────────────────────────────────────────────────
  async function sendMessage(message, msgEl, inputEl, sendBtn) {
    if (!message.trim() || isLoading) return;
    isLoading = true;

    // Hide chips after first message
    const chips = document.getElementById("osc-chips");
    if (chips) { chips.style.display = "none"; chipsShown = false; }

    inputEl.value = "";
    inputEl.style.height = "auto";
    sendBtn.disabled = true;

    appendMessage("user", message, msgEl);
    showTyping(msgEl);

    try {
      const res  = await fetch(API_URL, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({
          message,
          history: history.map(h => ({ role: h.role, content: h.content })),
        }),
      });
      const data = await res.json();
      removeTyping();

      const reply = data.reply || data.error || "Sorry, something went wrong. Please try again.";
      appendMessage("model", reply, msgEl);

      history.push({ role: "user",  content: message });
      history.push({ role: "model", content: reply   });
      if (history.length > 20) history = history.slice(-20);

    } catch (err) {
      removeTyping();
      appendMessage("model", "⚠️ Connection error — please check your connection and try again.", msgEl);
    }

    isLoading = false;
    sendBtn.disabled = false;
    inputEl.focus();
  }

  // ── Init ──────────────────────────────────────────────────────────────────
  function init() {
    const { bubble, panel, unreadBadge } = buildWidget();
    const msgEl   = document.getElementById("osc-messages");
    const inputEl = document.getElementById("osc-input");
    const sendBtn = document.getElementById("osc-send");
    const closeBtn = document.getElementById("osc-close");

    // Welcome message (delayed for polish)
    setTimeout(() => {
      appendMessage(
        "model",
        "👋 Hi! I'm **Opportunity Scout** — your 24/7 student advisor.\n\nI have access to a live database of verified **scholarships**, **internships**, **research programs**, **fellowships**, and **hackathons**.\n\nTell me about yourself — your field of study, academic level, and what kind of opportunity you're after. I'll find the best matches for you! 🎯",
        msgEl
      );

      // Show unread badge after 3s if still closed
      setTimeout(() => {
        if (!isOpen) {
          unreadCount = 1;
          unreadBadge.textContent = "1";
          unreadBadge.classList.add("visible");
        }
      }, 3000);
    }, 500);

    // ── Open / close ──
    function openPanel() {
      isOpen = true;
      panel.classList.add("osc-open");
      bubble.innerHTML = ICON_CLOSE;
      bubble.appendChild(unreadBadge);
      unreadCount = 0;
      unreadBadge.classList.remove("visible");
      requestAnimationFrame(() => inputEl.focus());
    }

    function closePanel() {
      isOpen = false;
      panel.classList.remove("osc-open");
      bubble.innerHTML = ICON_CHAT;
      bubble.appendChild(unreadBadge);
    }

    bubble.addEventListener("click", () => isOpen ? closePanel() : openPanel());
    closeBtn.addEventListener("click", closePanel);

    // ── Chip clicks ──
    document.querySelectorAll(".osc-chip").forEach(chip => {
      chip.addEventListener("click", () => {
        const prompt = chip.getAttribute("data-prompt");
        if (!isOpen) openPanel();
        setTimeout(() => sendMessage(prompt, msgEl, inputEl, sendBtn), 100);
      });
    });

    // ── Send ──
    sendBtn.addEventListener("click", () => sendMessage(inputEl.value, msgEl, inputEl, sendBtn));

    inputEl.addEventListener("keydown", e => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage(inputEl.value, msgEl, inputEl, sendBtn);
      }
    });

    inputEl.addEventListener("input", () => {
      inputEl.style.height = "auto";
      inputEl.style.height = Math.min(inputEl.scrollHeight, 100) + "px";
      sendBtn.disabled = inputEl.value.trim().length === 0 || isLoading;
    });

    // ── Expose global API ──
    window.askAdvisor = function (promptText) {
      if (!isOpen) openPanel();
      setTimeout(() => {
        if (promptText && promptText.trim()) {
          sendMessage(promptText.trim(), msgEl, inputEl, sendBtn);
        }
      }, isOpen ? 0 : 350); // small delay to let panel open
    };
  }

  // Ensure DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

})();
