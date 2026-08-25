namespace Word2Sentence.Models;

public sealed class SentenceChallenge
{
    public string Scenario { get; set; } = string.Empty;
    public string ScenarioCategory { get; set; } = string.Empty;
    public string Goal { get; set; } = string.Empty;
    public string Hint { get; set; } = string.Empty;
    public string UsagePattern { get; set; } = string.Empty;
    public string UsageExplanation { get; set; } = string.Empty;
    public string UsageExample { get; set; } = string.Empty;
    public List<UsagePatternItem> UsageItems { get; set; } = [];
}

public sealed class SentenceEvaluation
{
    public int Score { get; set; }
    public string Summary { get; set; } = string.Empty;
    public string CorrectedSentence { get; set; } = string.Empty;
    public string BetterSentence { get; set; } = string.Empty;
    public TargetUsageEvidence TargetUsage { get; set; } = new();
    public List<FeedbackSegment> Segments { get; set; } = [];
    public List<DetectedWordError> ErrorWords { get; set; } = [];
}

public sealed class TargetUsageEvidence
{
    public bool TargetPresent { get; set; }
    public bool SpellingCorrect { get; set; }
    public bool MeaningCorrect { get; set; }
    public bool FormCorrect { get; set; }
    public bool CollocationCorrect { get; set; }
    public bool LocalGrammarCorrect { get; set; }
    public bool NaturalUsage { get; set; }
    public bool CoreCorrectionRequired { get; set; }
    public double Confidence { get; set; }
    public string EvidenceSummary { get; set; } = string.Empty;
}

public sealed class FeedbackSegment
{
    public string Text { get; set; } = string.Empty;
    public string Rating { get; set; } = "acceptable";
    public string Reason { get; set; } = string.Empty;
}

public sealed class DetectedWordError
{
    public string ObservedForm { get; set; } = string.Empty;
    public string Word { get; set; } = string.Empty;
    public string PartOfSpeech { get; set; } = string.Empty;
    public string Meaning { get; set; } = string.Empty;
    public string Reason { get; set; } = string.Empty;

    public string MeaningWithPartOfSpeech => string.IsNullOrWhiteSpace(PartOfSpeech)
        ? Meaning
        : $"{PartOfSpeech} {Meaning}".Trim();

    public string CorrectionLabel => string.IsNullOrWhiteSpace(ObservedForm) ||
                                     ObservedForm.Equals(Word, StringComparison.OrdinalIgnoreCase)
        ? string.Empty
        : $"{ObservedForm} → {Word}";
}
