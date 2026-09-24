/*
 * Aktionen ohne Inline-Eventhandler.
 *
 * Die Content-Security-Policy lässt Skripte nur noch mit Nonce zu. Handler im
 * HTML (onclick="…", onsubmit="…", href="javascript:…") können keine Nonce
 * tragen und werden blockiert. Stattdessen beschreiben Elemente ihre Aktion in
 * Daten-Attributen, und dieses Skript lauscht einmal am Dokument:
 *
 *   data-click="setTool"        data-click-args='["pen"]'
 *   data-click="switchTab"      data-click-args='["chat", "$el"]'
 *   data-change="jumpToDate"    data-change-args='["$value"]'
 *   data-mouseover="showPreview" data-mouseover-args='["$el", "$event"]'
 *   data-mouseout="hidePreview"
 *
 * Platzhalter in den Argumenten: "$el" = das Element (bisher `this`),
 * "$event" = das Ereignis, "$value" = el.value. Aufgerufen werden globale
 * Funktionen (window.name) — dieselbe Voraussetzung wie bei Inline-Handlern.
 * Gibt die Funktion bei einem Klick `false` zurück, wird die Standardaktion
 * unterbunden, wie früher bei `onclick="return fn()"`.
 *
 * Eingebaute Aktionen ohne eigene Funktion:
 *   data-confirm="Text"       Formular: vor dem Absenden nachfragen
 *   data-autosubmit           Auswahlfeld: bei Änderung Formular abschicken
 *   data-href="/pfad/"        Klick navigiert dorthin
 *   data-history-back         Link: eine Seite zurück; das echte href bleibt als Rückfall
 *   data-close-dialog="id"    schließt <dialog id="…">
 *   data-select-on-click      markiert den Inhalt des Eingabefelds
 *   data-copy-from="id"       kopiert den Wert von #id in die Zwischenablage
 *   data-remove-closest="tr"  entfernt das nächste passende Elternelement
 *   data-stop-propagation     Klick hier löst die Aktion eines umgebenden Elements
 *                             nicht aus (Links darin funktionieren normal)
 *
 * Maßgeblich ist immer das nächstgelegene Element mit einer Aktion — so wie ein
 * Inline-Handler mit event.stopPropagation() verhindert hat, dass auch das
 * umgebende Element reagiert. Weil nur am Dokument gelauscht wird, gelten die
 * Attribute auch für Elemente, die erst später per JavaScript entstehen.
 */
(function () {
    "use strict";

    var CLICK_SELECTOR = [
        "[data-click]",
        "[data-href]",
        "[data-history-back]",
        "[data-close-dialog]",
        "[data-select-on-click]",
        "[data-copy-from]",
        "[data-remove-closest]",
        "[data-stop-propagation]",
    ].join(",");

    function resolveArgs(el, event, kind) {
        var raw = el.getAttribute("data-" + kind + "-args");
        if (!raw) return [];
        var args;
        try {
            args = JSON.parse(raw);
        } catch (err) {
            console.error("data-" + kind + "-args ist kein gültiges JSON:", raw);
            return null;
        }
        if (!Array.isArray(args)) args = [args];
        return args.map(function (arg) {
            if (arg === "$el") return el;
            if (arg === "$event") return event;
            if (arg === "$value") return el.value;
            return arg;
        });
    }

    function invoke(el, kind, event) {
        var name = el.getAttribute("data-" + kind);
        var fn = window[name];
        if (typeof fn !== "function") {
            console.error("data-" + kind + ': Funktion "' + name + '" nicht gefunden');
            return undefined;
        }
        var args = resolveArgs(el, event, kind);
        if (args === null) return undefined;
        return fn.apply(el, args);
    }

    function closestFrom(event, selector) {
        var target = event.target;
        if (!(target instanceof Element)) target = target && target.parentElement;
        return target ? target.closest(selector) : null;
    }

    document.addEventListener("click", function (event) {
        var el = closestFrom(event, CLICK_SELECTOR);
        if (!el) return;

        if (el.hasAttribute("data-click")) {
            if (invoke(el, "click", event) === false) event.preventDefault();
            return;
        }
        if (el.hasAttribute("data-href")) {
            window.location.href = el.getAttribute("data-href");
            return;
        }
        if (el.hasAttribute("data-history-back")) {
            if (window.history.length > 1) {
                event.preventDefault();
                window.history.back();
            }
            return; // sonst folgt der Link seinem echten href
        }
        if (el.hasAttribute("data-close-dialog")) {
            var dialog = document.getElementById(el.getAttribute("data-close-dialog"));
            if (dialog && typeof dialog.close === "function") dialog.close();
            return;
        }
        if (el.hasAttribute("data-select-on-click")) {
            if (typeof el.select === "function") el.select();
            return;
        }
        if (el.hasAttribute("data-copy-from")) {
            var source = document.getElementById(el.getAttribute("data-copy-from"));
            if (source && navigator.clipboard) navigator.clipboard.writeText(source.value);
            return;
        }
        if (el.hasAttribute("data-remove-closest")) {
            var row = el.closest(el.getAttribute("data-remove-closest"));
            if (row) row.remove();
            return;
        }
        // data-stop-propagation: bewusst nichts tun.
    });

    // Capture-Phase: Die Rückfrage entscheidet, bevor andere submit-Listener
    // (etwa ein Absenden per fetch) überhaupt laufen.
    document.addEventListener(
        "submit",
        function (event) {
            var form = event.target;
            if (!(form instanceof HTMLFormElement)) return;
            var message = form.getAttribute("data-confirm");
            if (message !== null && !window.confirm(message)) {
                event.preventDefault();
                event.stopImmediatePropagation();
            }
        },
        true
    );

    document.addEventListener("change", function (event) {
        var el = closestFrom(event, "[data-change],[data-autosubmit]");
        if (!el) return;
        if (el.hasAttribute("data-autosubmit")) {
            if (el.form) el.form.submit();
            return;
        }
        invoke(el, "change", event);
    });

    document.addEventListener("mouseover", function (event) {
        var el = closestFrom(event, "[data-mouseover]");
        if (el) invoke(el, "mouseover", event);
    });

    document.addEventListener("mouseout", function (event) {
        var el = closestFrom(event, "[data-mouseout]");
        if (el) invoke(el, "mouseout", event);
    });
})();
