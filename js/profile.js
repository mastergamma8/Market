// Скрипт для profile.html

document.addEventListener('DOMContentLoaded', () => {
  // Вычисление размера шрифта бейджа в rem
  function computeFontSize(num) {
    const base = 1.8;       // rem для 1 цифры
    const dec  = 0.6;       // вычитаем на каждую дополнительную цифру
    const digits = num.toString().length;
    return (base - (digits - 1) * dec) + 'rem';
  }

  // Обновляем нумерацию и размер шрифта бейджей
  function updateNumbering(container) {
    container.querySelectorAll('.card-wrapper[data-id]').forEach((item, idx) => {
      const badge = item.querySelector('.order-badge');
      const num = idx + 1;
      badge.textContent = num;
      badge.style.fontSize = computeFontSize(num);
    });
  }

  // SortableJS для владельца
  const sortable = document.getElementById('sortable');
  if (sortable) {
    updateNumbering(sortable);
    Sortable.create(sortable, {
      animation: 150,
      delay: 300,
      onEnd: () => {
        updateNumbering(sortable);
        const order = Array.from(sortable.querySelectorAll('.card-wrapper'))
                           .map(el => el.dataset.id);
        fetch('/update_order', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ order })
        });
      }
    });
  }

  // Для чужого профиля — просто нумеруем
  const tokensList = document.getElementById('tokensList');
  if (tokensList) updateNumbering(tokensList);

  // Превью нового аватара
  const avatarInput = document.getElementById('avatar');
  avatarInput?.addEventListener('change', e => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = ev => {
      const prev = document.getElementById('avatarPreview');
      const img = document.createElement('img');
      img.id = 'avatarPreview';
      img.src = ev.target.result;
      img.className = 'rounded-circle';
      img.style.width = '80px';
      img.style.height = '80px';
      img.style.objectFit = 'cover';
      prev.replaceWith(img);
    };
    reader.readAsDataURL(file);
  });

  // Кнопка "Наверх"
  const content   = document.querySelector('.content');
  const scrollBtn = document.getElementById('scrollToTopBtn');
  content.addEventListener('scroll', () => {
    scrollBtn.style.display = content.scrollTop > 300 ? 'flex' : 'none';
  }, { passive: true });
});

// Плавная прокрутка наверх
function scrollToTop() {
  document.querySelector('.content').scrollTo({ top: 0, behavior: 'smooth' });
}

// Кнопка "Назад"
function goBack() {
  if (document.referrer) location.href = document.referrer;
  else history.back();
}
