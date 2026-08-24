using Word2Sentence.Models;

namespace Word2Sentence.Services;

public enum FsrsCardState
{
    Learning = 1,
    Review = 2,
    Relearning = 3
}

public sealed record ReviewScheduleResult(
    AutomaticMemoryGrade Grade,
    DateTimeOffset NextReviewAt,
    FsrsCardState State,
    double Stability,
    double Difficulty,
    bool IsShortTerm);

/// <summary>
/// Deterministic port of py-fsrs 6.3.1 using its published 21 default parameters,
/// desired retention 0.90, 1m/10m learning steps, and a 10m relearning step.
/// Interval fuzzing is intentionally disabled for reproducible desktop behavior.
/// </summary>
public static class ReviewScheduler
{
    public const string Version = "py-fsrs-6.3.1-default-dr0.90";

    private static readonly double[] Parameters =
    [
        0.212, 1.2931, 2.3065, 8.2956, 6.4133, 0.8334, 3.0194, 0.001,
        1.8722, 0.1666, 0.796, 1.4835, 0.0614, 0.2629, 1.6483, 0.6014,
        1.8729, 0.5425, 0.0912, 0.0658, 0.1542
    ];

    private static readonly TimeSpan[] LearningSteps =
    [
        TimeSpan.FromMinutes(1),
        TimeSpan.FromMinutes(10)
    ];

    private static readonly TimeSpan[] RelearningSteps = [TimeSpan.FromMinutes(10)];
    private const double DesiredRetention = 0.90;
    private const int MaximumIntervalDays = 36500;
    private const double StabilityMin = 0.001;
    private const double DifficultyMin = 1.0;
    private const double DifficultyMax = 10.0;
    private static readonly double Decay = -Parameters[20];
    private static readonly double Factor = Math.Pow(0.9, 1 / Decay) - 1;

