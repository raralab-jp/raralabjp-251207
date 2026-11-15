/* awai facets: opt-in analytics. No Google script or ping before consent. */
(function () {
  'use strict';
  var ID = 'G-JF02RW2R0M', KEY = 'awai.analytics-consent.v1', DAYS = 180;
  var enabled = false, banner, settings;
  function saved() {
    try { var v = JSON.parse(localStorage.getItem(KEY));
      return v && Date.now() - v.at < DAYS * 86400000 && /^(granted|denied)$/.test(v.choice) ? v.choice : null;
    } catch (_) { return null; }
  }
  function remember(choice) {
    try { localStorage.setItem(KEY, JSON.stringify({choice: choice, at: Date.now()})); } catch (_) {}
  }
  function cleanURL(value) {
    try { var u = new URL(value, location.href); return /^https?:$/.test(u.protocol) ? u.origin + u.pathname : ''; }
    catch (_) { return ''; }
  }
  function referrerOrigin() {
    try { var u = new URL(document.referrer); return /^https?:$/.test(u.protocol) ? u.origin + '/' : ''; } catch (_) { return ''; }
  }
  function clearCookies() {
    document.cookie.split(';').forEach(function (part) {
      var name = part.trim().split('=')[0];
      if (!/^_ga(?:_|$)/.test(name)) return;
      ['', '; domain=' + location.hostname, '; domain=.awaifacets.com'].forEach(function (domain) {
        document.cookie = name + '=; max-age=0; path=/' + domain + '; SameSite=Lax';
      });
    });
  }
  function start() {
    if (enabled || location.hostname !== 'awaifacets.com') return;
    enabled = true;
    window['ga-disable-' + ID] = false;
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    gtag('consent', 'default', {analytics_storage:'granted', ad_storage:'denied', ad_user_data:'denied', ad_personalization:'denied'});
    gtag('js', new Date());
    gtag('config', ID, {send_page_view:true, allow_google_signals:false, allow_ad_personalization_signals:false,
      page_location:cleanURL(location.href), page_referrer:referrerOrigin()});
    var script = document.createElement('script');
    script.async = true; script.src = 'https://www.googletagmanager.com/gtag/js?id=' + ID;
    script.referrerPolicy = 'no-referrer'; document.head.appendChild(script);
  }
  function choose(choice) {
    remember(choice); banner.hidden = true;
    if (choice === 'granted') { start(); return; }
    var wasEnabled = enabled;
    enabled = false; window['ga-disable-' + ID] = true; clearCookies();
    // Reload unloads Google listeners too; the persisted denial prevents reloading GA.
    if (wasEnabled) location.reload(); else settings.focus();
  }
  function mount() {
    var style = document.createElement('style');
    style.textContent = '#awai-analytics-choice{box-sizing:border-box;position:fixed;z-index:10000;bottom:12px;left:12px;right:12px;max-width:580px;margin:0 auto;padding:16px;background:#fff;color:#303030;border:1px solid #ddd;box-shadow:0 3px 18px #0002;border-radius:6px;font:14px/1.6 system-ui,sans-serif;text-align:left}#awai-analytics-choice[hidden]{display:none}#awai-analytics-choice p{margin:0 0 10px}#awai-analytics-choice a{color:inherit;text-decoration:underline}#awai-analytics-choice button{font:inherit;cursor:pointer;padding:8px 18px;margin:0 8px 0 0;border:1px solid #555;border-radius:3px;background:#fff;color:#303030;min-height:42px}#awai-analytics-settings{display:block;margin:16px auto;padding:6px 10px;border:0;background:transparent;color:#555;text-decoration:underline;font:12px/1.5 system-ui,sans-serif;cursor:pointer}';
    document.head.appendChild(style);
    banner = document.createElement('section'); banner.id = 'awai-analytics-choice';
    banner.setAttribute('role','region'); banner.setAttribute('aria-label','アクセス解析の設定');
    banner.innerHTML = '<p>サイト改善のため、Googleアナリティクスによるアクセス解析を利用します。許可するまで解析用Cookieの保存や解析のためのGoogleへの情報送信は行いません。<a href="/privacypolicy-jp/">プライバシーポリシー</a></p><button type="button" data-choice="denied">拒否する</button><button type="button" data-choice="granted">許可する</button>';
    banner.querySelectorAll('button').forEach(function (button) { button.addEventListener('click', function () { choose(button.dataset.choice); }); });
    settings = document.createElement('button'); settings.id='awai-analytics-settings'; settings.type='button'; settings.textContent='アクセス解析の設定';
    settings.addEventListener('click', function () { banner.hidden=false; banner.querySelector('button').focus(); });
    var footer = document.querySelector('footer'); (footer || document.body).appendChild(settings); document.body.appendChild(banner);
    var choice = saved(); banner.hidden = !!choice;
    if (choice === 'granted') start(); else { window['ga-disable-' + ID] = true; clearCookies(); }
    document.addEventListener('click', function (event) {
      if (!enabled) return;
      var a=event.target.closest && event.target.closest('a[href]'); if (!a) return;
      try { var u=new URL(a.href,location.href);
        if (u.hostname === 'shop.awaifacets.com' && u.protocol === 'https:')
          gtag('event','shop_click',{link_domain:u.hostname,link_url:u.origin+u.pathname});
      } catch (_) {}
    });
    window.addEventListener('storage',function(event){ if(event.key===KEY) location.reload(); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',mount); else mount();
})();
