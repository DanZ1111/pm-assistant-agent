(function () {

  // =========================================================
  // Card / Table view toggle
  // =========================================================
  var cardView  = document.getElementById('cardView');
  var tableView = document.getElementById('tableView');
  var cardBtn   = document.getElementById('cardViewBtn');
  var tableBtn  = document.getElementById('tableViewBtn');

  window.setView = function (mode, silent) {
    if (!cardView || !tableView) return;
    if (mode === 'table') {
      cardView.classList.add('d-none');
      tableView.classList.remove('d-none');
      if (cardBtn)  cardBtn.classList.remove('active');
      if (tableBtn) tableBtn.classList.add('active');
    } else {
      tableView.classList.add('d-none');
      cardView.classList.remove('d-none');
      if (cardBtn)  cardBtn.classList.add('active');
      if (tableBtn) tableBtn.classList.remove('active');
    }
    if (!silent) localStorage.setItem('pm_view', mode);
  };

  var savedView = localStorage.getItem('pm_view') || 'card';
  setView(savedView, true);

  // =========================================================
  // File gallery — image index for lightbox
  // =========================================================
  var galleryImages = [];
  var currentLightboxIndex = 0;

  function buildGalleryIndex() {
    galleryImages = [];
    document.querySelectorAll('.gallery-img').forEach(function (img) {
      galleryImages.push({
        src:  img.getAttribute('data-full') || img.src,
        name: img.getAttribute('data-name') || '',
      });
    });
  }
  buildGalleryIndex();

  // =========================================================
  // Lightbox
  // =========================================================
  window.openLightbox = function (index) {
    if (galleryImages.length === 0) buildGalleryIndex();
    currentLightboxIndex = index;
    _showLightboxAt(index);
    document.getElementById('lightbox').style.display = 'flex';
    document.body.style.overflow = 'hidden';
  };

  function _showLightboxAt(index) {
    var lb    = document.getElementById('lightbox');
    var img   = document.getElementById('lightboxImg');
    var cap   = document.getElementById('lightboxCaption');
    var prev  = document.getElementById('lightboxPrev');
    var next  = document.getElementById('lightboxNext');

    if (!lb || !img || galleryImages.length === 0) return;

    img.src = galleryImages[index].src;
    if (cap)  cap.textContent = galleryImages[index].name;

    var multiple = galleryImages.length > 1;
    if (prev) prev.style.display = multiple ? 'flex' : 'none';
    if (next) next.style.display = multiple ? 'flex' : 'none';
  }

  window.lightboxNav = function (dir) {
    currentLightboxIndex = (currentLightboxIndex + dir + galleryImages.length) % galleryImages.length;
    _showLightboxAt(currentLightboxIndex);
  };

  window.closeLightbox = function () {
    var lb = document.getElementById('lightbox');
    if (!lb) return;
    lb.style.display = 'none';
    document.body.style.overflow = '';
  };

  document.addEventListener('keydown', function (e) {
    var lb = document.getElementById('lightbox');
    if (!lb || lb.style.display === 'none') return;
    if (e.key === 'Escape')      closeLightbox();
    if (e.key === 'ArrowLeft')   lightboxNav(-1);
    if (e.key === 'ArrowRight')  lightboxNav(1);
  });

  // =========================================================
  // File category filter
  // =========================================================
  window.filterFiles = function (category) {
    document.querySelectorAll('.file-item').forEach(function (item) {
      var match = category === 'all' || item.getAttribute('data-category') === category;
      item.classList.toggle('d-none', !match);
    });
    document.querySelectorAll('.file-filter-btn').forEach(function (btn) {
      btn.classList.toggle('active', btn.getAttribute('data-cat') === category);
    });
  };

  // =========================================================
  // File upload — drag-drop + preview
  // =========================================================
  var dropArea    = document.getElementById('uploadDropArea');
  var fileInput   = document.getElementById('fileInput');
  var preview     = document.getElementById('fileNamePreview');
  var submitBtn   = document.getElementById('uploadSubmitBtn');

  function setFile(file) {
    if (!file) return;
    if (preview) preview.textContent = file.name;
    if (submitBtn) submitBtn.disabled = false;
  }

  if (dropArea && fileInput) {
    dropArea.addEventListener('click', function () { fileInput.click(); });

    dropArea.addEventListener('dragover', function (e) {
      e.preventDefault();
      dropArea.classList.add('drag-over');
    });
    dropArea.addEventListener('dragleave', function () {
      dropArea.classList.remove('drag-over');
    });
    dropArea.addEventListener('drop', function (e) {
      e.preventDefault();
      dropArea.classList.remove('drag-over');
      var files = e.dataTransfer.files;
      if (files.length > 0) {
        // Assign dropped file to input via DataTransfer
        var dt = new DataTransfer();
        dt.items.add(files[0]);
        fileInput.files = dt.files;
        setFile(files[0]);
      }
    });

    fileInput.addEventListener('change', function () {
      if (fileInput.files.length > 0) setFile(fileInput.files[0]);
    });
  }

  // =========================================================
  // Phase add toggle
  // =========================================================
  window.toggleAddPhase = function () {
    var form = document.getElementById('addPhaseForm');
    var btn  = document.getElementById('addPhaseToggle');
    if (!form) return;
    if (form.classList.contains('d-none')) {
      form.classList.remove('d-none');
      btn.style.display = 'none';
      var nameInput = form.querySelector('input[name="phase_name"]');
      if (nameInput) nameInput.focus();
    } else {
      form.classList.add('d-none');
      btn.style.display = '';
    }
  };

})();


