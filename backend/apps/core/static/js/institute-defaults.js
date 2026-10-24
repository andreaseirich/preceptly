/* Stundensatz und Einheitsdauer beim Anlegen eines Schülers aus dem gewählten Institut vorbelegen.
 *
 * Läuft nur, wenn das Formular neu ist (data-institute-prefill am Institutsfeld). Hat der Tutor Stundensatz oder
 * Einheitsdauer selbst geändert, bleibt der Wert beim Wechsel des Instituts stehen. Ein automatisch eingetragener
 * Wert wird zurückgesetzt, wenn das neu gewählte Institut dafür nichts vorgibt (oder "Kein Institut" gewählt
 * wird), sonst bliebe der Wert des vorigen Instituts stehen. Die Standardwerte stehen als JSON im Element
 * #institute-defaults (json_script), also ohne Inline-Skript. Die Meldung für Screenreader steht am Feld
 * (data-prefill-message). */
(function () {
  'use strict';

  function start() {
    var data = document.getElementById('institute-defaults');
    var institute = document.querySelector('select[name="institute_fk"][data-institute-prefill="true"]');
    var rate = document.querySelector('input[name="hourly_rate"]');
    var duration = document.querySelector('input[name="unit_duration_minutes"]');
    if (!data || !institute || !rate || !duration) return;

    var defaults;
    try {
      defaults = JSON.parse(data.textContent || '{}');
    } catch (e) {
      return;
    }

    // Der Hinweis muss schon im Dokument stehen, bevor er Text bekommt, sonst liest ihn ein Screenreader nicht vor.
    var status = document.createElement('p');
    status.setAttribute('role', 'status');
    status.className = 'helptext';
    status.style.margin = '4px 0 0';
    institute.insertAdjacentElement('afterend', status);

    // Wert beim Laden der Seite, auf den ein automatisch gesetzter Wert zurückfällt.
    var original = new Map([[rate, rate.value], [duration, duration.value]]);

    [rate, duration].forEach(function (field) {
      field.addEventListener('input', function () {
        field.dataset.touched = '1';
      });
    });

    // true, wenn der Wert dabei durch einen Standardwert des Instituts ersetzt wurde.
    function apply(field, value) {
      if (field.dataset.touched) return false;
      if (value) {
        field.value = value;
        field.dataset.auto = '1';
        return true;
      }
      if (field.dataset.auto) {
        field.value = original.get(field);
        delete field.dataset.auto;
      }
      return false;
    }

    institute.addEventListener('change', function () {
      var entry = defaults[institute.value] || {};
      var filledRate = apply(rate, entry.rate);
      var filledDuration = apply(duration, entry.duration);
      status.textContent =
        filledRate || filledDuration ? institute.getAttribute('data-prefill-message') || '' : '';
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
