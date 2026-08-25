using Word2Sentence.Models;

namespace Word2Sentence.Services;

public sealed record ScenarioDiversityContext(
    string CategoryKey,
    string CategoryLabelEnglish,
    string CategoryLabelChinese,
    string CategoryInstruction,
    IReadOnlyList<string> RecentScenarios);

public static class ScenarioDiversityService
{
    private sealed record ScenarioCategory(string Key, string EnglishLabel, string ChineseLabel, string Instruction);

    private static readonly ScenarioCategory[] Categories =
    [
        new("learning", "learning and research", "学习与研究", "learning, teaching, an assignment, research, or solving a knowledge problem"),
        new("work", "work and collaboration", "工作与协作", "workplace collaboration, a professional decision, a meeting, or completing a practical task"),
        new("travel", "travel and transport", "旅行与交通", "travel, transport, navigating an unfamiliar place, or dealing with a journey"),
        new("home", "home and family", "家庭与日常生活", "home life, family communication, or handling an everyday responsibility"),
        new("services", "shopping and services", "购物与服务", "shopping, using a service, asking for help, or resolving a customer problem"),
        new("social", "friends and social life", "朋友与社交", "friends, social communication, relationships, or a shared group activity"),
        new("wellbeing", "health and wellbeing", "健康与身心状态", "health, exercise, rest, habits, or personal wellbeing"),
        new("digital", "digital life", "数字生活", "technology, online communication, digital media, or managing information"),
        new("hobbies", "hobbies and creativity", "兴趣与创造", "a hobby, creative activity, entertainment, or learning a practical skill"),
        new("unexpected", "unexpected situations", "意外与公共情境", "an unexpected problem, a public situation, a disagreement, or a time-sensitive decision")
    ];

    public static ScenarioDiversityContext Create(Guid wordId, IEnumerable<ReviewRecord> history)
    {
        var reviews = history
            .Where(review => review.WordId == wordId)
            .OrderByDescending(review => review.ReviewedAt)
            .ToList();
        var startIndex = StableStartIndex(wordId);
        var category = Categories[(startIndex + reviews.Count) % Categories.Length];
        var recentScenarios = reviews
            .Select(review => review.Scenario?.Trim())
            .Where(scenario => !string.IsNullOrWhiteSpace(scenario))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .Take(5)
            .Select(scenario => scenario!)
            .ToList();

        return new ScenarioDiversityContext(
            category.Key,
            category.EnglishLabel,
            category.ChineseLabel,
            category.Instruction,
            recentScenarios);
    }

    private static int StableStartIndex(Guid wordId)
    {
        var bytes = wordId.ToByteArray();
        var hash = 17u;
        foreach (var value in bytes) hash = unchecked(hash * 31 + value);
        return (int)(hash % (uint)Categories.Length);
    }
}
