// Navigation only: choosing a solution never starts training or provider calls.
export function connectPlatform({view}) {
  const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const reveal = target => document.getElementById(target)?.scrollIntoView({behavior:reducedMotion()?'instant':'smooth',block:'start'});
  document.querySelectorAll('[data-route]').forEach(button => {
    button.addEventListener('click',()=>{
      view(button.dataset.route);
      const algorithm=document.getElementById('trainingAlgorithm');
      if(button.dataset.algorithm && !algorithm.disabled) {
        const mode=document.getElementById('trainingMode');
        mode.value='new'; mode.dispatchEvent(new Event('change',{bubbles:true}));
        algorithm.value=button.dataset.algorithm; algorithm.dispatchEvent(new Event('change',{bubbles:true}));
      }
      if(button.dataset.target) reveal(button.dataset.target);
      else window.scrollTo({top:0,behavior:reducedMotion()?'instant':'smooth'});
      const heading=document.getElementById(button.dataset.target) || document.getElementById('pageTitle');
      heading?.setAttribute('tabindex','-1'); heading?.focus({preventScroll:true});
    });
  });
  document.querySelectorAll('[data-scroll]').forEach(button => button.addEventListener('click',()=>{
    reveal(button.dataset.scroll);
    const target=document.getElementById(button.dataset.scroll);
    target?.setAttribute('tabindex','-1'); target?.focus({preventScroll:true});
    if(button.hasAttribute('data-play-video')) target?.querySelector('video')?.play().catch(()=>{});
  }));
}
