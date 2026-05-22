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
