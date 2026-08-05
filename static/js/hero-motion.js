/**
 * hero-motion.js
 * Landing-page-only entrance timeline for the hero section. Built entirely
 * on top of window.Motion (from motion-core.js) — it does not create its
 * own GSAP/ScrollTrigger/Lenis instances.
 *
 * Safe by default: if GSAP failed to load, or the visitor has asked for
 * reduced motion, this does nothing and the hero simply renders in its
 * normal static (fully visible) state — nothing here can leave content
 * stuck hidden.
 */
(function () {
  const Motion = window.Motion;
  if (!Motion || !Motion.gsap || Motion.reducedMotion) return;

  const gsap = Motion.gsap;

  const nav = document.getElementById('hero-nav');
  const badge = document.getElementById('hero-badge');
  const headline = document.getElementById('hero-headline');
  const subtext = document.getElementById('hero-subtext');
  const ctas = document.getElementById('hero-ctas');
  const note = document.getElementById('hero-note');
  const illustration = document.getElementById('hero-illustration');
  const orbit1 = document.getElementById('hero-orbit-1');
  const orbit2 = document.getElementById('hero-orbit-2');
  const blob = document.getElementById('hero-blob');
  const floats = illustration ? illustration.querySelectorAll('.hero-float') : [];

  if (!headline) return; // not on the landing page

  // Split the headline into per-word spans for a staggered reveal.
  const words = headline.textContent.trim().split(/\s+/);
  headline.innerHTML = words
    .map((w) => `<span class="inline-block will-change-transform">${w}</span>`)
    .join(' ');
  const headlineWords = headline.querySelectorAll('span');

  const tl = gsap.timeline({ defaults: { ease: 'power3.out' } });

  tl.set([nav, badge, subtext, ctas.children, note, orbit1, orbit2, blob], { opacity: 0 })
    .set(headlineWords, { opacity: 0, y: 26 })
    .set(nav, { y: -16 })
    .set(badge, { y: 10, scale: 0.9 })
    .set(subtext, { y: 16 })
    .set(ctas.children, { y: 16 })
    .set(note, { y: 10 })
    .set([orbit1, orbit2], { scale: 0.7, rotate: -20 })
    .set(blob, { scale: 0.4 })
    .set(floats, { opacity: 0, scale: 0.5, y: 12 });

  tl.to(nav, { opacity: 1, y: 0, duration: 0.55 }, 0)
    .to(badge, { opacity: 1, y: 0, scale: 1, duration: 0.5 }, 0.15)
    .to(headlineWords, { opacity: 1, y: 0, duration: 0.6, stagger: 0.06 }, 0.3)
    .to(subtext, { opacity: 1, y: 0, duration: 0.6 }, 0.55)
    .to(ctas.children, { opacity: 1, y: 0, duration: 0.5, stagger: 0.1 }, 0.68)
    .to(note, { opacity: 1, y: 0, duration: 0.5 }, 0.85)
    // Illustration comes in slightly after the text column starts, for a
    // layered feel rather than everything landing at once.
    .to([orbit1, orbit2], {
      opacity: 1, scale: 1, rotate: 0, duration: 1, stagger: 0.12, ease: 'power2.out',
      onComplete: () => { orbit1.classList.add('orbit'); orbit2.classList.add('orbit-reverse'); },
    }, 0.35)
    .to(blob, {
      opacity: 1, scale: 1, duration: 0.7, ease: 'back.out(1.6)',
      onComplete: () => blob.classList.add('blob-pulse'),
    }, 0.5)
    .to(floats, {
      opacity: 1, scale: 1, y: 0, duration: 0.6, stagger: 0.12, ease: 'back.out(1.7)',
    }, 0.75)
    .call(() => {
      // Hand off to the continuous CSS bob only after each badge's own
      // pop-in has settled, so GSAP's transform isn't fighting the keyframe.
      floats.forEach((el, i) => {
        gsap.delayedCall(i * 0.12, () => el.classList.add('float-badge'));
      });
    }, [], 0.75 + 0.6);

  // Subtle scroll parallax: the illustration drifts slightly slower than
  // the page as the hero scrolls away, giving the layout a sense of depth.
  const heroSection = document.getElementById('hero');
  if (Motion.ScrollTrigger && illustration) {
    gsap.to(illustration, {
      y: 60,
      ease: 'none',
      scrollTrigger: {
        trigger: heroSection,
        start: 'top top',
        end: 'bottom top',
        scrub: true,
      },
    });
  }

  // Cursor-reactive 3D tilt: the whole illustration leans gently toward the
  // pointer anywhere in the hero section. Skipped on touch devices (there's
  // no hover/cursor there) — the illustration just stays static, which is
  // the correct behavior on mobile anyway.
  if (heroSection && illustration && window.matchMedia('(pointer: fine)').matches) {
    gsap.set(illustration, { transformPerspective: 800 });
    const rotateX = gsap.quickTo(illustration, 'rotateX', { duration: 0.6, ease: 'power3.out' });
    const rotateY = gsap.quickTo(illustration, 'rotateY', { duration: 0.6, ease: 'power3.out' });

    heroSection.addEventListener('mousemove', (e) => {
      const rect = heroSection.getBoundingClientRect();
      const px = (e.clientX - rect.left) / rect.width - 0.5;
      const py = (e.clientY - rect.top) / rect.height - 0.5;
      rotateY(px * 10);
      rotateX(-py * 10);
    });
    heroSection.addEventListener('mouseleave', () => {
      rotateX(0);
      rotateY(0);
    });
  }
})();
