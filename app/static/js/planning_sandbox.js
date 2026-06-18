(function () {
  var canvas = document.getElementById('sandboxCanvas');
  var workspace = document.querySelector('[data-sandbox-workspace]');
  if (!canvas || !workspace || typeof cytoscape === 'undefined') return;

  var projectId = workspace.dataset.projectId;
  var sandboxId = workspace.dataset.sandboxId;
  var canEdit = workspace.dataset.canEdit === 'true';
  var emptyLabel = canvas.dataset.emptyLabel || 'Empty canvas';
  var cy = null;
  var payload = {};
  var warningCopy = {};
  var selectedNodeId = null;
  var connectSourceNodeId = null;
  var dropModuleKey = null;
  var activeModuleFilter = 'default';
  var initialViewport = {zoom: 1, pan: {x: 0, y: 0}};

  try {
    payload = JSON.parse(workspace.dataset.payload || '{}');
  } catch (err) {
    payload = {};
  }
  try {
    warningCopy = JSON.parse(workspace.dataset.warningCopy || '{}');
  } catch (err) {
    warningCopy = {};
  }

  function addDaysIso(dateValue, days) {
    if (!dateValue) return '';
    var parts = String(dateValue).split('-').map(function (part) { return Number(part); });
    if (parts.length !== 3 || parts.some(function (part) { return !Number.isFinite(part); })) return '';
    var date = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2]));
    date.setUTCDate(date.getUTCDate() + Number(days || 0));
    return date.toISOString().slice(0, 10);
  }

  function endpoint(path) {
    return '/projects/' + projectId + '/sandbox/' + sandboxId + path;
  }

  function postForm(url, data) {
    var form = new FormData();
    Object.keys(data || {}).forEach(function (key) {
      if (Array.isArray(data[key])) {
        data[key].forEach(function (value) {
          form.append(key, value);
        });
      } else {
        form.append(key, data[key]);
      }
    });
    return fetch(url, {
      method: 'POST',
      body: form,
      credentials: 'same-origin'
    }).then(function (res) {
      return res.json().then(function (json) {
        if (!res.ok || !json.ok) {
          throw new Error(json.error || 'sandbox_error');
        }
        return json;
      });
    });
  }

  function elements() {
    return payload.elements || [];
  }

  function nodeElements() {
    return elements().filter(function (el) {
      return el.data && String(el.data.id || '').indexOf('node-') === 0;
    });
  }

  function edgeElements() {
    return elements().filter(function (el) {
      return el.data && String(el.data.id || '').indexOf('edge-') === 0;
    });
  }

  function findNode(dbId) {
    var normalized = normalizeNodeId(dbId);
    return nodeElements().find(function (el) {
      return String(el.data.db_id) === String(normalized);
    });
  }

  function nodeTitle(dbId) {
    var node = findNode(dbId);
    return node && node.data ? (node.data.display_label || node.data.label) : ('Node ' + dbId);
  }

  function findIncomingEdge(fromNodeId, toNodeId) {
    return edgeElements().find(function (edge) {
      return String(edge.data.source) === 'node-' + fromNodeId && String(edge.data.target) === 'node-' + toNodeId;
    });
  }

  function updateViewportHooks() {
    if (cy) {
      var pan = cy.pan();
      workspace.dataset.sandboxZoom = String(Math.round(cy.zoom() * 10000) / 10000);
      workspace.dataset.sandboxPanX = String(Math.round(pan.x * 100) / 100);
      workspace.dataset.sandboxPanY = String(Math.round(pan.y * 100) / 100);
    }
    workspace.dataset.sandboxSelectedNodeId = selectedNodeId ? String(selectedNodeId) : '';
  }

  function initApplyPreview() {
    var panel = document.querySelector('[data-apply-preview]');
    var startInput = document.querySelector('[data-apply-start-date]');
    var endOutput = document.querySelector('[data-apply-end-date]');
    if (!panel || !startInput || !endOutput) return;
    var totalDays = Number(panel.dataset.totalDays || 0);
    var updateEnd = function () {
      endOutput.textContent = addDaysIso(startInput.value, totalDays) || '—';
    };
    startInput.addEventListener('input', updateEnd);
    updateEnd();
  }

  function showMessage(text, isError) {
    var msg = document.querySelector('[data-node-message]');
    if (!msg) return;
    msg.textContent = text;
    msg.hidden = false;
    msg.classList.toggle('sandbox-node-message-error', !!isError);
    window.setTimeout(function () {
      msg.hidden = true;
    }, 2400);
  }

  function normalizeNodeId(dbId) {
    var value = String(dbId || '');
    return value.indexOf('node-') === 0 ? value.slice(5) : value;
  }

  function setConnectSource(dbId) {
    connectSourceNodeId = dbId ? normalizeNodeId(dbId) : null;
    document.querySelectorAll('[data-sandbox-connect-from]').forEach(function (button) {
      button.classList.toggle('is-connecting', !!connectSourceNodeId);
    });
    if (connectSourceNodeId) {
      showMessage(workspace.dataset.labelConnectReady || 'Click the next step on the canvas to create an arrow.', false);
    }
  }

  function setCanvasLoading(isLoading) {
    canvas.classList.toggle('sandbox-canvas-loading', !!isLoading);
  }

  function updateSummary() {
    var schedule = payload.schedule || {};
    document.querySelectorAll('[data-sandbox-total-days]').forEach(function (el) {
      el.textContent = schedule.total_days || 0;
    });
    document.querySelectorAll('[data-sandbox-node-count]').forEach(function (el) {
      el.textContent = (schedule.nodes || []).length;
    });
    document.querySelectorAll('[data-sandbox-warning-count]').forEach(function (el) {
      el.textContent = (schedule.hard_errors || []).length + (schedule.soft_warnings || []).length;
    });
  }

  function issueText(issue) {
    var code = issue && issue.code ? issue.code : String(issue || '');
    return warningCopy[code] || code;
  }

  function appendWarningChips(strip, label, warnings) {
    var labelEl = document.createElement('span');
    labelEl.className = 'sandbox-warning-label';
    labelEl.textContent = label;
    strip.appendChild(labelEl);
    warnings.forEach(function (warning) {
      var chip = document.createElement('span');
      chip.className = 'sandbox-warning-chip';
      chip.dataset.sandboxWarningChip = '';
      chip.textContent = issueText(warning);
      strip.appendChild(chip);
    });
  }

  function updateWarningStrip() {
    var strip = document.querySelector('[data-sandbox-warning-strip]');
    if (!strip) return;
    var schedule = payload.schedule || {};
    var hardErrors = schedule.hard_errors || [];
    var softWarnings = schedule.soft_warnings || [];
    strip.classList.toggle('sandbox-error-strip', hardErrors.length > 0);
    strip.innerHTML = '';
    if (hardErrors.length) {
      strip.hidden = false;
      appendWarningChips(strip, workspace.dataset.labelWarningHard || 'Hard error', hardErrors);
    } else if (softWarnings.length) {
      strip.hidden = false;
      appendWarningChips(strip, workspace.dataset.labelWarningSoft || 'Warning', softWarnings);
    } else {
      strip.hidden = true;
    }
  }

  function updateIssuesPanel() {
    var list = document.querySelector('[data-sandbox-issues-list]');
    if (!list) return;
    var schedule = payload.schedule || {};
    var hardErrors = schedule.hard_errors || [];
    var softWarnings = schedule.soft_warnings || [];
    list.innerHTML = '';
    if (!hardErrors.length && !softWarnings.length) {
      var empty = document.createElement('p');
      empty.className = 'sandbox-read-only-note';
      empty.textContent = workspace.dataset.labelNoIssues || 'No issues.';
      list.appendChild(empty);
      return;
    }
    hardErrors.forEach(function (issue) {
      list.appendChild(issueCard(issue, workspace.dataset.labelWarningHard || 'Hard error', true));
    });
    softWarnings.forEach(function (issue) {
      list.appendChild(issueCard(issue, workspace.dataset.labelWarningSoft || 'Warning', false));
    });
  }

  function issueCard(issue, label, isHard) {
    var card = document.createElement('article');
    card.className = 'sandbox-issue-card' + (isHard ? ' sandbox-issue-card-hard' : '');
    var type = document.createElement('span');
    type.className = 'sandbox-issue-type';
    type.textContent = label;
    var message = document.createElement('strong');
    message.dataset.sandboxIssueMessage = '';
    message.textContent = issueText(issue);
    var code = document.createElement('code');
    code.dataset.sandboxIssueCode = '';
    code.dataset.issueCode = issue && issue.code ? issue.code : String(issue || '');
    code.className = 'visually-hidden';
    card.appendChild(type);
    card.appendChild(message);
    card.appendChild(code);
    return card;
  }

  function setActiveTab(tabName) {
    // data-sandbox-palette is the persistent Modules tab; older Build 04
    // regressions look for this marker to prove palette mode still exists.
    var target = tabName || 'modules';
    document.querySelectorAll('[data-sandbox-tab]').forEach(function (tab) {
      tab.classList.toggle('is-active', tab.dataset.sandboxTab === target);
    });
    document.querySelectorAll('[data-sandbox-panel]').forEach(function (panel) {
      panel.hidden = panel.dataset.sandboxPanel !== target;
    });
  }

  function showPalette() {
    selectedNodeId = null;
    setConnectSource(null);
    setActiveTab('modules');
    if (cy) cy.elements().unselect();
    var noNode = document.querySelector('[data-no-node]');
    if (noNode) noNode.hidden = false;
    var status = document.querySelector('[data-node-status]');
    if (status) status.textContent = status.dataset.emptyText || status.textContent;
    ['[data-node-id]', '[data-node-title]', '[data-node-duration]', '[data-node-owner]', '[data-node-deliverable]', '[data-node-exit]'].forEach(function (selector) {
      var field = document.querySelector(selector);
      if (field) field.value = '';
    });
    updateViewportHooks();
  }

  function nodeStyle() {
    // Backend still emits duration_bin for schedule/debug consumers; the UI
    // rescue intentionally uses fixed compact node height instead.
    return [
      {
        selector: 'node',
        style: {
          'shape': 'round-rectangle',
          'width': 164,
          'height': 74,
          'background-color': '#ffffff',
          'border-width': 2,
          'border-color': '#94a3b8',
          'label': 'data(display_label)',
          'font-size': 12,
          'font-weight': 750,
          'color': '#0f172a',
          'text-wrap': 'wrap',
          'text-max-width': 132,
          'text-valign': 'center',
          'text-halign': 'center',
          'padding': 8
        }
      },
      {
        selector: 'node:selected',
        style: {
          'border-color': '#2563eb',
          'border-width': 4,
          'background-color': '#eff6ff'
        }
      },
      {
        selector: 'node[phase_type = "launch"]',
        style: {'border-color': '#16a34a', 'background-color': '#f0fdf4'}
      },
      {
        selector: 'node[phase_type = "production"]',
        style: {'border-color': '#d97706', 'background-color': '#fffbeb'}
      },
      {
        selector: 'node[phase_type = "prototype"]',
        style: {'border-color': '#2563eb', 'background-color': '#eff6ff'}
      },
      {
        selector: 'edge',
        style: {
          'width': 3.5,
          'line-color': '#334155',
          'target-arrow-color': '#334155',
          'target-arrow-shape': 'triangle',
          'arrow-scale': 1.25,
          'curve-style': 'bezier'
        }
      },
      {
        selector: 'edge:selected',
        style: {
          'width': 5,
          'line-color': '#2563eb',
          'target-arrow-color': '#2563eb'
        }
      }
    ];
  }

  function bindCyEvents() {
    cy.on('tap', 'node', function (event) {
      var targetId = normalizeNodeId(event.target.data('db_id'));
      if (connectSourceNodeId && canEdit) {
        if (connectSourceNodeId === targetId) {
          setConnectSource(null);
          selectNode(targetId);
          return;
        }
        createEdge(connectSourceNodeId, targetId, {selectTarget: true});
        return;
      }
      selectNode(targetId);
    });
    cy.on('tap', 'edge', function (event) {
      if (cy) {
        cy.elements().unselect();
        event.target.select();
        updateViewportHooks();
      }
    });
    cy.on('tap', function (event) {
      if (event.target === cy) {
        showPalette();
      }
    });
    cy.on('pan zoom', updateViewportHooks);
    if (canEdit) {
      cy.on('dragfree', 'node', function (event) {
        var node = event.target;
        var position = node.position();
        updateViewportHooks();
        postForm(endpoint('/nodes/' + node.data('db_id') + '/position'), {
          x_position: position.x,
          y_position: position.y
        }).then(function (json) {
          payload = json.sandbox_payload || payload;
          updateSummary();
          updateWarningStrip();
          updateIssuesPanel();
        }).catch(function (err) {
          showMessage(workspace.dataset.labelNodeError || err.message, true);
        });
      });
    }
  }

  function ensureCy(shouldFit) {
    if (!elements().length) {
      if (cy) {
        cy.destroy();
        cy = null;
      }
      canvas.innerHTML = '<div class="sandbox-canvas-empty">' + emptyLabel + '</div>';
      updateViewportHooks();
      return;
    }
    if (cy) return;
    canvas.innerHTML = '';
    cy = cytoscape({
      container: canvas,
      elements: elements(),
      userZoomingEnabled: false,
      userPanningEnabled: true,
      boxSelectionEnabled: false,
      autoungrabify: !canEdit,
      style: nodeStyle(),
      layout: {
        name: 'preset',
        fit: !!shouldFit,
        padding: 46
      }
    });
    bindCyEvents();
    if (shouldFit) {
      initialViewport = {zoom: cy.zoom(), pan: cy.pan()};
    }
    updateViewportHooks();
  }

  function applyElementDiff() {
    if (!cy) return;
    var next = elements();
    var nextById = {};
    next.forEach(function (el) {
      if (el.data && el.data.id) nextById[el.data.id] = el;
    });
    cy.elements().forEach(function (ele) {
      if (!nextById[ele.id()]) {
        ele.remove();
      }
    });
    next.forEach(function (el) {
      var id = el.data && el.data.id;
      if (!id) return;
      var existing = cy.getElementById(id);
      if (existing && existing.length) {
        existing.data(el.data || {});
        if (el.position && existing.isNode()) {
          existing.position(el.position);
        }
      } else {
        cy.add(el);
      }
    });
  }

  function refreshFromPayload(nextPayload, options) {
    options = options || {};
    var viewport = cy ? {zoom: cy.zoom(), pan: cy.pan()} : null;
    payload = nextPayload || payload;
    canvas.dataset.elements = JSON.stringify(elements());
    updateSummary();
    updateWarningStrip();
    updateIssuesPanel();
    ensureCy(!cy && options.fit !== false);
    if (cy) {
      applyElementDiff();
      if (viewport && !options.fit) {
        cy.zoom(viewport.zoom);
        cy.pan(viewport.pan);
      } else if (options.fit) {
        cy.fit(undefined, 46);
      }
    }
    if (selectedNodeId && findNode(selectedNodeId)) {
      selectNode(selectedNodeId, {preserveViewport: true});
    } else if (selectedNodeId) {
      showPalette();
    } else {
      updateViewportHooks();
    }
    filterModules();
  }

  function populateDependencyPanel(data) {
    var select = document.querySelector('[data-node-dependencies]');
    var list = document.querySelector('[data-dependency-list]');
    var noOptions = document.querySelector('[data-no-dependency-options]');
    if (!select || !list) return;
    var selectedIds = (data.depends_on_ids || []).map(function (id) { return String(id); });
    var options = nodeElements().filter(function (node) {
      return String(node.data.db_id) !== String(data.db_id);
    });
    select.innerHTML = '';
    options.forEach(function (node) {
      var option = document.createElement('option');
      option.value = node.data.db_id;
      option.textContent = node.data.display_label || node.data.label;
      option.selected = selectedIds.indexOf(String(node.data.db_id)) !== -1;
      select.appendChild(option);
    });
    if (noOptions) noOptions.hidden = options.length > 0;

    list.innerHTML = '';
    selectedIds.forEach(function (fromId) {
      var row = document.createElement('div');
      row.className = 'sandbox-dependency-row';
      var label = document.createElement('span');
      label.textContent = nodeTitle(fromId) + ' -> ' + (data.display_label || data.label);
      row.appendChild(label);
      var edge = findIncomingEdge(fromId, data.db_id);
      if (canEdit && edge) {
        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'btn btn-sm btn-outline-danger';
        button.dataset.deleteEdgeId = edge.data.db_id;
        button.textContent = workspace.dataset.labelDeleteEdge || 'Delete dependency';
        row.appendChild(button);
      }
      list.appendChild(row);
    });
  }

  function selectNode(dbId) {
    selectedNodeId = normalizeNodeId(dbId);
    var node = findNode(dbId);
    if (!node) {
      showPalette();
      return;
    }
    setActiveTab('selected');
    var data = node.data || {};
    var set = function (selector, value) {
      var field = document.querySelector(selector);
      if (field) field.value = value || '';
    };
    set('[data-node-id]', data.db_id);
    set('[data-node-title]', data.label);
    set('[data-node-duration]', data.duration_days);
    set('[data-node-owner]', data.owner_role);
    set('[data-node-deliverable]', data.deliverable);
    set('[data-node-exit]', data.exit_criteria);
    var noNode = document.querySelector('[data-no-node]');
    if (noNode) noNode.hidden = true;
    var status = document.querySelector('[data-node-status]');
    if (status) {
      if (!status.dataset.emptyText) status.dataset.emptyText = status.textContent;
      status.textContent = data.display_label || data.label || status.dataset.emptyText;
    }
    populateDependencyPanel(data);
    if (cy) {
      cy.elements().unselect();
      var cyNode = cy.getElementById('node-' + data.db_id);
      if (cyNode && cyNode.length) cyNode.select();
    }
    updateViewportHooks();
  }

  function addModule(moduleKey, position) {
    if (!canEdit || !moduleKey) return;
    var sourceNodeId = selectedNodeId ? normalizeNodeId(selectedNodeId) : null;
    postForm(endpoint('/nodes/add'), {
      module_key: moduleKey,
      x_position: position && position.x !== undefined ? position.x : 120,
      y_position: position && position.y !== undefined ? position.y : 120
    }).then(function (json) {
      // SB-Rescue-03 lock: Add Module must leave the panel on the Modules
      // tab. The new node is NOT auto-selected; the user explicitly clicks
      // it on the canvas if they want to edit. Auto-connect from a pre-Add
      // source node is preserved as a one-shot, then selection clears.
      var createdNodeId = json.created_node_id ? normalizeNodeId(json.created_node_id) : null;
      if (sourceNodeId && createdNodeId && sourceNodeId !== createdNodeId) {
        return postForm(endpoint('/edges'), {
          from_node_id: sourceNodeId,
          to_node_id: createdNodeId
        }).then(function (edgeJson) {
          selectedNodeId = null;
          refreshFromPayload(edgeJson.sandbox_payload, {fit: false});
          setActiveTab('modules');
          return edgeJson;
        });
      }
      selectedNodeId = null;
      refreshFromPayload(json.sandbox_payload, {fit: false});
      setActiveTab('modules');
      return json;
    }).catch(function (err) {
      showMessage(workspace.dataset.labelNodeError || err.message, true);
    });
  }

  function createEdge(fromNodeId, toNodeId, options) {
    options = options || {};
    if (!canEdit || !fromNodeId || !toNodeId) return;
    postForm(endpoint('/edges'), {
      from_node_id: normalizeNodeId(fromNodeId),
      to_node_id: normalizeNodeId(toNodeId)
    }).then(function (json) {
      setConnectSource(null);
      selectedNodeId = options.selectTarget ? normalizeNodeId(toNodeId) : selectedNodeId;
      refreshFromPayload(json.sandbox_payload, {fit: false});
      if (options.selectTarget) selectNode(toNodeId);
      showMessage(workspace.dataset.labelConnectSaved || 'Connection created.', false);
    }).catch(function (err) {
      setConnectSource(null);
      var message = err.message === 'circular_dependency'
        ? (workspace.dataset.labelCycleError || 'That dependency would create a cycle.')
        : (workspace.dataset.labelConnectError || err.message);
      showMessage(message, true);
    });
  }

  function collectPositions() {
    if (!cy) return [];
    return cy.nodes().map(function (node) {
      var position = node.position();
      return {
        node_id: node.data('db_id'),
        x_position: position.x,
        y_position: position.y
      };
    });
  }

  function persistTidyPositions() {
    postForm(endpoint('/nodes/positions'), {
      positions_json: JSON.stringify(collectPositions())
    }).then(function (json) {
      refreshFromPayload(json.sandbox_payload, {fit: false});
      showMessage(workspace.dataset.labelTidySaved || 'Canvas tidied.', false);
    }).catch(function (err) {
      showMessage(workspace.dataset.labelTidyError || err.message, true);
    }).finally(function () {
      setCanvasLoading(false);
    });
  }

  function runFallbackTidy() {
    if (!cy) return;
    var orderedIds = ((payload.schedule || {}).topological_node_ids || []).map(function (id) { return String(id); });
    var nodes = cy.nodes().sort(function (a, b) {
      var aIndex = orderedIds.indexOf(String(a.data('db_id')));
      var bIndex = orderedIds.indexOf(String(b.data('db_id')));
      if (aIndex === -1) aIndex = 9999;
      if (bIndex === -1) bIndex = 9999;
      return aIndex - bIndex;
    });
    nodes.forEach(function (node, index) {
      node.position({
        x: 130 + index * 210,
        y: 170 + (index % 2) * 95
      });
    });
  }

  function tidyCanvas() {
    if (!canEdit || !cy || !cy.nodes().length) return;
    setCanvasLoading(true);
    var persisted = false;
    var persistOnce = function () {
      if (persisted) return;
      persisted = true;
      cy.fit(undefined, 52);
      updateViewportHooks();
      persistTidyPositions();
    };
    try {
      var layout = cy.layout({
        name: 'dagre',
        rankDir: 'LR',
        nodeSep: 64,
        rankSep: 120,
        animate: false,
        fit: false
      });
      layout.on('layoutstop', persistOnce);
      layout.run();
      window.setTimeout(persistOnce, 800);
    } catch (err) {
      runFallbackTidy();
      persistOnce();
    }
  }

  function filterModules() {
    var search = document.querySelector('[data-sandbox-module-search]');
    var query = search ? search.value.trim().toLowerCase() : '';
    document.querySelectorAll('[data-sandbox-module-card]').forEach(function (card) {
      var title = (card.dataset.moduleTitle || '').toLowerCase();
      var category = card.dataset.moduleCategory || '';
      var isAdvanced = card.dataset.moduleAdvanced === 'true';
      var matchesSearch = !query || title.indexOf(query) !== -1 || (card.textContent || '').toLowerCase().indexOf(query) !== -1;
      var matchesFilter = true;
      if (activeModuleFilter === 'default') matchesFilter = !isAdvanced;
      if (activeModuleFilter === 'advanced') matchesFilter = isAdvanced;
      if (!['default', 'advanced'].includes(activeModuleFilter)) matchesFilter = category === activeModuleFilter && !isAdvanced;
      card.hidden = !(matchesSearch && matchesFilter);
    });
    document.querySelectorAll('[data-module-group]').forEach(function (group) {
      var visible = Array.prototype.slice.call(group.querySelectorAll('[data-sandbox-module-card]')).some(function (card) {
        return !card.hidden;
      });
      group.hidden = !visible;
    });
  }

  function fitCanvas() {
    if (!cy || !cy.elements().length) return;
    cy.fit(undefined, 52);
    updateViewportHooks();
  }

  function resetCanvasView() {
    if (!cy) return;
    cy.zoom(initialViewport.zoom || 1);
    cy.pan(initialViewport.pan || {x: 0, y: 0});
    updateViewportHooks();
  }

  document.querySelectorAll('[data-sandbox-tab]').forEach(function (tab) {
    tab.addEventListener('click', function () {
      setActiveTab(tab.dataset.sandboxTab);
    });
  });

  document.querySelectorAll('[data-sandbox-tab-target]').forEach(function (button) {
    button.addEventListener('click', function () {
      setActiveTab(button.dataset.sandboxTabTarget);
    });
  });

  document.addEventListener('click', function (event) {
    document.querySelectorAll('.sandbox-action-menu[open]').forEach(function (menu) {
      if (!menu.contains(event.target)) {
        menu.open = false;
      }
    });
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') {
      document.querySelectorAll('.sandbox-action-menu[open]').forEach(function (menu) {
        menu.open = false;
      });
      setConnectSource(null);
    }
  });

  var backToModules = document.querySelector('[data-sandbox-back-to-modules]');
  if (backToModules) {
    backToModules.addEventListener('click', showPalette);
  }

  document.querySelectorAll('.sandbox-add-module-btn').forEach(function (button) {
    button.addEventListener('click', function () {
      addModule(button.dataset.moduleKey, {x: 140, y: 160});
    });
  });

  document.querySelectorAll('.sandbox-module-card[draggable="true"]').forEach(function (card) {
    card.addEventListener('dragstart', function (event) {
      dropModuleKey = card.dataset.moduleKey;
      if (event.dataTransfer) {
        event.dataTransfer.effectAllowed = 'copy';
        event.dataTransfer.setData('text/plain', dropModuleKey);
      }
    });
  });

  var moduleSearch = document.querySelector('[data-sandbox-module-search]');
  if (moduleSearch) {
    moduleSearch.addEventListener('input', filterModules);
  }
  document.querySelectorAll('[data-sandbox-module-filter]').forEach(function (button) {
    button.addEventListener('click', function () {
      activeModuleFilter = button.dataset.sandboxModuleFilter || 'default';
      document.querySelectorAll('[data-sandbox-module-filter]').forEach(function (other) {
        other.classList.toggle('is-active', other === button);
      });
      filterModules();
    });
  });

  var fitButton = document.querySelector('[data-sandbox-fit]');
  if (fitButton) fitButton.addEventListener('click', fitCanvas);

  var resetButton = document.querySelector('[data-sandbox-reset-view]');
  if (resetButton) resetButton.addEventListener('click', resetCanvasView);

  var tidyButton = document.querySelector('[data-tidy-canvas]');
  if (tidyButton && canEdit) {
    tidyButton.addEventListener('click', tidyCanvas);
  }

  var connectButton = document.querySelector('[data-sandbox-connect-from]');
  if (connectButton && canEdit) {
    connectButton.addEventListener('click', function () {
      if (!selectedNodeId) return;
      if (connectSourceNodeId === normalizeNodeId(selectedNodeId)) {
        setConnectSource(null);
      } else {
        setConnectSource(selectedNodeId);
      }
    });
  }

  if (canEdit) {
    canvas.addEventListener('dragover', function (event) {
      event.preventDefault();
    });
    canvas.addEventListener('drop', function (event) {
      event.preventDefault();
      var moduleKey = dropModuleKey || (event.dataTransfer && event.dataTransfer.getData('text/plain'));
      var rendered = cy ? cy.renderer().projectIntoViewport(event.clientX, event.clientY) : null;
      addModule(moduleKey, rendered ? {x: rendered[0], y: rendered[1]} : {x: 140, y: 160});
      dropModuleKey = null;
    });
  }

  var nodeForm = document.querySelector('[data-node-form]');
  if (nodeForm && canEdit) {
    nodeForm.addEventListener('submit', function (event) {
      event.preventDefault();
      var nodeId = document.querySelector('[data-node-id]').value;
      if (!nodeId) return;
      var formData = new FormData(nodeForm);
      var data = {};
      formData.forEach(function (value, key) {
        data[key] = value;
      });
      postForm(endpoint('/nodes/' + nodeId + '/update'), data).then(function (json) {
        selectedNodeId = nodeId;
        refreshFromPayload(json.sandbox_payload, {fit: false});
        showMessage(workspace.dataset.labelNodeSaved || 'Node saved.', false);
      }).catch(function (err) {
        showMessage(workspace.dataset.labelNodeError || err.message, true);
      });
    });
  }

  var dependencyForm = document.querySelector('[data-dependency-form]');
  if (dependencyForm && canEdit) {
    dependencyForm.addEventListener('submit', function (event) {
      event.preventDefault();
      var nodeId = document.querySelector('[data-node-id]').value;
      var select = document.querySelector('[data-node-dependencies]');
      if (!nodeId || !select) return;
      var selected = Array.prototype.slice.call(select.selectedOptions).map(function (option) {
        return option.value;
      });
      postForm(endpoint('/nodes/' + nodeId + '/dependencies'), {
        depends_on_ids: selected
      }).then(function (json) {
        selectedNodeId = nodeId;
        refreshFromPayload(json.sandbox_payload, {fit: false});
        showMessage(workspace.dataset.labelDependenciesSaved || 'Dependencies saved.', false);
      }).catch(function (err) {
        var message = err.message === 'circular_dependency'
          ? (workspace.dataset.labelCycleError || 'That dependency would create a cycle.')
          : (workspace.dataset.labelDependencyError || err.message);
        showMessage(message, true);
      });
    });
  }

  var dependencyList = document.querySelector('[data-dependency-list]');
  if (dependencyList && canEdit) {
    dependencyList.addEventListener('click', function (event) {
      var button = event.target.closest('[data-delete-edge-id]');
      if (!button) return;
      postForm(endpoint('/edges/' + button.dataset.deleteEdgeId + '/delete'), {}).then(function (json) {
        refreshFromPayload(json.sandbox_payload, {fit: false});
        showMessage(workspace.dataset.labelDependenciesSaved || 'Dependencies saved.', false);
      }).catch(function (err) {
        showMessage(workspace.dataset.labelDependencyError || err.message, true);
      });
    });
  }

  var deleteBtn = document.querySelector('[data-delete-node]');
  if (deleteBtn && canEdit) {
    deleteBtn.addEventListener('click', function () {
      var nodeId = document.querySelector('[data-node-id]').value;
      if (!nodeId) return;
      if (!window.confirm(workspace.dataset.confirmDelete || 'Delete this sandbox node?')) return;
      postForm(endpoint('/nodes/' + nodeId + '/delete'), {}).then(function (json) {
        selectedNodeId = null;
        refreshFromPayload(json.sandbox_payload, {fit: false});
        showPalette();
      }).catch(function (err) {
        showMessage(workspace.dataset.labelNodeError || err.message, true);
      });
    });
  }

  ensureCy(true);
  updateSummary();
  updateWarningStrip();
  updateIssuesPanel();
  initApplyPreview();
  filterModules();
  showPalette();
  window.__planningSandboxQA = {
    selectFirstNode: function () {
      var first = nodeElements()[0];
      if (!first || !first.data) return null;
      selectNode(first.data.db_id);
      return first.data.db_id;
    },
    selectNodeByIndex: function (index) {
      var node = nodeElements()[Number(index || 0)];
      if (!node || !node.data) return null;
      selectNode(node.data.db_id);
      return node.data.db_id;
    },
    connectSelectedToIndex: function (index) {
      var node = nodeElements()[Number(index || 0)];
      if (!node || !node.data || !selectedNodeId) return null;
      createEdge(selectedNodeId, node.data.db_id, {selectTarget: true});
      return node.data.db_id;
    },
    nodeCount: function () {
      return nodeElements().length;
    },
    edgeCount: function () {
      return edgeElements().length;
    },
    nodeLabels: function () {
      return nodeElements().map(function (node) {
        return node && node.data ? node.data.label : '';
      });
    },
    viewport: function () {
      return {
        zoom: workspace.dataset.sandboxZoom,
        panX: workspace.dataset.sandboxPanX,
        panY: workspace.dataset.sandboxPanY,
        selectedNodeId: workspace.dataset.sandboxSelectedNodeId
      };
    }
  };
})();
