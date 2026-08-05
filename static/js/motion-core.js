/**
 * motion-core.js
 * Site-wide animation bootstrap: Lenis smooth scroll + GSAP/ScrollTrigger,
 * wired together and exposed as `window.Motion` for page-specific scripts
 * (e.g. the hero timeline) to reuse instead of re-initializing anything.
 *
 * Loaded once, on every page, via base.html. Individual pages should only
 * ever call into `Motion.*` — they should not create their own Lenis or
 * gsap.ticker instances.
 */
(function () {
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const Motion = {
    gsap: window.gsap || null,
    ScrollTrigger: window.ScrollTrigger || null,
    lenis: null,
    reducedMotion: prefersReducedMotion,
  };

  if (Motion.gsap && Motion.ScrollTrigger) {
    Motion.gsap.registerPlugin(Motion.ScrollTrigger);
    Motion.gsap.defaults({ ease: 'power3.out', duration: 0.8 });
  }

  // --- Smooth scroll (Lenis) ---------------------------------------------
  // Skipped entirely under reduced-motion: native scrolling stays instant/jumpy
  // (as the user's OS setting requests) instead of being smoothed.
  if (!prefersReducedMotion && window.Lenis) {
    const lenis = new window.Lenis({
      duration: 1.1,
      easing: (t) => 1 - Math.pow(1 - t, 3),
      smoothWheel: true,
    });

    if (Motion.gsap) {
      Motion.gsap.ticker.add((time) => lenis.raf(time * 1000));
      Motion.gsap.ticker.lagSmoothing(0);
    } else {
      const raf = (time) => {
        lenis.raf(time);
        requestAnimationFrame(raf);
      };
      requestAnimationFrame(raf);
    }

    if (Motion.ScrollTrigger) {
      lenis.on('scroll', Motion.ScrollTrigger.update);
    }

    Motion.lenis = lenis;
  }

  // --- Smooth anchor scrolling, site-wide ---------------------------------
  document.addEventListener('click', (e) => {
    const link = e.target.closest('a[href^="#"]');
    if (!link) return;
    const targetId = link.getAttribute('href');
    if (targetId.length <= 1) return;
    const target = document.querySelector(targetId);
    if (!target) return;
    e.preventDefault();
    if (Motion.lenis) {
      Motion.lenis.scrollTo(target, { offset: -16 });
    } else {
      target.scrollIntoView({ behavior: prefersReducedMotion ? 'auto' : 'smooth', block: 'start' });
    }
  });

  // --- Generic scroll-reveal, attribute-driven ----------------------------
  // Any element can opt in with data-reveal (no per-page JS needed):
  //   data-reveal              -> fade + slide up when scrolled into view
  //   data-reveal="left"|"right" -> fade + slide in from that side
  //   data-reveal-delay="120"  -> stagger offset in ms
  Motion.initReveal = function initReveal(root = document) {
    const els = root.querySelectorAll('[data-reveal]');
    if (!els.length) return;

    if (prefersReducedMotion || !Motion.gsap || !Motion.ScrollTrigger) {
      els.forEach((el) => el.classList.add('reveal-visible'));
      return;
    }

    els.forEach((el) => {
      const direction = el.getAttribute('data-reveal');
      const delay = parseInt(el.getAttribute('data-reveal-delay') || '0', 10) / 1000;
      const fromVars = { opacity: 0, y: 28 };
      if (direction === 'left') { fromVars.y = 0; fromVars.x = -32; }
      if (direction === 'right') { fromVars.y = 0; fromVars.x = 32; }

      Motion.gsap.fromTo(
        el,
        fromVars,
        {
          opacity: 1,
          x: 0,
          y: 0,
          delay,
          duration: 0.9,
          ease: 'power3.out',
          scrollTrigger: {
            trigger: el,
            start: 'top 85%',
            once: true,
          },
        }
      );
    });
  };

  // --- Generic magnetic pull, attribute-driven ----------------------------
  // Any element can opt in with data-magnetic (optionally data-magnetic="0.4"
  // for pull strength, default 0.35): it nudges toward the cursor on hover
  // and springs back on leave. Skipped on touch/coarse pointers (there's no
  // hover there) and under reduced-motion.
  Motion.initMagnetic = function initMagnetic(root = document) {
    if (prefersReducedMotion || !Motion.gsap) return;
    if (!window.matchMedia('(pointer: fine)').matches) return;

    root.querySelectorAll('[data-magnetic]').forEach((el) => {
      const strength = parseFloat(el.getAttribute('data-magnetic')) || 0.35;
      const xTo = Motion.gsap.quickTo(el, 'x', { duration: 0.5, ease: 'power3.out' });
      const yTo = Motion.gsap.quickTo(el, 'y', { duration: 0.5, ease: 'power3.out' });

      el.addEventListener('mousemove', (e) => {
        const rect = el.getBoundingClientRect();
        xTo((e.clientX - (rect.left + rect.width / 2)) * strength);
        yTo((e.clientY - (rect.top + rect.height / 2)) * strength);
      });
      el.addEventListener('mouseleave', () => {
        xTo(0);
        yTo(0);
      });
    });
  };

  window.Motion = Motion;

  document.addEventListener('DOMContentLoaded', () => {
    Motion.initReveal();
    Motion.initMagnetic();
  });
})();