    public static ReviewScheduleResult Apply(
        WordEntry word,
        AutomaticMemoryGrade grade,
        DateTimeOffset reviewedAt)
    {
        if (grade is AutomaticMemoryGrade.Uncertain)
            throw new ArgumentException("Uncertain evidence must not update FSRS state.", nameof(grade));

        InitializeOrMigrate(word);
        var rating = (int)grade;
        var state = (FsrsCardState)word.FsrsState;
        var step = word.FsrsStep;
        var stability = word.FsrsStability;
        var difficulty = word.FsrsDifficulty;
        var elapsedDays = word.LastReviewedAt is null
            ? (int?)null
            : Math.Max(0, (int)Math.Floor((reviewedAt - word.LastReviewedAt.Value).TotalDays));
        TimeSpan nextInterval;

        switch (state)
        {
            case FsrsCardState.Learning:
                step ??= 0;
                if (stability is null || difficulty is null)
                {
                    stability = InitialStability(rating);
                    difficulty = InitialDifficulty(rating, true);
                }
                else if (elapsedDays is not null && elapsedDays < 1)
                {
                    stability = ShortTermStability(stability.Value, rating);
                    difficulty = NextDifficulty(difficulty.Value, rating);
                }
                else
                {
                    stability = NextStability(
                        difficulty.Value,
                        stability.Value,
                        Retrievability(word, reviewedAt),
                        rating);
                    difficulty = NextDifficulty(difficulty.Value, rating);
                }

                (state, step, nextInterval) = ScheduleLearning(
                    state,
                    step.GetValueOrDefault(),
                    stability ?? throw new InvalidOperationException("FSRS learning stability was not initialized."),
                    rating);
                break;

            case FsrsCardState.Review:
                if (stability is null || difficulty is null)
                    throw new InvalidOperationException("FSRS review card is missing memory state.");

                stability = elapsedDays is not null && elapsedDays < 1
                    ? ShortTermStability(stability.Value, rating)
                    : NextStability(difficulty.Value, stability.Value, Retrievability(word, reviewedAt), rating);
                difficulty = NextDifficulty(difficulty.Value, rating);

                if (grade == AutomaticMemoryGrade.Again)
                {
                    state = FsrsCardState.Relearning;
                    step = 0;
                    nextInterval = RelearningSteps[0];
                }
                else
                {
                    nextInterval = TimeSpan.FromDays(NextIntervalDays(stability.Value));
                }
                break;

            case FsrsCardState.Relearning:
                if (stability is null || difficulty is null || step is null)
                    throw new InvalidOperationException("FSRS relearning card is missing memory state.");

                if (elapsedDays is not null && elapsedDays < 1)
                {
                    stability = ShortTermStability(stability.Value, rating);
                    difficulty = NextDifficulty(difficulty.Value, rating);
                }
                else
                {
                    stability = NextStability(difficulty.Value, stability.Value, Retrievability(word, reviewedAt), rating);
                    difficulty = NextDifficulty(difficulty.Value, rating);
                }

                (state, step, nextInterval) = ScheduleRelearning(
                    state,
                    step.GetValueOrDefault(),
                    stability ?? throw new InvalidOperationException("FSRS relearning stability was not initialized."),
                    rating);
                break;

            default:
                throw new InvalidOperationException($"Unknown FSRS state: {word.FsrsState}");
        }

        word.FsrsState = (int)state;
        word.FsrsStep = step;
        word.FsrsStability = stability;
        word.FsrsDifficulty = difficulty;
        word.SchedulerVersion = Version;
        word.LastReviewedAt = reviewedAt;
        word.NextReviewAt = reviewedAt + nextInterval;
        word.IntervalDays = Math.Max(0, (int)Math.Round(nextInterval.TotalDays, MidpointRounding.ToEven));
        if (grade == AutomaticMemoryGrade.Again)
        {
            word.Repetitions = 0;
            word.Lapses++;
        }
        else
        {
            word.Repetitions++;
        }

        return new ReviewScheduleResult(
            grade,
            word.NextReviewAt,
            state,
            stability ?? StabilityMin,
            difficulty ?? DifficultyMax,
            nextInterval < TimeSpan.FromDays(1));
    }

    public static void ScheduleUncertainRetest(WordEntry word, DateTimeOffset reviewedAt)
    {
        // This is an application-level evidence retry, not an FSRS review event.
        word.NextReviewAt = reviewedAt.AddMinutes(10);
    }

    public static double GetRetrievability(WordEntry word, DateTimeOffset at) => Retrievability(word, at);

    private static void InitializeOrMigrate(WordEntry word)
    {
        if (word.SchedulerVersion == Version &&
            Enum.IsDefined(typeof(FsrsCardState), word.FsrsState)) return;

        word.FsrsState = (int)FsrsCardState.Learning;
        word.FsrsStep = 0;
        word.FsrsStability = null;
        word.FsrsDifficulty = null;
        word.SchedulerVersion = Version;
    }

    private static (FsrsCardState State, int? Step, TimeSpan Interval) ScheduleLearning(
        FsrsCardState state,
        int step,
        double stability,
        int rating)
    {
        return rating switch
        {
            1 => (state, 0, LearningSteps[0]),
            2 when step == 0 => (state, step, (LearningSteps[0] + LearningSteps[1]) / 2),
            2 => (state, step, LearningSteps[step]),
            3 when step + 1 == LearningSteps.Length =>
                (FsrsCardState.Review, null, TimeSpan.FromDays(NextIntervalDays(stability))),
            3 => (state, step + 1, LearningSteps[step + 1]),
            4 => (FsrsCardState.Review, null, TimeSpan.FromDays(NextIntervalDays(stability))),
            _ => throw new ArgumentOutOfRangeException(nameof(rating))
        };
    }

