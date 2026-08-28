using System.Net;
using Word2Sentence.Models;
using Word2Sentence.Services;

var origin = DateTimeOffset.Parse("2026-08-24T02:00:00Z");
var initialVectors = new[]
{
    (AutomaticMemoryGrade.Again, 60d, FsrsCardState.Learning, 0, 0.212, 6.4133),
    (AutomaticMemoryGrade.Hard, 330d, FsrsCardState.Learning, 0, 1.2931, 5.112170705601056),
    (AutomaticMemoryGrade.Good, 600d, FsrsCardState.Learning, 1, 2.3065, 2.118103970459016),
    (AutomaticMemoryGrade.Easy, 691200d, FsrsCardState.Review, -1, 8.2956, 1.0)
};

foreach (var vector in initialVectors)
{
    var word = new WordEntry();
    var result = ReviewScheduler.Apply(word, vector.Item1, origin);
    RequireClose((result.NextReviewAt - origin).TotalSeconds, vector.Item2, 1e-9, $"{vector.Item1} due");
    Require(result.State == vector.Item3, $"{vector.Item1} state");
    Require((word.FsrsStep ?? -1) == vector.Item4, $"{vector.Item1} step");
    RequireClose(result.Stability, vector.Item5, 1e-12, $"{vector.Item1} stability");
    RequireClose(result.Difficulty, vector.Item6, 1e-12, $"{vector.Item1} difficulty");
}

var sequenceWord = new WordEntry();
var first = ReviewScheduler.Apply(sequenceWord, AutomaticMemoryGrade.Good, origin);
var second = ReviewScheduler.Apply(sequenceWord, AutomaticMemoryGrade.Good, origin.AddMinutes(10));
var third = ReviewScheduler.Apply(sequenceWord, AutomaticMemoryGrade.Good, second.NextReviewAt);
var fourth = ReviewScheduler.Apply(sequenceWord, AutomaticMemoryGrade.Again, third.NextReviewAt);
RequireClose(second.Stability, 2.3065, 1e-12, "sequence second stability");
RequireClose(second.Difficulty, 2.111214235785395, 1e-12, "sequence second difficulty");
Require((second.NextReviewAt - origin.AddMinutes(10)).TotalDays == 2, "sequence second due");
RequireClose(third.Stability, 10.971048263078135, 1e-12, "sequence third stability");
Require((third.NextReviewAt - second.NextReviewAt).TotalDays == 11, "sequence third due");
RequireClose(fourth.Stability, 1.53901253028147, 1e-12, "sequence lapse stability");
Require(fourth.State == FsrsCardState.Relearning, "sequence lapse state");
Require((fourth.NextReviewAt - third.NextReviewAt).TotalMinutes == 10, "sequence lapse due");

var successEvidence = Evidence(success: true, natural: true, confidence: 0.95);
var failureEvidence = Evidence(success: false, natural: false, confidence: 0.95);
Require(AutomaticMemoryGradeService.Decide(successEvidence, false, false, 30_000, 3, []).Grade == AutomaticMemoryGrade.Good,
    "automatic Good mapping");
Require(AutomaticMemoryGradeService.Decide(successEvidence, true, false, 30_000, 3, []).Grade == AutomaticMemoryGrade.Hard,
    "hint caps grade at Hard");
Require(AutomaticMemoryGradeService.Decide(successEvidence, false, true, 30_000, 1, []).Grade == AutomaticMemoryGrade.Hard,
    "paste caps grade at Hard");
Require(AutomaticMemoryGradeService.Decide(failureEvidence, false, false, 30_000, 3, []).Grade == AutomaticMemoryGrade.Again,
    "critical failure maps to Again");
successEvidence.Confidence = 0.5;
Require(AutomaticMemoryGradeService.Decide(successEvidence, false, false, 30_000, 3, []).Grade == AutomaticMemoryGrade.Uncertain,
    "low confidence maps to Uncertain");

successEvidence = Evidence(success: true, natural: true, confidence: 0.95);
var speedHistory = Enumerable.Range(0, 10).Select(index => new ReviewRecord
{
    TargetUsageCorrect = true,
    HintUsed = false,
    ResponseTimeMs = 100_000 + index * 1_000,
    ReviewedAt = origin.AddDays(-index)
}).ToList();
Require(AutomaticMemoryGradeService.Decide(successEvidence, false, false, 50_000, 1, speedHistory).Grade == AutomaticMemoryGrade.Easy,
    "Easy requires personal speed baseline");

