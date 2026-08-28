using Word2Sentence.Models;

namespace Word2Sentence.Services;

public static class StatisticsService
{
    public static StatisticsSnapshot Create(AppData data, DateTimeOffset? nowValue = null)
    {
        var now = (nowValue ?? DateTimeOffset.Now).ToLocalTime();
        var today = now.Date;
        var reviews = data.Reviews.OrderBy(review => review.ReviewedAt).ToList();
        var words = data.Words.ToList();
        var activity = BuildActivityMap(words, reviews);
        var activeDates = activity.Where(pair => pair.Value > 0).Select(pair => pair.Key).ToHashSet();
        var reviewedWordIds = reviews.Select(review => review.WordId).Where(id => id != Guid.Empty).Distinct().ToHashSet();
        var lastReviewByWord = reviews
            .Where(review => review.WordId != Guid.Empty)
            .GroupBy(review => review.WordId)
            .ToDictionary(group => group.Key, group => group.MaxBy(review => review.ReviewedAt)!);

        var stableWords = words.Count(word =>
            word.IntervalDays >= 14 ||
            word.Repetitions >= 3 ||
            word.FsrsStability is >= 14);
        var reinforcementNeeded = words.Count(word =>
            (word.NextReviewAt <= now && word.Lapses > 0) ||
            (lastReviewByWord.TryGetValue(word.Id, out var review) && review.Score < 70));

        var calendarStart = StartOfCalendar(today);
        var calendarDays = Enumerable.Range(0, 42)
            .Select(offset => calendarStart.AddDays(offset))
            .Select(date =>
            {
                var count = activity.GetValueOrDefault(date);
                return new CalendarActivityDay
                {
                    Date = date,
                    ActivityCount = count,
                    Level = HeatLevel(count),
                    IsCurrentMonth = date.Month == today.Month,
                    IsToday = date == today,
                    ToolTip = LocalizationService.T("StatisticsCalendarTooltip", date.ToString("yyyy-MM-dd"), count)
                };
            })
            .ToList();

        var trend = Enumerable.Range(0, 14)
            .Select(offset => today.AddDays(offset - 13))
            .Select(date =>
            {
                var dayReviews = reviews.Where(review => review.ReviewedAt.ToLocalTime().Date == date).ToList();
                return new DailyLearningPoint
                {
                    Date = date,
                    Reviews = dayReviews.Count,
                    NewWords = words.Count(word => word.CreatedAt.ToLocalTime().Date == date),
                    AverageScore = dayReviews.Count == 0 ? null : dayReviews.Average(review => review.Score)
                };
            })
            .ToList();

        var scoreDistribution = new[]
        {
            CreateBucket("0–59", reviews.Count(review => review.Score < 60), reviews.Count),
            CreateBucket("60–69", reviews.Count(review => review.Score is >= 60 and < 70), reviews.Count),
            CreateBucket("70–79", reviews.Count(review => review.Score is >= 70 and < 80), reviews.Count),
            CreateBucket("80–89", reviews.Count(review => review.Score is >= 80 and < 90), reviews.Count),
            CreateBucket("90–100", reviews.Count(review => review.Score >= 90), reviews.Count)
        };

        var newCount = words.Count(word => word.Repetitions == 0);
        var learningCount = words.Count(word => word.Repetitions == 1);
        var familiarCount = words.Count(word => word.Repetitions >= 2 && word.IntervalDays < 30);
        var masteredCount = words.Count(word => word.Repetitions >= 2 && word.IntervalDays >= 30);
        var mastery = new[]
        {
            CreateMastery("StageNew", newCount, words.Count, "#D9D8D2"),
            CreateMastery("StageLearning", learningCount, words.Count, "#8FB1D2"),
            CreateMastery("StageFamiliar", familiarCount, words.Count, "#7FB89A"),
            CreateMastery("StageMastered", masteredCount, words.Count, "#2F6048")
        };

        return new StatisticsSnapshot
        {
            TotalReviews = reviews.Count,
            LearnedWords = reviewedWordIds.Count,
            NewWords30 = words.Count(word => word.CreatedAt.ToLocalTime().Date >= today.AddDays(-29)),
            AverageScore = reviews.Count == 0 ? 0 : reviews.Average(review => review.Score),
            CurrentStreak = CurrentStreak(activeDates, today),
            BestStreak = BestStreak(activeDates),
            ActiveDays30 = activeDates.Count(date => date >= today.AddDays(-29) && date <= today),
            RecallCoverage = Percent(reviewedWordIds.Count, words.Count),
            StableMasteryRate = Percent(stableWords, words.Count),
            ReinforcementNeeded = reinforcementNeeded,
            CalendarDays = calendarDays,
            Trend = trend,
            ScoreDistribution = scoreDistribution,
            MasteryBreakdown = mastery
        };
    }

    private static Dictionary<DateTime, int> BuildActivityMap(IEnumerable<WordEntry> words, IEnumerable<ReviewRecord> reviews)
    {
        var result = new Dictionary<DateTime, int>();
        foreach (var review in reviews)
            Add(result, review.ReviewedAt.ToLocalTime().Date);
        foreach (var word in words)
            Add(result, word.CreatedAt.ToLocalTime().Date);
        return result;
    }

    private static void Add(Dictionary<DateTime, int> map, DateTime date) => map[date] = map.GetValueOrDefault(date) + 1;

    private static DateTime StartOfCalendar(DateTime today)
    {
        var first = new DateTime(today.Year, today.Month, 1);
        var daysSinceMonday = ((int)first.DayOfWeek + 6) % 7;
        return first.AddDays(-daysSinceMonday);
    }

    private static int HeatLevel(int count) => count switch
    {
        <= 0 => 0,
        1 => 1,
        <= 3 => 2,
        <= 6 => 3,
        _ => 4
    };

    private static int CurrentStreak(HashSet<DateTime> activeDates, DateTime today)
    {
        var cursor = activeDates.Contains(today) ? today : today.AddDays(-1);
        var streak = 0;
        while (activeDates.Contains(cursor))
        {
            streak++;
            cursor = cursor.AddDays(-1);
        }
        return streak;
    }

    private static int BestStreak(HashSet<DateTime> activeDates)
    {
        var best = 0;
        var current = 0;
        DateTime? previous = null;
        foreach (var date in activeDates.OrderBy(date => date))
        {
            current = previous is not null && date == previous.Value.AddDays(1) ? current + 1 : 1;
            best = Math.Max(best, current);
            previous = date;
        }
        return best;
    }

    private static double Percent(int value, int total) => total == 0 ? 0 : value * 100.0 / total;

    private static ScoreBucket CreateBucket(string label, int count, int total) => new()
    {
        Label = label,
        Count = count,
        Percentage = Percent(count, total)
    };

    private static MasteryBreakdownItem CreateMastery(string localizationKey, int count, int total, string color) => new()
    {
        Label = LocalizationService.T(localizationKey),
        Count = count,
        Percentage = Percent(count, total),
        Color = color
    };
}
