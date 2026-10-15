/**
 * Opportunity Scout — Floating Chat Widget
 * Embed on any page: <script src="https://your-app.vercel.app/widget.js"></script>
 * Optional: data-api-url="https://your-app.vercel.app/api/chat"
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

  // ── State ─────────────────────────────────────────────────────────────────
  let isOpen = false;
  let isLoading = false;
  let history = [];
  let unreadCount = 0;

  // ── Styles ────────────────────────────────────────────────────────────────
  const styles = `
    #osc-widget * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }

    #osc-bubble {
      position: fixed;
      bottom: 28px;
      right: 28px;
      width: 60px;
      height: 60px;
      border-radius: 50%;
      background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
      box-shadow: 0 8px 32px rgba(99, 102, 241, 0.5);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 2147483647;
      border: none;
      outline: none;
      transition: transform 0.2s ease, box-shadow 0.2s ease;
      animation: osc-pulse 3s ease-in-out infinite;
    }
    #osc-bubble:hover {
      transform: scale(1.1);
      box-shadow: 0 12px 40px rgba(99, 102, 241, 0.65);
    }
    #osc-bubble svg { width: 28px; height: 28px; fill: white; transition: opacity 0.2s; }

    #osc-badge {
      position: absolute;
      top: -4px;
      right: -4px;
      background: #ef4444;
      color: white;
      font-size: 11px;
      font-weight: 700;
      width: 20px;
      height: 20px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      border: 2px solid white;
      display: none;
    }

    #osc-panel {
      position: fixed;
      bottom: 100px;
      right: 28px;
      width: 380px;
      max-width: calc(100vw - 32px);
      height: 560px;
      max-height: calc(100vh - 130px);
      background: #0f0f1f;
      border-radius: 20px;
      box-shadow: 0 24px 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(99,102,241,0.25);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      z-index: 2147483646;
      transform: scale(0.85) translateY(20px);
      opacity: 0;
      pointer-events: none;
      transform-origin: bottom right;
      transition: transform 0.3s cubic-bezier(0.34,1.56,0.64,1), opacity 0.25s ease;
    }
    #osc-panel.osc-open {
      transform: scale(1) translateY(0);
      opacity: 1;
      pointer-events: all;
    }

    #osc-header {
      background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
      padding: 16px 18px;
      display: flex;
      align-items: center;
      gap: 12px;
      flex-shrink: 0;
    }
    #osc-avatar {
      width: 40px;
      height: 40px;
      border-radius: 50%;
      background: rgba(255,255,255,0.2);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      flex-shrink: 0;
    }
    #osc-header-text { flex: 1; min-width: 0; }
    #osc-header-name { color: white; font-weight: 700; font-size: 15px; }
    #osc-header-status {
      color: rgba(255,255,255,0.75);
      font-size: 12px;
      display: flex;
      align-items: center;
      gap: 5px;
      margin-top: 2px;
    }
    #osc-status-dot {
      width: 7px; height: 7px;
      border-radius: 50%;
      background: #4ade80;
      animation: osc-blink 2s ease-in-out infinite;
    }
    #osc-close {
      background: rgba(255,255,255,0.15);
      border: none;
      color: white;
      width: 30px;
      height: 30px;
      border-radius: 50%;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 16px;
      line-height: 1;
      transition: background 0.2s;
      flex-shrink: 0;
    }
    #osc-close:hover { background: rgba(255,255,255,0.25); }

    #osc-messages {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      scroll-behavior: smooth;
    }
    #osc-messages::-webkit-scrollbar { width: 4px; }
    #osc-messages::-webkit-scrollbar-track { background: transparent; }
    #osc-messages::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 2px; }

    .osc-msg {
      display: flex;
      gap: 8px;
      animation: osc-fadeup 0.3s ease;
      max-width: 92%;
    }
    .osc-msg.osc-user { align-self: flex-end; flex-direction: row-reverse; }
    .osc-msg.osc-bot  { align-self: flex-start; }

    .osc-msg-avatar {
      width: 30px;
      height: 30px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 14px;
      flex-shrink: 0;
      margin-top: auto;
    }
    .osc-bot .osc-msg-avatar  { background: linear-gradient(135deg,#4f46e5,#7c3aed); }
    .osc-user .osc-msg-avatar { background: rgba(255,255,255,0.1); }

    .osc-bubble-text {
      padding: 10px 14px;
      border-radius: 16px;
      font-size: 13.5px;
      line-height: 1.55;
      max-width: 100%;
      word-break: break-word;
    }
    .osc-bot  .osc-bubble-text {
      background: rgba(255,255,255,0.07);
      color: #e2e8f0;
      border-bottom-left-radius: 4px;
    }
    .osc-user .osc-bubble-text {
      background: linear-gradient(135deg,#4f46e5,#7c3aed);
      color: white;
      border-bottom-right-radius: 4px;
    }

    /* Markdown-ish rendering */
    .osc-bubble-text strong { font-weight: 700; color: #c4b5fd; }
    .osc-bubble-text a { color: #818cf8; text-decoration: underline; }
    .osc-bubble-text ul { padding-left: 18px; margin-top: 4px; }
    .osc-bubble-text li { margin-bottom: 3px; }

    .osc-typing {
      display: flex;
      gap: 5px;
      align-items: center;
      padding: 10px 14px;
      background: rgba(255,255,255,0.07);
      border-radius: 16px;
      border-bottom-left-radius: 4px;
      width: fit-content;
    }
    .osc-typing span {
      width: 7px; height: 7px;
      background: #6366f1;
      border-radius: 50%;
      animation: osc-bounce 1.2s ease-in-out infinite;
    }
    .osc-typing span:nth-child(2) { animation-delay: 0.15s; }
    .osc-typing span:nth-child(3) { animation-delay: 0.30s; }

    #osc-footer {
      padding: 12px 14px;
      border-top: 1px solid rgba(255,255,255,0.08);
      display: flex;
      gap: 8px;
      align-items: flex-end;
      flex-shrink: 0;
      background: rgba(255,255,255,0.03);
    }
    #osc-input {
      flex: 1;
      background: rgba(255,255,255,0.07);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 12px;
      color: #e2e8f0;
      font-size: 13.5px;
      padding: 10px 14px;
      outline: none;
      resize: none;
      max-height: 100px;
      min-height: 42px;
      line-height: 1.4;
      transition: border-color 0.2s;
    }
    #osc-input::placeholder { color: rgba(255,255,255,0.3); }
    #osc-input:focus { border-color: rgba(99,102,241,0.6); }

    #osc-send {
      width: 42px;
      height: 42px;
      background: linear-gradient(135deg, #4f46e5, #7c3aed);
      border: none;
      border-radius: 12px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      transition: opacity 0.2s, transform 0.15s;
    }
    #osc-send:hover { opacity: 0.9; transform: scale(1.05); }
    #osc-send:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }
    #osc-send svg { width: 18px; height: 18px; fill: white; }

    #osc-powered {
      text-align: center;
      font-size: 10.5px;
      color: rgba(255,255,255,0.2);
      padding: 6px 0 8px;
      flex-shrink: 0;
    }
    #osc-powered a { color: rgba(99,102,241,0.6); text-decoration: none; }

    @keyframes osc-pulse {
      0%, 100% { box-shadow: 0 8px 32px rgba(99,102,241,0.5); }
      50%       { box-shadow: 0 8px 48px rgba(99,102,241,0.75); }
    }
    @keyframes osc-blink {
      0%, 100% { opacity: 1; } 50% { opacity: 0.4; }
    }
    @keyframes osc-bounce {
      0%, 80%, 100% { transform: translateY(0); }
      40%           { transform: translateY(-6px); }
    }
    @keyframes osc-fadeup {
      from { opacity: 0; transform: translateY(8px); }
      to   { opacity: 1; transform: translateY(0); }
    }

    @media (max-width: 440px) {
      #osc-panel { width: calc(100vw - 16px); right: 8px; bottom: 90px; }
      #osc-bubble { right: 16px; bottom: 16px; }
    }
  `;

  // ── DOM Construction ──────────────────────────────────────────────────────
  function buildWidget() {
    // Inject styles
    const styleEl = document.createElement("style");
    styleEl.textContent = styles;
    document.head.appendChild(styleEl);

    // Wrapper (for namespacing)
    const wrapper = document.createElement("div");
    wrapper.id = "osc-widget";
    document.body.appendChild(wrapper);

    // ── Bubble button ──
    const bubble = document.createElement("button");
    bubble.id = "osc-bubble";
    bubble.setAttribute("aria-label", "Open Opportunity Scout chat");
    bubble.innerHTML = `
      <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path d="M20 2H4C2.9 2 2 2.9 2 4v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 10H6v-2h12v2zm0-3H6V7h12v2z"/>
      </svg>
    `;
    const badge = document.createElement("span");
    badge.id = "osc-badge";
    bubble.appendChild(badge);
    wrapper.appendChild(bubble);

    // ── Chat panel ──
    const panel = document.createElement("div");
    panel.id = "osc-panel";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", "Opportunity Scout chat");
    panel.innerHTML = `
      <div id="osc-header">
        <div id="osc-avatar">🎓</div>
        <div id="osc-header-text">
          <div id="osc-header-name">Opportunity Scout</div>
          <div id="osc-header-status">
            <span id="osc-status-dot"></span>
            <span>24/7 Student Advisor · AI Powered</span>
          </div>
        </div>
        <button id="osc-close" aria-label="Close chat">✕</button>
      </div>

      <div id="osc-messages" role="log" aria-live="polite" aria-label="Chat messages"></div>

      <div id="osc-footer">
        <textarea
          id="osc-input"
          placeholder="Ask about scholarships, internships, research…"
          rows="1"
          aria-label="Message input"
        ></textarea>
        <button id="osc-send" aria-label="Send message" disabled>
          <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
        </button>
      </div>
      <div id="osc-powered">Powered by <a href="https://github.com/Jaiswal096/Student-opportunities-agents" target="_blank">Opportunity Scout</a></div>
    `;
    wrapper.appendChild(panel);

    return { bubble, panel, badge };
  }

  // ── Helpers ───────────────────────────────────────────────────────────────
  function escapeHtml(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  /** Very light markdown → HTML (bold, links, lists) */
  function renderMarkdown(text) {
    return text
      .split("\n")
      .map((line) => {
        line = escapeHtml(line);
        // Bold **text**
        line = line.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
        // Inline code `text`
        line = line.replace(/`(.+?)`/g, "<code>$1</code>");
        // Links [text](url)
        line = line.replace(
          /\[(.+?)\]\((https?:\/\/[^\)]+)\)/g,
          '<a href="$2" target="_blank" rel="noopener">$1</a>'
        );
        // Bare URLs
        line = line.replace(
          /(https?:\/\/[^\s<>"]+)/g,
          '<a href="$1" target="_blank" rel="noopener">$1</a>'
        );
        // Bullet list items
        if (/^[-•✓✗]\s/.test(line)) {
          line = "<li>" + line.slice(2) + "</li>";
        }
        return line;
      })
      .join("\n")
      .replace(/(<li>.*<\/li>\n?)+/gs, (match) => "<ul>" + match + "</ul>")
      .replace(/\n/g, "<br>");
  }

  function scrollToBottom(el) {
    el.scrollTop = el.scrollHeight;
  }

  function autoGrow(textarea) {
    textarea.style.height = "auto";
    textarea.style.height = Math.min(textarea.scrollHeight, 100) + "px";
  }

  // ── Message rendering ─────────────────────────────────────────────────────
  function appendMessage(role, text, messagesEl) {
    const wrap = document.createElement("div");
    wrap.className = "osc-msg " + (role === "user" ? "osc-user" : "osc-bot");

    const avatar = document.createElement("div");
    avatar.className = "osc-msg-avatar";
    avatar.textContent = role === "user" ? "👤" : "🎓";

    const bubble = document.createElement("div");
    bubble.className = "osc-bubble-text";
    bubble.innerHTML = renderMarkdown(text);

    wrap.appendChild(avatar);
    wrap.appendChild(bubble);
    messagesEl.appendChild(wrap);
    scrollToBottom(messagesEl);
    return wrap;
  }

  function showTyping(messagesEl) {
    const wrap = document.createElement("div");
    wrap.className = "osc-msg osc-bot";
    wrap.id = "osc-typing-indicator";
    wrap.innerHTML = `
      <div class="osc-msg-avatar">🎓</div>
      <div class="osc-typing"><span></span><span></span><span></span></div>
    `;
    messagesEl.appendChild(wrap);
    scrollToBottom(messagesEl);
    return wrap;
  }

  function removeTyping() {
    const el = document.getElementById("osc-typing-indicator");
    if (el) el.remove();
  }

  // ── API call ──────────────────────────────────────────────────────────────
  async function sendMessage(message, messagesEl, inputEl, sendBtn) {
    if (!message.trim() || isLoading) return;
    isLoading = true;

    inputEl.value = "";
    inputEl.style.height = "auto";
    sendBtn.disabled = true;

    appendMessage("user", message, messagesEl);
    const typing = showTyping(messagesEl);

    const payload = {
      message: message,
      history: history.map((h) => ({ role: h.role, content: h.content })),
    };

    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      removeTyping();

      const reply = data.reply || data.error || "Sorry, something went wrong.";
      appendMessage("model", reply, messagesEl);

      // Update history
      history.push({ role: "user", content: message });
      history.push({ role: "model", content: reply });

      // Keep last 20 messages to avoid token overflow
      if (history.length > 20) history = history.slice(-20);

    } catch (err) {
      removeTyping();
      appendMessage(
        "model",
        "⚠️ Connection error — please try again in a moment.",
        messagesEl
      );
    }

    isLoading = false;
    sendBtn.disabled = false;
    inputEl.focus();
  }

  // ── Initialise ────────────────────────────────────────────────────────────
  function init() {
    const { bubble, panel, badge } = buildWidget();
    const messagesEl = document.getElementById("osc-messages");
    const inputEl    = document.getElementById("osc-input");
    const sendBtn    = document.getElementById("osc-send");
    const closeBtn   = document.getElementById("osc-close");

    // Welcome message
    setTimeout(() => {
      appendMessage(
        "model",
        "👋 Hi! I'm **Opportunity Scout** — your 24/7 student advisor.\n\nI have access to a live database of verified scholarships, internships, research programs, fellowships, and hackathons.\n\nTell me about yourself — your field of study, academic level, and what kind of opportunity you're looking for. I'll find the best matches for you!",
        messagesEl
      );
      // Show unread badge after 3s if panel is still closed
      setTimeout(() => {
        if (!isOpen) {
          unreadCount = 1;
          badge.textContent = "1";
          badge.style.display = "flex";
        }
      }, 3000);
    }, 400);

    // Toggle panel
    function openPanel() {
      isOpen = true;
      panel.classList.add("osc-open");
      bubble.innerHTML = `<svg viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>`;
      unreadCount = 0;
      badge.style.display = "none";
      inputEl.focus();
    }

    function closePanel() {
      isOpen = false;
      panel.classList.remove("osc-open");
      bubble.innerHTML = `<svg viewBox="0 0 24 24"><path d="M20 2H4C2.9 2 2 2.9 2 4v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 10H6v-2h12v2zm0-3H6V7h12v2z"/></svg>`;
      bubble.appendChild(badge);
    }

    bubble.addEventListener("click", () =>
      isOpen ? closePanel() : openPanel()
    );
    closeBtn.addEventListener("click", closePanel);

    // Send on button click or Enter (Shift+Enter = newline)
    sendBtn.addEventListener("click", () =>
      sendMessage(inputEl.value, messagesEl, inputEl, sendBtn)
    );

    inputEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage(inputEl.value, messagesEl, inputEl, sendBtn);
      }
    });

    inputEl.addEventListener("input", () => {
      autoGrow(inputEl);
      sendBtn.disabled = inputEl.value.trim().length === 0 || isLoading;
    });
  }

  // Run after DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
