using Word2Sentence.Services;

namespace Word2Sentence.Models;

public sealed class WordEntry
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public string Word { get; set; } = string.Empty;
    public string Meaning { get; set; } = string.Empty;
    public string Note { get; set; } = string.Empty;
    public string Source { get; set; } = "手动添加";
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.Now;
    public DateTimeOffset NextReviewAt { get; set; } = DateTimeOffset.Now;
    public DateTimeOffset? LastReviewedAt { get; set; }
    public int Repetitions { get; set; }
    public int IntervalDays { get; set; }
    public double EaseFactor { get; set; } = 2.5;
    public int Lapses { get; set; }
    public int FsrsState { get; set; } = 1;
    public int? FsrsStep { get; set; } = 0;
    public double? FsrsStability { get; set; }
    public double? FsrsDifficulty { get; set; }
    public string SchedulerVersion { get; set; } = "py-fsrs-6.3.1-default-dr0.90";

    public bool IsDue => NextReviewAt <= DateTimeOffset.Now;

    public string Stage => Repetitions switch
    {
        0 => LocalizationService.T("StageNew"),
        1 => LocalizationService.T("StageLearning"),
        2 => LocalizationService.T("StageFamiliar"),
        _ when IntervalDays >= 30 => LocalizationService.T("StageMastered"),
        _ => LocalizationService.T("StageReview")
    };

    public string DueLabel
    {
        get
        {
            if (IsDue) return LocalizationService.T("Today");
            var days = (NextReviewAt.Date - DateTimeOffset.Now.Date).Days;
            if (days <= 0) return LocalizationService.T("TodayAt", NextReviewAt.ToString("HH:mm"));
            return days == 1 ? LocalizationService.T("Tomorrow") : LocalizationService.T("DaysLater", days);
        }
    }
}
