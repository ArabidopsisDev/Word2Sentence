using System.Collections.ObjectModel;
using System.Diagnostics;
using System.Net.Http;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Documents;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Threading;
using Word2Sentence.Models;
using Word2Sentence.Services;

namespace Word2Sentence;

public partial class MainWindow : Window
{
    private enum PracticeMode
    {
        Recommended,
        Manual
    }

    private const string RepositoryUrl = "https://github.com/ArabidopsisDev/Word2Sentence";
    private const string AwesomeFsrsUrl = "https://github.com/open-spaced-repetition/awesome-fsrs#specialized-flashcard";
    private const string AwesomeReciteToolsUrl = "https://github.com/OpenRecite/awesome-recite-tools";
    private readonly DataStore _store = new();
    private readonly OpenRouterService _ai = new(new HttpClient
    {
        Timeout = TimeSpan.FromMinutes(4)
    });
    private readonly DispatcherTimer _cardCarouselTimer = new() { Interval = TimeSpan.FromSeconds(6) };

    private AppData _data = new();
    private WordEntry? _currentWord;
    private SentenceChallenge? _challenge;
    private CancellationTokenSource? _requestCancellation;
    private bool _isBusy;
    private bool _hintUsed;
    private bool _pasteUsed;
    private bool _suppressInputMetrics;
    private int _sentenceEditCount;
    private DateTimeOffset _practiceStartedAt;
    private PracticeMode _practiceMode = PracticeMode.Manual;
    private List<UsageCard> _recentCards = [];

    public MainWindow()
    {
        InitializeComponent();
        _cardCarouselTimer.Tick += (_, _) => MoveCardCarousel(1);
        Loaded += MainWindow_Loaded;
        Closed += (_, _) =>
        {
            _cardCarouselTimer.Stop();
            _requestCancellation?.Cancel();
        };
    }

    private async void MainWindow_Loaded(object sender, RoutedEventArgs e)
    {
        _data = await _store.LoadAsync();
        LocalizationService.Instance.SetLanguage(_data.Settings.UiLanguage);
        ModelTextBox.Text = _data.Settings.Model;
        DailyGoalTextBox.Text = _data.Settings.DailyGoal.ToString();
        UiLanguageComboBox.SelectedValue = _data.Settings.UiLanguage;
        TargetLanguageTextBox.Text = _data.Settings.TargetLanguage;
        ExplanationLanguageTextBox.Text = _data.Settings.ExplanationLanguage;
        var version = typeof(MainWindow).Assembly.GetName().Version;
        AboutVersionText.Text = version is null ? "1.0.0" : $"{version.Major}.{version.Minor}.{Math.Max(0, version.Build)}";
        DataPathText.Text = _store.DataPath;
        RefreshAll();
        ShowPage(TodayPage, TodayNav);
        _cardCarouselTimer.Start();
        if (!_ai.HasApiKey)
        {
            var setupWindow = new OpenRouterSetupWindow(_ai) { Owner = this };
            setupWindow.ShowDialog();
            RefreshApiStatus();
        }
    }

    private void TitleBar_MouseLeftButtonDown(object sender, MouseButtonEventArgs e)
    {
        if (e.ChangedButton != MouseButton.Left) return;
        if (e.ClickCount == 2)
        {
            ToggleMaximize();
            return;
        }

        try { DragMove(); }
        catch (InvalidOperationException) { }
    }

    private void MinimizeWindow_Click(object sender, RoutedEventArgs e) => WindowState = WindowState.Minimized;
    private void MaximizeWindow_Click(object sender, RoutedEventArgs e) => ToggleMaximize();
    private void CloseWindow_Click(object sender, RoutedEventArgs e) => Close();

    private void ToggleMaximize() => WindowState = WindowState == WindowState.Maximized
        ? WindowState.Normal
        : WindowState.Maximized;

    private void Window_StateChanged(object sender, EventArgs e)
    {
        if (MaximizeWindowButton is not null)
            MaximizeWindowButton.Content = WindowState == WindowState.Maximized ? "\uE923" : "\uE922";
    }