    private static (FsrsCardState State, int? Step, TimeSpan Interval) ScheduleRelearning(
        FsrsCardState state,
        int step,
        double stability,
        int rating)
    {
        return rating switch
        {
            1 => (state, 0, RelearningSteps[0]),
            2 when RelearningSteps.Length == 1 => (state, step, RelearningSteps[0] * 1.5),
            2 => (state, step, RelearningSteps[step]),
            3 when step + 1 == RelearningSteps.Length =>
                (FsrsCardState.Review, null, TimeSpan.FromDays(NextIntervalDays(stability))),
            3 => (state, step + 1, RelearningSteps[step + 1]),
            4 => (FsrsCardState.Review, null, TimeSpan.FromDays(NextIntervalDays(stability))),
            _ => throw new ArgumentOutOfRangeException(nameof(rating))
        };
    }

    private static double InitialStability(int rating) => ClampStability(Parameters[rating - 1]);

    private static double InitialDifficulty(int rating, bool clamp)
    {
        var value = Parameters[4] - Math.Exp(Parameters[5] * (rating - 1)) + 1;
        return clamp ? ClampDifficulty(value) : value;
    }

    private static int NextIntervalDays(double stability)
    {
        var interval = stability / Factor * (Math.Pow(DesiredRetention, 1 / Decay) - 1);
        return Math.Clamp((int)Math.Round(interval, MidpointRounding.ToEven), 1, MaximumIntervalDays);
    }

    private static double ShortTermStability(double stability, int rating)
    {
        var increase = Math.Exp(Parameters[17] * (rating - 3 + Parameters[18])) *
                       Math.Pow(stability, -Parameters[19]);
        if (rating is 3 or 4) increase = Math.Max(increase, 1.0);
        return ClampStability(stability * increase);
    }

    private static double NextDifficulty(double difficulty, int rating)
    {
        var easyInitialDifficulty = InitialDifficulty(4, false);
        var delta = -(Parameters[6] * (rating - 3));
        var dampedDelta = (10 - difficulty) * delta / 9;
        var next = Parameters[7] * easyInitialDifficulty + (1 - Parameters[7]) * (difficulty + dampedDelta);
        return ClampDifficulty(next);
    }

    private static double NextStability(double difficulty, double stability, double retrievability, int rating)
    {
        var value = rating == 1
            ? NextForgetStability(difficulty, stability, retrievability)
            : NextRecallStability(difficulty, stability, retrievability, rating);
        return ClampStability(value);
    }

    private static double NextForgetStability(double difficulty, double stability, double retrievability)
    {
        var longTerm = Parameters[11] * Math.Pow(difficulty, -Parameters[12]) *
                       (Math.Pow(stability + 1, Parameters[13]) - 1) *
                       Math.Exp((1 - retrievability) * Parameters[14]);
        var shortTerm = stability / Math.Exp(Parameters[17] * Parameters[18]);
        return Math.Min(longTerm, shortTerm);
    }

    private static double NextRecallStability(
        double difficulty,
        double stability,
        double retrievability,
        int rating)
    {
        var hardPenalty = rating == 2 ? Parameters[15] : 1;
        var easyBonus = rating == 4 ? Parameters[16] : 1;
        return stability * (1 + Math.Exp(Parameters[8]) * (11 - difficulty) *
            Math.Pow(stability, -Parameters[9]) *
            (Math.Exp((1 - retrievability) * Parameters[10]) - 1) *
            hardPenalty * easyBonus);
    }

    private static double Retrievability(WordEntry word, DateTimeOffset at)
    {
        if (word.LastReviewedAt is null || word.FsrsStability is null) return 0;
        var elapsedDays = Math.Max(0, (int)Math.Floor((at - word.LastReviewedAt.Value).TotalDays));
        return Math.Pow(1 + Factor * elapsedDays / word.FsrsStability.Value, Decay);
    }

    private static double ClampDifficulty(double difficulty) =>
        Math.Clamp(difficulty, DifficultyMin, DifficultyMax);

    private static double ClampStability(double stability) => Math.Max(stability, StabilityMin);
}
