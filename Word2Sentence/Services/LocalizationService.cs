using System.ComponentModel;
using System.Globalization;

namespace Word2Sentence.Services;

public sealed class LocalizationService : INotifyPropertyChanged
{
    private static readonly IReadOnlyDictionary<string, (string Zh, string En)> Strings =
        new Dictionary<string, (string, string)>(StringComparer.Ordinal)
        {
            ["AppTagline"] = ("把生词写进句子里", "Learn through sentences"),
            ["NavToday"] = ("今天", "Today"), ["NavPractice"] = ("造句练习", "Practice"),
            ["NavLibrary"] = ("单词库", "Word library"), ["NavSettings"] = ("设置", "Settings"),
            ["NavAbout"] = ("关于", "About"),
            ["TodayEyebrow"] = ("TODAY · 今日计划", "TODAY · STUDY PLAN"),
            ["TodayTitle"] = ("今天先写几句话", "Write a few sentences today"),
            ["TodaySubtitle"] = ("到期的词会排在前面。写完一句，再决定它什么时候回来。", "Due words come first. Each sentence helps decide when the word returns."),
            ["RecentCards"] = ("最近的单词 / 用法卡", "Recent word & usage cards"),
            ["RecentCardsHint"] = ("最近生成的 10 张卡片，每 6 秒从左到右轮播", "Your 10 latest cards rotate from left to right every 6 seconds"),
            ["UsageCard"] = ("用法卡", "Usage card"), ["CardsEmpty"] = ("完成一次 AI 出题后，这里会出现单词与常用搭配卡片。", "Complete an AI exercise to create word and usage cards."),
            ["Due"] = ("待复习", "Due"), ["WrittenToday"] = ("今日已写", "Written today"), ["WordTotal"] = ("单词总数", "Words"),
            ["UpNext"] = ("接下来", "Up next"), ["SortedByDue"] = ("按到期时间排序", "Sorted by due time"), ["StartWriting"] = ("开始造句", "Start writing"),
            ["ColumnWord"] = ("单词", "Word"), ["ColumnMeaning"] = ("释义 / 备注", "Meaning / notes"), ["ColumnStage"] = ("阶段", "Stage"),
            ["ColumnDue"] = ("到期", "Due"), ["ColumnNextReview"] = ("下次复习", "Next review"), ["ColumnSource"] = ("来源", "Source"),
            ["TodayEmpty"] = ("单词库还是空的，先去添加一个不会的词。", "Your word library is empty. Add a word you want to learn."),
            ["PracticeEyebrow"] = ("WRITE · 造句练习", "WRITE · SENTENCE PRACTICE"), ["NextWord"] = ("换一个词", "Another word"),
            ["NextRecommendedWord"] = ("下一个推荐词", "Next recommended word"),
            ["PracticeModeTitle"] = ("选择练习方式", "Choose a practice mode"), ["PracticeModeSubtitle"] = ("让系统挑选最紧急的词，或从近期复习候选中自由选择。", "Let the scheduler choose the most urgent word, or pick from your recent review candidates."),
            ["RecommendedMode"] = ("自动推荐", "Recommended"), ["RecommendedModeDesc"] = ("根据到期时间和 FSRS 状态选择当前最值得复习的词。", "Start with the word that is most urgent according to its due time and FSRS state."),
            ["StartRecommended"] = ("开始推荐练习", "Start recommended practice"), ["ChooseMode"] = ("从近期候选中选择", "Choose from recent candidates"),
            ["ChooseModeDesc"] = ("以下候选由同一推荐队列产生；优先显示已到期的词。", "These words come from the same recommendation queue, with due items first."),
            ["NoPracticeCandidates"] = ("暂无可练习的词，请先到单词库添加。", "No practice candidates yet. Add a word to the library first."),
            ["Scenario"] = ("情境", "Scenario"), ["WritingGoal"] = ("写作目标", "Writing goal"),
            ["RevealHint"] = ("查看提示（将影响自动复习判定）", "Reveal hint (affects automatic scheduling)"),
            ["WordUsageCard"] = ("单词 / 用法卡", "WORD / USAGE CARD"), ["YourSentence"] = ("你的句子", "Your sentence"),
            ["Submit"] = ("提交批改", "Check sentence"), ["SegmentFeedback"] = ("逐段反馈", "Inline feedback"),
            ["Excellent"] = ("表达出色", "Excellent"), ["Acceptable"] = ("正确，可优化", "Correct, can improve"), ["Error"] = ("语法 / 用法错误", "Grammar / usage error"),
            ["CorrectedSentence"] = ("修改后的句子 · 只修正错误", "Corrected sentence · errors only"),
            ["BetterSentence"] = ("表达更好的句子 · 更自然地道", "Stronger sentence · more natural"),
            ["LibraryEyebrow"] = ("WORD BOOK · 单词库", "WORD BOOK · LIBRARY"), ["LibraryTitle"] = ("把不会的词留在这里", "Keep the words you want to learn"),
            ["LibrarySubtitle"] = ("手动添加是主入口；造句中真正用错的词也会经你确认后收录。", "Add words yourself; mistakes found in writing are suggested for your approval."),
            ["TargetTerm"] = ("目标语言词 / 短语", "Target-language word / phrase"), ["MeaningOptional"] = ("释义或个人备注（可选）", "Meaning or personal note (optional)"),
            ["AddWord"] = ("加入单词库", "Add to library"), ["SearchTooltip"] = ("搜索单词或释义", "Search words or meanings"),
            ["DeleteSelected"] = ("删除选中", "Delete selected"), ["PracticeSelected"] = ("用选中词造句", "Practice selected"),
            ["SettingsEyebrow"] = ("PREFERENCES · 设置", "PREFERENCES · SETTINGS"), ["SettingsTitle"] = ("模型、语言与复习", "Model, languages & review"),
            ["SettingsSubtitle"] = ("密钥只从环境变量读取，不写入磁盘。", "The API key is read from the environment and never written to disk."),
            ["ModelId"] = ("模型 ID", "Model ID"), ["ModelHelp"] = ("支持 stealth/ox-alpha 与 deepseek/deepseek-v4-flash-0731；DeepSeek 会自动使用低推理强度平衡速度与完整性。", "Supports stealth/ox-alpha and deepseek/deepseek-v4-flash-0731; DeepSeek automatically uses low reasoning effort to balance speed and complete output."),
            ["ApiKey"] = ("环境变量 OR_KEY", "OR_KEY environment variable"), ["Refresh"] = ("重新检测", "Refresh"),
            ["LanguageInterface"] = ("界面语言", "Interface language"), ["TargetLanguage"] = ("学习目标语言", "Target language"),
            ["ExplanationLanguage"] = ("AI 解释语言", "AI explanation language"),
            ["ReviewData"] = ("复习与数据", "Review & data"), ["FsrsLabel"] = ("FSRS-6 · 目标留存率 90%", "FSRS-6 · 90% desired retention"),
            ["AutomaticScheduling"] = ("由 AI 多维证据自动调度，不提供用户自评按钮。", "Scheduled from multidimensional AI evidence—no self-rating buttons."),
            ["DailyGoal"] = ("每日目标", "Daily goal"), ["DataFile"] = ("本地数据文件", "Local data file"), ["SaveSettings"] = ("保存设置", "Save settings"),
            ["DialogTitle"] = ("选择要加入单词库的词", "Choose words to add"), ["DialogEyebrow"] = ("WORD CHECK · 错词确认", "WORD CHECK · REVIEW CANDIDATES"),
            ["DialogHeading"] = ("哪些词需要继续练？", "Which words need more practice?"),
            ["DialogDescription"] = ("下面是本次造句中可能掌握不好的词。已排除已有词和本批次重复项，请勾选后加入。", "These words may need more practice. Existing and duplicate entries have been removed; select what to add."),
            ["SelectAll"] = ("全选", "Select all"), ["SelectNone"] = ("全不选", "Select none"), ["NothingUnchecked"] = ("不勾选的词不会写入单词库。", "Unchecked words will not be added."),
            ["Skip"] = ("暂不添加", "Not now"), ["AddSelected"] = ("加入所选", "Add selected"), ["ChooseFirst"] = ("请先选择", "Select a word"),
            ["StageNew"] = ("新词", "New"), ["StageLearning"] = ("初识", "Learning"), ["StageFamiliar"] = ("熟悉", "Familiar"), ["StageMastered"] = ("掌握", "Mastered"), ["StageReview"] = ("巩固", "Review"),
            ["Today"] = ("今天", "Today"), ["Tomorrow"] = ("明天", "Tomorrow"), ["DaysLater"] = ("{0} 天后", "In {0} days"), ["TodayAt"] = ("今天 {0}", "Today {0}"),
            ["Chars"] = ("{0} 字符", "{0} chars"), ["AllWords"] = ("全部单词 · {0}", "All words · {0}"), ["SearchResults"] = ("搜索结果 · {0}", "Results · {0}"),
            ["ApiReady"] = ("OpenRouter 已就绪", "OpenRouter ready"), ["ApiMissing"] = ("未检测到 OR_KEY", "OR_KEY not found"),
            ["KeyDetected"] = ("已检测到（密钥不会显示或保存）", "Detected (never displayed or saved)"), ["KeyFallback"] = ("当前进程未检测到，将使用离线基础检查", "Not detected; basic offline checks will be used"),
            ["NoMeaning"] = ("暂未记录释义", "No meaning recorded"), ["PreparingScenario"] = ("正在准备情境…", "Preparing a scenario…"),
            ["CreatingExercise"] = ("正在通过 OpenRouter 出题…", "Creating an exercise with OpenRouter…"), ["OfflineMode"] = ("离线模式：未检测到 OR_KEY", "Offline mode: OR_KEY not found"),
            ["HintPrefix"] = ("提示：{0}", "Hint: {0}"), ["CreatedBy"] = ("由 {0} 出题", "Exercise by {0}"), ["OfflineBasic"] = ("离线基础模式", "Basic offline mode"),
            ["SentenceRequired"] = ("请先写一个完整句子。", "Write a complete sentence first."), ["CheckingSentence"] = ("正在并行检查写作质量与目标词用法…", "Checking writing quality and target usage in parallel…"),
            ["CheckingCombined"] = ("正在一次完成写作批改与目标词核验…", "Checking writing and target usage in one structured pass…"),
            ["OfflineChecking"] = ("正在进行离线基础检查…", "Running basic offline checks…"), ["CheckingEvidence"] = ("写作批改完成，正在独立核验目标词用法…", "Writing feedback complete. Verifying target usage independently…"),
            ["RecheckingEvidence"] = ("目标词证据不够稳定，正在进行第二次独立核验…", "Target evidence is uncertain. Running a second independent check…"),
            ["NoNewCandidates"] = ("本次没有新的错词候选；已有词和重复项已排除。", "No new word candidates; existing and duplicate entries were removed."),
            ["NoWordsAdded"] = ("本次未向单词库添加错词。", "No suggested words were added."), ["WordsAdded"] = ("已按你的选择加入单词库：{0}", "Added to the library: {0}"),
            ["ScheduledNext"] = ("已由系统自动安排 · 下次复习 {0}", "Scheduled automatically · next review {0}"),
            ["EvidenceConflict"] = ("AI 证据仍不一致：未改动长期记忆状态，10 分钟后自动复测。", "AI evidence still conflicts. Long-term memory state was preserved; automatic retest in 10 minutes."),
            ["AutoDecision"] = ("系统自动记忆判定：{0}", "Automatic memory decision: {0}"), ["RejectedDecision"] = ("系统未采用本次记忆判定：{0}", "Memory decision not applied: {0}"),
            ["InvalidTerm"] = ("请输入有效的目标语言词或短语。", "Enter a valid target-language word or phrase."), ["DuplicateWord"] = ("这个词已经在单词库里了。", "This word is already in the library."),
            ["WordAdded"] = ("已加入 {0}，现在就可以开始造句。", "Added {0}. You can start writing now."), ["SelectWord"] = ("请先选择一个单词。", "Select a word first."),
            ["DeleteConfirm"] = ("删除“{0}”及其复习进度？历史造句记录会保留。", "Delete “{0}” and its review progress? Sentence history will be kept."), ["DeleteTitle"] = ("删除单词", "Delete word"), ["WordDeleted"] = ("已删除 {0}。", "Deleted {0}."),
            ["ModelInvalid"] = ("请输入完整的 OpenRouter 模型 ID。", "Enter a complete OpenRouter model ID."), ["DailyInvalid"] = ("每日目标请输入 1–100。", "Daily goal must be between 1 and 100."),
            ["LanguageInvalid"] = ("请填写学习目标语言和 AI 解释语言。", "Enter both the target language and AI explanation language."), ["SettingsSaved"] = ("设置已保存。", "Settings saved."),
            ["Cancelled"] = ("操作已取消。", "Operation cancelled."), ["TodayComplete"] = ("今天的到期词已经写完了。你仍可从单词库自由练习。", "You are done with today's due words. You can still practice from the library."),
            ["RequestTimedOut"] = ("模型请求超时，请重试；长期记忆状态未改动。", "The model request timed out. Please retry; long-term memory state was not changed."),
            ["SourceManual"] = ("手动添加", "Manual"), ["SourceMistake"] = ("造句错词", "Writing mistake"),
            ["CandidateSummary"] = ("候选 {0} 个 · 已选 {1} 个", "{0} candidates · {1} selected"), ["AddSelectedCount"] = ("加入所选（{0}）", "Add selected ({0})"),
            ["AboutEyebrow"] = ("ABOUT · 关于软件", "ABOUT · WORD2SENTENCE"), ["AboutTitle"] = ("关于 Word2Sentence", "About Word2Sentence"),
            ["AboutDescription"] = ("一款通过主动造句、AI 多维反馈和 FSRS-6 自动调度学习词汇的本地优先桌面软件。", "A local-first desktop app for learning vocabulary through sentence production, multidimensional AI feedback, and automatic FSRS-6 scheduling."),
            ["AboutDeveloper"] = ("开发者", "Developer"), ["AboutVersion"] = ("版本", "Version"), ["AboutLicense"] = ("软件许可证", "License"),
            ["AboutListed"] = ("已被 awesome-fsrs 收录", "Listed in awesome-fsrs"),
            ["AboutListedDescription"] = ("Word2Sentence 已收录于 Open Spaced Repetition 社区维护的 awesome-fsrs 项目列表。", "Word2Sentence is included in the community-maintained awesome-fsrs project list by Open Spaced Repetition."),
            ["AboutThanks"] = ("感谢你使用 Word2Sentence。你的支持会帮助项目持续改进。", "Thank you for using Word2Sentence. Your support helps the project keep improving."),
            ["AboutStarPrompt"] = ("如果这个项目对你有帮助，欢迎在 GitHub 上为它点亮 Star。", "If Word2Sentence helps you, please consider starring the project on GitHub."),
            ["StarOnGitHub"] = ("在 GitHub 上星标", "Star on GitHub"), ["ViewSource"] = ("查看源代码", "View source"), ["ViewAwesomeFsrs"] = ("查看 awesome-fsrs", "View awesome-fsrs"),
        };

    public static LocalizationService Instance { get; } = new();
    private string _language = "zh-CN";

    public event PropertyChangedEventHandler? PropertyChanged;
    public string Language => _language;
    public bool IsEnglish => _language.StartsWith("en", StringComparison.OrdinalIgnoreCase);
    public string this[string key] => Get(key);

    public void SetLanguage(string? language)
    {
        var normalized = language?.StartsWith("en", StringComparison.OrdinalIgnoreCase) == true ? "en-US" : "zh-CN";
        if (_language == normalized) return;
        _language = normalized;
        CultureInfo.CurrentUICulture = CultureInfo.GetCultureInfo(normalized);
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs("Item[]"));
    }

    public string Get(string key, params object[] args)
    {
        if (!Strings.TryGetValue(key, out var pair)) return key;
        var value = IsEnglish ? pair.En : pair.Zh;
        return args.Length == 0 ? value : string.Format(CultureInfo.CurrentCulture, value, args);
    }

    public static string T(string key, params object[] args) => Instance.Get(key, args);
}
