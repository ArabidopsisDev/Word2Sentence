namespace Word2Sentence.Models;

public sealed class UsageCard
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid WordId { get; set; }
    public string Word { get; set; } = string.Empty;
    public string UsagePattern { get; set; } = string.Empty;
    public string Explanation { get; set; } = string.Empty;
    public string Example { get; set; } = string.Empty;
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.Now;
}
