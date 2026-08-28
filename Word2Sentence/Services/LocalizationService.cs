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
            ["NavLibrary"] = ("单词库", "Word library"), ["NavStatistics"] = ("学习统计", "Statistics"), ["NavSettings"] = ("设置", "Settings"),
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
            ["StatisticsEyebrow"] = ("INSIGHTS · 学习统计", "INSIGHTS · LEARNING STATS"),
            ["StatisticsTitle"] = ("让进步看得见", "See your progress"),
            ["StatisticsSubtitle"] = ("从造句记录、分数和复习状态中，看到学习节奏与真正需要巩固的词。", "See your learning rhythm and what needs reinforcement from sentence reviews, scores, and memory state."),
            ["StatisticsTotalReviews"] = ("累计造句", "Sentence reviews"), ["StatisticsLearnedWords"] = ("练过的词", "Words practised"),
            ["StatisticsNewWords30"] = ("近 30 天新增", "New in 30 days"), ["StatisticsAverageScore"] = ("平均得分", "Average score"),
            ["StatisticsStreak"] = ("连续学习", "Learning streak"), ["StatisticsCurrentStreak"] = ("当前连胜", "Current streak"),
            ["StatisticsBestStreak"] = ("最长连胜", "Best streak"), ["StatisticsActiveDays"] = ("近 30 天活跃", "Active in 30 days"),
            ["StatisticsDays"] = ("{0} 天", "{0} days"), ["StatisticsCalendar"] = ("打卡日历", "Activity calendar"),
            ["StatisticsCalendarHint"] = ("造句复习或新增单词都会点亮一天。颜色越深，当天投入越多。", "A review or a new word lights up the day. Darker cells mean more activity."),
            ["StatisticsCalendarTooltip"] = ("{0} · {1} 次学习活动", "{0} · {1} learning activities"),
            ["StatisticsTrend"] = ("最近 14 天", "Last 14 days"), ["StatisticsTrendHint"] = ("练习次数、平均分与新增词", "Reviews, average score, and new words"),
            ["StatisticsReviewsLegend"] = ("练习次数", "Reviews"), ["StatisticsScoreLegend"] = ("平均分", "Average score"),
            ["StatisticsNewWordsLegend"] = ("新增词", "New words"), ["StatisticsScoreDistribution"] = ("分数分布", "Score distribution"),
            ["StatisticsMastery"] = ("掌握阶段", "Mastery stages"), ["StatisticsRecallCoverage"] = ("主动回忆覆盖率", "Active recall coverage"),
            ["StatisticsRecallCoverageHint"] = ("至少完成过一次造句的词，占词库总数的比例。", "The share of library words used in at least one sentence review."),
            ["StatisticsStableMastery"] = ("稳定掌握率", "Stable mastery"),
            ["StatisticsStableMasteryHint"] = ("达到稳定间隔或完成多轮复习的词，占词库总数的比例。", "The share of words with a stable interval or several completed reviews."),
            ["StatisticsReinforcement"] = ("需要巩固", "Needs reinforcement"),
            ["StatisticsReinforcementHint"] = ("已经到期且有遗忘记录，或最近一次得分低于 70 的词。", "Words due after a lapse, or scoring below 70 on their latest review."),
            ["StatisticsNoData"] = ("完成第一句造句后，这里会开始记录你的学习轨迹。", "Complete your first sentence to start building your learning history."),
            ["WeekMon"] = ("一", "Mon"), ["WeekTue"] = ("二", "Tue"), ["WeekWed"] = ("三", "Wed"), ["WeekThu"] = ("四", "Thu"),
            ["WeekFri"] = ("五", "Fri"), ["WeekSat"] = ("六", "Sat"), ["WeekSun"] = ("日", "Sun"),
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
            ["SettingsSubtitle"] = ("API 密钥可从 OR_KEY 读取，或加密保存在 Windows 凭据管理器中。", "The API key can come from OR_KEY or be stored securely in Windows Credential Manager."),
            ["SettingsAiBoundary"] = ("AI 功能可以不启用；启用后只发送当前练习所需文本。", "AI is optional; when enabled, only text needed for the current exercise is sent."),
            ["SettingsLocalBoundary"] = ("完整词库、复习历史与用法卡默认保存在本机。", "The full word library, review history, and usage cards stay on this device by default."),
            ["ModelId"] = ("模型 ID", "Model ID"), ["ModelHelp"] = ("支持 stealth/ox-alpha 与 deepseek/deepseek-v4-flash-0731；DeepSeek 会自动使用低推理强度平衡速度与完整性。", "Supports stealth/ox-alpha and deepseek/deepseek-v4-flash-0731; DeepSeek automatically uses low reasoning effort to balance speed and complete output."),
            ["ApiKey"] = ("OpenRouter API 密钥", "OpenRouter API key"), ["Refresh"] = ("重新检测", "Refresh"), ["ConfigureKey"] = ("配置 / 更换", "Configure / replace"),
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
            ["ApiReady"] = ("OpenRouter 已就绪", "OpenRouter ready"), ["ApiMissing"] = ("尚未配置 API 密钥", "API key not configured"),
            ["KeyDetectedEnvironment"] = ("已从 OR_KEY 环境变量读取", "Loaded from the OR_KEY environment variable"),
            ["KeyDetectedCredential"] = ("已安全保存在 Windows 凭据管理器", "Stored securely in Windows Credential Manager"),
            ["KeyFallback"] = ("尚未配置，将使用离线基础检查", "Not configured; basic offline checks will be used"),
            ["NoMeaning"] = ("暂未记录释义", "No meaning recorded"), ["PreparingScenario"] = ("正在准备情境…", "Preparing a scenario…"),
            ["CreatingExercise"] = ("正在通过 OpenRouter 出题…", "Creating an exercise with OpenRouter…"), ["OfflineMode"] = ("离线模式：尚未配置 API 密钥", "Offline mode: API key not configured"),
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
            ["AboutReciteListed"] = ("已被 awesome-recite-tools 收录", "Listed in awesome-recite-tools"),
            ["AboutReciteListedDescription"] = ("如果您有自己开发或推荐的复习软件，欢迎提交到OpenRecite社区维护的awesome-recite-tools目录", "If you have developed or recommend a review app, you are welcome to submit it to the awesome-recite-tools directory maintained by the OpenRecite community."),
            ["AboutThanks"] = ("感谢你使用 Word2Sentence。你的支持会帮助项目持续改进。", "Thank you for using Word2Sentence. Your support helps the project keep improving."),
            ["AboutStarPrompt"] = ("如果这个项目对你有帮助，欢迎在 GitHub 上为它点亮 Star。", "If Word2Sentence helps you, please consider starring the project on GitHub."),
            ["StarOnGitHub"] = ("在 GitHub 上星标", "Star on GitHub"), ["ViewSource"] = ("查看源代码", "View source"), ["ViewAwesomeFsrs"] = ("查看 awesome-fsrs", "View awesome-fsrs"),
            ["ViewAwesomeReciteTools"] = ("查看 awesome-recite-tools", "View awesome-recite-tools"),
            ["SetupWindowTitle"] = ("配置 OpenRouter", "Set up OpenRouter"), ["SetupEyebrow"] = ("FIRST RUN · 首次配置", "FIRST RUN · OPENROUTER"),
            ["SetupTitle"] = ("连接你的 OpenRouter 账户", "Connect your OpenRouter account"),
            ["SetupSubtitle"] = ("Word2Sentence 使用 OpenRouter 生成造句题目并进行反馈。选择适合你的配置方式。", "Word2Sentence uses OpenRouter to create exercises and feedback. Choose the setup path that suits you."),
            ["SetupChoosePath"] = ("你希望怎样开始？", "How would you like to start?"),
            ["SetupBeginner"] = ("我是小白用户", "Guide me step by step"),
            ["SetupBeginnerDesc"] = ("依次完成注册、充值、创建密钥和连接验证，每一步都有官方入口。", "Walk through sign-up, credits, key creation, and connection verification with official links."),
            ["SetupTechnical"] = ("我是技术用户", "I am a technical user"),
            ["SetupTechnicalDesc"] = ("我已经有 OpenRouter API key，直接粘贴并验证。", "I already have an OpenRouter API key and want to validate it directly."),
            ["SetupOffline"] = ("暂时离线使用", "Use offline for now"), ["SetupOfficialOnly"] = ("仅打开 OpenRouter 官方页面", "Opens official OpenRouter pages only"),
            ["SetupStep"] = ("第 {0} 步，共 {1} 步", "STEP {0} OF {1}"), ["SetupBack"] = ("返回", "Back"), ["SetupNext"] = ("下一步", "Next"),
            ["SetupAccountTitle"] = ("注册或登录 OpenRouter", "Create or sign in to your account"),
            ["SetupAccountDesc"] = ("不需要安装其他软件。点击按钮后会使用默认浏览器打开 OpenRouter 官方登录页，注册和登录使用同一个入口。", "You do not need to install anything else. The button opens OpenRouter's official sign-in page in your default browser; sign-up and sign-in use the same entry point."),
            ["SetupAccountInstruction"] = ("1. 点击下方“打开 OpenRouter 登录页”。\n2. 在网页上选择任意可用的登录方式；首次使用时按页面提示完成账户创建和确认。\n3. 登录成功并看到 OpenRouter 页面后，不要关闭 Word2Sentence。\n4. 回到本窗口，点击右下角“下一步”。", "1. Choose Open OpenRouter sign-in below.\n2. Pick any sign-in method shown on the page; first-time users should follow the prompts to create and confirm an account.\n3. After OpenRouter signs you in, leave Word2Sentence open.\n4. Return to this window and choose Next in the lower-right corner."),
            ["OpenSignIn"] = ("打开 OpenRouter 登录页", "Open OpenRouter sign-in"),
            ["SetupCreditsTitle"] = ("为账户添加余额", "Add credits to your account"),
            ["SetupCreditsDesc"] = ("充值入口不在页面顶部。进入 Credits 页面后，需要向下找到 One-time payment（一次性付款）区域。当前免费模型可以先体验，不充值也能继续下一步。", "The top-up control is not at the top of the page. On Credits, scroll down to the One-time payment section. You can continue without paying if you only want to try a free model."),
            ["SetupCreditsInstruction"] = ("1. 点击下方“打开余额与充值页面”。\n2. 如果网页要求登录，先完成登录；随后向下滚动页面。\n3. 找到 One-time payment（一次性付款），不要误选 Auto top-up（自动充值）。\n4. 点击一次性付款区域，在金额框中填写你愿意充值的美元金额。\n5. 选择网页提供的支付方式，核对实际金额和手续费后再确认付款。\n6. 付款完成后返回 Credits 页面，确认余额已经增加；若暂未到账可刷新或稍等片刻。\n7. 回到 Word2Sentence，点击“下一步”。只体验免费模型时可跳过第 3–6 步。", "1. Choose Open Credits page below.\n2. Sign in if asked, then scroll down the page.\n3. Find One-time payment; do not accidentally choose Auto top-up.\n4. Open the one-time payment section and enter the USD amount you are comfortable adding.\n5. Select an offered payment method and review the amount and fee before confirming.\n6. Return to Credits and confirm that the balance increased; refresh or wait briefly if it has not appeared yet.\n7. Return to Word2Sentence and choose Next. To try only a free model, skip steps 3–6."),
            ["OpenCredits"] = ("打开余额与充值页面", "Open Credits page"),
            ["SetupCreateKeyTitle"] = ("创建专用 API 密钥", "Create a dedicated API key"),
            ["SetupCreateKeyDesc"] = ("为 Word2Sentence 单独创建一个密钥，日后可以独立查看和限制用量。创建完成后的完整密钥只会显示一次。", "Create a separate key for Word2Sentence so you can inspect and limit its usage independently. The complete key is shown only once after creation."),
            ["SetupCreateKeyInstruction"] = ("1. 点击下方按钮打开 API Keys 页面。\n2. 点击 Create Key（创建密钥）。\n3. 名称填写 Word2Sentence；消费上限是可选项，小白用户可以先保持默认。\n4. 确认创建后，立即点击复制按钮，保存以 sk-or- 开头的完整密钥。\n5. 不要把密钥发送给他人，也不要发布包含密钥的截图。复制后回到本窗口点击“下一步”。", "1. Open API Keys using the button below.\n2. Choose Create Key.\n3. Enter Word2Sentence as the name; the spending limit is optional and beginners may leave its default.\n4. Confirm creation, then immediately copy the complete key beginning with sk-or-.\n5. Never send the key to anyone or publish it in a screenshot. Return here and choose Next after copying it."),
            ["OpenKeys"] = ("打开 API Keys 页面", "Open API Keys"),
            ["SetupConnectTitle"] = ("粘贴并验证密钥", "Paste and verify your key"),
            ["SetupConnectDesc"] = ("点击输入框右侧的“粘贴”，确认你复制的是以 sk-or- 开头的完整密钥，再点击右下角“验证并保存”。软件只会向 OpenRouter 官方接口发送一次只读验证请求。", "Choose Paste beside the field, make sure you copied the complete key beginning with sk-or-, then choose Validate and save in the lower-right corner. The app sends only one read-only request to OpenRouter's official API."),
            ["OpenRouterApiKey"] = ("OPENROUTER API KEY", "OPENROUTER API KEY"), ["PasteKey"] = ("粘贴", "Paste"),
            ["KeyPrivacy"] = ("密钥不会显示在界面或写入 wordbook.json；保存后仅当前 Windows 用户可读取。", "The key is never displayed or written to wordbook.json; after saving, only the current Windows user can retrieve it."),
            ["ValidateAndSave"] = ("验证并保存", "Validate and save"), ["ValidatingKey"] = ("正在连接 OpenRouter 验证密钥…", "Connecting to OpenRouter to validate the key…"),
            ["KeyValid"] = ("验证成功，密钥已安全保存。", "Validated and saved securely."), ["KeyInvalid"] = ("密钥无效或没有访问权限，请确认复制了完整的 API key。", "The key is invalid or unauthorized. Make sure you copied the complete API key."),
            ["KeyNetwork"] = ("无法连接 OpenRouter，请检查网络后重试。密钥尚未保存。", "Could not reach OpenRouter. Check your connection and try again; the key was not saved."),
            ["KeyServer"] = ("OpenRouter 暂时无法完成验证，请稍后重试。密钥尚未保存。", "OpenRouter could not complete validation. Try again later; the key was not saved."),
            ["KeySaveFailed"] = ("验证成功，但无法写入 Windows 凭据管理器。请以当前用户重新运行软件后重试。", "Validation succeeded, but Windows Credential Manager could not save the key. Run the app as the current user and try again."),
            ["SetupTechnicalEyebrow"] = ("DIRECT SETUP · 直接配置", "DIRECT SETUP"), ["SetupTechnicalTitle"] = ("直接连接现有密钥", "Connect an existing key"),
            ["SetupTechnicalInstruction"] = ("粘贴现有 OpenRouter API key。软件通过 GET /api/v1/key 验证后，将其保存到当前用户的 Windows 凭据管理器。现有 OR_KEY 环境变量仍具有更高优先级。", "Paste an existing OpenRouter API key. After validation with GET /api/v1/key, it is stored in Windows Credential Manager for the current user. An existing OR_KEY environment variable still takes precedence."),
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
