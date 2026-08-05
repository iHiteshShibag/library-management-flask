/**
 * page-transition.js
 * A branded curtain wipe between guest pages (landing/login/signup) —
 * deliberately scoped to ONLY those pages via the presence of #page-curtain
 * in the DOM (see base.html). The authenticated app never renders the
 * curtain at all, so this script is a no-op there.
 *
 * Why the narrow scope: this overlay sits on top of the entire page. A bug
 * that left it stuck visible would be a minor annoyance on a marketing page,
 * but would make the whole app unusable if it ever happened there — not a
 * trade worth making for a decorative transition. Multiple safety nets below
 * exist so it can never get permanently stuck even on the pages it does run.
 */
(function () {
  const curtain = document.getElementById('page-curtain');
  if (!curtain) return; // authenticated app pages: nothing to do

  const Motion = window.Motion;
  const gsap = Motion && Motion.gsap;
  const reducedMotion = Motion ? Motion.reducedMotion : window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function hideInstantly() {
    curtain.style.transition = 'none';
    curtain.style.transform = 'translateY(-100%)';
    curtain.style.display = 'none';
  }

  // Safety net: no matter what else happens (a tween that never fires its
  // callback, an unexpected error elsewhere on the page), the curtain is
  // force-hidden after 2.5s so it can never block the page indefinitely.
  const safetyTimer = setTimeout(hideInstantly, 2500);

  function revealPage() {
    clearTimeout(safetyTimer);
    if (!gsap || reducedMotion) {
      hideInstantly();
      return;
    }
    gsap.to(curtain, {
      yPercent: -100,
      duration: 0.6,
      ease: 'power3.inOut',
      onComplete: () => { curtain.style.display = 'none'; },
    });
  }

  function coverAndNavigate(url) {
    if (!gsap || reducedMotion) {
      window.location.href = url;
      return;
    }
    gsap.fromTo(
      curtain,
      { yPercent: -100, display: 'block' },
      {
        yPercent: 0,
        duration: 0.45,
        ease: 'power3.in',
        onComplete: () => { window.location.href = url; },
      }
    );
  }

  // Entrance: reveal shortly after the page is interactive.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', revealPage);
  } else {
    revealPage();
  }

  // Back/forward via bfcache: Chrome/Firefox restore the page without firing
  // DOMContentLoaded again. Skip the animation entirely and just ensure the
  // curtain isn't covering anything, so the back button never feels stuck.
  window.addEventListener('pageshow', (e) => {
    if (e.persisted) hideInstantly();
  });

  // Only intercept plain left-clicks on same-origin, same-tab links that
  // aren't hash anchors (Lenis/motion-core already smooth-scrolls those),
  // mailto/tel, or downloads — everything else behaves exactly as normal.
  document.addEventListener('click', (e) => {
    if (e.defaultPrevented || e.button !== 0) return;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;

    const link = e.target.closest('a[href]');
    if (!link) return;
    if (link.target && link.target !== '_self') return;
    if (link.hasAttribute('download')) return;

    const href = link.getAttribute('href');
    if (!href || href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('tel:')) return;

    let url;
    try {
      url = new URL(href, window.location.href);
    } catch (err) {
      return;
    }
    if (url.origin !== window.location.origin) return;
    if (url.href === window.location.href) return;

    e.preventDefault();
    coverAndNavigate(url.href);
  });
})();
