You are classifying economics journal articles by their primary research question.

Categories:
- causal: primarily focused on estimating, identifying, or interpreting causal effects.
- predictive: primarily focused on prediction, forecasting, classification, predictive performance, or out-of-sample accuracy.
- other: does not clearly fit causal or predictive.
- insufficient_text: title and abstract are not enough to classify reliably.

Use only the title and abstract. Do not use journal prestige, authors, institutions, year, DOI, or outside knowledge of the paper.

Return JSON with exactly:
{
  "category": "causal|predictive|other|insufficient_text",
  "confidence": "high|medium|low",
  "reason": "one short sentence grounded in the title/abstract"
}
