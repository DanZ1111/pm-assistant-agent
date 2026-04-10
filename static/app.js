(function () {
  var JWT_KEY = "pm_jwt_token";
  var SESSION_KEY = "pm_session_id";

  var token = localStorage.getItem(JWT_KEY);

  // Session ID — persists in localStorage so conversation continues across refreshes
  var sessionId = localStorage.getItem(SESSION_KEY);
  if (!sessionId) {
    sessionId = "sess_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
    localStorage.setItem(SESSION_KEY, sessionId);
  }

  var loginScreen = document.getElementById("loginScreen");
  var appShell = document.getElementById("appShell");
  var chatWindow = document.getElementById("chatWindow");
  var input = document.getElementById("messageInput");
  var sendButton = document.getElementById("sendButton");

  function getAuthHeader() {
    return {
      "Authorization": "Bearer " + token,
      "Content-Type": "application/json",
    };
  }

  function showLogin() {
    loginScreen.style.display = "flex";
    appShell.style.display = "none";
  }

  function showApp() {
    loginScreen.style.display = "none";
    appShell.style.display = "flex";
  }

  function handleUnauthorized() {
    localStorage.removeItem(JWT_KEY);
    token = null;
    showLogin();
  }

  // Auth: login or register
  function doAuth(endpoint) {
    var username = document.getElementById("loginUsername").value.trim();
    var password = document.getElementById("loginPassword").value;
    document.getElementById("loginError").textContent = "";

    if (!username || !password) {
      document.getElementById("loginError").textContent = "Username and password are required.";
      return;
    }

    fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: username, password: password }),
    })
      .then(function (r) {
        if (!r.ok) return r.json().then(function (e) { throw new Error(e.detail || "Failed"); });
        return r.json();
      })
      .then(function (data) {
        token = data.access_token;
        localStorage.setItem(JWT_KEY, token);
        showApp();
        initChat();
      })
      .catch(function (err) {
        document.getElementById("loginError").textContent = err.message;
      });
  }

  document.getElementById("loginBtn").addEventListener("click", function () {
    doAuth("/api/auth/login");
  });
  document.getElementById("registerBtn").addEventListener("click", function () {
    doAuth("/api/auth/register");
  });
  document.getElementById("loginPassword").addEventListener("keydown", function (e) {
    if (e.key === "Enter") doAuth("/api/auth/login");
  });

  document.getElementById("logoutBtn").addEventListener("click", function () {
    localStorage.removeItem(JWT_KEY);
    token = null;
    // Clear chat window for next user
    chatWindow.innerHTML = "";
    showLogin();
  });

  // Chat init — called after successful auth or on page load with existing token
  function initChat() {
    chatWindow.innerHTML = "";

    fetch("/api/history?session_id=" + encodeURIComponent(sessionId), {
      headers: getAuthHeader(),
    })
      .then(function (r) {
        if (r.status === 401) { handleUnauthorized(); throw new Error("Unauthorized"); }
        return r.json();
      })
      .then(function (data) {
        if (data.messages && data.messages.length > 0) {
          data.messages.forEach(function (m) {
            addMessage(m.content, m.role);
          });
        } else {
          addMessage(
            "Good to see you. Tell me what's going on — a new project, an update on something, or just talk and I'll figure it out.",
            "assistant"
          );
        }
      })
      .catch(function (err) {
        if (err.message !== "Unauthorized") {
          addMessage(
            "Good to see you. Tell me what's going on — a new project, an update on something, or just talk and I'll figure it out.",
            "assistant"
          );
        }
      });
  }

  // Auto-resize textarea up to max-height
  input.addEventListener("input", function () {
    this.style.height = "auto";
    this.style.height = Math.min(this.scrollHeight, 120) + "px";
  });

  // Enter sends, Shift+Enter adds newline
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  });

  sendButton.addEventListener("click", send);

  function send() {
    var text = input.value.trim();
    if (!text || sendButton.disabled) return;

    addMessage(text, "user");
    input.value = "";
    input.style.height = "auto";
    setLoading(true);

    fetch("/api/chat", {
      method: "POST",
      headers: getAuthHeader(),
      body: JSON.stringify({ message: text, session_id: sessionId }),
    })
      .then(function (r) {
        if (r.status === 401) { handleUnauthorized(); throw new Error("Unauthorized"); }
        if (!r.ok) {
          return r.json().then(function (e) {
            throw new Error(e.detail || "Request failed");
          });
        }
        return r.json();
      })
      .then(function (data) {
        setLoading(false);
        addMessage(data.response, "assistant");
      })
      .catch(function (err) {
        setLoading(false);
        if (err.message !== "Unauthorized") {
          addMessage(
            "Something went wrong: " + err.message + ". Please try again.",
            "assistant"
          );
        }
      });
  }

  function addMessage(text, role) {
    var div = document.createElement("div");
    div.className = "message " + role;

    var bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.innerHTML = role === "assistant" ? formatAssistant(text) : escapeHtml(text);

    div.appendChild(bubble);
    chatWindow.appendChild(div);
    chatWindow.scrollTop = chatWindow.scrollHeight;
  }

  function escapeHtml(text) {
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatAssistant(text) {
    var t = escapeHtml(text);

    // Bold: **text**
    t = t.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");

    // Unordered list: lines starting with "- " or "• "
    t = t.replace(/((?:^|\n)[•\-] .+)+/g, function (block) {
      var items = block
        .trim()
        .split("\n")
        .map(function (line) {
          return "<li>" + line.replace(/^[•\-]\s+/, "") + "</li>";
        })
        .join("");
      return "<ul>" + items + "</ul>";
    });

    // Line breaks (after list handling so <ul> stays intact)
    t = t.replace(/\n/g, "<br>");

    return t;
  }

  function setLoading(loading) {
    sendButton.disabled = loading;
    input.disabled = loading;

    var existing = document.getElementById("typingIndicator");
    if (loading && !existing) {
      var div = document.createElement("div");
      div.className = "message assistant typing-indicator";
      div.id = "typingIndicator";
      div.innerHTML = "<div class='bubble'>Thinking\u2026</div>";
      chatWindow.appendChild(div);
      chatWindow.scrollTop = chatWindow.scrollHeight;
    } else if (!loading && existing) {
      existing.remove();
    }

    if (!loading) {
      input.focus();
    }
  }

  // On page load: check for existing token
  if (token) {
    showApp();
    initChat();
  } else {
    showLogin();
  }
})();