    private void TodayNav_Click(object sender, RoutedEventArgs e) => ShowPage(TodayPage, TodayNav);
    private void PracticeNav_Click(object sender, RoutedEventArgs e) => ShowPracticeChooser();
    private void LibraryNav_Click(object sender, RoutedEventArgs e) => ShowPage(LibraryPage, LibraryNav);
    private void SettingsNav_Click(object sender, RoutedEventArgs e) => ShowPage(SettingsPage, SettingsNav);
    private void AboutNav_Click(object sender, RoutedEventArgs e) => ShowPage(AboutPage, AboutNav);

    private void ShowPage(FrameworkElement page, Button navButton)
    {
        TodayPage.Visibility = Visibility.Collapsed;
        PracticePage.Visibility = Visibility.Collapsed;
        LibraryPage.Visibility = Visibility.Collapsed;
        SettingsPage.Visibility = Visibility.Collapsed;
        AboutPage.Visibility = Visibility.Collapsed;
        page.Visibility = Visibility.Visible;

        foreach (var button in new[] { TodayNav, PracticeNav, LibraryNav, SettingsNav, AboutNav })
        {
            button.Background = Brushes.Transparent;
            button.Foreground = FindBrush("TextMutedBrush");
            button.FontWeight = FontWeights.Normal;
        }

        navButton.Background = FindBrush("AccentSoftBrush");
        navButton.Foreground = FindBrush("AccentBrush");
        navButton.FontWeight = FontWeights.SemiBold;
    }

    private void OpenRepository_Click(object sender, RoutedEventArgs e) => OpenExternalUrl(RepositoryUrl);
    private void OpenAwesomeFsrs_Click(object sender, RoutedEventArgs e) => OpenExternalUrl(AwesomeFsrsUrl);
    private void OpenAwesomeReciteTools_Click(object sender, RoutedEventArgs e) => OpenExternalUrl(AwesomeReciteToolsUrl);

    private static void OpenExternalUrl(string url)
    {
        try { Process.Start(new ProcessStartInfo(url) { UseShellExecute = true }); }
        catch { }
    }

    private void StartPractice_Click(object sender, RoutedEventArgs e)
    {
        ShowPracticeChooser();
    }

    private async void DueList_MouseDoubleClick(object sender, MouseButtonEventArgs e)
    {
        if (DueList.SelectedItem is WordEntry word)
        {
            _practiceMode = PracticeMode.Manual;
            await BeginPracticeAsync(word);
        }
    }

    private async Task BeginPracticeAsync(WordEntry? requestedWord)
    {
        if (_data.Words.Count == 0)
        {
            LibraryMessageText.Text = LocalizationService.T("TodayEmpty");
            ShowPage(LibraryPage, LibraryNav);
            NewWordTextBox.Focus();
            return;
        }

        _currentWord = requestedWord ?? SelectNextWord(_currentWord?.Id);
        if (_currentWord is null) return;

        ShowPage(PracticePage, PracticeNav);
        PracticeChooserPanel.Visibility = Visibility.Collapsed;
        PracticeSessionPanel.Visibility = Visibility.Visible;
        SessionWordActionButton.Content = LocalizationService.T(
            _practiceMode == PracticeMode.Recommended ? "NextRecommendedWord" : "NextWord");
        PracticeWordText.Text = _currentWord.Word;
        PracticeMeaningText.Text = string.IsNullOrWhiteSpace(_currentWord.Meaning)
            ? LocalizationService.T("NoMeaning")
            : _currentWord.Meaning;
        PracticeStageText.Text = _currentWord.Stage;
        ScenarioText.Text = LocalizationService.T("PreparingScenario");
        GoalText.Text = string.Empty;
        HintText.Text = string.Empty;
        HintText.Visibility = Visibility.Collapsed;
        RevealHintButton.Visibility = Visibility.Visible;
        _hintUsed = false;
        _pasteUsed = false;
        PracticeUsageCard.Visibility = Visibility.Collapsed;
        PracticeUsageItems.ItemsSource = null;
        _suppressInputMetrics = true;
        SentenceInput.Text = string.Empty;
        _suppressInputMetrics = false;
        _sentenceEditCount = 0;
        FeedbackCard.Visibility = Visibility.Collapsed;
        PracticeStatusText.Text = _ai.HasApiKey
            ? LocalizationService.T("CreatingExercise")
            : LocalizationService.T("OfflineMode");

        await RunBusyAsync(async cancellationToken =>
        {
            using var requestTimeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            requestTimeout.CancelAfter(TimeSpan.FromSeconds(90));
            _challenge = await _ai.CreateChallengeAsync(
                _currentWord,
                _data.Settings.Model,
                _data.Settings.TargetLanguage,
                _data.Settings.ExplanationLanguage,
                _data.Reviews,
                requestTimeout.Token);
            ScenarioText.Text = _challenge.Scenario;
            GoalText.Text = _challenge.Goal;
            HintText.Text = LocalizationService.T("HintPrefix", _challenge.Hint);
            _practiceStartedAt = DateTimeOffset.Now;
            PracticeStatusText.Text = _ai.HasApiKey
                ? LocalizationService.T("CreatedBy", _data.Settings.Model)
                : LocalizationService.T("OfflineBasic");
            SentenceInput.Focus();
        });
    }

