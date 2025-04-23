// static/js/tth.js
$(function(){
  // 1) Показ ошибки по ?error
  const params = new URLSearchParams(window.location.search);
  if (params.has('error')) {
    $('#errorModal').modal('show');
  }

  // 2) Toggle сортировки
  $('#toggle-sort').on('click', function(){
    $('#sort-options').slideToggle();
    const arrow = $('#sort-arrow');
    arrow.text( arrow.text()==='▼' ? '▲' : '▼' );
  });

  // 3) Сортировка карточек
  $('.sort-btn').on('click', function(){
    const sortType = $(this).data('sort');
    const activeRow = $('.tab-pane.show.active .row');
    const cards = activeRow.children('.col-md-6').get();
    cards.sort((a,b) => {
      const aC = $(a).find('.market-card'),
            bC = $(b).find('.market-card');
      let aVal, bVal;
      switch(sortType) {
        case 'token-length-asc':
          aVal = +aC.data('token-length'); bVal = +bC.data('token-length');
          return aVal - bVal;
        case 'repeats-desc':
          aVal = +aC.data('repeats'); bVal = +bC.data('repeats');
          return bVal - aVal;
        case 'bg-rarity-asc':
          aVal = +aC.data('bg-rarity'); bVal = +bC.data('bg-rarity');
          return aVal - bVal;
        case 'price-asc':
          aVal = +aC.data('price'); bVal = +bC.data('price');
          return aVal - bVal;
        case 'price-desc':
          aVal = +aC.data('price'); bVal = +bC.data('price');
          return bVal - aVal;
      }
    });
    $.each(cards, (_,el)=> activeRow.append(el));
  });

  // 4) Ленивый фон через IntersectionObserver
  const lazyBgElems = document.querySelectorAll('.lazy-bg');
  if ('IntersectionObserver' in window) {
    let bgObserver = new IntersectionObserver((entries, io) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const el = entry.target;
          el.style.background = `url(${el.dataset.bgSrc}) no-repeat center/cover`;
          el.style.backgroundSize = 'cover';
          io.unobserve(el);
        }
      });
    }, {rootMargin: '100px'});
    lazyBgElems.forEach(el => bgObserver.observe(el));
  } else {
    lazyBgElems.forEach(el => {
      el.style.background = `url(${el.dataset.bgSrc}) no-repeat center/cover`;
      el.style.backgroundSize = 'cover';
    });
  }

  // 5) Фильтр по фону
  function getBgInfo(color) {
    const isImg = color.startsWith('/static/image/');
    if (isImg) {
      const name = color.split('/').pop().split('.')[0];
      return {type:'image', name, value:color};
    } else {
      return {type:'color', name:color, value:color};
    }
  }
  const colors = {};
  $('.market-card').each(function(){
    colors[$(this).data('bg-color')] = true;
  });
  const $ul = $('#custom-bg-filter ul').empty()
    .append('<li data-color=""><div class="color-circle" style="background:#fff;"></div><span>Все цвета</span></li>');
  Object.keys(colors).forEach(c => {
    const info = getBgInfo(c);
    $ul.append(
      `<li data-color="${info.value}">
         <div class="color-circle" style="${info.type==='image'?
           `background-image:url(${info.value});`:`background:${info.value};`}"></div>
         <span>${info.name}</span>
       </li>`
    );
  });
  $('#custom-bg-filter .selected').click(()=> $ul.slideToggle());
  $ul.on('click','li',function(){
    const sel = $(this).data('color'), name = $(this).find('span').text();
    $('#custom-bg-filter .selected').html(
      `<div class="color-circle" style="${sel?`background:${sel};`:`background:#fff;`}"></div><span>${name}</span>`
    );
    $ul.slideUp();
    $('.market-card').each(function(){
      const col = $(this).closest('.col-md-6');
      ($(this).data('bg-color')===sel || !sel) ? col.show() : col.hide();
    });
  });

  // 6) Redirect для поиска
  window.redirectToToken = function(e) {
    e.preventDefault();
    const v = $('#tokenNumberInput').val().trim();
    if (v) window.location = '/token/'+encodeURIComponent(v);
  };

  // 7) Плавная прокрутка вверх
  const content = document.querySelector('.content'),
        scrollBtn = $('#scrollToTopBtn');
  content.addEventListener('scroll', ()=> scrollBtn.toggle(content.scrollTop>300));
  window.scrollToTop = ()=> content.scrollTo({top:0, behavior:'smooth'});
});
