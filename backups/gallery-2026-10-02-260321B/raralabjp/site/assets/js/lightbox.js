document.addEventListener('DOMContentLoaded', function () {
  var detail = document.querySelector('main.detail');
  if (!detail) return;

  var overlay = document.querySelector('[data-lb-root]');
  if (!overlay) return;

  var imgEl    = overlay.querySelector('[data-lb-img]');
  var closeEls = overlay.querySelectorAll('[data-lb-close]');
  var prevBtn  = overlay.querySelector('[data-lb-prev]');
  var nextBtn  = overlay.querySelector('[data-lb-next]');

  var thumbLinks = Array.prototype.slice.call(detail.querySelectorAll('.thumbs a[data-full]'));
  var heroLink   = detail.querySelector('.hero a[data-full], a.hero-link[data-full]');

  var images = thumbLinks.map(function (a) { return a.getAttribute('data-full'); });
  var current = -1;

  function openAt(index) {
    if (!images.length) return;
    if (index < 0) index = images.length - 1;
    if (index >= images.length) index = 0;
    current = index;
    var src = images[current];
    imgEl.setAttribute('src', src);
    overlay.removeAttribute('hidden');
    document.documentElement.classList.add('lb-open');
  }

  function close() {
    overlay.setAttribute('hidden', 'hidden');
    document.documentElement.classList.remove('lb-open');
  }

  function showNext(delta) {
    if (current === -1) return;
    openAt(current + delta);
  }

  thumbLinks.forEach(function (a, index) {
    a.addEventListener('click', function (e) {
      e.preventDefault();
      openAt(index);
    });
  });

  if (heroLink) {
    heroLink.addEventListener('click', function (e) {
      e.preventDefault();
      var heroFull = heroLink.getAttribute('data-full');
      var idx = images.indexOf(heroFull);
      openAt(idx !== -1 ? idx : 0);
    });
  }

  closeEls.forEach(function (el) {
    el.addEventListener('click', function (e) {
      e.preventDefault();
      close();
    });
  });

  // 黒い余白（overlay 自体）をクリックしたら閉じる
  overlay.addEventListener('click', function (e) {
    // クリックされた要素が overlay 自体のときだけ閉じる
    // （画像やボタンをクリックしたときには反応しない）
    if (e.target === overlay) {
      e.preventDefault();
      close();
    }
  });
  
  // 画像の左右タップで前後移動
  imgEl.addEventListener('click', function (e) {
    var rect = imgEl.getBoundingClientRect();
    var x = e.clientX - rect.left;
    if (x < rect.width / 2) {
      showNext(-1);
    } else {
      showNext(1);
    }
  });

  if (prevBtn) prevBtn.addEventListener('click', function (e) {
    e.preventDefault();
    showNext(-1);
  });

  if (nextBtn) nextBtn.addEventListener('click', function (e) {
    e.preventDefault();
    showNext(1);
  });

  // ESC キーで閉じる
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      close();
    }
  });
});