    private void ShowPracticeChooser()
    {
        if (_data.Words.Count == 0)
        {
            LibraryMessageText.Text = LocalizationService.T("TodayEmpty");
            ShowPage(LibraryPage, LibraryNav);
            NewWordTextBox.Focus();
            return;
        }

        ShowPage(PracticePage, PracticeNav);
        PracticeSessionPanel.Visibility = Visibility.Collapsed;
        PracticeChooserPanel.Visibility = Visibility.Visible;
        var candidates = GetPracticeCandidates();
        PracticeCandidateList.ItemsSource = candidates;
        PracticeCandidateEmptyText.Visibility = candidates.Count == 0 ? Visibility.Visible : Visibility.Collapsed;
    }

    private List<WordEntry> GetPracticeCandidates() => _data.Words
        .OrderBy(word => word.NextReviewAt <= DateTimeOffset.Now ? 0 : 1)
        .ThenBy(word => word.NextReviewAt)
        .ThenBy(word => word.CreatedAt)
        .Take(10)
        .ToList();

    private async void StartRecommended_Click(object sender, RoutedEventArgs e)
    {
        var recommended = GetPracticeCandidates().FirstOrDefault();
        if (recommended is not null)
        {
            _practiceMode = PracticeMode.Recommended;
            await BeginPracticeAsync(recommended);
        }
    }

    private async void PracticeCandidate_Click(object sender, RoutedEventArgs e)
    {
        if (sender is Button { Tag: WordEntry word })
        {
            _practiceMode = PracticeMode.Manual;
            await BeginPracticeAsync(word);
        }
    }

    private void RevealHint_Click(object sender, RoutedEventArgs e)
    {
        _hintUsed = true;
        HintText.Visibility = Visibility.Visible;
        RevealHintButton.Visibility = Visibility.Collapsed;
    }

    private WordEntry? SelectNextWord(Guid? excludeId = null)
    {
        var ordered = _data.Words
            .OrderBy(word => word.NextReviewAt)
            .ThenBy(word => word.CreatedAt)
            .ToList();
        return ordered.FirstOrDefault(word => word.Id != excludeId) ?? ordered.FirstOrDefault();
    }

