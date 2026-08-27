using System.Diagnostics;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using Word2Sentence.Services;

namespace Word2Sentence;

public partial class OpenRouterSetupWindow : Window
{
    private const string SignInUrl = "https://openrouter.ai/sign-in";
    private const string CreditsUrl = "https://openrouter.ai/settings/credits";
    private const string KeysUrl = "https://openrouter.ai/settings/keys";
    private readonly OpenRouterService _openRouter;
    private int _beginnerStep = 1;
    private bool _validating;
    private CancellationTokenSource? _validationCancellation;

    public OpenRouterSetupWindow(OpenRouterService openRouter)
    {
        _openRouter = openRouter;
        InitializeComponent();
        UpdateBeginnerStep();
        Closed += (_, _) => _validationCancellation?.Cancel();
    }

    private void TitleBar_MouseLeftButtonDown(object sender, MouseButtonEventArgs e)
    {
        if (e.ChangedButton != MouseButton.Left) return;
        try { DragMove(); }
        catch (InvalidOperationException) { }
    }

    private void Close_Click(object sender, RoutedEventArgs e)
    {
        _validationCancellation?.Cancel();
        Close();
    }

    private void Offline_Click(object sender, RoutedEventArgs e)
    {
        _validationCancellation?.Cancel();
        Close();
    }

    private void BeginnerMode_Click(object sender, RoutedEventArgs e)
    {
        ModeChoicePanel.Visibility = Visibility.Collapsed;
        TechnicalPanel.Visibility = Visibility.Collapsed;
        BeginnerPanel.Visibility = Visibility.Visible;
        _beginnerStep = 1;
        UpdateBeginnerStep();
    }

    private void TechnicalMode_Click(object sender, RoutedEventArgs e)
    {
        ModeChoicePanel.Visibility = Visibility.Collapsed;
        BeginnerPanel.Visibility = Visibility.Collapsed;
        TechnicalPanel.Visibility = Visibility.Visible;
        TechnicalKeyBox.Focus();
    }

    private void BackToMode_Click(object sender, RoutedEventArgs e) => ShowModeChoice();

    private void ShowModeChoice()
    {
        BeginnerPanel.Visibility = Visibility.Collapsed;
        TechnicalPanel.Visibility = Visibility.Collapsed;
        ModeChoicePanel.Visibility = Visibility.Visible;
    }

    private void BeginnerBack_Click(object sender, RoutedEventArgs e)
    {
        if (_beginnerStep <= 1)
        {
            ShowModeChoice();
            return;
        }

        _beginnerStep--;
        UpdateBeginnerStep();
    }

    private async void BeginnerNext_Click(object sender, RoutedEventArgs e)
    {
        if (_beginnerStep < 4)
        {
            _beginnerStep++;
            UpdateBeginnerStep();
            return;
        }

        await ValidateAndSaveAsync(BeginnerKeyBox, BeginnerStatusText);
    }

    private void UpdateBeginnerStep()
    {
        BeginnerStepLabel.Text = LocalizationService.T("SetupStep", _beginnerStep, 4);
        BeginnerStepOne.Visibility = _beginnerStep == 1 ? Visibility.Visible : Visibility.Collapsed;
        BeginnerStepTwo.Visibility = _beginnerStep == 2 ? Visibility.Visible : Visibility.Collapsed;
        BeginnerStepThree.Visibility = _beginnerStep == 3 ? Visibility.Visible : Visibility.Collapsed;
        BeginnerStepFour.Visibility = _beginnerStep == 4 ? Visibility.Visible : Visibility.Collapsed;
        BeginnerNextButton.Content = LocalizationService.T(_beginnerStep == 4 ? "ValidateAndSave" : "SetupNext");
        if (_beginnerStep == 4) BeginnerKeyBox.Focus();
    }

    private async void ValidateTechnical_Click(object sender, RoutedEventArgs e) =>
        await ValidateAndSaveAsync(TechnicalKeyBox, TechnicalStatusText);

    private async Task ValidateAndSaveAsync(PasswordBox keyBox, TextBlock statusText)
    {
        if (_validating) return;
        var apiKey = keyBox.Password.Trim();
        if (apiKey.Length < 20)
        {
            ShowStatus(statusText, "KeyInvalid", "RedBrush");
            keyBox.Focus();
            return;
        }

        _validating = true;
        BeginnerNextButton.IsEnabled = false;
        TechnicalValidateButton.IsEnabled = false;
        ShowStatus(statusText, "ValidatingKey", "TextMutedBrush");
        try
        {
            _validationCancellation = new CancellationTokenSource(TimeSpan.FromSeconds(20));
            var result = await _openRouter.ValidateApiKeyAsync(apiKey, _validationCancellation.Token);
            if (!IsVisible) return;
            if (!result.IsValid)
            {
                var messageKey = result.Reason switch
                {
                    "unauthorized" or "invalid" => "KeyInvalid",
                    "network" or "timeout" => "KeyNetwork",
                    _ => "KeyServer"
                };
                ShowStatus(statusText, messageKey, "RedBrush");
                return;
            }

            try
            {
                OpenRouterCredentialStore.SaveApiKey(apiKey);
            }
            catch
            {
                ShowStatus(statusText, "KeySaveFailed", "RedBrush");
                return;
            }

            keyBox.Clear();
            ShowStatus(statusText, "KeyValid", "GreenBrush");
            DialogResult = true;
            Close();
        }
        catch (OperationCanceledException)
        {
            if (IsVisible) ShowStatus(statusText, "KeyNetwork", "RedBrush");
        }
        finally
        {
            _validationCancellation?.Dispose();
            _validationCancellation = null;
            _validating = false;
            BeginnerNextButton.IsEnabled = true;
            TechnicalValidateButton.IsEnabled = true;
        }
    }

    private void ShowStatus(TextBlock target, string messageKey, string brushKey)
    {
        target.Text = LocalizationService.T(messageKey);
        target.Foreground = (Brush)FindResource(brushKey);
    }

    private void PasteBeginnerKey_Click(object sender, RoutedEventArgs e) => PasteKey(BeginnerKeyBox);
    private void PasteTechnicalKey_Click(object sender, RoutedEventArgs e) => PasteKey(TechnicalKeyBox);

    private static void PasteKey(PasswordBox target)
    {
        try
        {
            if (Clipboard.ContainsText()) target.Password = Clipboard.GetText().Trim();
            target.Focus();
        }
        catch { }
    }

    private void OpenSignIn_Click(object sender, RoutedEventArgs e) => OpenExternalUrl(SignInUrl);
    private void OpenCredits_Click(object sender, RoutedEventArgs e) => OpenExternalUrl(CreditsUrl);
    private void OpenKeys_Click(object sender, RoutedEventArgs e) => OpenExternalUrl(KeysUrl);

    private static void OpenExternalUrl(string url)
    {
        try { Process.Start(new ProcessStartInfo(url) { UseShellExecute = true }); }
        catch { }
    }
}
