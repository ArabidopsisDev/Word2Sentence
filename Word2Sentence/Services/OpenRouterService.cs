using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Word2Sentence.Models;

namespace Word2Sentence.Services;

public sealed class OpenRouterService(HttpClient httpClient)
{
    private const string Endpoint = "https://openrouter.ai/api/v1/chat/completions";
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        AllowTrailingCommas = true,
        ReadCommentHandling = JsonCommentHandling.Skip,
        NumberHandling = JsonNumberHandling.AllowReadingFromString
    };
    private readonly HashSet<string> _plainJsonOnlyModels = new(StringComparer.OrdinalIgnoreCase);

    public bool HasApiKey => !string.IsNullOrWhiteSpace(ResolveApiKey());

    public async Task<SentenceChallenge> CreateChallengeAsync(
        WordEntry word,
        string model,
        string targetLanguage,
        string explanationLanguage,
        CancellationToken cancellationToken = default)
    {
        if (!HasApiKey) return CreateOfflineChallenge(word, targetLanguage);

        var system = $$"""
            You design short {{targetLanguage}} sentence-writing exercises for language learners.
            Return JSON only. The exercise must require the target word naturally, avoid giving a complete sample answer,
            and use concise natural {{explanationLanguage}} for scenario, goal, hint, and usageExplanation. scenario and goal must not reveal the target
            word's collocation or a sentence template. hint may give a general grammatical direction, but not a complete answer.
            Also create a compact usage card. usagePattern is the most useful real-world collocation or grammar pattern
            for this word. usageExample is one natural {{targetLanguage}} example sentence that demonstrates it.
            """;
        var user = $"Target language: {targetLanguage}\nTarget word: {word.Word}\nLearner note/meaning: {word.Meaning}\nCreate one realistic everyday or work scenario.";

        var schema = new
        {
            type = "object",
            properties = new
            {
                scenario = new { type = "string" },
                goal = new { type = "string" },
                hint = new { type = "string" },
                usagePattern = new { type = "string", maxLength = 160 },
                usageExplanation = new { type = "string", maxLength = 300 },
                usageExample = new { type = "string", maxLength = 500 }
            },
            required = new[] { "scenario", "goal", "hint", "usagePattern", "usageExplanation", "usageExample" },
            additionalProperties = false
        };

        var challenge = await SendStructuredAsync<SentenceChallenge>(model, system, user, "sentence_challenge", schema, cancellationToken);
        if (string.IsNullOrWhiteSpace(challenge.Scenario)) challenge.Scenario = LocalizationService.Instance.IsEnglish
            ? $"Use {word.Word} to describe a specific situation."
            : $"请使用 {word.Word} 描述一个具体情境。";
        if (string.IsNullOrWhiteSpace(challenge.Goal)) challenge.Goal = LocalizationService.Instance.IsEnglish
            ? $"Write one complete, natural sentence in {targetLanguage}."
            : $"用{targetLanguage}写一个完整、自然的句子。";
        if (string.IsNullOrWhiteSpace(challenge.Hint)) challenge.Hint = LocalizationService.Instance.IsEnglish
            ? "Check the target term's form and collocation."
            : "注意目标词的词性和固定搭配。";
        if (string.IsNullOrWhiteSpace(challenge.UsagePattern)) challenge.UsagePattern = word.Word;
        if (string.IsNullOrWhiteSpace(challenge.UsageExplanation)) challenge.UsageExplanation = word.Meaning;
        if (string.IsNullOrWhiteSpace(challenge.UsageExample)) challenge.UsageExample = $"Try using “{word.Word}” in a complete sentence.";
        return challenge;
    }

    public async Task<SentenceEvaluation> EvaluateAsync(
        WordEntry word,
        SentenceChallenge challenge,
        string sentence,
        string model,
        string targetLanguage,
        string explanationLanguage,
        CancellationToken cancellationToken = default)
    {
        if (!HasApiKey) return CreateOfflineEvaluation(word, sentence);

        var system = $$"""
            You are a rigorous but encouraging {{targetLanguage}} writing coach for language learners.
            Evaluate grammar, collocation, word choice, naturalness, and whether the target word is used correctly.
            Calibrate score consistently: 90-100 is accurate and natural with the target used well; 75-89 has only minor
            issues; 60-74 is understandable but has notable errors; 40-59 has major grammar or usage problems; 0-39
            misuses or omits the target word, or makes the meaning difficult to understand.
            Split the learner's ORIGINAL sentence into ordered, non-overlapping segments. Their text concatenation must
            reproduce the original sentence exactly, including spaces and punctuation. Rate each segment as:
            excellent (genuinely strong/natural), acceptable (correct but ordinary or improvable), or error (grammar/usage error).
            Do not mark everything excellent. List only lexical words that were actually misspelled or misused in errorWords;
            never add punctuation, function words, or the target word when it was used correctly. For every error word,
            partOfSpeech is a compact conventional label suitable for {{targetLanguage}} (for English: n., vt., vi., adj., adv., etc.).
            meaning contains only the definition in {{explanationLanguage}} and must never begin with or repeat the word itself.
            Meanings, reasons, and summaries use {{explanationLanguage}}.
            correctedSentence must make only the changes needed to fix grammar and usage while preserving the learner's meaning.
            betterSentence must express the same core meaning in a more natural, vivid, or idiomatic way and must be different
            from correctedSentence. Both sentences must use the target word correctly.
            Use no more than 12 segments. Keep the summary under 120 Chinese characters and each reason under 40 Chinese characters.
            Return JSON only.
            """;
        var user = $"""
            Target language: {targetLanguage}
            Target word: {word.Word}
            Meaning/note: {word.Meaning}
            Exercise scenario: {challenge.Scenario}
            Exercise goal: {challenge.Goal}
            Learner sentence: {sentence}
            """;

        var schema = new
        {
            type = "object",
            properties = new
            {
                score = new { type = "integer", minimum = 0, maximum = 100 },
                summary = new { type = "string", maxLength = 300 },
                correctedSentence = new { type = "string", maxLength = 800 },
                betterSentence = new { type = "string", maxLength = 800 },
                segments = new
                {
                    type = "array",
                    maxItems = 12,
                    items = new
                    {
                        type = "object",
                        properties = new
                        {
                            text = new { type = "string" },
                            rating = new { type = "string", @enum = new[] { "excellent", "acceptable", "error" } },
                            reason = new { type = "string", maxLength = 120 }
                        },
                        required = new[] { "text", "rating", "reason" },
                        additionalProperties = false
                    }
                },
                errorWords = new
                {
                    type = "array",
                    maxItems = 8,
                    items = new
                    {
                        type = "object",
                        properties = new
                        {
                            word = new { type = "string" },
                            partOfSpeech = new { type = "string", maxLength = 32 },
                            meaning = new { type = "string" },
                            reason = new { type = "string", maxLength = 120 }
                        },
                        required = new[] { "word", "partOfSpeech", "meaning", "reason" },
                        additionalProperties = false
                    }
                }
            },
            required = new[] { "score", "summary", "correctedSentence", "betterSentence", "segments", "errorWords" },
            additionalProperties = false
        };

        var evaluation = await SendStructuredAsync<SentenceEvaluation>(model, system, user, "sentence_evaluation", schema, cancellationToken);
        evaluation.Score = Math.Clamp(evaluation.Score, 0, 100);
        evaluation.TargetUsage = new TargetUsageEvidence();
        evaluation.Segments ??= [];
        evaluation.ErrorWords ??= [];
        if (string.IsNullOrWhiteSpace(evaluation.CorrectedSentence)) evaluation.CorrectedSentence = sentence;
        if (string.IsNullOrWhiteSpace(evaluation.BetterSentence)) evaluation.BetterSentence = evaluation.CorrectedSentence;

        if (!string.Equals(string.Concat(evaluation.Segments.Select(segment => segment.Text)), sentence, StringComparison.Ordinal))
        {
            evaluation.Segments = [new FeedbackSegment
            {
                Text = sentence,
                Rating = evaluation.Score >= 60 ? "acceptable" : "error",
                Reason = LocalizationService.Instance.IsEnglish
                    ? "The model did not return stable segment ranges, so the whole-sentence rating was preserved."
                    : "模型未能稳定返回逐段范围，已保留整句评价。"
            }];
        }

        return evaluation;
    }

    public async Task<TargetUsageEvidence> RecheckTargetUsageAsync(
        WordEntry word,
        string sentence,
        string model,
        string targetLanguage,
        string explanationLanguage,
        CancellationToken cancellationToken = default)
    {
        if (!HasApiKey) return new TargetUsageEvidence
        {
            Confidence = 0,
            EvidenceSummary = LocalizationService.Instance.IsEnglish
                ? "Offline mode cannot verify target usage reliably."
                : "离线模式无法可靠判断目标词用法。"
        };

        var system = $$"""
            Independently verify only the learner's use of the target {{targetLanguage}} word. Return factual JSON evidence.
            Ignore unrelated sentence errors. Do not infer effort or assign a memory grade. CoreCorrectionRequired is true
            when the target word, spelling, intended meaning, word form, collocation, or its local grammar must change.
            Confidence is from 0 to 1. Use concise {{explanationLanguage}} for evidenceSummary.
            """;
        var user = $"Target language: {targetLanguage}\nTarget word: {word.Word}\nMeaning/note: {word.Meaning}\nOriginal sentence: {sentence}";
        var evidence = await SendStructuredAsync<TargetUsageEvidence>(
            model,
            system,
            user,
            "target_usage_recheck",
            BuildTargetUsageSchema(),
            cancellationToken);
        evidence.Confidence = Math.Clamp(evidence.Confidence, 0, 1);
        return evidence;
    }

    private static object BuildTargetUsageSchema() => new
    {
        type = "object",
        properties = new
        {
            targetPresent = new { type = "boolean" },
            spellingCorrect = new { type = "boolean" },
            meaningCorrect = new { type = "boolean" },
            formCorrect = new { type = "boolean" },
            collocationCorrect = new { type = "boolean" },
            localGrammarCorrect = new { type = "boolean" },
            naturalUsage = new { type = "boolean" },
            coreCorrectionRequired = new { type = "boolean" },
            confidence = new { type = "number", minimum = 0, maximum = 1 },
            evidenceSummary = new { type = "string", maxLength = 240 }
        },
        required = new[]
        {
            "targetPresent", "spellingCorrect", "meaningCorrect", "formCorrect", "collocationCorrect",
            "localGrammarCorrect", "naturalUsage", "coreCorrectionRequired", "confidence", "evidenceSummary"
        },
        additionalProperties = false
    };

    private async Task<T> SendStructuredAsync<T>(
        string model,
        string system,
        string user,
        string schemaName,
        object schema,
        CancellationToken cancellationToken)
    {
        var schemaText = JsonSerializer.Serialize(schema);
        var strictPayload = new
        {
            model,
            messages = new object[]
            {
                new { role = "system", content = system },
                new { role = "user", content = user }
            },
            temperature = 0.25,
            max_tokens = 3000,
            response_format = new
            {
                type = "json_schema",
                json_schema = new { name = schemaName, strict = true, schema }
            },
            plugins = new[] { new { id = "response-healing" } },
            provider = new { require_parameters = true }
        };

        string content;
        if (!_plainJsonOnlyModels.Contains(model))
        {
            try
            {
                content = await PostAndExtractContentAsync(strictPayload, cancellationToken);
            }
            catch (OpenRouterApiException exception) when (
                exception.StatusCode is HttpStatusCode.BadRequest or HttpStatusCode.NotFound)
            {
                _plainJsonOnlyModels.Add(model);
                content = await SendPlainJsonAsync(model, system, user, schemaText, cancellationToken);
            }
        }
        else
        {
            content = await SendPlainJsonAsync(model, system, user, schemaText, cancellationToken);
        }

        if (TryDeserializeStructured(content, out T? result)) return result!;

        var repairPayload = new
        {
            model,
            messages = new object[]
            {
                new
                {
                    role = "system",
                    content = "Repair or reconstruct malformed/truncated JSON. Return exactly one complete JSON object, no markdown or explanation. Preserve the intended data and obey the schema."
                },
                new
                {
                    role = "user",
                    content = $"JSON Schema:\n{schemaText}\n\nMalformed model output:\n{LimitLength(content, 14000)}"
                }
            },
            temperature = 0.0,
            max_tokens = 4000
        };

        var repairedContent = await PostAndExtractContentAsync(repairPayload, cancellationToken);
        if (TryDeserializeStructured(repairedContent, out result)) return result!;

        throw new InvalidOperationException(LocalizationService.Instance.IsEnglish
            ? "The AI response remained invalid after extraction, repair, and one retry. Please submit again."
            : "AI 返回的 JSON 格式异常；已自动提取、修复并重试一次，但仍无法解析。请重新提交。");
    }

    private async Task<string> SendPlainJsonAsync(
        string model,
        string system,
        string user,
        string schemaText,
        CancellationToken cancellationToken)
    {
        var payload = new
        {
            model,
            messages = new object[]
            {
                new { role = "system", content = system },
                new
                {
                    role = "user",
                    content = user + "\nRequired JSON Schema (return exactly one complete JSON object, no markdown):\n" + schemaText
                }
            },
            temperature = 0.2,
            max_tokens = 4000
        };
        return await PostAndExtractContentAsync(payload, cancellationToken);
    }

    private async Task<string> PostAndExtractContentAsync(object payload, CancellationToken cancellationToken)
    {
        var apiKey = ResolveApiKey()
                     ?? throw new InvalidOperationException(LocalizationService.Instance.IsEnglish
                         ? "OR_KEY environment variable was not found."
                         : "未检测到环境变量 OR_KEY。");

        using var request = new HttpRequestMessage(HttpMethod.Post, Endpoint);
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", apiKey);
        request.Headers.TryAddWithoutValidation("HTTP-Referer", "https://github.com/Project-MethodBox/Word2Sentence");
        request.Headers.TryAddWithoutValidation("X-OpenRouter-Title", "Word2Sentence");
        request.Content = new StringContent(JsonSerializer.Serialize(payload), Encoding.UTF8, "application/json");

        using var response = await httpClient.SendAsync(request, cancellationToken);
        var body = await response.Content.ReadAsStringAsync(cancellationToken);
        if (!response.IsSuccessStatusCode)
        {
            throw new OpenRouterApiException(
                response.StatusCode,
                LocalizationService.Instance.IsEnglish
                    ? $"OpenRouter request failed ({(int)response.StatusCode}): {ReadError(body)}"
                    : $"OpenRouter 请求失败 ({(int)response.StatusCode})：{ReadError(body)}");
        }

        using var document = JsonDocument.Parse(body);
        var content = document.RootElement
            .GetProperty("choices")[0]
            .GetProperty("message")
            .GetProperty("content")
            .GetString();

        if (string.IsNullOrWhiteSpace(content)) throw new InvalidOperationException(
            LocalizationService.Instance.IsEnglish ? "OpenRouter returned empty content." : "OpenRouter 返回了空内容。");
        return content;
    }

    private static string ReadError(string body)
    {
        try
        {
            using var document = JsonDocument.Parse(body);
            return document.RootElement.GetProperty("error").GetProperty("message").GetString() ??
                   (LocalizationService.Instance.IsEnglish ? "Unknown error" : "未知错误");
        }
        catch
        {
            return body.Length > 240 ? body[..240] : body;
        }
    }

    private static string? ResolveApiKey()
    {
        return Environment.GetEnvironmentVariable("OR_KEY")
               ?? Environment.GetEnvironmentVariable("OR_KEY", EnvironmentVariableTarget.User)
               ?? Environment.GetEnvironmentVariable("OR_KEY", EnvironmentVariableTarget.Machine);
    }

    private static bool TryDeserializeStructured<T>(string content, out T? result)
    {
        var candidates = new List<string>();
        var stripped = StripCodeFence(content);
        candidates.Add(stripped);
        var extracted = ExtractFirstJsonObject(stripped);
        if (!string.IsNullOrWhiteSpace(extracted) && !string.Equals(extracted, stripped, StringComparison.Ordinal))
            candidates.Add(extracted);

        foreach (var candidate in candidates.Distinct(StringComparer.Ordinal))
        {
            try
            {
                result = JsonSerializer.Deserialize<T>(candidate, JsonOptions);
                if (result is not null) return true;
            }
            catch (JsonException)
            {
                // Try the next local recovery candidate before spending another API call.
            }
            catch (NotSupportedException)
            {
                // The caller reports one consistent parse failure after all recovery paths.
            }
        }

        result = default;
        return false;
    }

    private static string? ExtractFirstJsonObject(string text)
    {
        var start = text.IndexOf('{');
        if (start < 0) return null;

        var depth = 0;
        var inString = false;
        var escaped = false;
        for (var index = start; index < text.Length; index++)
        {
            var character = text[index];
            if (inString)
            {
                if (escaped)
                {
                    escaped = false;
                    continue;
                }
                if (character == '\\')
                {
                    escaped = true;
                    continue;
                }
                if (character == '"') inString = false;
                continue;
            }

            if (character == '"')
            {
                inString = true;
                continue;
            }
            if (character == '{') depth++;
            if (character != '}') continue;
            depth--;
            if (depth == 0) return text[start..(index + 1)];
        }

        return null;
    }

    private static string LimitLength(string value, int maxLength) =>
        value.Length <= maxLength ? value : value[..maxLength];

    private static string StripCodeFence(string text)
    {
        var trimmed = text.Trim();
        if (!trimmed.StartsWith("```", StringComparison.Ordinal)) return trimmed;
        var firstNewLine = trimmed.IndexOf('\n');
        var lastFence = trimmed.LastIndexOf("```", StringComparison.Ordinal);
        return firstNewLine >= 0 && lastFence > firstNewLine
            ? trimmed[(firstNewLine + 1)..lastFence].Trim()
            : trimmed;
    }

    private static SentenceChallenge CreateOfflineChallenge(WordEntry word, string targetLanguage) => new()
    {
        Scenario = LocalizationService.Instance.IsEnglish
            ? $"Describe something that happened today and use “{word.Word}” naturally."
            : $"描述今天发生的一件事，并自然地用上“{word.Word}”。",
        Goal = LocalizationService.Instance.IsEnglish
            ? $"Write one complete, specific sentence in {targetLanguage}."
            : $"用{targetLanguage}写一个完整、具体、能独立理解的句子。",
        Hint = string.IsNullOrWhiteSpace(word.Meaning)
            ? (LocalizationService.Instance.IsEnglish ? "Choose the tense first, then clarify who did what and why." : "先确定时态，再把人物、动作和原因写清楚。")
            : (LocalizationService.Instance.IsEnglish ? $"Your note: {word.Meaning}" : $"你记录的含义是：{word.Meaning}"),
        UsagePattern = word.Word,
        UsageExplanation = string.IsNullOrWhiteSpace(word.Meaning)
            ? (LocalizationService.Instance.IsEnglish ? "Collocations require an AI connection." : "离线模式下暂不生成固定搭配。")
            : word.Meaning,
        UsageExample = $"Write a complete sentence using “{word.Word}”."
    };

    private static SentenceEvaluation CreateOfflineEvaluation(WordEntry word, string sentence)
    {
        var containsTarget = sentence.Contains(word.Word, StringComparison.OrdinalIgnoreCase);
        var startsUpper = sentence.Length > 0 && char.IsUpper(sentence[0]);
        var endsWell = sentence.EndsWith('.') || sentence.EndsWith('!') || sentence.EndsWith('?');
        var score = (containsTarget ? 55 : 20) + (startsUpper ? 20 : 0) + (endsWell ? 20 : 0);

        return new SentenceEvaluation
        {
            Score = Math.Min(score, 95),
            Summary = LocalizationService.Instance.IsEnglish
                ? "OR_KEY was not detected. This is a basic offline check; configure the key for full grammar and usage feedback."
                : "当前未检测到 OR_KEY，以上是离线基础检查；配置密钥后可获得语法、搭配和自然度的完整 AI 批改。",
            CorrectedSentence = sentence,
            BetterSentence = sentence,
            TargetUsage = new TargetUsageEvidence
            {
                TargetPresent = containsTarget,
                SpellingCorrect = containsTarget,
                MeaningCorrect = false,
                FormCorrect = false,
                CollocationCorrect = false,
                LocalGrammarCorrect = false,
                NaturalUsage = false,
                CoreCorrectionRequired = true,
                Confidence = 0,
                EvidenceSummary = LocalizationService.Instance.IsEnglish ? "Offline mode cannot verify target usage reliably." : "离线模式无法可靠判断目标词用法。"
            },
            Segments = [new FeedbackSegment
            {
                Text = sentence,
                Rating = containsTarget && startsUpper && endsWell ? "acceptable" : "error",
                Reason = containsTarget
                    ? (LocalizationService.Instance.IsEnglish ? "The target term appears in the sentence." : "已使用目标词。")
                    : (LocalizationService.Instance.IsEnglish ? "The target term does not appear in the sentence." : "句子中没有出现目标词。")
            }]
        };
    }

    private sealed class OpenRouterApiException(HttpStatusCode statusCode, string message) : Exception(message)
    {
        public HttpStatusCode StatusCode { get; } = statusCode;
    }
}
