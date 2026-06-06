(function () {
  var el = document.getElementById('sandboxCanvas');
  if (!el || typeof cytoscape === 'undefined') return;

  var elements = [];
  try {
    elements = JSON.parse(el.dataset.elements || '[]');
  } catch (err) {
    elements = [];
  }

  if (!elements.length) {
    el.innerHTML = '<div class="sandbox-canvas-empty">' + (el.dataset.emptyLabel || 'Empty canvas') + '</div>';
    return;
  }

  cytoscape({
    container: el,
    elements: elements,
    userZoomingEnabled: true,
    userPanningEnabled: true,
    boxSelectionEnabled: false,
    autoungrabify: true,
    style: [
      {
        selector: 'node',
        style: {
          'shape': 'round-rectangle',
          'width': 190,
          'height': 72,
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
        selector: 'edge',
        style: {
          'width': 2,
          'line-color': '#94a3b8',
          'target-arrow-color': '#94a3b8',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier'
        }
      }
    ],
    layout: {
      name: 'preset',
      fit: true,
      padding: 40
    }
  });
})();
