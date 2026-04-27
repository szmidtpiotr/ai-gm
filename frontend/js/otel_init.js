// OTel RUM placeholder for AI test mode only.
(function () {
  var TEST_RUN_ID = window.__AI_TEST_RUN_ID || ("manual-" + Date.now());

  function logSpan(name, attrs) {
    try {
      var payload = Object.assign({ test_run_id: TEST_RUN_ID }, attrs || {});
      console.log("[OTel]", name, payload);
    } catch (err) {
      console.log("[OTel] log error", err);
    }
  }

  window.AITestOTel = {
    logAction: function (action, attrs) {
      logSpan("AI_ACTION", Object.assign({ action: action }, attrs || {}));
    },
    logGMResponse: function (content, tags) {
      logSpan("GM_RESPONSE", { content: content, tags: tags || [] });
    },
    logLocationChange: function (from, to, reason, isLegal) {
      logSpan("LOCATION_CHANGE", {
        old_location: from,
        new_location: to,
        reason: reason,
        is_legal: !!isLegal,
      });
    },
  };

  console.log("[OTel] AI Test RUM initialized. test_run_id:", TEST_RUN_ID);
})();
