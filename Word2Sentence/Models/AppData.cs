namespace Word2Sentence.Models;

public sealed class AppData
{
    public List<WordEntry> Words { get; set; } = [];
    public List<ReviewRecord> Reviews { get; set; } = [];
    public List<UsageCard> Cards { get; set; } = [];
    public AppSettings Settings { get; set; } = new();
}

public sealed class AppSettings
{
    public string Model { get; set; } = "stealth/ox-alpha";
    public string SuggestedNextModel { get; set; } = "deepseek/deepseek-v4-flash-0731";
    public int DailyGoal { get; set; } = 12;
    public string UiLanguage { get; set; } = "zh-CN";
    public string TargetLanguage { get; set; } = "English";
    public string ExplanationLanguage { get; set; } = "Chinese";
}
