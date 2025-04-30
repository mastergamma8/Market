document.addEventListener('DOMContentLoaded', function() {
  // Подбираем размер шрифта в зависимости от числа цифр
  function computeFontSize(number) {
    var baseSize = 1.8, decrement = 0.6;
    return (baseSize - (number.toString().length - 1) * decrement) + 'rem';
  }

  // Пронумеровать все карточки внутри заданного контейнера
  function updateNumbering(container) {
    container.querySelectorAll('.card-wrapper[data-id]').forEach(function(item, i) {
      var badge = item.querySelector('.order-badge');
      badge.textContent = i + 1;
      badge.style.fontSize = computeFontSize(i + 1);
    });
  }

  // Если это собственный профиль — инициализируем Sortable
  var sortable = document.getElementById('sortable');
  if (sortable) {
    updateNumbering(sortable);
    Sortable.create(sortable, {
      animation: 150,
      delay: 300,
      onEnd: function() {
        updateNumbering(sortable);
        var order = Array.from(sortable.querySelectorAll('.card-wrapper'))
                         .map(el => el.dataset.id);
        fetch('/update_order', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ order: order })
        });
      }
    });
  }

  // Для чужого профиля просто пронумеровать
  var tokensList = document.getElementById('tokensList');
  if (tokensList) {
    updateNumbering(tokensList);
  }

  // Превью выбранного аватара
  var avatarInput = document.getElementById('avatar');
  if (avatarInput) {
    avatarInput.addEventListener('change', function(e) {
      var file = e.target.files[0];
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function(ev) {
        var prev = document.getElementById('avatarPreview');
        if (prev.tagName === 'IMG') {
          prev.src = ev.target.result;
        } else {
          var img = document.createElement('img');
          img.src = ev.target.result;
          img.style.width = img.style.height = '80px';
          img.style.objectFit = 'cover';
          img.className = 'rounded-circle';
          prev.parentNode.replaceChild(img, prev);
          img.id = 'avatarPreview';
        }
      };
      reader.readAsDataURL(file);
    });
  }

  // Показ/скрытие кнопки "Наверх" при скролле
  var content = document.querySelector('.content'),
      scrollBtn = document.getElementById('scrollToTopBtn');
  if (content && scrollBtn) {
    content.addEventListener('scroll', function() {
      scrollBtn.style.display = content.scrollTop > 300 ? 'flex' : 'none';
    });
  }

  // ===== Добавлено для WebApp-магазина алмазов =====
if (window.Telegram && Telegram.WebApp) {
  const webApp = Telegram.WebApp;
  webApp.ready();

  document.querySelectorAll('.shop-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const diamonds = btn.dataset.diamonds;
      const price    = btn.dataset.price;

      // Показываем статус и блокируем кнопки
      const statusEl = document.getElementById('shopStatus');
      statusEl.style.display = 'block';
      document.querySelectorAll('.shop-btn').forEach(b => b.disabled = true);

      try {
        // Запрос ссылки на инвойс, теперь с двумя параметрами
        const res = await fetch('/create-invoice', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: new URLSearchParams({
            diamond_count: diamonds,
            price:          price
          })
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);

        // Открываем форму оплаты Stars
        webApp.openInvoice(data.invoiceLink, status => {
          if (status === 'paid') {
            webApp.showAlert('✅ Оплата прошла успешно!');
            $('#shopModal').modal('hide');
          } else {
            webApp.showAlert('❌ Оплата не состоялась или отменена.');
          }
        });
      } catch (err) {
        console.error(err);
        webApp.showAlert('Ошибка при создании инвойса.');
      } finally {
        statusEl.style.display = 'none';
        document.querySelectorAll('.shop-btn').forEach(b => b.disabled = false);
      }
    });
  });
}

// ===== Новый блок: перехват форм swap49 =====
document.querySelectorAll('.swap49-form').forEach(form => {
  form.addEventListener('submit', async e => {
    e.preventDefault();
    const data = new FormData(form);
    try {
      const res = await fetch('/swap49', {
        method: 'POST',
        body: data,
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      });

      if (res.ok) {
        const json = await res.json();
        if (json.success) {
          // Скрываем ту модалку, где была форма
          $(form).closest('.modal').modal('hide');
          // Обновляем баланс в шапке
          document.querySelector('#balanceValue').textContent = json.new_balance + ' 💎';
          // Показываем окно успеха
          $('#swapSuccessModal').modal('show');
        } else {
          // Если success=false
          $('#swapErrorModal').modal('show');
        }
      } else {
        // Ошибочный статус (400, 403 и пр.)
        $(form).closest('.modal').modal('hide');
        $('#swapErrorModal').modal('show');
      }
    } catch (err) {
      console.error('Ошибка при swap49:', err);
      // При исключении тоже скрываем текущую модалку и показываем ошибку
      $(form).closest('.modal').modal('hide');
      $('#swapErrorModal').modal('show');
    }
  });
});

}); // конец DOMContentLoaded

// Плавная прокрутка вверх
function scrollToTop() {
  document.querySelector('.content')
          .scrollTo({ top: 0, behavior: 'smooth' });
}

// Кнопка "Назад"
function goBack() {
  if (document.referrer) {
    window.location = document.referrer;
  } else {
    window.history.back();
  }
}
