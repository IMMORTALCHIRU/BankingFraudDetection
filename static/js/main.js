/* ============================================================
   BankGuard — Main JS
   ============================================================ */

// ─── Toggle Password Visibility ───
function togglePassword(inputId, btn) {
  const input = document.getElementById(inputId);
  if (!input) return;
  const isHidden = input.type === 'password';
  input.type = isHidden ? 'text' : 'password';
  const icon = btn.querySelector('i');
  if (icon) {
    icon.className = isHidden ? 'bi bi-eye-slash' : 'bi bi-eye';
  }
}

// ─── Animated Counter ───
function animateCounters() {
  document.querySelectorAll('.counter[data-target]').forEach(el => {
    const target = parseFloat(el.dataset.target);
    if (isNaN(target)) return;
    const duration = 1400;
    const start = performance.now();
    const isDecimal = target % 1 !== 0;
    function step(now) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const ease = 1 - Math.pow(1 - progress, 4);
      const current = target * ease;
      el.textContent = isDecimal ? current.toFixed(1) : Math.round(current).toLocaleString();
      if (progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  });
}

// ─── Navbar Scroll Effect ───
function initNavbarScroll() {
  const navbar = document.querySelector('.bfd-navbar');
  if (!navbar) return;
  function updateNavbar() {
    if (window.scrollY > 20) navbar.classList.add('scrolled');
    else navbar.classList.remove('scrolled');
  }
  window.addEventListener('scroll', updateNavbar, { passive: true });
  updateNavbar();
}

// ─── Auto-dismiss Toasts ───
function initToasts() {
  document.querySelectorAll('.toast').forEach(toastEl => {
    const toast = new bootstrap.Toast(toastEl, { delay: 5000 });
    toast.show();
  });
}

// ─── Intersection Observer for Counters ───
function initCounterObserver() {
  const counters = document.querySelectorAll('.counter[data-target]');
  if (!counters.length) return;
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        animateCounters();
        observer.disconnect();
      }
    });
  }, { threshold: 0.3 });
  counters.forEach(c => observer.observe(c));
}

// ─── Smooth Scroll for anchor links ───
function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach(a => {
    a.addEventListener('click', e => {
      const target = document.querySelector(a.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });
}

// ─── Init ───
document.addEventListener('DOMContentLoaded', () => {
  initNavbarScroll();
  initToasts();
  initCounterObserver();
  initSmoothScroll();
});
