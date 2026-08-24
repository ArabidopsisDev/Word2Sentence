using System.IO;
using System.Text.Json;
using System.Text.RegularExpressions;
using Word2Sentence.Models;

namespace Word2Sentence.Services;

public sealed class DataStore
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = true
    };

    public DataStore()
    {
        var overrideDirectory = Environment.GetEnvironmentVariable("WORD2SENTENCE_DATA_DIR");
        DataDirectory = string.IsNullOrWhiteSpace(overrideDirectory)
            ? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Word2Sentence")
            : Path.GetFullPath(overrideDirectory);
    }

    public string DataDirectory { get; }

    public string DataPath => Path.Combine(DataDirectory, "wordbook.json");

    public async Task<AppData> LoadAsync()
    {
        Directory.CreateDirectory(DataDirectory);
        if (!File.Exists(DataPath)) return new AppData();

        try
        {
            await using var stream = File.OpenRead(DataPath);
            var data = await JsonSerializer.DeserializeAsync<AppData>(stream, JsonOptions) ?? new AppData();
            data.Words ??= [];
            data.Reviews ??= [];
            data.Cards ??= [];
            data.Settings ??= new AppSettings();
            MigrateLegacyWordEntries(data.Words);
            MigrateLegacyUsageCards(data.Cards);
            return data;
        }
        catch (JsonException)
        {
            var backupPath = Path.Combine(DataDirectory, $"wordbook.corrupt-{DateTime.Now:yyyyMMdd-HHmmss}.json");
            File.Copy(DataPath, backupPath, true);
            return new AppData();
        }
    }

    public async Task SaveAsync(AppData data)
    {
        Directory.CreateDirectory(DataDirectory);
        var temporaryPath = DataPath + ".tmp";
        await using (var stream = File.Create(temporaryPath))
        {
            await JsonSerializer.SerializeAsync(stream, data, JsonOptions);
        }

        File.Move(temporaryPath, DataPath, true);
    }

    private static void MigrateLegacyWordEntries(IEnumerable<WordEntry> words)
    {
        const string prefixedDefinition = @"^\s*(?<lemma>\p{L}[\p{L}\p{M}\p{Nd}'-]*)\s*[:：]\s*(?<definition>.+)$";
        foreach (var word in words)
        {
            var automaticSource = word.Source.Contains("错词", StringComparison.OrdinalIgnoreCase) ||
                                  word.Source.Contains("mistake", StringComparison.OrdinalIgnoreCase);
            if (!automaticSource || string.IsNullOrWhiteSpace(word.Meaning)) continue;

            var match = Regex.Match(word.Meaning, prefixedDefinition, RegexOptions.CultureInvariant);
            if (!match.Success) continue;

            var canonical = WordCandidateService.NormalizeKey(match.Groups["lemma"].Value);
            if (!WordCandidateService.IsValidTerm(canonical)) continue;
            word.Word = canonical;
            word.Meaning = match.Groups["definition"].Value.Trim();
        }
    }

    private static void MigrateLegacyUsageCards(IEnumerable<UsageCard> cards)
    {
        foreach (var card in cards)
        {
            card.UsageItems ??= [];
            if (card.UsageItems.Count > 0) continue;

            var patterns = card.UsagePattern
                .Replace("\r", "\n", StringComparison.Ordinal)
                .Split(["/", "\n"], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
            foreach (var pattern in patterns.Take(3))
            {
                card.UsageItems.Add(new UsagePatternItem
                {
                    Pattern = pattern,
                    Meaning = card.Explanation,
                    Example = card.Example
                });
            }
        }
    }
}
