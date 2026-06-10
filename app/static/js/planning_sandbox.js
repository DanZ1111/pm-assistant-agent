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
  var selectedNodeId = null;
  var dropModuleKey = null;

  try {
    payload = JSON.parse(workspace.dataset.payload || '{}');
  } catch (err) {
    payload = {};
  }

  function addDaysIso(dateValue, days) {
    if (!dateValue) return '';
    var parts = String(dateValue).split('-').map(function (part) { return Number(part); });
    if (parts.length !== 3 || parts.some(function (part) { return !Number.isFinite(part); })) return '';
    var date = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2]));
    date.setUTCDate(date.getUTCDate() + Number(days || 0));
    return date.toISOString().slice(0, 10);
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

  function elements() {
    return payload.elements || [];
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

  function endpoint(path) {
    return '/projects/' + projectId + '/sandbox/' + sandboxId + path;
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

  function setCanvasLoading(isLoading) {
    canvas.classList.toggle('sandbox-canvas-loading', !!isLoading);
  }

  function updateSummary() {
    var schedule = payload.schedule || {};
    var totalDays = document.querySelector('[data-sandbox-total-days]');
    var nodeCount = document.querySelector('[data-sandbox-node-count]');
    var warningCount = document.querySelector('[data-sandbox-warning-count]');
    if (totalDays) totalDays.textContent = schedule.total_days || 0;
    if (nodeCount) nodeCount.textContent = (schedule.nodes || []).length;
    if (warningCount) warningCount.textContent = (schedule.soft_warnings || []).length;
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

  function appendWarningChips(strip, label, warnings) {
    var labelEl = document.createElement('span');
    labelEl.className = 'sandbox-warning-label';
    labelEl.textContent = label;
    strip.appendChild(labelEl);
    warnings.forEach(function (warning) {
      var chip = document.createElement('span');
      chip.className = 'sandbox-warning-chip';
      chip.textContent = warning.code || warning;
      strip.appendChild(chip);
    });
  }

  function refreshFromPayload(nextPayload) {
    payload = nextPayload || payload;
    canvas.dataset.elements = JSON.stringify(elements());
    updateSummary();
    updateWarningStrip();
    renderCanvas();
    if (selectedNodeId) {
      var found = findNode(selectedNodeId);
      if (found) {
        selectNode(selectedNodeId);
      } else {
        selectedNodeId = null;
        showPalette();
      }
    }
  }

  function renderCanvas() {
    if (cy) {
      cy.destroy();
      cy = null;
    }
    if (!elements().length) {
      canvas.innerHTML = '<div class="sandbox-canvas-empty">' + emptyLabel + '</div>';
      return;
    }
    canvas.innerHTML = '';
    cy = cytoscape({
      container: canvas,
      elements: elements(),
      userZoomingEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: false,
      autoungrabify: !canEdit,
      style: [
        {
          selector: 'node',
          style: {
            'shape': 'round-rectangle',
            'width': 190,
            'height': 'data(node_height)',
            'background-color': '#ffffff',
            'border-width': 2,
            'border-color': '#cbd5e1',
            'label': 'data(label)',
            'font-size': 13,
            'font-weight': 700,
            'color': '#0f172a',
            'text-wrap': 'wrap',
            'text-max-width': 160,
            'text-valign': 'center',
            'text-halign': 'center'
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
          style: {'border-color': '#22c55e', 'background-color': '#f0fdf4'}
        },
        {
          selector: 'node[phase_type = "production"]',
          style: {'border-color': '#f59e0b', 'background-color': '#fffbeb'}
        },
        {
          selector: 'node[phase_type = "prototype"]',
          style: {'border-color': '#3b82f6', 'background-color': '#eff6ff'}
        },
        {
          selector: 'node[duration_bin = "S"]',
          style: {'height': 66}
        },
        {
          selector: 'node[duration_bin = "M"]',
          style: {'height': 82}
        },
        {
          selector: 'node[duration_bin = "L"]',
          style: {'height': 100}
        },
        {
          selector: 'node[duration_bin = "XL"]',
          style: {'height': 122, 'border-width': 3}
        },
        {
          selector: 'edge',
          style: {
            'width': 2,
            'line-color': '#94a3b8',
            'target-arrow-color': '#94a3b8',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier'
          }
        },
        {
          selector: 'edge:selected',
          style: {
            'width': 4,
            'line-color': '#2563eb',
            'target-arrow-color': '#2563eb'
          }
        }
      ],
      layout: {
        name: 'preset',
        fit: true,
        padding: 40
      }
    });

    cy.on('tap', 'node', function (event) {
      selectNode(event.target.data('db_id'));
    });
    cy.on('tap', 'edge', function (event) {
      if (cy) {
        cy.elements().unselect();
        event.target.select();
      }
    });
    cy.on('tap', function (event) {
      if (event.target === cy) {
        selectedNodeId = null;
        showPalette();
      }
    });
    if (canEdit) {
      cy.on('dragfree', 'node', function (event) {
        var node = event.target;
        var position = node.position();
        postForm(endpoint('/nodes/' + node.data('db_id') + '/position'), {
          x_position: position.x,
          y_position: position.y
        }).then(function (json) {
          payload = json.sandbox_payload || payload;
        }).catch(function (err) {
          showMessage(workspace.dataset.labelNodeError || err.message, true);
        });
      });
    }
  }

  function findNode(dbId) {
    return elements().find(function (el) {
      return el.data && String(el.data.db_id) === String(dbId) && String(el.data.id || '').indexOf('node-') === 0;
    });
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

  function nodeTitle(dbId) {
    var node = findNode(dbId);
    return node && node.data ? node.data.label : ('Node ' + dbId);
  }

  function findIncomingEdge(fromNodeId, toNodeId) {
    return edgeElements().find(function (edge) {
      return String(edge.data.source) === 'node-' + fromNodeId && String(edge.data.target) === 'node-' + toNodeId;
    });
  }

  function showPalette() {
    var palette = document.querySelector('[data-sandbox-palette]');
    var properties = document.querySelector('[data-sandbox-properties]');
    if (palette) palette.hidden = false;
    if (properties) properties.hidden = true;
    if (cy) cy.elements().unselect();
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
      option.textContent = node.data.label;
      option.selected = selectedIds.indexOf(String(node.data.db_id)) !== -1;
      select.appendChild(option);
    });
    if (noOptions) noOptions.hidden = options.length > 0;

    list.innerHTML = '';
    selectedIds.forEach(function (fromId) {
      var row = document.createElement('div');
      row.className = 'sandbox-dependency-row';
      var label = document.createElement('span');
      label.textContent = nodeTitle(fromId) + ' -> ' + data.label;
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
    selectedNodeId = dbId;
    var node = findNode(dbId);
    if (!node) {
      showPalette();
      return;
    }
    var palette = document.querySelector('[data-sandbox-palette]');
    var properties = document.querySelector('[data-sandbox-properties]');
    if (palette) palette.hidden = true;
    if (properties) properties.hidden = false;
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
    populateDependencyPanel(data);
    if (cy) {
      cy.elements().unselect();
      var cyNode = cy.getElementById('node-' + data.db_id);
      if (cyNode) cyNode.select();
    }
  }

  function addModule(moduleKey, position) {
    if (!canEdit || !moduleKey) return;
    postForm(endpoint('/nodes/add'), {
      module_key: moduleKey,
      x_position: position && position.x !== undefined ? position.x : 80,
      y_position: position && position.y !== undefined ? position.y : 80
    }).then(function (json) {
      refreshFromPayload(json.sandbox_payload);
    }).catch(function (err) {
      showMessage(workspace.dataset.labelNodeError || err.message, true);
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
      refreshFromPayload(json.sandbox_payload);
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
        x: 140 + (index % 3) * 260,
        y: 120 + Math.floor(index / 3) * 160
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
      persistTidyPositions();
    };
    try {
      var layout = cy.layout({
        name: 'dagre',
        rankDir: 'TB',
        nodeSep: 80,
        rankSep: 110,
        animate: false,
        fit: true,
        padding: 40
      });
      layout.on('layoutstop', persistOnce);
      layout.run();
      window.setTimeout(persistOnce, 800);
    } catch (err) {
      runFallbackTidy();
      persistOnce();
    }
  }

  document.querySelectorAll('.sandbox-add-module-btn').forEach(function (button) {
    button.addEventListener('click', function () {
      addModule(button.dataset.moduleKey, {x: 120, y: 120});
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

  var tidyButton = document.querySelector('[data-tidy-canvas]');
  if (tidyButton && canEdit) {
    tidyButton.addEventListener('click', tidyCanvas);
  }

  if (canEdit) {
    canvas.addEventListener('dragover', function (event) {
      event.preventDefault();
    });
    canvas.addEventListener('drop', function (event) {
      event.preventDefault();
      var moduleKey = dropModuleKey || (event.dataTransfer && event.dataTransfer.getData('text/plain'));
      var rect = canvas.getBoundingClientRect();
      addModule(moduleKey, {
        x: event.clientX - rect.left,
        y: event.clientY - rect.top
      });
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
        refreshFromPayload(json.sandbox_payload);
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
        refreshFromPayload(json.sandbox_payload);
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
        refreshFromPayload(json.sandbox_payload);
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
        refreshFromPayload(json.sandbox_payload);
        showPalette();
      }).catch(function (err) {
        showMessage(workspace.dataset.labelNodeError || err.message, true);
      });
    });
  }

  renderCanvas();
  updateSummary();
  updateWarningStrip();
  initApplyPreview();
  showPalette();
})();
