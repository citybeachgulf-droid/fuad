document.addEventListener('DOMContentLoaded', function () {
  // Testimonials simple submit animation feedback
  const form = document.getElementById('testimonial-form');
  if (form) {
    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      const btn = form.querySelector('[type="submit"]');
      const original = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>جاري الإرسال...';

      const payload = {
        name: form.name?.value?.trim() || document.getElementById('name')?.value?.trim(),
        property_type: form.property_type?.value || document.getElementById('property_type')?.value || '',
        rating: form.rating?.value || document.getElementById('rating')?.value || '',
        experience: form.experience?.value?.trim() || document.getElementById('experience')?.value?.trim(),
      };

      try {
        const res = await fetch('/api/testimonials', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (!res.ok) throw new Error('failed');
        const data = await res.json();

        // Prepend the new testimonial to the list if exists
        const list = document.getElementById('testimonials-list');
        if (list) {
          const col = document.createElement('div');
          col.className = 'col-md-4 text-center';
          col.innerHTML = `
            <blockquote class="blockquote">
              <p>${(data.body || '').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</p>
              <footer class="blockquote-footer">${(data.name || '').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</footer>
            </blockquote>
          `;
          list.prepend(col);
          // remove empty-state alert if present
          const alert = list.querySelector('.alert');
          if (alert) alert.parentElement?.remove();
        }

        btn.classList.add('btn-success');
        btn.innerHTML = 'تم الإرسال ✓';
        form.reset();
      } catch (err) {
        btn.classList.add('btn-danger');
        btn.innerHTML = 'فشل الإرسال';
      } finally {
        setTimeout(() => {
          btn.classList.remove('btn-success', 'btn-danger');
          btn.disabled = false;
          btn.innerHTML = original;
        }, 1800);
      }
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

