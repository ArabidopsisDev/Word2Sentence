using System.IO;
using System.Text.Json;
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
}
