(function () {
  "use strict";

  // Find our own <script> tag to read data-agent-id / data-api-base-url.
  // Must run synchronously at the top of the IIFE, before any await/async
  // boundary, since document.currentScript is only valid during the
  // initial synchronous execution of a classic (non-module) script.
  var currentScript = document.currentScript;
  if (!currentScript) {
    var scripts = document.getElementsByTagName("script");
    for (var i = scripts.length - 1; i >= 0; i--) {
      if (scripts[i].src && scripts[i].src.indexOf("widget.js") !== -1) {
        currentScript = scripts[i];
        break;
      }
    }
  }
  if (!currentScript) {
    console.error("[AIChatWidget] Could not locate its own <script> tag.");
    return;
  }

  var AGENT_ID = currentScript.getAttribute("data-agent-id");
  if (!AGENT_ID) {
    console.error("[AIChatWidget] Missing required data-agent-id attribute.");
    return;
  }

  var LOGIN_TOKEN = currentScript.getAttribute("data-login-token") || null;

  var API_BASE =
    currentScript.getAttribute("data-api-base-url") ||
    (function () {
      try {
        var scriptUrl = new URL(currentScript.src, window.location.href);
        return scriptUrl.origin;
      } catch (e) {
        return "";
      }
    })();

  var POLL_INTERVAL_MS = 4000;
  var BACKGROUND_POLL_INTERVAL_MS = 20000;

  // Arabic gets a right-to-left layout; every fetch() below also sends the
  // browser's Accept-Language automatically, which is what the backend
  // uses to pick Arabic/English for greeting + menu text — this only
  // needs to separately decide the *layout* direction client-side.
  var BROWSER_LANG = (navigator.language || (navigator.languages && navigator.languages[0]) || "").toLowerCase();
  var IS_RTL = BROWSER_LANG.indexOf("ar") === 0;
  var STRINGS = IS_RTL
    ? { onlineNow: "متصل الآن", openChat: "فتح المحادثة", closeChat: "إغلاق المحادثة", sendMessage: "إرسال" }
    : { onlineNow: "Online now", openChat: "Open chat", closeChat: "Close chat", sendMessage: "Send message" };

  function apiUrl(path) {
    return API_BASE + "/api/widget" + path;
  }

  async function apiRequest(path, options) {
    var response = await fetch(apiUrl(path), options);
    if (!response.ok) {
      var detail = "";
      try {
        var body = await response.json();
        detail = body.detail || "";
      } catch (e) {}
      throw new Error(detail || "Request failed (" + response.status + ")");
    }
    if (response.status === 204) return null;
    return response.json();
  }


  // Streams a turn over SSE, calling onToken per fragment. Resolves with
  // the same payload the non-streaming endpoint returns. Rejects on any
  // transport failure so the caller can fall back to that endpoint.
  async function streamRequest(path, payload, onToken) {
    var response = await fetch(apiUrl(path), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok || !response.body) throw new Error("Stream unavailable (" + response.status + ")");

    var reader = response.body.getReader();
    var decoder = new TextDecoder();
    var buffer = "";
    var result = null;
    var failure = null;

    try {
      while (true) {
        var step = await reader.read();
        if (step.done) break;
        buffer += decoder.decode(step.value, { stream: true });

        var boundary;
        while ((boundary = buffer.indexOf("\n\n")) !== -1) {
          var frame = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);

          var event = "message";
          var dataLines = [];
          frame.split("\n").forEach(function (line) {
            if (line.indexOf("event: ") === 0) event = line.slice(7);
            else if (line.indexOf("data: ") === 0) dataLines.push(line.slice(6));
          });
          if (!dataLines.length) continue;

          var data;
          try { data = JSON.parse(dataLines.join("\n")); } catch (e) { continue; }

          if (event === "token") onToken(data.text);
          else if (event === "done") result = data;
          else if (event === "error") failure = data.detail || "Request failed";
        }
      }
    } finally {
      // Safari leaks the reader lock if the stream ends mid-frame.
      try { reader.releaseLock(); } catch (e) {}
    }

    if (failure) throw new Error(failure);
    if (!result) throw new Error("Stream ended without a result");
    return result;
  }

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (key) {
        if (key === "style") {
          Object.assign(node.style, attrs[key]);
        } else if (key.indexOf("on") === 0 && typeof attrs[key] === "function") {
          node.addEventListener(key.slice(2).toLowerCase(), attrs[key]);
        } else {
          node.setAttribute(key, attrs[key]);
        }
      });
    }
    (children || []).forEach(function (child) {
      if (typeof child === "string") node.appendChild(document.createTextNode(child));
      else if (child) node.appendChild(child);
    });
    return node;
  }

  function escapeHtml(str) {
    var div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function hexToRgba(hex, alpha) {
    var clean = (hex || "").replace("#", "");
    if (clean.length === 3) {
      clean = clean[0] + clean[0] + clean[1] + clean[1] + clean[2] + clean[2];
    }
    var num = parseInt(clean, 16);
    if (isNaN(num)) return "rgba(0,0,0," + alpha + ")";
    var r = (num >> 16) & 255;
    var g = (num >> 8) & 255;
    var b = num & 255;
    return "rgba(" + r + "," + g + "," + b + "," + alpha + ")";
  }

  function ChatWidget() {
    this.config = null;
    this.sessionToken = null;
    this.conversationId = null;
    this.conversationStatus = "ai_active";
    this.isOpen = false;
    this.hasOpenedOnce = false;
    this.unreadCount = 0;
    this.pollTimer = null;
    this.lastMessageId = null;
    this.renderedMessageIds = {};
    this.lastRenderedSender = null;
  }

  ChatWidget.prototype.init = async function () {
    try {
      this.config = await apiRequest("/config/" + AGENT_ID, { method: "GET" });
    } catch (e) {
      console.error("[AIChatWidget] Failed to load config:", e.message);
      return;
    }
    this._buildDom();
  };

  ChatWidget.prototype._buildDom = function () {
    var host = el("div", { id: "ai-chat-widget-host" });
    var position = this.config.widget_position === "bottom_left" ? "left" : "right";
    host.style.position = "fixed";
    host.style.bottom = "20px";
    host.style[position] = "20px";
    host.style.zIndex = "2147483647";
    document.body.appendChild(host);

    var shadow = host.attachShadow({ mode: "closed" });
    this.shadow = shadow;

    var sizeMap = { compact: "340px", standard: "380px", large: "420px" };
    var panelWidth = sizeMap[this.config.widget_size] || sizeMap.standard;

    var style = el("style", null, [
      this._css(panelWidth, position),
    ]);
    shadow.appendChild(style);

    var container = el("div", { class: "widget-root", dir: IS_RTL ? "rtl" : "ltr" });
    shadow.appendChild(container);

    this.launcher = el(
      "button",
      { class: "launcher", "aria-label": STRINGS.openChat, onclick: this._toggle.bind(this) },
      [
        el("span", { class: "pulse-ring" }),
        this._launcherIcon(),
        (this.unreadBadge = el("span", { class: "unread-badge hidden" })),
      ]
    );
    container.appendChild(this.launcher);

    this.panel = el("div", { class: "panel hidden" }, [
      this._buildHeader(),
      (this.messagesEl = el("div", { class: "messages" })),
      this._buildInputArea(),
    ]);
    container.appendChild(this.panel);
  };

  ChatWidget.prototype._launcherIcon = function () {
    var span = el("span", { class: "launcher-icon" });
    span.innerHTML =
      '<svg class="icon-chat" width="26" height="26" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">' +
      '<path d="M4 4h16v12H7l-3 3V4z" fill="white"/></svg>' +
      '<svg class="icon-close" width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">' +
      '<path d="M6 6l12 12M18 6L6 18" stroke="white" stroke-width="2" stroke-linecap="round"/></svg>';
    return span;
  };

  ChatWidget.prototype._buildHeader = function () {
    var logo = this.config.logo_url
      ? el("img", { class: "avatar", src: this._resolveMediaUrl(this.config.logo_url), alt: "" })
      : el("div", { class: "avatar avatar-fallback" }, [this.config.company_name.charAt(0)]);

    var avatarWrap = el("div", { class: "avatar-wrap" }, [logo, el("span", { class: "status-dot" })]);

    return el("div", { class: "header" }, [
      avatarWrap,
      el("div", { class: "header-text" }, [
        el("div", { class: "header-title" }, [this.config.agent_name]),
        el("div", { class: "header-subtitle" }, [STRINGS.onlineNow]),
      ]),
      el("button", { class: "close-btn", "aria-label": STRINGS.closeChat, onclick: this._toggle.bind(this) }, [
        this._closeIcon(),
      ]),
    ]);
  };

  ChatWidget.prototype._closeIcon = function () {
    var span = el("span", { class: "close-icon" });
    span.innerHTML =
      '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">' +
      '<path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>';
    return span;
  };

  ChatWidget.prototype._buildInputArea = function () {
    var self = this;
    this.inputEl = el("input", {
      type: "text",
      class: "text-input",
      placeholder: this.config.placeholder_text,
      "aria-label": "Message",
    });
    this.inputEl.addEventListener("keydown", function (e) {
      if (e.key === "Enter") self._sendCurrentInput();
    });

    this.sendBtn = el(
      "button",
      { class: "send-btn", "aria-label": STRINGS.sendMessage, onclick: function () { self._sendCurrentInput(); } },
      []
    );
    this.sendBtn.innerHTML =
      '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">' +
      '<path d="M3.4 20.6L21 12 3.4 3.4 3 10l13 2-13 2z" fill="currentColor"/></svg>';

    return el("div", { class: "input-area" }, [this.inputEl, this.sendBtn]);
  };

  ChatWidget.prototype._resolveMediaUrl = function (url) {
    if (!url) return url;
    if (url.indexOf("http") === 0) return url;
    return API_BASE + url;
  };

  ChatWidget.prototype._css = function (panelWidth, position) {
    var c = this.config;
    var focusRing = hexToRgba(c.primary_color, 0.25);
    var launcherRing = hexToRgba(c.button_color, 0.45);
    var secondary = c.secondary_color || c.primary_color;
    var headerGradient = "linear-gradient(135deg, " + c.primary_color + ", " + secondary + ")";
    var transformOrigin = "bottom " + position;
    var easing = "cubic-bezier(0.22, 0.9, 0.32, 1)";
    return (
      ".widget-root, .widget-root * { box-sizing: border-box; font-family: " +
      c.font_family +
      ", -apple-system, sans-serif; font-size: " +
      c.font_size +
      "; }" +
      ".launcher { position: relative; width: 60px; height: 60px; border-radius: 50%; border: none; background: " +
      c.button_color +
      "; cursor: pointer; box-shadow: 0 8px 24px " +
      hexToRgba(c.button_color, 0.35) +
      ", 0 2px 6px rgba(0,0,0,0.15); display: flex; align-items: center; justify-content: center; transition: transform 200ms " +
      easing +
      ", box-shadow 200ms " +
      easing +
      "; }" +
      ".launcher:hover { transform: scale(1.07); box-shadow: 0 10px 28px " +
      hexToRgba(c.button_color, 0.45) +
      ", 0 2px 8px rgba(0,0,0,0.18); }" +
      ".launcher:active { transform: scale(0.94); }" +
      ".pulse-ring { position: absolute; inset: 0; border-radius: 50%; background: " +
      launcherRing +
      "; animation: pulseRing 2.4s ease-out infinite; pointer-events: none; }" +
      ".launcher.opened-once .pulse-ring { display: none; }" +
      "@keyframes pulseRing { 0% { transform: scale(1); opacity: 0.55; } 100% { transform: scale(1.7); opacity: 0; } }" +
      ".unread-badge { position: absolute; top: -3px; right: -3px; min-width: 20px; height: 20px; padding: 0 5px; border-radius: 10px; background: #ef4444; color: #fff; font-size: 11px; font-weight: 700; line-height: 20px; text-align: center; box-shadow: 0 0 0 2px #fff; }" +
      ".unread-badge.hidden { display: none; }" +
      ".launcher-icon { position: relative; width: 26px; height: 26px; display: flex; align-items: center; justify-content: center; }" +
      ".launcher-icon svg { position: absolute; inset: 0; margin: auto; transition: opacity 160ms ease, transform 160ms ease; }" +
      ".launcher-icon .icon-close { opacity: 0; transform: rotate(-45deg) scale(0.5); }" +
      ".launcher.open .launcher-icon .icon-chat { opacity: 0; transform: rotate(45deg) scale(0.5); }" +
      ".launcher.open .launcher-icon .icon-close { opacity: 1; transform: rotate(0) scale(1); }" +
      ".panel { position: absolute; bottom: 76px; " +
      position +
      ": 0; width: " +
      panelWidth +
      "; max-width: calc(100vw - 40px); height: 70vh; max-height: 600px; background: " +
      c.background_color +
      "; color: " +
      c.text_color +
      "; border-radius: 20px; box-shadow: 0 16px 48px rgba(0,0,0,0.2), 0 4px 12px rgba(0,0,0,0.08); display: flex; flex-direction: column; overflow: hidden; transform-origin: " +
      transformOrigin +
      "; opacity: 1; transform: translateY(0) scale(1); transition: opacity 220ms " +
      easing +
      ", transform 220ms " +
      easing +
      ", visibility 0s linear 0s; }" +
      ".panel.hidden { opacity: 0; visibility: hidden; transform: translateY(14px) scale(0.95); transition: opacity 160ms ease, transform 160ms ease, visibility 0s linear 160ms; }" +
      ".header { display: flex; align-items: center; gap: 10px; padding: 16px; background: " +
      headerGradient +
      "; color: #fff; }" +
      ".avatar-wrap { position: relative; flex-shrink: 0; }" +
      ".avatar { width: 38px; height: 38px; border-radius: 50%; object-fit: cover; background: rgba(255,255,255,0.22); box-shadow: 0 0 0 2px rgba(255,255,255,0.35); display: block; }" +
      ".avatar-fallback { display: flex; align-items: center; justify-content: center; font-weight: 600; }" +
      ".status-dot { position: absolute; right: -1px; bottom: -1px; width: 11px; height: 11px; border-radius: 50%; background: #22c55e; border: 2px solid " +
      c.primary_color +
      "; }" +
      ".header-text { flex: 1; min-width: 0; }" +
      ".header-title { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }" +
      ".header-subtitle { font-size: 0.82em; opacity: 0.88; }" +
      ".close-btn { background: rgba(255,255,255,0.14); border: none; color: #fff; cursor: pointer; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; transition: background 150ms ease, transform 150ms ease; }" +
      ".close-btn:hover { background: rgba(255,255,255,0.26); transform: rotate(90deg); }" +
      ".messages { flex: 1; overflow-y: auto; padding: 14px 12px; display: flex; flex-direction: column; gap: 3px; scrollbar-width: thin; scrollbar-color: rgba(0,0,0,0.2) transparent; background: " +
      c.background_color +
      "; }" +
      ".messages::-webkit-scrollbar { width: 6px; }" +
      ".messages::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.18); border-radius: 3px; }" +
      ".messages::-webkit-scrollbar-track { background: transparent; }" +
      ".msg-row { display: flex; align-items: flex-end; gap: 6px; max-width: 85%; align-self: flex-start; margin-top: 8px; }" +
      ".msg-row.visitor-row { align-self: flex-end; flex-direction: row-reverse; }" +
      ".msg-avatar { width: 22px; height: 22px; border-radius: 50%; flex-shrink: 0; object-fit: cover; background: " +
      hexToRgba(c.primary_color, 0.15) +
      "; }" +
      ".msg-avatar.spacer { visibility: hidden; }" +
      ".msg-avatar.avatar-fallback { font-size: 11px; color: " +
      c.primary_color +
      "; }" +
      ".msg-col { display: flex; flex-direction: column; min-width: 0; }" +
      ".msg-row.visitor-row .msg-col { align-items: flex-end; }" +
      ".msg { max-width: 100%; padding: 10px 14px; border-radius: 17px; line-height: 1.42; white-space: pre-wrap; word-break: break-word; animation: msgIn 200ms " +
      easing +
      "; }" +
      ".msg.visitor { background: " +
      c.primary_color +
      "; color: #fff; border-bottom-right-radius: 5px; }" +
      ".msg.ai, .msg.operator, .msg.system { background: rgba(0,0,0,0.055); border-bottom-left-radius: 5px; }" +
      ".msg-time { font-size: 10.5px; color: rgba(0,0,0,0.35); margin: 3px 4px 0; }" +
      "@keyframes msgIn { from { opacity: 0; transform: translateY(6px) scale(0.98); } to { opacity: 1; transform: translateY(0) scale(1); } }" +
      ".typing-row { display: flex; align-items: flex-end; gap: 6px; align-self: flex-start; margin-top: 8px; }" +
      ".typing { display: flex; align-items: center; gap: 4px; padding: 12px 15px; background: rgba(0,0,0,0.055); border-radius: 17px; border-bottom-left-radius: 5px; }" +
      ".typing-dot { width: 6px; height: 6px; border-radius: 50%; background: rgba(0,0,0,0.35); animation: typingBounce 1.2s infinite ease-in-out; }" +
      ".typing-dot:nth-child(2) { animation-delay: 0.15s; }" +
      ".typing-dot:nth-child(3) { animation-delay: 0.3s; }" +
      "@keyframes typingBounce { 0%, 60%, 100% { transform: translateY(0); opacity: 0.5; } 30% { transform: translateY(-4px); opacity: 1; } }" +
      ".handoff-buttons { display: flex; gap: 8px; margin-top: 8px; }" +
      ".handoff-buttons button { flex: 1; padding: 9px; border-radius: 20px; border: 1.5px solid " +
      c.primary_color +
      "; background: #fff; color: " +
      c.primary_color +
      "; cursor: pointer; font-size: 0.9em; font-weight: 500; transition: background 150ms ease, transform 150ms ease; }" +
      ".handoff-buttons button:hover { background: rgba(0,0,0,0.04); transform: translateY(-1px); }" +
      ".handoff-buttons button.primary { background: " +
      c.button_color +
      "; color: #fff; border: none; }" +
      ".handoff-buttons button.primary:hover { opacity: 0.92; background: " +
      c.button_color +
      "; }" +
      ".quick-replies { display: flex; flex-direction: column; gap: 6px; margin-top: 8px; }" +
      ".quick-replies button { padding: 9px 14px; border-radius: 14px; border: 1.5px solid " +
      c.primary_color +
      "; background: #fff; color: " +
      c.primary_color +
      "; cursor: pointer; font-size: 0.9em; font-weight: 500; text-align: left; transition: background 150ms ease, transform 150ms ease, opacity 150ms ease; }" +
      ".quick-replies button:hover:not(:disabled) { background: rgba(0,0,0,0.04); transform: translateY(-1px); }" +
      ".quick-replies button:disabled { opacity: 0.5; cursor: default; transform: none; }" +
      ".input-area { display: flex; align-items: center; gap: 8px; padding: 12px; border-top: 1px solid rgba(0,0,0,0.08); background: " +
      c.background_color +
      "; }" +
      ".text-input { flex: 1; padding: 10px 15px; border-radius: 22px; border: 1.5px solid rgba(0,0,0,0.12); outline: none; background: rgba(0,0,0,0.02); color: " +
      c.text_color +
      "; transition: border-color 150ms ease, box-shadow 150ms ease, background 150ms ease; }" +
      ".text-input:focus { border-color: " +
      c.primary_color +
      "; background: transparent; box-shadow: 0 0 0 3px " +
      focusRing +
      "; }" +
      ".send-btn { flex-shrink: 0; width: 40px; height: 40px; padding: 0; border-radius: 50%; border: none; background: " +
      c.button_color +
      "; color: #fff; cursor: pointer; display: flex; align-items: center; justify-content: center; box-shadow: 0 3px 10px " +
      hexToRgba(c.button_color, 0.35) +
      "; transition: transform 150ms " +
      easing +
      ", opacity 150ms ease, box-shadow 150ms ease; }" +
      ".send-btn svg { margin-left: 1px; }" +
      ".send-btn:hover { transform: scale(1.08); box-shadow: 0 4px 14px " +
      hexToRgba(c.button_color, 0.45) +
      "; }" +
      ".send-btn:active { transform: scale(0.94); }" +
      ".send-btn:disabled { opacity: 0.5; cursor: default; transform: none; box-shadow: none; }" +
      ".error-banner { align-self: center; padding: 8px 12px; background: #fdecea; color: #b3261e; font-size: 0.85em; border-radius: 10px; margin-top: 8px; }" +
      ".widget-root[dir='rtl'] { direction: rtl; }" +
      "@media (max-width: 480px) { .panel { width: calc(100vw - 24px); height: 80vh; bottom: 72px; } }" +
      "@media (prefers-reduced-motion: reduce) { .msg, .launcher, .panel, .launcher-icon svg, .send-btn, .typing-dot, .pulse-ring, .close-btn { animation: none !important; transition: none !important; } }"
    );
  };

  ChatWidget.prototype._toggle = async function () {
    this.isOpen = !this.isOpen;
    this.panel.classList.toggle("hidden", !this.isOpen);
    this.launcher.classList.toggle("open", this.isOpen);
    if (this.isOpen) {
      this.hasOpenedOnce = true;
      this.launcher.classList.add("opened-once");
      this._clearUnread();
    }
    if (this.isOpen && !this.conversationId) {
      await this._ensureSession();
    }
    if (this.isOpen) {
      this._startPolling(POLL_INTERVAL_MS);
    } else if (this.sessionToken) {
      this._startPolling(BACKGROUND_POLL_INTERVAL_MS);
    } else {
      this._stopPolling();
    }
  };

  ChatWidget.prototype._ensureSession = async function () {
    try {
      var data = await apiRequest("/" + AGENT_ID + "/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_token: this.sessionToken, login_token: LOGIN_TOKEN }),
      });
      this.sessionToken = data.session_token;
      this.conversationId = data.conversation_id;
      this.conversationStatus = data.conversation_status;
      data.messages.forEach(this._renderMessage.bind(this));
    } catch (e) {
      this._renderError("Sorry, we couldn't start the chat. Please try again shortly.");
    }
  };


  ChatWidget.prototype._openLiveBubble = function () {
    var sameAsLast = this.lastRenderedSender === "ai";
    this.lastRenderedSender = "ai";
    var bubble = el("div", { class: "msg ai" }, [""]);
    var col = el("div", { class: "msg-col" }, [bubble]);
    var avatar = sameAsLast ? el("span", { class: "msg-avatar spacer" }) : this._buildAvatarNode();
    var row = el("div", { class: "msg-row" }, [avatar, col]);
    this.messagesEl.appendChild(row);
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
    return { row: row, bubble: bubble, text: "" };
  };

  ChatWidget.prototype._appendLiveToken = function (live, piece) {
    live.text += piece;
    live.bubble.textContent = live.text;
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
  };

  ChatWidget.prototype._discardLiveBubble = function (live) {
    if (live && live.row && live.row.parentNode) live.row.parentNode.removeChild(live.row);
    // The final message is rendered from the server payload, so the
    // sender-run tracking has to be rewound as if this never existed.
    this.lastRenderedSender = null;
  };

  ChatWidget.prototype._sendCurrentInput = async function () {
    var text = this.inputEl.value.trim();
    if (!text) return;
    this.inputEl.value = "";
    this.inputEl.disabled = true;
    this.sendBtn.disabled = true;

    this._renderMessage({ id: "local-" + Date.now(), sender_type: "visitor", content: text, message_metadata: {} });
    var typingEl = this._showTyping();
    var payload = { session_token: this.sessionToken, message: text };
    var self = this;
    var live = null;

    try {
      var data;
      try {
        data = await streamRequest("/" + AGENT_ID + "/message/stream", payload, function (piece) {
          if (!live) {
            self._removeTyping(typingEl);
            typingEl = null;
            live = self._openLiveBubble();
          }
          self._appendLiveToken(live, piece);
        });
      } catch (streamError) {
        // Any transport that can't do SSE — a buffering proxy, an old
        // browser, the endpoint being unavailable — falls back rather
        // than losing the visitor's message.
        self._discardLiveBubble(live);
        live = null;
        data = await apiRequest("/" + AGENT_ID + "/message", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      }
      // The streamed text was a preview; the server's stored message is
      // what gets rendered, so ids, timestamps and quick replies are right.
      this._discardLiveBubble(live);
      this.conversationStatus = data.conversation_status;
      data.messages.forEach(this._renderMessage.bind(this));
    } catch (e) {
      this._discardLiveBubble(live);
      this._renderError("Message failed to send. Please try again.");
    } finally {
      this._removeTyping(typingEl);
      this.inputEl.disabled = false;
      this.sendBtn.disabled = false;
      this.inputEl.focus();
    }
  };

  ChatWidget.prototype._buildAvatarNode = function () {
    var url = this.config.avatar_url || this.config.logo_url;
    if (url) return el("img", { class: "msg-avatar", src: this._resolveMediaUrl(url), alt: "" });
    return el("div", { class: "msg-avatar avatar-fallback" }, [this.config.agent_name.charAt(0)]);
  };

  ChatWidget.prototype._formatTime = function (iso) {
    try {
      var d = new Date(iso);
      if (isNaN(d.getTime())) return "";
      return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    } catch (e) {
      return "";
    }
  };

  ChatWidget.prototype._showTyping = function () {
    var avatar =
      this.lastRenderedSender && this.lastRenderedSender !== "visitor"
        ? el("span", { class: "msg-avatar spacer" })
        : this._buildAvatarNode();
    var node = el("div", { class: "typing-row" }, [
      avatar,
      el("div", { class: "typing" }, [
        el("span", { class: "typing-dot" }),
        el("span", { class: "typing-dot" }),
        el("span", { class: "typing-dot" }),
      ]),
    ]);
    this.messagesEl.appendChild(node);
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
    return node;
  };

  ChatWidget.prototype._removeTyping = function (node) {
    if (node && node.parentNode) node.parentNode.removeChild(node);
  };

  ChatWidget.prototype._renderError = function (text) {
    var node = el("div", { class: "error-banner" }, [text]);
    this.messagesEl.appendChild(node);
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
  };

  ChatWidget.prototype._addUnread = function () {
    this.unreadCount++;
    this.unreadBadge.textContent = this.unreadCount > 9 ? "9+" : String(this.unreadCount);
    this.unreadBadge.classList.remove("hidden");
  };

  ChatWidget.prototype._clearUnread = function () {
    this.unreadCount = 0;
    this.unreadBadge.textContent = "";
    this.unreadBadge.classList.add("hidden");
  };

  ChatWidget.prototype._renderMessage = function (message) {
    if (this.renderedMessageIds[message.id]) return;
    this.renderedMessageIds[message.id] = true;
    var isLocalEcho = typeof message.id === "string" && message.id.indexOf("local-") === 0;
    if (!isLocalEcho) {
      this.lastMessageId = message.id;
    }

    var isVisitor = message.sender_type === "visitor";
    var sameAsLast = this.lastRenderedSender === message.sender_type;
    this.lastRenderedSender = message.sender_type;

    var bubble = el("div", { class: "msg " + message.sender_type }, [message.content]);
    var colChildren = [bubble];
    if (message.created_at) {
      colChildren.push(el("span", { class: "msg-time" }, [this._formatTime(message.created_at)]));
    }
    var col = el("div", { class: "msg-col" }, colChildren);

    var row;
    if (isVisitor) {
      row = el("div", { class: "msg-row visitor-row" }, [col]);
    } else {
      var avatar = sameAsLast ? el("span", { class: "msg-avatar spacer" }) : this._buildAvatarNode();
      row = el("div", { class: "msg-row" }, [avatar, col]);
    }
    this.messagesEl.appendChild(row);

    var metadata = message.message_metadata || {};
    if (metadata.type === "handoff_offer") {
      var self = this;
      var yesBtn = el("button", { class: "primary", onclick: function () { self._respondHandoff(true); } }, [
        "Yes, connect me",
      ]);
      var noBtn = el("button", { onclick: function () { self._respondHandoff(false); } }, ["Continue with AI"]);
      col.appendChild(el("div", { class: "handoff-buttons" }, [yesBtn, noBtn]));
    }

    if (Array.isArray(metadata.options)) {
      var self2 = this;
      var wrap = el("div", { class: "quick-replies" });
      metadata.options.forEach(function (opt) {
        var btn = el("button", { onclick: function () { self2._sendQuickReply(opt, wrap); } }, [opt.label]);
        wrap.appendChild(btn);
      });
      col.appendChild(wrap);
    }

    if (!this.isOpen && !isVisitor && !isLocalEcho) {
      this._addUnread();
    }

    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
  };

  ChatWidget.prototype._respondHandoff = async function (accepted) {
    try {
      var data = await apiRequest("/" + AGENT_ID + "/handoff", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_token: this.sessionToken, accepted: accepted }),
      });
      this.conversationStatus = data.conversation_status;
      data.messages.forEach(this._renderMessage.bind(this));
    } catch (e) {
      this._renderError("Couldn't process that — please try again.");
    }
  };

  ChatWidget.prototype._sendQuickReply = async function (option, buttonsWrap) {
    // Only disabled for the duration of this one request (guards against a
    // rapid double-click firing it twice) — re-enabled afterwards rather
    // than left dead, since the reply isn't always a final answer: if the
    // visitor still owes their name/email/phone, the backend just re-asks
    // for that instead of answering, and they need to be able to click this
    // same button again once they've finished.
    var buttons = buttonsWrap ? buttonsWrap.querySelectorAll("button") : [];
    Array.prototype.forEach.call(buttons, function (b) { b.disabled = true; });

    this._renderMessage({ id: "local-" + Date.now(), sender_type: "visitor", content: option.label, message_metadata: {} });
    var typingEl = this._showTyping();

    try {
      var data = await apiRequest("/" + AGENT_ID + "/message", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_token: this.sessionToken, message: option.label, quick_reply: option.value }),
      });
      this.conversationStatus = data.conversation_status;
      data.messages.forEach(this._renderMessage.bind(this));
    } catch (e) {
      this._renderError("Couldn't process that — please try again.");
    } finally {
      this._removeTyping(typingEl);
      Array.prototype.forEach.call(buttons, function (b) { b.disabled = false; });
    }
  };

  ChatWidget.prototype._startPolling = function (intervalMs) {
    this._stopPolling();
    var self = this;
    this.pollTimer = window.setInterval(function () {
      self._poll();
    }, intervalMs || POLL_INTERVAL_MS);
  };

  ChatWidget.prototype._stopPolling = function () {
    if (this.pollTimer) {
      window.clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
  };

  ChatWidget.prototype._poll = async function () {
    if (!this.sessionToken) return;
    try {
      var params = "session_token=" + encodeURIComponent(this.sessionToken);
      if (this.lastMessageId) params += "&after=" + encodeURIComponent(this.lastMessageId);
      var data = await apiRequest("/" + AGENT_ID + "/messages?" + params, { method: "GET" });
      this.conversationStatus = data.conversation_status;
      data.messages.forEach(this._renderMessage.bind(this));
    } catch (e) {
      // Silent — polling failures shouldn't interrupt the visitor's session.
    }
  };

  var widget = new ChatWidget();
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      widget.init();
    });
  } else {
    widget.init();
  }
})();