var conflictingEvidence = Evidence(success: false, natural: false, confidence: 0.95);
Require(AutomaticMemoryGradeService.Reconcile(successEvidence, conflictingEvidence) is null,
    "conflicting AI passes stay uncertain");

var uncertainWord = new WordEntry { FsrsStability = 2.5, FsrsDifficulty = 5.0 };
ReviewScheduler.ScheduleUncertainRetest(uncertainWord, origin);
Require(uncertainWord.FsrsStability == 2.5 && uncertainWord.FsrsDifficulty == 5.0,
    "uncertain retest must not mutate FSRS state");
Require((uncertainWord.NextReviewAt - origin).TotalMinutes == 10,
    "uncertain retest due");

Require(WordCandidateService.IsValidTerm("résilient"), "Latin diacritics are accepted");
Require(WordCandidateService.IsValidTerm("気が散る"), "CJK terms are accepted");
Require(WordCandidateService.IsValidTerm("über-sichtlich"), "Unicode hyphenated terms are accepted");

var detectedWords = new[]
{
    new DetectedWordError
    {
        Word = "distract",
        PartOfSpeech = "vt.",
        Meaning = "distract: 转移，使分心；打扰",
        Reason = "usage test"
    }
};
var cleanedCandidate = WordCandidateService.Prepare(detectedWords, [], "focus").Single();
Require(cleanedCandidate.Meaning == "转移，使分心；打扰", "repeated word prefix is removed");
Require(WordCandidateService.ComposeMeaning(cleanedCandidate) == "vt. 转移，使分心；打扰", "part of speech is preserved");

var scenarioWordId = Guid.Parse("07db3388-c15b-4d89-97f8-4dd8b1dc2dcc");
var scenarioHistory = new List<ReviewRecord>();
var scenarioCategories = new List<string>();
for (var index = 0; index < 10; index++)
{
    var context = ScenarioDiversityService.Create(scenarioWordId, scenarioHistory);
    scenarioCategories.Add(context.CategoryKey);
    scenarioHistory.Add(new ReviewRecord
    {
        WordId = scenarioWordId,
        Scenario = $"Scenario {index}",
        ScenarioCategory = context.CategoryKey,
        ReviewedAt = origin.AddMinutes(index)
    });
}
Require(scenarioCategories.Distinct(StringComparer.Ordinal).Count() == 10,
    "scenario categories rotate without repetition across a complete cycle");
var diversityContext = ScenarioDiversityService.Create(scenarioWordId, scenarioHistory);
Require(diversityContext.CategoryKey == scenarioCategories[0], "scenario category cycle is deterministic");
Require(diversityContext.RecentScenarios.SequenceEqual(new[] { "Scenario 9", "Scenario 8", "Scenario 7", "Scenario 6", "Scenario 5" }),
    "the five most recent scenarios are supplied for novelty filtering");

var validKeyHandler = new ApiKeyValidationHandler(HttpStatusCode.OK);
var validKeyResult = await new OpenRouterService(new HttpClient(validKeyHandler))
    .ValidateApiKeyAsync("sk-or-v1-test-key-long-enough");
Require(validKeyResult.IsValid, "OpenRouter key validation accepts a successful official response");
Require(validKeyHandler.SawBearerAuthorization, "OpenRouter key validation uses bearer authorization");
var invalidKeyResult = await new OpenRouterService(new HttpClient(new ApiKeyValidationHandler(HttpStatusCode.Unauthorized)))
    .ValidateApiKeyAsync("sk-or-v1-test-key-long-enough");
Require(!invalidKeyResult.IsValid && invalidKeyResult.Reason == "unauthorized",
    "OpenRouter key validation rejects an unauthorized response");

