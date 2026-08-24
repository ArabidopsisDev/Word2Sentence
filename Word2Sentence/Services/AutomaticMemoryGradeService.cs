using Word2Sentence.Models;

namespace Word2Sentence.Services;

public enum AutomaticMemoryGrade
{
    Uncertain = 0,
    Again = 1,
    Hard = 2,
    Good = 3,
    Easy = 4
}

public sealed record MemoryGradeDecision(
    AutomaticMemoryGrade Grade,
    string Reason,
    double Confidence,
    bool TargetUsageCorrect)
{
    public bool ShouldUpdateLongTermMemory => Grade != AutomaticMemoryGrade.Uncertain;
}

public static class AutomaticMemoryGradeService
{
    private const double MinimumConfidence = 0.75;

    public static MemoryGradeDecision Decide(
        TargetUsageEvidence evidence,
        bool hintUsed,
        bool pasteUsed,
        long responseTimeMs,
        int editCount,
        IEnumerable<ReviewRecord> history)
    {
        var criticalSuccess = HasCriticalSuccess(evidence);
        if (evidence.Confidence < MinimumConfidence || !IsInternallyConsistent(evidence, criticalSuccess))
        {
            return new MemoryGradeDecision(
                AutomaticMemoryGrade.Uncertain,
                LocalizationService.Instance.IsEnglish
                    ? "AI evidence is low-confidence or contradictory; an automatic retest is required."
                    : "AI 对目标词用法的证据置信度不足或相互矛盾，需要自动复测。",
                evidence.Confidence,
                false);
        }

        if (!criticalSuccess)
        {
            return new MemoryGradeDecision(
                AutomaticMemoryGrade.Again,
                evidence.EvidenceSummary.Length > 0
                    ? evidence.EvidenceSummary
                    : LocalizationService.Instance.IsEnglish ? "The target word was not recalled or used correctly." : "目标词的提取或核心用法存在错误。",
                evidence.Confidence,
                false);
        }

        if (hintUsed || pasteUsed)
        {
            return new MemoryGradeDecision(
                AutomaticMemoryGrade.Hard,
                hintUsed
                    ? (LocalizationService.Instance.IsEnglish ? "Target usage is correct, but a hint was revealed." : "目标用法正确，但本次查看过提示，按困难回忆处理。")
                    : (LocalizationService.Instance.IsEnglish ? "Target usage is correct, but pasted input prevents an independent-easy result." : "目标用法正确，但检测到粘贴输入，不能视为轻松独立回忆。"),
                evidence.Confidence,
                true);
        }

        if (!evidence.NaturalUsage)
        {
            return new MemoryGradeDecision(
                AutomaticMemoryGrade.Hard,
                LocalizationService.Instance.IsEnglish ? "Core target usage is correct, but the expression is not yet natural." : "目标词核心用法正确，但表达尚不自然。",
                evidence.Confidence,
                true);
        }

        if (CanAwardEasy(evidence, responseTimeMs, editCount, history))
        {
            return new MemoryGradeDecision(
                AutomaticMemoryGrade.Easy,
                LocalizationService.Instance.IsEnglish ? "Target usage is correct and natural, with a response faster than the personal baseline." : "目标词使用正确自然，且响应速度明显快于个人基线。",
                evidence.Confidence,
                true);
        }

        return new MemoryGradeDecision(
            AutomaticMemoryGrade.Good,
            LocalizationService.Instance.IsEnglish ? "No hint used; meaning, form, collocation, and local grammar are correct." : "未查看提示，目标词的词义、词形、搭配和局部语法均正确。",
            evidence.Confidence,
            true);
    }

    public static TargetUsageEvidence? Reconcile(TargetUsageEvidence first, TargetUsageEvidence second)
    {
        if (first.Confidence < MinimumConfidence || second.Confidence < MinimumConfidence) return null;
        if (first.TargetPresent != second.TargetPresent ||
            first.SpellingCorrect != second.SpellingCorrect ||
            first.MeaningCorrect != second.MeaningCorrect ||
            first.FormCorrect != second.FormCorrect ||
            first.CollocationCorrect != second.CollocationCorrect ||
            first.LocalGrammarCorrect != second.LocalGrammarCorrect ||
            first.CoreCorrectionRequired != second.CoreCorrectionRequired)
        {
            return null;
        }

        return new TargetUsageEvidence
        {
            TargetPresent = first.TargetPresent,
            SpellingCorrect = first.SpellingCorrect,
            MeaningCorrect = first.MeaningCorrect,
            FormCorrect = first.FormCorrect,
            CollocationCorrect = first.CollocationCorrect,
            LocalGrammarCorrect = first.LocalGrammarCorrect,
            NaturalUsage = first.NaturalUsage && second.NaturalUsage,
            CoreCorrectionRequired = first.CoreCorrectionRequired,
            Confidence = (first.Confidence + second.Confidence) / 2,
            EvidenceSummary = string.Join("；", new[] { first.EvidenceSummary, second.EvidenceSummary }
                .Where(text => !string.IsNullOrWhiteSpace(text))
                .Distinct(StringComparer.Ordinal))
        };
    }

    private static bool HasCriticalSuccess(TargetUsageEvidence evidence) =>
        evidence.TargetPresent &&
        evidence.SpellingCorrect &&
        evidence.MeaningCorrect &&
        evidence.FormCorrect &&
        evidence.CollocationCorrect &&
        evidence.LocalGrammarCorrect &&
        !evidence.CoreCorrectionRequired;

    private static bool IsInternallyConsistent(TargetUsageEvidence evidence, bool criticalSuccess)
    {
        if (!evidence.TargetPresent &&
            (evidence.SpellingCorrect || evidence.MeaningCorrect || evidence.FormCorrect || evidence.CollocationCorrect))
            return false;
        return evidence.CoreCorrectionRequired != criticalSuccess;
    }

    private static bool CanAwardEasy(
        TargetUsageEvidence evidence,
        long responseTimeMs,
        int editCount,
        IEnumerable<ReviewRecord> history)
    {
        if (evidence.Confidence < 0.9 || responseTimeMs <= 0 || editCount > 2) return false;

        var baseline = history
            .Where(record => record.TargetUsageCorrect && !record.HintUsed && record.ResponseTimeMs > 0)
            .OrderByDescending(record => record.ReviewedAt)
            .Take(30)
            .Select(record => record.ResponseTimeMs)
            .OrderBy(value => value)
            .ToList();
        if (baseline.Count < 10) return false;

        var median = baseline.Count % 2 == 1
            ? baseline[baseline.Count / 2]
            : (baseline[baseline.Count / 2 - 1] + baseline[baseline.Count / 2]) / 2d;
        return responseTimeMs <= median * 0.8;
    }
}
