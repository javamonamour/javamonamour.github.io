(function () {
  var input = document.getElementById('q');
  var status = document.getElementById('status');
  var list = document.getElementById('results');
  var data = null, timer = null;

  function norm(s) {
    return (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  }
  function esc(s) {
    return s.replace(/[&<>"]/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; });
  }
  function highlight(text, terms) {
    var out = esc(text);
    terms.forEach(function (t) {
      if (t.length < 2) return;
      var re = new RegExp('(' + t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'ig');
      out = out.replace(re, '<mark>$1</mark>');
    });
    return out;
  }
  function snippet(x, terms) {
    var lx = norm(x), pos = -1;
    for (var i = 0; i < terms.length && pos < 0; i++) pos = lx.indexOf(terms[i]);
    var start = Math.max(0, pos - 80);
    var s = x.substr(start, 240);
    return (start > 0 ? '…' : '') + s + (start + 240 < x.length ? '…' : '');
  }
  var ENT = {'&lt;':'<','&gt;':'>','&amp;':'&','&quot;':'"','&#39;':"'",'&apos;':"'",'&nbsp;':' '};
  function decode(s) {
    return (s || '').replace(/&(?:lt|gt|amp|quot|apos|nbsp|#39);/g, function (m) { return ENT[m]; })
      .replace(/&#(\d+);/g, function (m, n) { return String.fromCharCode(+n); });
  }
  function run() {
    var q = input.value.trim();
    var params = new URLSearchParams(location.search);
    if (params.get('q') !== q) history.replaceState(null, '', q ? '?q=' + encodeURIComponent(q) : location.pathname);
    list.innerHTML = '';
    if (!q) { status.textContent = data ? data.length + ' posts indexed. Type something to search.' : ''; return; }
    var terms = norm(q).split(/\s+/).filter(Boolean);
    var hits = [];
    data.forEach(function (p) {
      var score = 0;
      for (var i = 0; i < terms.length; i++) {
        var t = terms[i], s = 0;
        if (p._t.indexOf(t) >= 0) s += 10;
        if (p._g.indexOf(t) >= 0) s += 6;
        var n = 0, idx = p._x.indexOf(t);
        while (idx >= 0 && n < 10) { n++; idx = p._x.indexOf(t, idx + t.length); }
        s += n;
        if (!s) return;
        score += s;
      }
      hits.push({ p: p, score: score });
    });
    hits.sort(function (a, b) { return b.score - a.score || (b.p.d > a.p.d ? 1 : -1); });
    status.textContent = hits.length ? hits.length + ' result' + (hits.length > 1 ? 's' : '') + ' for “' + q + '”' + (hits.length > 100 ? ' (showing first 100)' : '') : 'No results for “' + q + '”. Try fewer or different words.';
    list.innerHTML = hits.slice(0, 100).map(function (h) {
      var p = h.p;
      return '<li><a class="r-title" href="' + p.u + '">' + highlight(p.t, terms) + '</a>' +
        '<span class="meta">' + p.d + (p.g.length ? ' · ' + esc(p.g.join(', ')) : '') + '</span>' +
        '<p>' + highlight(snippet(p.x, terms), terms) + '</p></li>';
    }).join('');
  }
  input.value = new URLSearchParams(location.search).get('q') || '';
  status.textContent = 'Loading the search index…';
  fetch('/search.json').then(function (r) { return r.json(); }).then(function (d) {
    d.forEach(function (p) { p.t = decode(p.t); p.x = decode(p.x); p._t = norm(p.t); p._g = norm(p.g.join(' ')); p._x = norm(p.x); });
    data = d;
    run();
    input.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(run, 200); });
    document.querySelector('form.big').addEventListener('submit', function (e) { e.preventDefault(); run(); });
  }).catch(function () { status.textContent = 'Could not load the search index.'; });
})();
