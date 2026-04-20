const answer =
  ($json.answer ?? '').toString().toLowerCase();

const expectedKeywords = Array.isArray($json.expected_keywords)
  ? $json.expected_keywords
  : [];

if (expectedKeywords.length === 0) {
  return [
    {
      json: {
        ...$json,
        evaluation_score: null,
        evaluation_passed: null
      }
    }
  ];
}

const normalizedKeywords = expectedKeywords
  .map((value) => value.toString().toLowerCase().trim())
  .filter(Boolean);

const matched = normalizedKeywords.filter((keyword) => answer.includes(keyword));
const score = normalizedKeywords.length === 0
  ? null
  : matched.length / normalizedKeywords.length;

return [
  {
    json: {
      ...$json,
      evaluation_score: score,
      evaluation_passed: score !== null ? score >= 0.6 : null,
      matched_keywords: matched
    }
  }
];
