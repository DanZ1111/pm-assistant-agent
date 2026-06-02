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
// Build 26 — Compact dock + resizable assistant workspace
// ========================================================================
(function () {
  var bar = document.getElementById('bottomChatBar');
  if (!bar) return;

  document.body.classList.add('has-bottom-chat');

  var dockForm = document.getElementById('bottomChatForm');
  var dockInput = document.getElementById('chatInputTextarea');
  var dockSubmit = document.getElementById('chatSubmitBtn');
  var panel = document.getElementById('aiSidePanel');
  var panelForm = document.getElementById('panelChatForm');
  var panelInput = document.getElementById('panelChatInput');
  var panelSubmit = document.getElementById('panelChatSubmit');
  var resizeHandle = document.getElementById('aiPanelResizeHandle');
  var msgList = document.getElementById('aiPanelMessages');
  var titleEl = document.getElementById('aiPanelTitle');
  var contextEl = document.getElementById('aiPanelContext');
  var historySel = document.getElementById('conversationHistorySelect');
  var archiveBtn = document.getElementById('aiPanelArchiveBtn');
  var closeBtn = document.getElementById('aiPanelCloseBtn');
  var defaultTitle = bar.dataset.defaultTitle || 'AI Chat';
  var historyLabel = bar.dataset.historyLabel || 'history';
  var defaultProjectId = parseInt(bar.dataset.projectId || '', 10) || null;
  var defaultProjectName = bar.dataset.projectName || '';
  var currentConversationId = null;
  var currentConversationProjectId = defaultProjectId;
  var currentConversationProjectName = defaultProjectName;
  var activeMode = 'intake';
  var activeScope = defaultProjectId ? 'project' : 'global';

  function bindTextarea(input, submit, form) {
    function resize() {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 120) + 'px';
    }
    input.addEventListener('input', function () {
      resize();
      submit.disabled = !input.value.trim();
    });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (!submit.disabled) form.requestSubmit();
      }
    });
    return resize;
  }

  var resizeDock = bindTextarea(dockInput, dockSubmit, dockForm);
  var resizePanel = bindTextarea(panelInput, panelSubmit, panelForm);

  function setSegment(kind, value) {
    document.querySelectorAll('[data-chat-' + kind + ']').forEach(function (btn) {
      btn.classList.toggle('active', btn.getAttribute('data-chat-' + kind) === value);
    });
  }

  document.querySelectorAll('[data-chat-mode]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      activeMode = btn.dataset.chatMode;
      setSegment('mode', activeMode);
    });
  });

  document.querySelectorAll('[data-chat-scope]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var nextScope = btn.dataset.chatScope;
      if (nextScope === activeScope) return;
      if (currentConversationId && !confirm(bar.dataset.confirmScopeSwitch)) return;
      if (currentConversationId) {
        currentConversationId = null;
        msgList.innerHTML = '';
        titleEl.textContent = defaultTitle;
      }
      activeScope = nextScope;
      currentConversationProjectId = activeScope === 'project' ? defaultProjectId : null;
      currentConversationProjectName = activeScope === 'project' ? defaultProjectName : '';
      setSegment('scope', activeScope);
      updateContext();
    });
  });

  function updateContext() {
    if (!contextEl) return;
    if (currentConversationProjectId) {
      contextEl.innerHTML = '<i class="bi bi-folder2"></i> ' +
        (contextEl.dataset.inProject || 'In project:') + ' <strong></strong>';
      contextEl.querySelector('strong').textContent = currentConversationProjectName || ('#' + currentConversationProjectId);
    } else {
      contextEl.innerHTML = '<i class="bi bi-globe2"></i> ' + (contextEl.dataset.globalLabel || 'Global');
    }
  }

  function openPanel() {
    panel.classList.add('open');
    panel.setAttribute('aria-hidden', 'false');
    document.body.classList.add('assistant-open');
    window.setTimeout(function () { panelInput.focus(); }, 180);
  }

  function closePanel() {
    panel.classList.remove('open');
    panel.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('assistant-open');
  }
  closeBtn.addEventListener('click', closePanel);

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

  function addActionButton(actions, label, className, onClick) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn-sm ' + className;
    btn.textContent = label;
    btn.addEventListener('click', onClick);
    actions.appendChild(btn);
  }

  async function resolveProposal(card, proposalId, action) {
    var res = await fetch('/ai/chat/' + currentConversationId + '/proposals/' + proposalId + '/confirm', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({action: action || 'confirm'}),
    });
    var data = await res.json();
    var result = card.querySelector('.chat-tool-call-card-result');
    if (data.ok) {
      card.className = 'chat-tool-call-card ok';
      result.textContent = data.message || 'Saved.';
      var actions = card.querySelector('.chat-tool-call-card-actions');
      if (actions) actions.remove();
    } else {
      result.textContent = data.message || data.error || 'Unable to save.';
    }
  }

  function renderToolCallCard(tc) {
    var outcome = tc.result || {};
    var pending = outcome.error === 'confirmation_required';
    var ok = outcome.ok;
    var d = document.createElement('div');
    d.className = 'chat-tool-call-card ' + (pending ? '' : (ok ? 'ok' : 'err'));
    var name = document.createElement('div');
    name.className = 'chat-tool-call-card-name';
    name.textContent = (pending ? 'Review: ' : (ok ? 'Saved: ' : 'Unable to run: ')) + tc.name;
    d.appendChild(name);
    var result = document.createElement('div');
    result.className = 'chat-tool-call-card-result';
    if (pending) {
      result.textContent = outcome.summary || bar.dataset.confirmAction || 'Confirm this action?';
    } else if (ok) {
      result.textContent = outcome.message || 'Success';
    } else {
      result.textContent = outcome.message || outcome.error || 'unknown error';
    }
    d.appendChild(result);

    if (pending && outcome.proposal_id) {
      var actions = document.createElement('div');
      actions.className = 'chat-tool-call-card-actions';
      if (outcome.duplicate) {
        addActionButton(actions, bar.dataset.linkExisting || 'Link existing', 'btn-primary', function () {
          resolveProposal(d, outcome.proposal_id, 'link_existing');
        });
        addActionButton(actions, bar.dataset.createNewAnyway || 'Create new anyway', 'btn-outline-secondary', function () {
          resolveProposal(d, outcome.proposal_id, 'create_new');
        });
      } else {
        addActionButton(actions, bar.dataset.confirmAction || 'Confirm', 'btn-primary', function () {
          resolveProposal(d, outcome.proposal_id, 'confirm');
        });
      }
      addActionButton(actions, bar.dataset.cancel || 'Cancel', 'btn-outline-secondary', async function () {
        await fetch('/ai/chat/' + currentConversationId + '/proposals/' + outcome.proposal_id + '/cancel', {method: 'POST'});
        d.className = 'chat-tool-call-card err';
        result.textContent = bar.dataset.cancel || 'Cancelled';
        actions.remove();
      });
      d.appendChild(actions);
    }
    msgList.appendChild(d);
    msgList.scrollTop = msgList.scrollHeight;
  }

  async function submitMessage(input, submit, resize) {
    var text = input.value.trim();
    if (!text) return;
    var sendProjectId = activeScope === 'project' ? (currentConversationProjectId || defaultProjectId) : null;
    openPanel();
    renderUserMessage(text);
    input.value = '';
    resize();
    submit.disabled = true;

    try {
      var body = {
        message: text,
        mode: activeMode,
        scope: activeScope,
        conversation_id: currentConversationId,
      };
      if (sendProjectId) body.project_id = sendProjectId;
      var res = await fetch('/ai/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body),
      });
      var data = await res.json();
      if (!data.ok) {
        renderAssistantMessage(data.message || ('Error: ' + (data.error || 'unknown')));
        return;
      }
      currentConversationId = data.conversation_id;
      currentConversationProjectId = data.project_id || null;
      currentConversationProjectName = data.project_name || '';
      updateContext();
      renderAssistantMessage(data.assistant_message || '(no response)');
      (data.tool_calls || []).forEach(renderToolCallCard);
      refreshHistory();
    } catch (err) {
      renderAssistantMessage('Request failed: ' + err.message);
    }
  }

  dockForm.addEventListener('submit', function (e) {
    e.preventDefault();
    submitMessage(dockInput, dockSubmit, resizeDock);
  });
  panelForm.addEventListener('submit', function (e) {
    e.preventDefault();
    submitMessage(panelInput, panelSubmit, resizePanel);
  });

  async function refreshHistory() {
    try {
      var res = await fetch('/ai/conversations');
      var data = await res.json();
      if (!data.ok) return;
      historySel.innerHTML = '<option value="">— ' + historyLabel + ' —</option>';
      data.conversations.forEach(function (c) {
        var opt = document.createElement('option');
        opt.value = c.id;
        opt.textContent = (c.title || '(untitled)') + (c.project_name ? ' · ' + c.project_name : '');
        if (c.id === currentConversationId) {
          opt.selected = true;
          titleEl.textContent = c.title || defaultTitle;
        }
        historySel.appendChild(opt);
      });
    } catch (_) { /* history is non-critical */ }
  }

  historySel.addEventListener('change', async function () {
    var id = parseInt(historySel.value, 10);
    if (!id) return;
    try {
      var res = await fetch('/ai/chat/' + id);
      var data = await res.json();
      if (!data.ok) return;
      currentConversationId = id;
      currentConversationProjectId = data.conversation.project_id || null;
      currentConversationProjectName = data.conversation.project_name || '';
      activeScope = currentConversationProjectId ? 'project' : 'global';
      setSegment('scope', activeScope);
      updateContext();
      titleEl.textContent = data.conversation.title || defaultTitle;
      msgList.innerHTML = '';
      data.messages.forEach(function (m) {
        if (m.role === 'user') renderUserMessage(m.message);
        else if (m.role === 'assistant') {
          renderAssistantMessage(m.message);
          ((m.metadata && m.metadata.tool_calls) || []).forEach(renderToolCallCard);
        }
      });
      openPanel();
    } catch (_) { /* history is non-critical */ }
  });

  archiveBtn.addEventListener('click', async function () {
    if (!currentConversationId) return;
    if (!confirm(bar.dataset.confirmArchive)) return;
    try {
      await fetch('/ai/conversations/' + currentConversationId + '/archive', {method: 'POST'});
      currentConversationId = null;
      currentConversationProjectId = defaultProjectId;
      currentConversationProjectName = defaultProjectName;
      msgList.innerHTML = '';
      titleEl.textContent = defaultTitle;
      refreshHistory();
      closePanel();
    } catch (_) { /* archive is non-critical */ }
  });

  var savedWidth = parseInt(localStorage.getItem('pm_assistant_width') || '', 10);
  function setPanelWidth(width) {
    var max = Math.min(680, window.innerWidth * 0.5);
    var next = Math.max(360, Math.min(width, max));
    document.documentElement.style.setProperty('--assistant-panel-width', next + 'px');
    localStorage.setItem('pm_assistant_width', String(next));
  }
  if (savedWidth && window.innerWidth > 760) setPanelWidth(savedWidth);
  resizeHandle.addEventListener('pointerdown', function (e) {
    e.preventDefault();
    resizeHandle.setPointerCapture(e.pointerId);
    function move(evt) { setPanelWidth(window.innerWidth - evt.clientX); }
    function stop() {
      resizeHandle.removeEventListener('pointermove', move);
      resizeHandle.removeEventListener('pointerup', stop);
    }
    resizeHandle.addEventListener('pointermove', move);
    resizeHandle.addEventListener('pointerup', stop);
  });
  resizeHandle.addEventListener('keydown', function (e) {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    var current = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--assistant-panel-width'), 10) || 440;
    setPanelWidth(current + (e.key === 'ArrowLeft' ? 20 : -20));
  });

  refreshHistory();
})();
