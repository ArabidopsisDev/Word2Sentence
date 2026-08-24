using System.Windows;
using System.Windows.Input;
using Word2Sentence.Models;
using Word2Sentence.Services;

namespace Word2Sentence;

public partial class WordSelectionDialog : Window
{
    private readonly List<SelectableWordCandidate> _candidates;

    public WordSelectionDialog(IEnumerable<DetectedWordError> candidates)
    {
        InitializeComponent();
        _candidates = candidates
            .Select(error => new SelectableWordCandidate(error))
            .ToList();
        CandidateList.ItemsSource = _candidates;
        Loaded += (_, _) => UpdateSelectionSummary();
    }

    public IReadOnlyList<DetectedWordError> SelectedWords => _candidates
        .Where(candidate => candidate.IsSelected)
        .Select(candidate => candidate.Error)
        .ToList();

    private void TitleBar_MouseLeftButtonDown(object sender, MouseButtonEventArgs e)
    {
        if (e.ChangedButton != MouseButton.Left) return;
        try { DragMove(); }
        catch (InvalidOperationException) { }
    }

    private void CloseWindow_Click(object sender, RoutedEventArgs e) => DialogResult = false;

    private void CandidateCheckChanged(object sender, RoutedEventArgs e) => UpdateSelectionSummary();

    private void SelectAll_Click(object sender, RoutedEventArgs e)
    {
        SetAll(true);
    }

    private void SelectNone_Click(object sender, RoutedEventArgs e)
    {
        SetAll(false);
    }

    private void SetAll(bool selected)
    {
        foreach (var candidate in _candidates) candidate.IsSelected = selected;
        CandidateList.Items.Refresh();
        UpdateSelectionSummary();
    }

    private void UpdateSelectionSummary()
    {
        if (CandidateCountText is null || ConfirmButton is null) return;
        var selectedCount = _candidates.Count(candidate => candidate.IsSelected);
        CandidateCountText.Text = LocalizationService.T("CandidateSummary", _candidates.Count, selectedCount);
        ConfirmButton.Content = selectedCount == 0
            ? LocalizationService.T("ChooseFirst")
            : LocalizationService.T("AddSelectedCount", selectedCount);
        ConfirmButton.IsEnabled = selectedCount > 0;
    }

    private void Confirm_Click(object sender, RoutedEventArgs e)
    {
        DialogResult = true;
    }

    private void Skip_Click(object sender, RoutedEventArgs e)
    {
        DialogResult = false;
    }

    private sealed class SelectableWordCandidate(DetectedWordError error)
    {
        public DetectedWordError Error { get; } = error;
        public bool IsSelected { get; set; } = true;
    }
}