var statisticsWordA = new WordEntry
{
    Id = Guid.NewGuid(), Word = "distract", CreatedAt = origin.AddDays(-2), Repetitions = 3,
    IntervalDays = 18, FsrsStability = 16, NextReviewAt = origin.AddDays(3)
};
var statisticsWordB = new WordEntry
{
    Id = Guid.NewGuid(), Word = "resilient", CreatedAt = origin.AddDays(-1), Repetitions = 1,
    Lapses = 1, NextReviewAt = origin.AddHours(-1)
};
var statisticsWordC = new WordEntry
{
    Id = Guid.NewGuid(), Word = "deliberate", CreatedAt = origin, Repetitions = 0,
    NextReviewAt = origin
};
var statisticsData = new AppData
{
    Words = [statisticsWordA, statisticsWordB, statisticsWordC],
    Reviews =
    [
        new ReviewRecord { WordId = statisticsWordA.Id, Word = statisticsWordA.Word, Score = 85, ReviewedAt = origin.AddDays(-1) },
        new ReviewRecord { WordId = statisticsWordB.Id, Word = statisticsWordB.Word, Score = 65, ReviewedAt = origin }
    ]
};
var statistics = StatisticsService.Create(statisticsData, origin);
Require(statistics.TotalReviews == 2, "statistics review total");
Require(statistics.LearnedWords == 2, "statistics distinct learned words");
Require(statistics.NewWords30 == 3, "statistics recent additions");
RequireClose(statistics.AverageScore, 75, 1e-9, "statistics average score");
Require(statistics.CurrentStreak == 3 && statistics.BestStreak == 3, "statistics streaks include review and add activity");
RequireClose(statistics.RecallCoverage, 200d / 3d, 1e-9, "statistics active recall coverage");
RequireClose(statistics.StableMasteryRate, 100d / 3d, 1e-9, "statistics stable mastery rate");
Require(statistics.ReinforcementNeeded == 1, "statistics reinforcement candidates");
Require(statistics.CalendarDays.Count == 42 && statistics.Trend.Count == 14, "statistics chart ranges");
Require(statistics.ScoreDistribution.Sum(bucket => bucket.Count) == 2, "statistics score buckets cover reviews");

LocalizationService.Instance.SetLanguage("en-US");
Require(LocalizationService.T("NavPractice") == "Practice", "English localization");
Require(LocalizationService.T("NavStatistics") == "Statistics", "English statistics localization");
Require(LocalizationService.T("SetupBeginner") == "Guide me step by step", "English onboarding localization");
Require(LocalizationService.T("SetupCreditsInstruction").Contains("One-time payment", StringComparison.Ordinal),
    "English beginner payment guide identifies one-time payment");
LocalizationService.Instance.SetLanguage("zh-CN");
Require(LocalizationService.T("NavPractice") == "造句练习", "Chinese localization");
Require(LocalizationService.T("NavStatistics") == "学习统计", "Chinese statistics localization");
Require(LocalizationService.T("SetupTechnical") == "我是技术用户", "Chinese onboarding localization");
Require(LocalizationService.T("SetupCreditsInstruction").Contains("一次性付款", StringComparison.Ordinal),
    "Chinese beginner payment guide identifies one-time payment");
Require(LocalizationService.T("AboutReciteListedDescription") ==
        "如果您有自己开发或推荐的复习软件，欢迎提交到OpenRecite社区维护的awesome-recite-tools目录",
    "OpenRecite contribution copy remains exact");

Console.WriteLine("FSRS_6_3_1_CONFORMANCE_OK");
Console.WriteLine("AUTOMATIC_MEMORY_GRADE_OK");
Console.WriteLine("SCENARIO_DIVERSITY_OK");
Console.WriteLine("OPENROUTER_ONBOARDING_OK");
Console.WriteLine("STATISTICS_ANALYTICS_OK");

static TargetUsageEvidence Evidence(bool success, bool natural, double confidence) => new()
{
    TargetPresent = success,
    SpellingCorrect = success,
    MeaningCorrect = success,
    FormCorrect = success,
    CollocationCorrect = success,
    LocalGrammarCorrect = success,
    NaturalUsage = natural,
    CoreCorrectionRequired = !success,
    Confidence = confidence,
    EvidenceSummary = success ? "正确" : "错误"
};

static void Require(bool condition, string label)
{
    if (!condition) throw new InvalidOperationException($"Check failed: {label}");
}

static void RequireClose(double actual, double expected, double tolerance, string label)
{
    if (Math.Abs(actual - expected) > tolerance)
        throw new InvalidOperationException($"Check failed: {label}; expected {expected:R}, got {actual:R}");
}

sealed class ApiKeyValidationHandler(HttpStatusCode statusCode) : HttpMessageHandler
{
    public bool SawBearerAuthorization { get; private set; }

    protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        SawBearerAuthorization = request.Headers.Authorization?.Scheme == "Bearer";
        return Task.FromResult(new HttpResponseMessage(statusCode));
    }
}
