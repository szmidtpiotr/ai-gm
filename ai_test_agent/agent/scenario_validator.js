/**
 * Walidacja pliku scenariusza przed uruchomieniem orchestratora.
 * @param {object} scenario
 * @returns {string[]} lista komunikatów błędów (pusta = OK)
 */
function validateScenario(scenario) {
  const errors = [];
  if (!scenario || typeof scenario !== "object") {
    return ["Scenariusz musi być obiektem JSON"];
  }

  const required = ["name", "goal", "persona", "success_criteria", "max_steps"];
  for (const field of required) {
    if (scenario[field] === undefined || scenario[field] === null) {
      errors.push(`Brak wymaganego pola: ${field}`);
    }
  }
  if (typeof scenario.name === "string" && !String(scenario.name).trim()) {
    errors.push("Pole name nie może być puste");
  }
  if (typeof scenario.goal === "string" && !String(scenario.goal).trim()) {
    errors.push("Pole goal nie może być puste");
  }
  if (typeof scenario.persona === "string" && !String(scenario.persona).trim()) {
    errors.push("Pole persona nie może być puste");
  }
  if (
    scenario.success_criteria !== undefined &&
    scenario.success_criteria !== null &&
    typeof scenario.success_criteria !== "object"
  ) {
    errors.push("success_criteria musi być obiektem");
  }
  if (Array.isArray(scenario.constraints) && scenario.constraints.length > 200) {
    errors.push("constraints: za długa lista");
  }

  if (scenario.max_steps !== undefined) {
    const n = Number(scenario.max_steps);
    if (!Number.isFinite(n) || n < 10 || n > 200) {
      errors.push(`max_steps musi być między 10 a 200 (obecnie: ${scenario.max_steps})`);
    }
  }

  const v = scenario.validation;
  if (v && typeof v === "object") {
    if (v.check_interval_steps != null && scenario.max_steps != null) {
      if (Number(v.check_interval_steps) > Number(scenario.max_steps)) {
        errors.push("validation.check_interval_steps > max_steps");
      }
    }
    if (v.api_endpoint != null && String(v.api_endpoint).trim() !== "") {
      if (!String(v.api_endpoint).startsWith("/api/debug/")) {
        errors.push("validation.api_endpoint musi zaczynać się od /api/debug/");
      }
    }
  }

  return errors;
}

module.exports = { validateScenario };
