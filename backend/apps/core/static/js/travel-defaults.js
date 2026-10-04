/* Fahrzeiten beim Anlegen einer Stunde oder Serie aus dem Vertrag des gewählten Schülers vorbelegen.
 *
 * Läuft nur, wenn das Formular neu ist (data-travel-prefill am Vertragsfeld). Hat der Tutor eine Fahrzeit
 * selbst geändert, bleibt sie beim Wechsel des Schülers stehen. Die Standardwerte stehen als JSON im Element
 * #contract-travel-defaults (json_script), also ohne Inline-Skript. */
(function () {
  'use strict';

  function start() {
    var data = document.getElementById('contract-travel-defaults');
    var contract = document.querySelector('select[name="contract"][data-travel-prefill="true"]');
    var before = document.querySelector('input[name="travel_time_before_minutes"]');
    var after = document.querySelector('input[name="travel_time_after_minutes"]');
    if (!data || !contract || !before || !after) return;

    var defaults;
    try {
      defaults = JSON.parse(data.textContent || '{}');
    } catch (e) {
      return;
    }

    [before, after].forEach(function (field) {
      field.addEventListener('input', function () {
        field.dataset.touched = '1';
      });
    });

    contract.addEventListener('change', function () {
      var entry = defaults[contract.value];
      if (!entry) return;
      if (!before.dataset.touched) before.value = entry.before;
      if (!after.dataset.touched) after.value = entry.after;
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