    private void UpsertUsageCard(WordEntry word, SentenceChallenge challenge)
    {
        var usageItems = challenge.UsageItems
            .Where(item => !string.IsNullOrWhiteSpace(item.Pattern))
            .Take(3)
            .Select(item => new UsagePatternItem
            {
                Pattern = item.Pattern.Trim(),
                Meaning = item.Meaning.Trim(),
                Example = item.Example.Trim()
            })
            .ToList();
        if (usageItems.Count == 0) return;

        var primary = usageItems[0];
        var existing = _data.Cards.FirstOrDefault(card => card.WordId == word.Id);

        if (existing is null)
        {
            _data.Cards.Add(new UsageCard
            {
                WordId = word.Id,
                Word = word.Word,
                UsagePattern = primary.Pattern,
                Explanation = primary.Meaning,
                Example = primary.Example,
                UsageItems = usageItems,
                CreatedAt = DateTimeOffset.Now
            });
        }
        else
        {
            existing.Word = word.Word;
            existing.UsagePattern = primary.Pattern;
            existing.Explanation = primary.Meaning;
            existing.Example = primary.Example;
            existing.UsageItems = usageItems;
            existing.CreatedAt = DateTimeOffset.Now;
        }

        foreach (var oldCard in _data.Cards.OrderByDescending(card => card.CreatedAt).Skip(100).ToList())
            _data.Cards.Remove(oldCard);
    }

    private void PreviousCard_Click(object sender, RoutedEventArgs e) => MoveCardCarousel(-1);
    private void NextCard_Click(object sender, RoutedEventArgs e) => MoveCardCarousel(1);

    private void MoveCardCarousel(int direction)
    {
        if (TodayPage.Visibility != Visibility.Visible || _recentCards.Count < 2) return;
        var current = CardCarousel.SelectedIndex < 0 ? 0 : CardCarousel.SelectedIndex;
        var next = (current + direction + _recentCards.Count) % _recentCards.Count;
        CardCarousel.SelectedIndex = next;
        CardCarousel.ScrollIntoView(CardCarousel.SelectedItem);
    }

    private async void NextWord_Click(object sender, RoutedEventArgs e)
    {
        if (_isBusy) return;
        if (_practiceMode == PracticeMode.Recommended)
        {
            var next = GetPracticeCandidates().FirstOrDefault(word => word.Id != _currentWord?.Id);
            if (next is not null)
            {
                await BeginPracticeAsync(next);
                return;
            }
        }
        ShowPracticeChooser();
    }

