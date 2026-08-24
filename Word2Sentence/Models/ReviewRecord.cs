namespace Word2Sentence.Models;

public sealed class ReviewRecord
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid WordId { get; set; }
    public string Word { get; set; } = string.Empty;
    public string Sentence { get; set; } = string.Empty;
    public string CorrectedSentence { get; set; } = string.Empty;
    public string BetterSentence { get; set; } = string.Empty;
    public int Score { get; set; }
    public int Quality { get; set; }
    public int MemoryGrade { get; set; }
    public string MemoryGradeReason { get; set; } = string.Empty;
    public bool HintUsed { get; set; }
    public bool PasteUsed { get; set; }
    public long ResponseTimeMs { get; set; }
    public int EditCount { get; set; }
    public double EvidenceConfidence { get; set; }
    public bool TargetUsageCorrect { get; set; }
    public string UsagePattern { get; set; } = string.Empty;
    public string SchedulerVersion { get; set; } = string.Empty;
    public DateTimeOffset? PreviousDueAt { get; set; }
    public DateTimeOffset? ScheduledDueAt { get; set; }
    public DateTimeOffset ReviewedAt { get; set; } = DateTimeOffset.Now;
}
