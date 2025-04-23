// static/js/index.js

$(function(){
  // Показ ошибки из URL
  const params = new URLSearchParams(location.search);
  if(params.has('error')) $('#errorModal').modal('show');

  // Toggle сортировки
  $('#toggle-sort').click(function(){
    $('#sort-options').slideToggle();
    const arrow = $('#sort-arrow');
    arrow.html( arrow.html()==='▼'?'&#9650;':'&#9660;' );
  });

  // Сортировка карточек
  $('.sort-btn').click(function(){
    const type = $(this).data('sort');
    $('.tab-pane.active .row').each(function(){
      const cards = $(this).children().get();
      cards.sort((a,b)=>{
        const A=$(a).find('.market-card'), B=$(b).find('.market-card');
        let va, vb;
        switch(type){
          case 'token-length-asc':
            va=A.data('token-length'); vb=B.data('token-length'); return va-vb;
          case 'repeats-desc':
            va=A.data('repeats'); vb=B.data('repeats'); return vb-va;
          case 'bg-rarity-asc':
            va=A.data('bg-rarity'); vb=B.data('bg-rarity'); return va-vb;
          case 'price-asc':
            va=A.data('price'); vb=B.data('price'); return va-vb;
          case 'price-desc':
            va=A.data('price'); vb=B.data('price'); return vb-va;
        }
      });
      $(this).append(cards);
    });
  });

  // Фильтр по bg-color
  const colors = {};
  $('.market-card').each(function(){
    colors[$(this).data('bg-color')] = true;
  });
  const $ul = $('#custom-bg-filter ul').empty();
  $ul.append('<li data-color=""><div class="color-circle" style="background:#fff"></div><span>Все цвета</span></li>');
  Object.keys(colors).forEach(c=>{
    $ul.append(`<li data-color="${c}"><div class="color-circle" style="background:${c}"></div><span>${c}</span></li>`);
  });
  $('#custom-bg-filter .selected').click(()=> $ul.slideToggle());
  $ul.on('click','li',function(){
    const sel=$(this).data('color'), name=$(this).text();
    $('#custom-bg-filter .selected').html(`<div class="color-circle" style="background:${sel||'#fff'}"></div><span>${name}</span>`);
    $ul.slideUp();
    $('.market-card').closest('div.col-md-6').toggle(sel===''||$(this).data('color')===sel);
  });

  // Показ кнопки «Наверх»
  const content=$('.content'), scrollBtn=$('#scrollToTopBtn');
  content.on('scroll',()=> scrollBtn.toggle(content.scrollTop()>300));
});

// Поиск токена
function redirectToToken(e){
  e.preventDefault();
  const t = $('#tokenNumberInput').val().trim();
  if(t) location.href = '/token/'+encodeURIComponent(t);
  return false;
}

// Плавная прокрутка наверх
function scrollToTop(){
  $('.content').animate({scrollTop:0}, 'slow');
}

// Кнопка «Назад»
function goBack(){
  if(document.referrer) location=document.referrer;
  else history.back();
}
