// On every link to kitomba.com (booking and voucher links): fires the GA4 book_now_click event,
// the "Book Now click to Kitomba" Google Ads conversion and the Meta "Schedule" pixel event.
document.addEventListener('DOMContentLoaded', function () {
  var links = document.querySelectorAll('a[href*="kitomba.com"]');
  links.forEach(function (link) {
    link.addEventListener('click', function (event) {
      if (typeof fbq === 'function') {
        fbq('track', 'Schedule');
      }

      if (typeof gtag !== 'function') {
        return;
      }

      var ga4Ready = typeof GA4_MEASUREMENT_ID === 'string' && GA4_MEASUREMENT_ID.indexOf('G-') === 0;
      if (ga4Ready) {
        gtag('event', 'book_now_click', {
          send_to: GA4_MEASUREMENT_ID,
          link_url: link.href,
          page_path: window.location.pathname,
          transport_type: 'beacon'
        });
      }

      var href = link.href;
      var target = link.target;
      var navigated = false;

      var navigate = function () {
        if (navigated) {
          return;
        }
        navigated = true;
        if (target !== '_blank') {
          window.location.href = href;
        }
      };

      if (target !== '_blank') {
        event.preventDefault();
      }

      gtag('event', 'conversion', {
        send_to: 'AW-976595232/YeIkCKyF5_UcEKDS1tED',
        event_callback: navigate,
        event_timeout: 300
      });

      setTimeout(navigate, 300);
    });
  });
});