// ========================================================================
// Build 21 — Bottom AI Chat + Right-Side Panel
// ========================================================================
(function () {
  var bar = document.getElementById('bottomChatBar');
  if (!bar) return;  // anonymous page, no chat

  document.body.classList.add('has-bottom-chat');

  var form        = document.getElementById('bottomChatForm');
  var textarea    = document.getElementById('chatInputTextarea');
  var submitBtn   = document.getElementById('chatSubmitBtn');
  var modeSelect  = document.getElementById('chatModeSelect');
  var scopeSelect = document.getElementById('chatScopeSelect');  // may be null
  var panel       = document.getElementById('aiSidePanel');
  var msgList     = document.getElementById('aiPanelMessages');
  var titleEl     = document.getElementById('aiPanelTitle');
  var historySel  = document.getElementById('conversationHistorySelect');
  var archiveBtn  = document.getElementById('aiPanelArchiveBtn');
  var closeBtn    = document.getElementById('aiPanelCloseBtn');

  var projectIdAttr = bar.getAttribute('data-project-id') || '';
  var defaultProjectId = projectIdAttr ? parseInt(projectIdAttr, 10) : null;
  var currentConversationId = null;

  // ── Textarea auto-grow + submit-button gate ──
  function resizeTextarea() {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
  }
  textarea.addEventListener('input', function () {
    resizeTextarea();
    submitBtn.disabled = !textarea.value.trim();
  });
  textarea.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!submitBtn.disabled) form.requestSubmit();
    }
  });

  // ── Panel open/close ──
  function openPanel() {
    panel.classList.add('open');
    panel.setAttribute('aria-hidden', 'false');
  }
  function closePanel() {
    panel.classList.remove('open');
    panel.setAttribute('aria-hidden', 'true');
  }
  closeBtn.addEventListener('click', closePanel);

  // ── Message rendering ──
  function renderUserMessage(text) {
    var d = document.createElement('div');
    d.className = 'chat-msg chat-msg-user';
    d.textContent = text;
    msgList.appendChild(d);
    msgList.scrollTop = msgList.scrollHeight;
  }
  function renderAssistantMessage(text) {
    var d = document.createElement('div');
    d.className = 'chat-msg chat-msg-assistant';
    d.textContent = text;
    msgList.appendChild(d);
    msgList.scrollTop = msgList.scrollHeight;
  }
  function renderToolCallCard(tc) {
    var ok = tc.result && tc.result.ok;
    var d = document.createElement('div');
    d.className = 'chat-tool-call-card ' + (ok ? 'ok' : 'err');
    var name = document.createElement('div');
    name.className = 'chat-tool-call-card-name';
    name.textContent = (ok ? '✓ ' : '⚠ ') + tc.name;
    d.appendChild(name);
    var result = document.createElement('div');
    result.className = 'chat-tool-call-card-result';
    if (ok) {
      result.textContent = 'Success' + (tc.result.entry_id ? ' (id ' + tc.result.entry_id + ')' : '');
    } else {
      result.textContent = (tc.result && tc.result.error) || 'unknown error';
    }
    d.appendChild(result);
    msgList.appendChild(d);
    msgList.scrollTop = msgList.scrollHeight;
  }

  // ── Submit ──
  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    var text = textarea.value.trim();
    if (!text) return;
    var mode = modeSelect.value;
    var sendProjectId = defaultProjectId;
    if (scopeSelect && scopeSelect.value === 'global') sendProjectId = null;

    openPanel();
    renderUserMessage(text);
    textarea.value = '';
    resizeTextarea();
    submitBtn.disabled = true;

    try {
      var body = {message: text, mode: mode, conversation_id: currentConversationId};
      if (sendProjectId) body.project_id = sendProjectId;
      var res = await fetch('/ai/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body),
      });
      var data = await res.json();
      if (!data.ok && data.error === 'question_blocked_by_permission_guard') {
        renderAssistantMessage(data.message || "I can't answer that based on your access level.");
        return;
      }
      if (!data.ok) {
        renderAssistantMessage('(Error: ' + (data.error || 'unknown') + ')');
        return;
      }
      currentConversationId = data.conversation_id;
      renderAssistantMessage(data.assistant_message || '(no response)');
      (data.tool_calls || []).forEach(renderToolCallCard);
      refreshHistory();
    } catch (err) {
      renderAssistantMessage('(Request failed: ' + err.message + ')');
    }
  });

  // ── Conversation history dropdown ──
  async function refreshHistory() {
    try {
      var res = await fetch('/ai/conversations');
      var data = await res.json();
      if (!data.ok) return;
      historySel.innerHTML = '<option value="">— history —</option>';
      data.conversations.forEach(function (c) {
        var opt = document.createElement('option');
        opt.value = c.id;
        opt.textContent = (c.title || '(untitled)') + (c.project_name ? ' · ' + c.project_name : '');
        if (c.id === currentConversationId) {
          opt.selected = true;
          titleEl.textContent = c.title || 'AI Chat';
        }
        historySel.appendChild(opt);
      });
    } catch (_) { /* ignore */ }
  }
  historySel.addEventListener('change', async function () {
    var id = parseInt(historySel.value, 10);
    if (!id) return;
    try {
      var res = await fetch('/ai/chat/' + id);
      var data = await res.json();
      if (!data.ok) return;
      currentConversationId = id;
      titleEl.textContent = data.conversation.title || 'AI Chat';
      msgList.innerHTML = '';
      data.messages.forEach(function (m) {
        if (m.role === 'user') renderUserMessage(m.message);
        else if (m.role === 'assistant') {
          renderAssistantMessage(m.message);
          var tcs = (m.metadata && m.metadata.tool_calls) || [];
          tcs.forEach(renderToolCallCard);
        }
      });
      openPanel();
    } catch (_) { /* ignore */ }
  });

  // ── Archive button ──
  archiveBtn.addEventListener('click', async function () {
    if (!currentConversationId) return;
    if (!confirm('Archive this conversation? It will disappear from the history dropdown.')) return;
    try {
      await fetch('/ai/conversations/' + currentConversationId + '/archive', {method: 'POST'});
      currentConversationId = null;
      msgList.innerHTML = '';
      titleEl.textContent = 'AI Chat';
      refreshHistory();
      closePanel();
    } catch (_) { /* ignore */ }
  });

  // Initial history fetch (so the dropdown is populated on page load).
  refreshHistory();
})();
