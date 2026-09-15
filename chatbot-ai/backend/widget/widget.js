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

  // Small hand-drawn icon set for quick-reply cards (see _qrIconSvg below) —
  // no icon library dependency, consistent with the rest of this file.
  // Each entry is just the inner <path>/<circle> markup for a 24x24,
  // stroke-based (currentColor) icon.
  var _QR_ICONS = {
    cart: '<path d="M6 8h12l-1.5 9a2 2 0 0 1-2 1.7H9.5a2 2 0 0 1-2-1.7L6 8Z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/>',
    support: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 4v3M12 17v3M4 12h3M17 12h3"/>',
    chart: '<path d="M4 20V10M12 20V4M20 20v-7"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 4-6 8-6s8 2 8 6"/>',
    plug: '<path d="M9 3v4M15 3v4M7 7h10l-1 6a4 4 0 0 1-4 3.5 4 4 0 0 1-4-3.5L7 7Z"/><path d="M12 16.5V21"/>',
    code: '<path d="M8 8l-4 4 4 4M16 8l4 4-4 4"/>',
    search: '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.5-4.5"/>',
    tag: '<path d="M12 3h6a2 2 0 0 1 2 2v6l-9 9-8-8 9-9Z"/><circle cx="16" cy="8" r="1.4"/>',
    megaphone: '<path d="M3 10v4a1 1 0 0 0 1 1h2l5 4V5L6 9H4a1 1 0 0 0-1 1Z"/><path d="M15 9a3 3 0 0 1 0 6"/><path d="M18 6a7 7 0 0 1 0 12"/>',
    card: '<rect x="3" y="6" width="18" height="12" rx="2"/><path d="M3 10h18"/>',
    shield: '<path d="M12 3l7 3v6c0 5-3.5 7.5-7 9-3.5-1.5-7-4-7-9V6l7-3Z"/>',
    pin: '<path d="M12 21s7-6.5 7-11a7 7 0 1 0-14 0c0 4.5 7 11 7 11Z"/><circle cx="12" cy="10" r="2.5"/>',
    lock: '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    chat: '<path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5c-1.2 0-2.4-.3-3.4-.8L3 21l1.8-4.8A8.5 8.5 0 1 1 21 11.5Z"/>',
    back: '<path d="M19 12H5M11 6l-6 6 6 6"/>',
    sparkles: '<path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3Z"/><path d="M19 15l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7.7-2Z"/>',
    box: '<path d="M21 8l-9-5-9 5 9 5 9-5Z"/><path d="M3 8v8l9 5 9-5V8"/><path d="M12 13v8"/>',
    dots: '<circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/>',
    alert: '<path d="M12 3 2 20h20L12 3Z"/><path d="M12 10v4"/><circle cx="12" cy="17" r="0.6" fill="currentColor" stroke="none"/>',
  };

  // Maps a quick-reply option's opaque routing `value` to one of the icons
  // above by keyword, so every menu/leaf option gets something on-topic
  // without the backend having to carry icon choices in message_metadata.
  function _qrIconKey(value) {
    value = value || "";
    if (value === "menu_sales") return "cart";
    if (value === "menu_support") return "support";
    if (value === "menu_reporting" || value.indexOf("reporting") !== -1 || value.indexOf("traffic") !== -1) return "chart";
    if (value === "menu_human" || value.indexOf("human_reason_") === 0 || value.indexOf("account_login") !== -1) return "user";
    if (value === "continue_ai") return "sparkles";
    if (value.indexOf("back") !== -1) return "back";
    if (value.indexOf("smpp") !== -1 || value === "support_cat_connection") return "plug";
    if (value.indexOf("http_api") !== -1 || value === "sales_api") return "code";
    if (value.indexOf("hlr") !== -1) return "search";
    if (value.indexOf("sender_id") !== -1 || value === "support_cat_senderid") return "tag";
    if (value.indexOf("campaign") !== -1) return "megaphone";
    if (value.indexOf("billing") !== -1 || value.indexOf("balance") !== -1 || value === "support_cat_account") return "card";
    if (value.indexOf("ip_whitelist") !== -1 || value.indexOf("security") !== -1) return "shield";
    if (value.indexOf("routing") !== -1 || value.indexOf("destination") !== -1) return "pin";
    if (value.indexOf("otp") !== -1) return "lock";
    if (value.indexOf("failure") !== -1) return "alert";
    if (value.indexOf("country") !== -1) return "pin";
    if (value.indexOf("other") !== -1 || value.indexOf("integration") !== -1) return "dots";
    if (value.indexOf("msgid") !== -1 || value.indexOf("dlr") !== -1 || value.indexOf("delivery") !== -1) return "chat";
    if (value.indexOf("sales_") === 0) return "box";
    return "chat";
  }

  function _qrIconSvg(value) {
    var inner = _QR_ICONS[_qrIconKey(value)] || _QR_ICONS.chat;
    return (
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" ' +
      'stroke-linecap="round" stroke-linejoin="round">' + inner + "</svg>"
    );
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
      ".quick-replies { display: grid; grid-template-columns: repeat(auto-fill, minmax(122px, 1fr)); gap: 8px; margin-top: 8px; }" +
      ".qr-card { display: flex; flex-direction: column; align-items: flex-start; gap: 8px; padding: 11px; border-radius: 14px; border: 1.5px solid " +
      hexToRgba(c.primary_color, 0.28) +
      "; background: #fff; color: " +
      c.text_color +
      "; cursor: pointer; font-size: 0.86em; font-weight: 500; text-align: left; line-height: 1.25; transition: background 150ms ease, transform 150ms ease, opacity 150ms ease, border-color 150ms ease; }" +
      ".qr-card:hover:not(:disabled) { background: " +
      hexToRgba(c.primary_color, 0.06) +
      "; border-color: " +
      c.primary_color +
      "; transform: translateY(-1px); }" +
      ".qr-card:disabled { opacity: 0.5; cursor: default; transform: none; }" +
      ".qr-card-icon { width: 30px; height: 30px; border-radius: 9px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; background: " +
      hexToRgba(c.primary_color, 0.12) +
      "; color: " +
      c.primary_color +
      "; }" +
      ".qr-card-icon svg { width: 16px; height: 16px; }" +
      ".chat-chart { margin-top: 8px; padding: 10px 10px 6px; border-radius: 12px; background: rgba(0,0,0,0.03); color: " +
      c.text_color +
      "; }" +
      ".chat-chart-legend { display: flex; flex-wrap: wrap; margin-top: 2px; }" +
      ".stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(92px, 1fr)); gap: 8px; margin-top: 8px; }" +
      ".stat-tile { padding: 9px 11px; border-radius: 12px; background: rgba(0,0,0,0.03); border-left: 3px solid " +
      c.primary_color +
      "; }" +
      ".stat-tile-value { font-size: 1.05em; font-weight: 700; line-height: 1.25; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }" +
      ".stat-tile-label { font-size: 0.72em; opacity: 0.62; margin-top: 2px; text-transform: uppercase; letter-spacing: 0.03em; }" +
      ".stat-tile.tone-positive { border-left-color: #16a34a; }" +
      ".stat-tile.tone-negative { border-left-color: #dc2626; }" +
      ".progress-block { margin-top: 10px; }" +
      ".progress-header { display: flex; justify-content: space-between; font-size: 0.82em; font-weight: 600; margin-bottom: 4px; }" +
      ".progress-track { height: 8px; border-radius: 5px; background: rgba(0,0,0,0.08); overflow: hidden; }" +
      ".progress-fill { height: 100%; border-radius: 5px; background: #16a34a; transition: width 400ms ease; }" +
      ".progress-fill.tone-negative { background: #dc2626; }" +
      ".progress-sub { display: flex; flex-wrap: wrap; gap: 10px; font-size: 0.76em; opacity: 0.68; margin-top: 5px; }" +
      ".report-section-title { font-size: 0.78em; font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em; opacity: 0.6; margin: 10px 0 4px; }" +
      ".report-rows { display: flex; flex-direction: column; gap: 4px; }" +
      ".report-row { display: flex; align-items: baseline; gap: 6px; padding: 6px 9px; border-radius: 9px; background: rgba(0,0,0,0.03); font-size: 0.86em; }" +
      ".report-row-label { font-weight: 700; flex-shrink: 0; }" +
      ".report-row-detail { opacity: 0.72; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }" +
      ".report-header-title { font-size: 1em; font-weight: 700; margin-top: 2px; }" +
      ".report-header-period { font-size: 0.78em; opacity: 0.6; margin-top: 1px; }" +
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

  // Shared by the standard quick-reply menus (metadata.options) and the
  // report drill-down buttons (metadata.report_actions) — same icon-card
  // grid either way, just a different option list and a fresh click
  // handler bound per render.
  ChatWidget.prototype._buildQuickRepliesNode = function (options) {
    var self = this;
    var wrap = el("div", { class: "quick-replies" });
    options.forEach(function (opt) {
      var icon = el("span", { class: "qr-card-icon" });
      icon.innerHTML = _qrIconSvg(opt.value);
      var btn = el(
        "button",
        { class: "qr-card", onclick: function () { self._sendQuickReply(opt, wrap); } },
        [icon, opt.label]
      );
      wrap.appendChild(btn);
    });
    return wrap;
  };

  // Compact labeled rows for a report's Peak Traffic / Low Activity /
  // breakdown sections — `rows` items are {date, primary, secondary}
  // (peak/low) or {label/date, primary, secondary} (breakdown), all
  // computed server-side from real data (see smsc_ai_service.py).
  ChatWidget.prototype._appendReportRows = function (col, title, rows) {
    if (!Array.isArray(rows) || !rows.length) return;
    col.appendChild(el("div", { class: "report-section-title" }, [title]));
    var list = el("div", { class: "report-rows" });
    rows.forEach(function (r) {
      var detail = [r.primary, r.secondary].filter(Boolean).join(" · ");
      list.appendChild(
        el("div", { class: "report-row" }, [
          el("span", { class: "report-row-label" }, [String(r.date || "")]),
          el("span", { class: "report-row-detail" }, [detail]),
        ])
      );
    });
    col.appendChild(list);
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

    // Dashboard-style report content (see smsc_ai_service._build_report_
    // extras/_build_breakdown_rows on the backend — every number here came
    // from a real tool call, never from the model's own text) renders in a
    // fixed top-to-bottom order: metric cards, delivery-rate progress,
    // trend chart, peak/low-activity rows, breakdown rows, then the
    // contextual drill-down buttons — with the generic Sales/Support/Live-
    // Agent follow-up options always last, so a report reads data-first.
    if (metadata.header && (metadata.header.title || metadata.header.period)) {
      if (metadata.header.title) {
        col.appendChild(el("div", { class: "report-header-title" }, ["📊 " + metadata.header.title]));
      }
      if (metadata.header.period) {
        col.appendChild(el("div", { class: "report-header-period" }, [metadata.header.period]));
      }
    }

    if (Array.isArray(metadata.stats) && metadata.stats.length) {
      var statGrid = el("div", { class: "stat-grid" });
      metadata.stats.forEach(function (stat) {
        var tone = ["positive", "negative", "neutral"].indexOf(stat.tone) !== -1 ? stat.tone : "neutral";
        statGrid.appendChild(
          el("div", { class: "stat-tile tone-" + tone }, [
            el("div", { class: "stat-tile-value" }, [String(stat.value)]),
            el("div", { class: "stat-tile-label" }, [stat.label]),
          ])
        );
      });
      col.appendChild(statGrid);
    }

    if (metadata.progress && typeof metadata.progress.percent === "number") {
      var pct = Math.max(0, Math.min(100, metadata.progress.percent));
      var fillTone = pct >= 90 ? "" : " tone-negative";
      var progressBlock = el("div", { class: "progress-block" }, [
        el("div", { class: "progress-header" }, [
          el("span", {}, ["Delivered"]),
          el("span", {}, [pct + "%"]),
        ]),
        el("div", { class: "progress-track" }, [
          el("div", { class: "progress-fill" + fillTone, style: { width: pct + "%" } }),
        ]),
      ]);
      if (Array.isArray(metadata.progress.sub) && metadata.progress.sub.length) {
        var subRow = el("div", { class: "progress-sub" });
        metadata.progress.sub.forEach(function (s) {
          subRow.appendChild(el("span", {}, [s.label + ": " + (s.percent != null ? s.percent + "%" : "—")]));
        });
        progressBlock.appendChild(subRow);
      }
      col.appendChild(progressBlock);
    }

    if (metadata.chart) {
      var chartNode = this._buildChartNode(metadata.chart);
      if (chartNode) col.appendChild(chartNode);
    }

    this._appendReportRows(col, "🔥 Peak Traffic", metadata.peak);
    this._appendReportRows(col, "📉 Low Activity", metadata.low);
    if (metadata.breakdown && Array.isArray(metadata.breakdown.rows) && metadata.breakdown.rows.length) {
      this._appendReportRows(col, metadata.breakdown.title, metadata.breakdown.rows);
    }

    if (Array.isArray(metadata.report_actions) && metadata.report_actions.length) {
      col.appendChild(this._buildQuickRepliesNode(metadata.report_actions));
    }

    if (Array.isArray(metadata.options)) {
      col.appendChild(this._buildQuickRepliesNode(metadata.options));
    }

    if (!this.isOpen && !isVisitor && !isLocalEcho) {
      this._addUnread();
    }

    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
  };

  // Renders a small inline SVG line chart from the backend's structured
  // chart metadata (see smsc_ai_service._build_chart on the Python side —
  // it only ever exists when a tool call returned real day-by-day data).
  // No chart library dependency: this widget is a single vanilla-JS file
  // with no bundler, so pulling in a charting library just for this would
  // be a much bigger change than the two-series line chart it needs to
  // draw.
  ChatWidget.prototype._buildChartNode = function (chart) {
    if (!chart || chart.type !== "line") return null;
    var labels = Array.isArray(chart.labels) ? chart.labels : [];
    var series = Array.isArray(chart.series) ? chart.series : [];
    var n = labels.length;
    if (n < 2 || !series.length) return null;

    var W = 300, H = 150, padL = 8, padR = 8, padT = 22, padB = 20;
    var plotW = W - padL - padR;
    var plotH = H - padT - padB;
    var colors = ["#2563eb", "#16a34a", "#dc2626", "#9333ea"];

    var max = 0;
    series.forEach(function (s) {
      (s.values || []).forEach(function (v) {
        if (typeof v === "number" && v > max) max = v;
      });
    });
    if (max <= 0) max = 1;

    function xAt(i) { return padL + (plotW * i) / (n - 1); }
    function yAt(v) { return padT + plotH - (plotH * (typeof v === "number" ? v : 0)) / max; }

    var svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" style="width:100%;height:auto;display:block" role="img" aria-label="' +
      escapeHtml(chart.title || "Chart") + '">';
    svg += '<text x="' + padL + '" y="13" font-size="11" font-weight="600" fill="currentColor">' +
      escapeHtml(chart.title || "") + "</text>";
    svg += '<line x1="' + padL + '" y1="' + (padT + plotH) + '" x2="' + (padL + plotW) + '" y2="' + (padT + plotH) +
      '" stroke="currentColor" stroke-opacity="0.15" />';

    series.forEach(function (s, si) {
      var color = colors[si % colors.length];
      var values = s.values || [];
      var pts = values.map(function (v, i) { return xAt(i).toFixed(1) + "," + yAt(v).toFixed(1); }).join(" ");
      svg += '<polyline points="' + pts + '" fill="none" stroke="' + color +
        '" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />';
      values.forEach(function (v, i) {
        svg += '<circle cx="' + xAt(i).toFixed(1) + '" cy="' + yAt(v).toFixed(1) + '" r="2.5" fill="' + color + '" />';
      });
    });

    svg += '<text x="' + padL + '" y="' + (H - 4) + '" font-size="9" fill="currentColor" fill-opacity="0.6">' +
      escapeHtml(labels[0] || "") + "</text>";
    svg += '<text x="' + (padL + plotW) + '" y="' + (H - 4) +
      '" font-size="9" fill="currentColor" fill-opacity="0.6" text-anchor="end">' +
      escapeHtml(labels[n - 1] || "") + "</text>";
    svg += "</svg>";

    var legend = series
      .map(function (s, si) {
        var color = colors[si % colors.length];
        return (
          '<span style="display:inline-flex;align-items:center;gap:4px;margin:2px 10px 0 0;font-size:11px;opacity:0.85">' +
          '<span style="width:8px;height:8px;border-radius:50%;background:' + color + ';display:inline-block"></span>' +
          escapeHtml(s.name || "") +
          "</span>"
        );
      })
      .join("");

    var wrap = el("div", { class: "chat-chart" });
    wrap.innerHTML = svg + '<div class="chat-chart-legend">' + legend + "</div>";
    return wrap;
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
      var self = this;
      data.messages.forEach(function (message) {
        // The visitor's own messages are never included in a send's
        // response (see conversation_service.handle_visitor_message on the
        // backend — reply_messages is AI/system only) because they're
        // already on screen via the local echo rendered at send time (see
        // _sendCurrentInput/_sendQuickReply). But this poll endpoint fetches
        // full history after a cursor with no such exclusion, so without
        // this it re-renders the visitor's own message a second time,
        // under its real id, once it shows up here — advance the cursor
        // past it without rendering.
        if (message.sender_type === "visitor") {
          self.lastMessageId = message.id;
          return;
        }
        self._renderMessage(message);
      });
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
