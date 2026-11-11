// Small enhancements; every page works without JavaScript.
(function () {
  // Mobile navigation
  var t = document.getElementById('navToggle');
  if (t) t.addEventListener('click', function () { document.body.classList.toggle('nav-open'); });
  document.addEventListener('click', function (e) {
    if (document.body.classList.contains('nav-open') && !e.target.closest('.side') && e.target.id !== 'navToggle')
      document.body.classList.remove('nav-open');
  });

  // Region -> district (and crop) selects. Data comes from <script type="application/json" id="locs">.
  var locEl = document.getElementById('locs');
  if (locEl) {
    var data = JSON.parse(locEl.textContent);
    document.querySelectorAll('[data-region]').forEach(function (reg) {
      var form = reg.form;
      var dist = form.querySelector('[data-district]');
      var crop = form.querySelector('[data-crop]');
      function fill(sel, items, keep) {
        if (!sel) return;
        var cur = keep || sel.value;
        sel.innerHTML = '<option value="">Choose…</option>' + (items || []).map(function (x) {
          return '<option' + (x === cur ? ' selected' : '') + '>' + x.replace(/</g, '&lt;') + '</option>';
        }).join('');
      }
      function update(first) {
        fill(dist, data.districts[reg.value], first ? dist && dist.dataset.value : null);
        if (crop && data.crops) fill(crop, data.crops[reg.value], first ? crop.dataset.value : null);
      }
      reg.addEventListener('change', function () { update(false); });
      update(true);
    });
  }

  // Show crop only for farmers
  document.querySelectorAll('[data-livelihood]').forEach(function (sel) {
    var box = sel.form.querySelector('[data-crop-box]');
    function sync() { if (box) box.hidden = sel.value !== 'farmer'; }
    sel.addEventListener('change', sync); sync();
  });

  // Confirm buttons (built into the page, no browser dialogs)
  document.querySelectorAll('[data-confirm]').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      if (btn.dataset.armed) return;
      e.preventDefault();
      btn.dataset.armed = '1';
      var label = btn.textContent;
      btn.textContent = btn.dataset.confirm;
      setTimeout(function () { delete btn.dataset.armed; btn.textContent = label; }, 4000);
    });
  });
})();
