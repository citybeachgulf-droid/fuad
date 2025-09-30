document.addEventListener('DOMContentLoaded', function () {
  // Testimonials simple submit animation feedback
  const form = document.getElementById('testimonial-form');
  if (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      const btn = form.querySelector('[type="submit"]');
      const original = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>جاري الإرسال...';
      setTimeout(() => {
        btn.classList.add('btn-success');
        btn.innerHTML = 'تم الإرسال ✓';
        form.reset();
        setTimeout(() => {
          btn.classList.remove('btn-success');
          btn.disabled = false;
          btn.innerHTML = original;
        }, 1800);
      }, 1200);
    });
  }

  // Property type toggle visual feedback
  document.querySelectorAll('[data-property-type]').forEach(function (el) {
    el.addEventListener('click', function () {
      const parent = el.closest('.btn-group');
      if (!parent) return;
      parent.querySelectorAll('input[type="radio"]').forEach((inp) => inp.checked = false);
      const input = el.querySelector('input[type="radio"]');
      if (input) input.checked = true;
    });
  });

});

