/**
 * app-motion.js
 * The authenticated app's GSAP layer — dashboard, books, members, issue,
 * return, transactions, import, settings. Everything here is a no-op on
 * guest pages (landing/login/signup), since #app-main only exists in the
 * logged-in shell.
 *
 * Safe by construction: if GSAP failed to load, or reduced-motion is on,
 * this returns immediately and the CSS fallback in base.html (scoped to
 * html.no-js) is what actually ends up rendering — never both at once,
 * and never neither.
 */
(function () {
  const appMain = document.getElementById('app-main');
  if (!appMain) return; // guest pages

  const Motion = window.Motion;
  if (!Motion || !Motion.gsap || Motion.reducedMotion) return;

  const gsap = Motion.gsap;

  function run() {
    // Top-level sections of the page (flash messages, stat grids, panels,
    // forms) cascade in together — replaces the CSS nth-child stagger with
    // a slightly livelier scale+fade version.
    const sections = Array.from(appMain.children);
    if (sections.length) {
      gsap.set(sections, { opacity: 0, y: 20, scale: 0.98 });
      gsap.to(sections, {
        opacity: 1, y: 0, scale: 1, duration: 0.55, stagger: 0.09, ease: 'power3.out',
      });
    }

    // Table rows reveal as they actually scroll into view, rather than all
    // animating on load regardless of whether they're visible yet — this
    // matters once a Books/Members/Transactions list runs long.
    if (Motion.ScrollTrigger) {
      appMain.querySelectorAll('tbody').forEach((tbody) => {
        const rows = tbody.querySelectorAll('tr');
        if (!rows.length) return;
        gsap.set(rows, { opacity: 0, y: 14 });
        Motion.ScrollTrigger.batch(rows, {
          start: 'top 95%',
          once: true,
          onEnter: (batch) => gsap.to(batch, {
            opacity: 1, y: 0, duration: 0.4, stagger: 0.05, ease: 'power2.out',
          }),
        });
      });
    }

    // Dashboard stat cards: a bouncier pop-in, plus a gentle cursor-tilt on
    // hover so the app's flagship page doesn't feel flatter than the
    // marketing site it's selling.
    const stats = appMain.querySelectorAll('.stat-card');
    if (stats.length) {
      gsap.set(stats, { opacity: 0, y: 24, scale: 0.92 });
      gsap.to(stats, {
        opacity: 1, y: 0, scale: 1, duration: 0.6, stagger: 0.1, delay: 0.05, ease: 'back.out(1.6)',
      });

      if (window.matchMedia('(pointer: fine)').matches) {
        stats.forEach((card) => {
          gsap.set(card, { transformPerspective: 600 });
          const rotateX = gsap.quickTo(card, 'rotateX', { duration: 0.4, ease: 'power3.out' });
          const rotateY = gsap.quickTo(card, 'rotateY', { duration: 0.4, ease: 'power3.out' });
          const liftY = gsap.quickTo(card, 'y', { duration: 0.4, ease: 'power3.out' });

          card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const px = (e.clientX - rect.left) / rect.width - 0.5;
            const py = (e.clientY - rect.top) / rect.height - 0.5;
            rotateY(px * 8);
            rotateX(-py * 8);
            liftY(-4);
          });
          card.addEventListener('mouseleave', () => {
            rotateX(0);
            rotateY(0);
            liftY(0);
          });
        });
      }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run);
  } else {
    run();
  }
})();