    private async void Evaluate_Click(object sender, RoutedEventArgs e)
    {
        if (_isBusy || _currentWord is null || _challenge is null) return;
        var sentence = SentenceInput.Text.Trim();
        if (sentence.Length < 3)
        {
            PracticeStatusText.Text = LocalizationService.T("SentenceRequired");
            SentenceInput.Focus();
            return;
        }

        PracticeStatusText.Text = _ai.HasApiKey
            ? LocalizationService.T(OpenRouterService.SupportsCombinedTargetEvidence(_data.Settings.Model)
                ? "CheckingCombined"
                : "CheckingSentence")
            : LocalizationService.T("OfflineChecking");
        await RunBusyAsync(async cancellationToken =>
        {
            var reviewedAt = DateTimeOffset.Now;
            var responseTimeMs = _practiceStartedAt == default
                ? 0
                : Math.Max(0, (long)(reviewedAt - _practiceStartedAt).TotalMilliseconds);
            using var primaryTimeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            primaryTimeout.CancelAfter(TimeSpan.FromSeconds(120));
            var evaluationTask = _ai.EvaluateAsync(
                _currentWord,
                _challenge,
                sentence,
                _data.Settings.Model,
                _data.Settings.TargetLanguage,
                _data.Settings.ExplanationLanguage,
                primaryTimeout.Token);
            Task<TargetUsageEvidence>? evidenceTask = null;
            if (!OpenRouterService.SupportsCombinedTargetEvidence(_data.Settings.Model))
            {
                evidenceTask = _ai.RecheckTargetUsageAsync(
                    _currentWord,
                    sentence,
                    _data.Settings.Model,
                    _data.Settings.TargetLanguage,
                    _data.Settings.ExplanationLanguage,
                    primaryTimeout.Token);
                await Task.WhenAll(evaluationTask, evidenceTask);
            }
            var evaluation = await evaluationTask;
            if (evidenceTask is not null) evaluation.TargetUsage = await evidenceTask;

            var decision = AutomaticMemoryGradeService.Decide(
                evaluation.TargetUsage,
                _hintUsed,
                _pasteUsed,
                responseTimeMs,
                _sentenceEditCount,
                _data.Reviews.Where(record => record.WordId == _currentWord.Id));

            if (decision.Grade == AutomaticMemoryGrade.Uncertain && _ai.HasApiKey)
            {
                PracticeStatusText.Text = LocalizationService.T("RecheckingEvidence");
                using var recheckTimeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
                recheckTimeout.CancelAfter(TimeSpan.FromSeconds(60));
                var recheck = await _ai.RecheckTargetUsageAsync(
                    _currentWord,
                    sentence,
                    _data.Settings.Model,
                    _data.Settings.TargetLanguage,
                    _data.Settings.ExplanationLanguage,
                    recheckTimeout.Token);
                var reconciled = AutomaticMemoryGradeService.Reconcile(evaluation.TargetUsage, recheck);
                if (reconciled is not null)
                {
                    evaluation.TargetUsage = reconciled;
                    decision = AutomaticMemoryGradeService.Decide(
                        reconciled,
                        _hintUsed,
                        _pasteUsed,
                        responseTimeMs,
                        _sentenceEditCount,
                        _data.Reviews.Where(record => record.WordId == _currentWord.Id));
                }
            }

            RenderEvaluation(evaluation, decision);
            PracticeUsageItems.ItemsSource = _challenge.UsageItems;
            PracticeUsageCard.Visibility = Visibility.Visible;
            UpsertUsageCard(_currentWord, _challenge);

            var previousDue = _currentWord.NextReviewAt;
            ReviewScheduleResult? schedule = null;
            if (decision.ShouldUpdateLongTermMemory)
            {
                schedule = ReviewScheduler.Apply(_currentWord, decision.Grade, reviewedAt);
            }
            else
            {
                ReviewScheduler.ScheduleUncertainRetest(_currentWord, reviewedAt);
            }

            _data.Reviews.Add(new ReviewRecord
            {
                WordId = _currentWord.Id,
                Word = _currentWord.Word,
                Sentence = sentence,
                CorrectedSentence = evaluation.CorrectedSentence,
                BetterSentence = evaluation.BetterSentence,
                Scenario = _challenge.Scenario,
                ScenarioCategory = _challenge.ScenarioCategory,
                Score = evaluation.Score,
                Quality = (int)decision.Grade,
                MemoryGrade = (int)decision.Grade,
                MemoryGradeReason = decision.Reason,
                HintUsed = _hintUsed,
                PasteUsed = _pasteUsed,
                ResponseTimeMs = responseTimeMs,
                EditCount = _sentenceEditCount,
                EvidenceConfidence = decision.Confidence,
                TargetUsageCorrect = decision.TargetUsageCorrect,
                UsagePattern = string.Join(" | ", _challenge.UsageItems.Select(item => item.Pattern)),
                SchedulerVersion = schedule is null ? "automatic-evidence-retest" : ReviewScheduler.Version,
                PreviousDueAt = previousDue,
                ScheduledDueAt = _currentWord.NextReviewAt,
                ReviewedAt = reviewedAt
            });

            var candidates = WordCandidateService.Prepare(evaluation.ErrorWords, _data.Words, _currentWord.Word);
            var selectedWords = PromptForDetectedWords(candidates);
            var addedWords = AddSelectedWords(selectedWords);
            AutoAddedWordsText.Text = candidates.Count == 0
                ? LocalizationService.T("NoNewCandidates")
                : addedWords.Count == 0
                    ? LocalizationService.T("NoWordsAdded")
                    : LocalizationService.T("WordsAdded", string.Join(LocalizationService.Instance.IsEnglish ? ", " : "、", addedWords));

            await _store.SaveAsync(_data);
            RefreshAll();
            PracticeStatusText.Text = decision.ShouldUpdateLongTermMemory
                ? LocalizationService.T("ScheduledNext", _currentWord.DueLabel)
                : LocalizationService.T("EvidenceConflict");
        });
    }

