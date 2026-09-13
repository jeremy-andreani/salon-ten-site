// Fires the "Book Now click to Kitomba" Google Ads conversion on every link to kitomba.com.
document.addEventListener('DOMContentLoaded', function () {
  var links = document.querySelectorAll('a[href*="kitomba.com"]');
  links.forEach(function (link) {
    link.addEventListener('click', function (event) {
      if (typeof gtag !== 'function') {
        return;
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
