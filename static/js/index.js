// static/js/index.js

$(document).ready(function(){
  // если error в URL
  const urlParams = new URLSearchParams(window.location.search);
  if(urlParams.has('error')){
    $('#errorModal').modal('show');
  }

  // toggle sort options
  $('#toggle-sort').click(function(){
    $('#sort-options').slideToggle();
    let arrow = $('#sort-arrow');
    arrow.html( arrow.html().includes('9660') ? '&#9650;' : '&#9660;' );
  });

  // сортировка
  $('.sort-btn').click(function(){
    let type = $(this).data('sort');
    $('.tab-pane.active .row').each(function(){
      let cards = $(this).children().get();
      cards.sort(function(a,b){
        let A = $(a).find('.market-card'), B = $(b).find('.market-card');
        let va = A.data(type.split('-')[0] + (type.includes('length')?'':''));
        let vb = B.data(type.split('-')[0] + (type.includes('length')?'':''));
        if(type.endsWith('asc')) return va - vb;
        else return vb - va;
      });
      $(this).append(cards);
    });
  });

  // фильтр по фону
  function getBgInfo(color){
    if(color.startsWith('/static/image/')){
      let name = color.split('/').pop().split('.')[0];
      return { type:'image', name, value:color };
    }
    const map = {/* …как в вашем коде… */};
    let name = map[color]|| (color.includes('linear-gradient')?'Gradient':color);
    return { type:'color', name, value:color };
  }
  let colors = {};
  $('.market-card').each(function(){
    let c = $(this).data('bg-color');
    if(c) colors[c] = true;
  });
  let $ul = $('#custom-bg-filter ul').empty();
  $ul.append('<li data-color=""><div class="color-circle" style="background:#fff;"></div><span>Все цвета</span></li>');
  Object.keys(colors).forEach(c=>{
    let info = getBgInfo(c);
    let circle = info.type==='image'
      ? `<div class="color-circle" style="background-image:url(${c});"></div>`
      : `<div class="color-circle" style="background:${c};"></div>`;
    $ul.append(`<li data-color="${c}">${circle}<span>${info.name}</span></li>`);
  });
  $('#custom-bg-filter .selected').click(()=> $ul.slideToggle());
  $ul.on('click','li',function(){
    let sel = $(this).data('color'), name=$(this).find('span').text();
    let circle = sel.startsWith('/static/image/')
      ? `<div class="color-circle" style="background-image:url(${sel});"></div>`
      : `<div class="color-circle" style="background:${sel||'#fff'};"></div>`;
    $('#custom-bg-filter .selected').html(circle+`<span>${name}</span>`);
    $ul.slideUp();
    $('.market-card').each(function(){
      let cardC = $(this).data('bg-color');
      $(this).closest('.col-md-6')[ sel===''||cardC===sel ? 'show' : 'hide' ]();
    });
  });

  // preview аватарки (для profile.js)
  $('#avatar').on('change',function(e){
    let file = e.target.files[0], reader=new FileReader();
    reader.onload = ev=>{
      let prev = $('#avatarPreview'), img;
      if(prev.is('img')){
        prev.attr('src',ev.target.result);
      } else {
        img = $('<img>').attr('src',ev.target.result)
          .css({width:'80px',height:'80px',objectFit:'cover'})
          .addClass('rounded-circle').attr('id','avatarPreview');
        prev.replaceWith(img);
      }
    };
    reader.readAsDataURL(file);
  });

  // кнопка Наверх
  let content = $('.content'), btn = $('#scrollToTopBtn');
  content.on('scroll',()=> btn.toggle(content.scrollTop()>300) );
});

// scrollToTop & goBack
function scrollToTop(){
  document.querySelector('.content')
    .scrollTo({ top:0, behavior:'smooth' });
}
function goBack(){
  if(document.referrer) window.location=document.referrer;
  else window.history.back();
}