    private void RenderEvaluation(SentenceEvaluation evaluation, MemoryGradeDecision decision)
    {
        ColoredSentenceText.Inlines.Clear();
        foreach (var segment in evaluation.Segments)
        {
            var (foreground, background) = segment.Rating.ToLowerInvariant() switch
            {
                "excellent" => (FindBrush("GreenBrush"), FindBrush("GreenSoftBrush")),
                "error" => (FindBrush("RedBrush"), FindBrush("RedSoftBrush")),
                _ => (FindBrush("BlueBrush"), FindBrush("BlueSoftBrush"))
            };

            var run = new Run(segment.Text)
            {
                Foreground = foreground,
                Background = background,
                ToolTip = segment.Reason
            };
            if (segment.Rating.Equals("error", StringComparison.OrdinalIgnoreCase))
            {
                run.TextDecorations = TextDecorations.Underline;
            }
            ColoredSentenceText.Inlines.Add(run);
        }

        ScoreText.Text = $"{evaluation.Score} / 100";
        FeedbackSummaryText.Text = evaluation.Summary;
        MemoryDecisionText.Text = decision.ShouldUpdateLongTermMemory
            ? LocalizationService.T("AutoDecision", decision.Reason)
            : LocalizationService.T("RejectedDecision", decision.Reason);
        CorrectedSentenceText.Text = evaluation.CorrectedSentence;
        BetterSentenceText.Text = evaluation.BetterSentence;
        FeedbackCard.Visibility = Visibility.Visible;
    }

    private IReadOnlyList<DetectedWordError> PromptForDetectedWords(IReadOnlyList<DetectedWordError> candidates)
    {
        if (candidates.Count == 0) return [];

        var dialog = new WordSelectionDialog(candidates) { Owner = this };
        return dialog.ShowDialog() == true ? dialog.SelectedWords : [];
    }

    private List<string> AddSelectedWords(IEnumerable<DetectedWordError> selectedWords)
    {
        var existingKeys = _data.Words
            .Select(word => WordCandidateService.NormalizeKey(word.Word))
            .Where(key => key.Length > 0)
            .ToHashSet(StringComparer.Ordinal);
        var added = new List<string>();

        foreach (var selected in selectedWords)
        {
            var normalized = WordCandidateService.NormalizeKey(selected.Word);
            if (normalized.Length == 0 || !existingKeys.Add(normalized)) continue;

            _data.Words.Add(new WordEntry
            {
                Word = normalized,
                Meaning = WordCandidateService.ComposeMeaning(selected),
                Note = selected.Reason.Trim(),
                Source = LocalizationService.T("SourceMistake"),
                NextReviewAt = DateTimeOffset.Now
            });
            added.Add(normalized);
        }

        return added;
    }

    private async void AddWord_Click(object sender, RoutedEventArgs e)
    {
        var word = WordCandidateService.NormalizeKey(NewWordTextBox.Text);
        if (!WordCandidateService.IsValidTerm(word))
        {
            LibraryMessageText.Text = LocalizationService.T("InvalidTerm");
            return;
        }

        if (_data.Words.Any(entry => WordCandidateService.NormalizeKey(entry.Word) == word))
        {
            LibraryMessageText.Text = LocalizationService.T("DuplicateWord");
            return;
        }

        _data.Words.Add(new WordEntry
        {
            Word = word,
            Meaning = NewMeaningTextBox.Text.Trim(),
            Source = LocalizationService.T("SourceManual"),
            NextReviewAt = DateTimeOffset.Now
        });
        await _store.SaveAsync(_data);
        NewWordTextBox.Text = string.Empty;
        NewMeaningTextBox.Text = string.Empty;
        LibraryMessageText.Text = LocalizationService.T("WordAdded", word);
        RefreshAll();
        NewWordTextBox.Focus();
    }

