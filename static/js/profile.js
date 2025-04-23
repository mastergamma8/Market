// static/js/profile.js

document.addEventListener('DOMContentLoaded', function() {

  // Вычисление размера шрифта для порядкового номера
  function computeFontSize(number) {
    var baseSize = 1.8;   // rem
    var decrement = 0.6;  // rem per extra digit
    var digits = number.toString().length;
    return (baseSize - (digits - 1) * decrement) + 'rem';
  }

  // Обновление нумерации карточек
  function updateNumbering(container) {
    var items = container.querySelectorAll('.card-wrapper[data-id]');
    items.forEach(function(item, index) {
      var badge = item.querySelector('.order-badge');
      if (badge) {
        badge.textContent = index + 1;
        badge.style.fontSize = computeFontSize(index + 1);
      }
    });
  }

  // Sortable для своего профиля
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
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({order: order})
        });
      }
    });
  }

  // Просто нумерация для чужого профиля
  var tokensList = document.getElementById('tokensList');
  if (tokensList) {
    updateNumbering(tokensList);
  }

  // Превью для выбора аватарки
  var avatarInput = document.getElementById('avatar');
  if (avatarInput) {
    avatarInput.addEventListener('change', function(e) {
      var file = e.target.files[0];
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function(ev) {
        var prev = document.getElementById('avatarPreview');
        if (prev.tagName.toLowerCase() === 'img') {
          prev.src = ev.target.result;
        } else {
          var img = document.createElement('img');
          img.src = ev.target.result;
          img.style.width = '80px';
          img.style.height = '80px';
          img.style.objectFit = 'cover';
          img.className = 'rounded-circle';
          prev.parentNode.replaceChild(img, prev);
          img.id = 'avatarPreview';
        }
      };
      reader.readAsDataURL(file);
    });
  }

  // Показ кнопки "Наверх"
  var content = document.querySelector('.content');
  var scrollBtn = document.getElementById('scrollToTopBtn');
  content.addEventListener('scroll', function() {
    scrollBtn.style.display = content.scrollTop > 300 ? 'flex' : 'none';
  });

});

// Плавная прокрутка наверх
function scrollToTop() {
  document.querySelector('.content')
          .scrollTo({top: 0, behavior: 'smooth'});
}

// Кнопка "Назад"
function goBack() {
  if (document.referrer) window.location = document.referrer;
  else window.history.back();
}
