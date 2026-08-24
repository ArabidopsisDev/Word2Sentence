using System.Text;
using System.Text.RegularExpressions;
using Word2Sentence.Models;

namespace Word2Sentence.Services;

public static class WordCandidateService
{
    private const string ValidWordOrPhrasePattern = @"^\p{L}[\p{L}\p{M}\p{Nd}'-]*( \p{L}[\p{L}\p{M}\p{Nd}'-]*)*$";

    public static bool IsValidTerm(string value) =>
        Regex.IsMatch(NormalizeKey(value), ValidWordOrPhrasePattern, RegexOptions.CultureInvariant);

    public static List<DetectedWordError> Prepare(
        IEnumerable<DetectedWordError> errors,
        IEnumerable<WordEntry> existingWords,
        string targetWord)
    {
        var targetKey = NormalizeKey(targetWord);
        var existingKeys = existingWords
            .Select(word => NormalizeKey(word.Word))
            .Where(key => key.Length > 0)
            .ToHashSet(StringComparer.Ordinal);
        var uniqueCandidates = new Dictionary<string, DetectedWordError>(StringComparer.Ordinal);

        foreach (var error in errors)
        {
            var normalized = NormalizeKey(error.Word);
            if (!IsValidTerm(normalized) ||
                normalized == targetKey || existingKeys.Contains(normalized))
            {
                continue;
            }

            if (uniqueCandidates.TryGetValue(normalized, out var existingCandidate))
            {
                if (string.IsNullOrWhiteSpace(existingCandidate.PartOfSpeech) && !string.IsNullOrWhiteSpace(error.PartOfSpeech))
                    existingCandidate.PartOfSpeech = error.PartOfSpeech.Trim();
                if (string.IsNullOrWhiteSpace(existingCandidate.Meaning) && !string.IsNullOrWhiteSpace(error.Meaning))
                    existingCandidate.Meaning = CleanDefinition(normalized, error.Meaning);
                if (!string.IsNullOrWhiteSpace(error.Reason) &&
                    !existingCandidate.Reason.Contains(error.Reason.Trim(), StringComparison.Ordinal))
                    existingCandidate.Reason = string.Join("；", new[] { existingCandidate.Reason, error.Reason.Trim() }.Where(text => text.Length > 0));
                continue;
            }

            uniqueCandidates[normalized] = new DetectedWordError
            {
                ObservedForm = error.ObservedForm.Trim(),
                Word = normalized,
                PartOfSpeech = error.PartOfSpeech.Trim(),
                Meaning = CleanDefinition(normalized, error.Meaning),
                Reason = error.Reason.Trim()
            };
        }

        return uniqueCandidates.Values.OrderBy(candidate => candidate.Word).ToList();
    }

    public static string NormalizeKey(string value)
    {
        if (string.IsNullOrWhiteSpace(value)) return string.Empty;

        var normalized = value
            .Normalize(NormalizationForm.FormKC)
            .Replace('’', '\'')
            .Replace('‘', '\'')
            .Replace('‐', '-')
            .Replace('‑', '-')
            .Replace('–', '-')
            .Trim()
            .ToLowerInvariant();
        normalized = Regex.Replace(normalized, "\\s+", " ", RegexOptions.CultureInvariant);
        return normalized.Trim(' ', '.', ',', '!', '?', ';', ':', '"', '“', '”', '(', ')', '[', ']', '{', '}');
    }

    public static string ComposeMeaning(DetectedWordError word)
    {
        var definition = CleanDefinition(NormalizeKey(word.Word), word.Meaning);
        var partOfSpeech = word.PartOfSpeech.Trim();
        if (partOfSpeech.Length == 0 || definition.StartsWith(partOfSpeech, StringComparison.OrdinalIgnoreCase))
            return definition;
        return $"{partOfSpeech} {definition}".Trim();
    }

    private static string CleanDefinition(string normalizedWord, string meaning)
    {
        var definition = meaning.Trim();
        if (normalizedWord.Length == 0 || definition.Length == 0) return definition;
        var repeatedPrefix = @"^\s*" + Regex.Escape(normalizedWord) + @"\s*(?:\([^)]{1,16}\)|（[^）]{1,16}）)?\s*[:：\-–—]\s*";
        return Regex.Replace(definition, repeatedPrefix, string.Empty, RegexOptions.IgnoreCase | RegexOptions.CultureInvariant).Trim();
    }
}