    private async void DeleteWord_Click(object sender, RoutedEventArgs e)
    {
        if (WordList.SelectedItem is not WordEntry selected)
        {
            LibraryMessageText.Text = LocalizationService.T("SelectWord");
            return;
        }

        var result = MessageBox.Show(
            LocalizationService.T("DeleteConfirm", selected.Word),
            LocalizationService.T("DeleteTitle"),
            MessageBoxButton.YesNo,
            MessageBoxImage.Question);
        if (result != MessageBoxResult.Yes) return;

        _data.Words.Remove(selected);
        if (_currentWord?.Id == selected.Id) _currentWord = null;
        await _store.SaveAsync(_data);
        LibraryMessageText.Text = LocalizationService.T("WordDeleted", selected.Word);
        RefreshAll();
    }

    private async void PracticeSelected_Click(object sender, RoutedEventArgs e)
    {
        if (WordList.SelectedItem is not WordEntry selected)
        {
            LibraryMessageText.Text = LocalizationService.T("SelectWord");
            return;
        }
        _practiceMode = PracticeMode.Manual;
        await BeginPracticeAsync(selected);
    }

    private void SearchTextBox_TextChanged(object sender, TextChangedEventArgs e) => RefreshLibrary();

    private async void SaveSettings_Click(object sender, RoutedEventArgs e)
    {
        var model = ModelTextBox.Text.Trim();
        if (string.IsNullOrWhiteSpace(model) || !model.Contains('/'))
        {
            SettingsMessageText.Text = LocalizationService.T("ModelInvalid");
            return;
        }

        if (!int.TryParse(DailyGoalTextBox.Text, out var dailyGoal) || dailyGoal is < 1 or > 100)
        {
            SettingsMessageText.Text = LocalizationService.T("DailyInvalid");
            return;
        }

        var targetLanguage = TargetLanguageTextBox.Text.Trim();
        var explanationLanguage = ExplanationLanguageTextBox.Text.Trim();
        if (targetLanguage.Length == 0 || explanationLanguage.Length == 0)
        {
            SettingsMessageText.Text = LocalizationService.T("LanguageInvalid");
            return;
        }

        _data.Settings.Model = model;
        _data.Settings.DailyGoal = dailyGoal;
        _data.Settings.UiLanguage = UiLanguageComboBox.SelectedValue?.ToString() ?? "zh-CN";
        _data.Settings.TargetLanguage = targetLanguage;
        _data.Settings.ExplanationLanguage = explanationLanguage;
        await _store.SaveAsync(_data);
        LocalizationService.Instance.SetLanguage(_data.Settings.UiLanguage);
        SettingsMessageText.Text = LocalizationService.T("SettingsSaved");
        RefreshAll();
        RefreshApiStatus();
    }

    private void RefreshKeyStatus_Click(object sender, RoutedEventArgs e) => RefreshApiStatus();

    private void ConfigureKey_Click(object sender, RoutedEventArgs e)
    {
        var setupWindow = new OpenRouterSetupWindow(_ai) { Owner = this };
        setupWindow.ShowDialog();
        RefreshApiStatus();
    }

    private void SentenceInput_TextChanged(object sender, TextChangedEventArgs e)
    {
        if (CharacterCountText is not null) CharacterCountText.Text = LocalizationService.T("Chars", SentenceInput.Text.Length);
        if (!_suppressInputMetrics) _sentenceEditCount += Math.Max(1, e.Changes.Count);
    }

    private void SentenceInput_Pasting(object sender, DataObjectPastingEventArgs e) => _pasteUsed = true;

