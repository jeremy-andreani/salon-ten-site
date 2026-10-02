document.addEventListener('DOMContentLoaded', function () {
  var toggle = document.getElementById('navToggle');
  var links = document.getElementById('navLinks');
  if (!toggle || !links) return;

  // Mobile submenus start collapsed only once this script runs; without JS
  // the CSS leaves them visible, so every page stays reachable.
  var subToggles = links.querySelectorAll('.sub-toggle');
  links.classList.add('js-subnav');

  function setSub(btn, open) {
    var name = btn.previousElementSibling ? btn.previousElementSibling.textContent.trim() : 'section';
    btn.parentNode.classList.toggle('sub-open', open);
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    btn.setAttribute('aria-label', (open ? 'Hide ' : 'Show ') + name + ' pages');
  }

  subToggles.forEach(function (btn) {
    btn.addEventListener('click', function () {
      setSub(btn, btn.getAttribute('aria-expanded') !== 'true');
    });
  });

  // The open panel scrolls within whatever is left of the screen below the header.
  function fitPanel() {
    if (links.classList.contains('nav-open')) {
      links.style.setProperty('--nav-top', Math.max(0, links.getBoundingClientRect().top) + 'px');
    }
  }

  function closeMenu() {
    links.classList.remove('nav-open');
    toggle.classList.remove('nav-toggle-open');
    toggle.setAttribute('aria-expanded', 'false');
    subToggles.forEach(function (btn) { setSub(btn, false); });
    links.scrollTop = 0;
  }

  toggle.addEventListener('click', function () {
    if (links.classList.contains('nav-open')) { closeMenu(); return; }
    links.classList.add('nav-open');
    toggle.classList.add('nav-toggle-open');
    toggle.setAttribute('aria-expanded', 'true');
    fitPanel();
  });

  window.addEventListener('resize', fitPanel);

  links.querySelectorAll('a').forEach(function (a) {
    a.addEventListener('click', closeMenu);
  });
});
