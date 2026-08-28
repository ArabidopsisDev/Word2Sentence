namespace Word2Sentence.Models;

public sealed class StatisticsSnapshot
{
    public int TotalReviews { get; init; }
    public int LearnedWords { get; init; }
    public int NewWords30 { get; init; }
    public double AverageScore { get; init; }
    public int CurrentStreak { get; init; }
    public int BestStreak { get; init; }
    public int ActiveDays30 { get; init; }
    public double RecallCoverage { get; init; }
    public double StableMasteryRate { get; init; }
    public int ReinforcementNeeded { get; init; }
    public IReadOnlyList<CalendarActivityDay> CalendarDays { get; init; } = [];
    public IReadOnlyList<DailyLearningPoint> Trend { get; init; } = [];
    public IReadOnlyList<ScoreBucket> ScoreDistribution { get; init; } = [];
    public IReadOnlyList<MasteryBreakdownItem> MasteryBreakdown { get; init; } = [];
}

public sealed class CalendarActivityDay
{
    public DateTime Date { get; init; }
    public int DayNumber => Date.Day;
    public int ActivityCount { get; init; }
    public int Level { get; init; }
    public bool IsCurrentMonth { get; init; }
    public bool IsToday { get; init; }
    public string ToolTip { get; init; } = string.Empty;
}

public sealed class DailyLearningPoint
{
    public DateTime Date { get; init; }
    public int Reviews { get; init; }
    public int NewWords { get; init; }
    public double? AverageScore { get; init; }
}

public sealed class ScoreBucket
{
    public string Label { get; init; } = string.Empty;
    public int Count { get; init; }
    public double Percentage { get; init; }
}

public sealed class MasteryBreakdownItem
{
    public string Label { get; init; } = string.Empty;
    public int Count { get; init; }
    public double Percentage { get; init; }
    public string Color { get; init; } = "#D9D8D2";
}