    private async Task RunBusyAsync(Func<CancellationToken, Task> work)
    {
        _requestCancellation?.Cancel();
        _requestCancellation?.Dispose();
        var operationCancellation = new CancellationTokenSource();
        _requestCancellation = operationCancellation;
        _isBusy = true;
        EvaluateButton.IsEnabled = false;

        try
        {
            await work(operationCancellation.Token);
        }
        catch (OperationCanceledException)
        {
            if (ReferenceEquals(_requestCancellation, operationCancellation))
            {
                PracticeStatusText.Text = operationCancellation.IsCancellationRequested
                    ? LocalizationService.T("Cancelled")
                    : LocalizationService.T("RequestTimedOut");
            }
        }
        catch (Exception exception)
        {
            if (ReferenceEquals(_requestCancellation, operationCancellation))
                PracticeStatusText.Text = exception.Message;
        }
        finally
        {
            if (ReferenceEquals(_requestCancellation, operationCancellation))
            {
                _requestCancellation = null;
                _isBusy = false;
                EvaluateButton.IsEnabled = true;
            }
            operationCancellation.Dispose();
        }
    }

    private void RefreshAll()
    {
        RefreshDashboard();
        RefreshCardCarousel();
        RefreshLibrary();
        RefreshApiStatus();
    }

    private void RefreshDashboard()
    {
        var now = DateTimeOffset.Now;
        var due = _data.Words
            .Where(word => word.NextReviewAt <= now)
            .OrderBy(word => word.NextReviewAt)
            .ThenBy(word => word.CreatedAt)
            .ToList();
        DueList.ItemsSource = due;
        DueCountText.Text = due.Count.ToString();
        WordCountText.Text = _data.Words.Count.ToString();
        TodayReviewCountText.Text = _data.Reviews.Count(review => review.ReviewedAt.Date == now.Date).ToString();
        EmptyTodayText.Visibility = due.Count == 0 ? Visibility.Visible : Visibility.Collapsed;
        EmptyTodayText.Text = _data.Words.Count == 0
            ? LocalizationService.T("TodayEmpty")
            : LocalizationService.T("TodayComplete");
    }

    private void RefreshCardCarousel()
    {
        _recentCards = _data.Cards
            .OrderByDescending(card => card.CreatedAt)
            .Take(10)
            .ToList();
        CardCarousel.ItemsSource = _recentCards;
        CardCarouselEmptyText.Visibility = _recentCards.Count == 0 ? Visibility.Visible : Visibility.Collapsed;
        CardCarouselControls.Visibility = _recentCards.Count > 1 ? Visibility.Visible : Visibility.Collapsed;
        if (_recentCards.Count > 0)
        {
            CardCarousel.SelectedIndex = 0;
            CardCarousel.ScrollIntoView(CardCarousel.SelectedItem);
        }
    }

    private void RefreshLibrary()
    {
        var query = SearchTextBox?.Text.Trim() ?? string.Empty;
        var words = _data.Words
            .Where(word => string.IsNullOrWhiteSpace(query) ||
                           word.Word.Contains(query, StringComparison.OrdinalIgnoreCase) ||
                           word.Meaning.Contains(query, StringComparison.OrdinalIgnoreCase))
            .OrderBy(word => word.Word)
            .ToList();
        WordList.ItemsSource = new ObservableCollection<WordEntry>(words);
        LibraryCountText.Text = string.IsNullOrWhiteSpace(query)
            ? LocalizationService.T("AllWords", _data.Words.Count)
            : LocalizationService.T("SearchResults", words.Count);
    }

    private void RefreshApiStatus()
    {
        var online = _ai.HasApiKey;
        ApiStatusDot.Fill = online ? FindBrush("GreenBrush") : FindBrush("RedBrush");
        ApiStatusText.Text = online ? LocalizationService.T("ApiReady") : LocalizationService.T("ApiMissing");
        SidebarModelText.Text = _data.Settings.Model;
        SettingsKeyStatusText.Text = _ai.ApiKeySource switch
        {
            "environment" => LocalizationService.T("KeyDetectedEnvironment"),
            "credential" => LocalizationService.T("KeyDetectedCredential"),
            _ => LocalizationService.T("KeyFallback")
        };
        SettingsKeyStatusText.Foreground = online ? FindBrush("GreenBrush") : FindBrush("RedBrush");
    }

    private Brush FindBrush(string key) => (Brush)FindResource(key);
}
