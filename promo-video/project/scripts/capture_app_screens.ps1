param(
    [string]$OutputDirectory = "D:\Projects\Word2Sentence\promo-video\assets\images\app",
    [string]$AssemblyPath = "D:\Projects\Word2Sentence\Word2Sentence\bin\Release\net10.0-windows\Word2Sentence.dll",
    [string]$UiLanguage = "zh-CN"
)

$ErrorActionPreference = "Stop"
$repositoryRoot = "D:\Projects\Word2Sentence"
$dataDirectory = Join-Path $repositoryRoot "promo-video\assets\screenshot-data"
$demoPath = Join-Path $dataDirectory "practice-demo.json"

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$env:WORD2SENTENCE_DATA_DIR = $dataDirectory
$env:OR_KEY = "sk-or-v1-screenshot-placeholder-not-used"

Add-Type -AssemblyName PresentationFramework,PresentationCore,WindowsBase
[System.Reflection.Assembly]::LoadFrom($AssemblyPath) | Out-Null

function Invoke-PrivateMethod {
    param([object]$Target, [string]$Name, [object[]]$Arguments = @())
    $flags = [System.Reflection.BindingFlags]::Instance -bor [System.Reflection.BindingFlags]::NonPublic
    $method = $Target.GetType().GetMethod($Name, $flags)
    if ($null -eq $method) { throw "Method not found: $Name" }
    return $method.Invoke($Target, $Arguments)
}

function Wait-ForDispatcher {
    param([int]$Milliseconds = 700)
    $frame = [System.Windows.Threading.DispatcherFrame]::new()
    $timer = [System.Windows.Threading.DispatcherTimer]::new()
    $timer.Interval = [TimeSpan]::FromMilliseconds($Milliseconds)
    $timer.Add_Tick({
        $timer.Stop()
        $frame.Continue = $false
    })
    $timer.Start()
    [System.Windows.Threading.Dispatcher]::PushFrame($frame)
}

function Save-WindowPng {
    param([System.Windows.Window]$Window, [string]$Name)
    $Window.UpdateLayout()
    $bitmap = [System.Windows.Media.Imaging.RenderTargetBitmap]::new(
        [int]$Window.ActualWidth,
        [int]$Window.ActualHeight,
        96,
        96,
        [System.Windows.Media.PixelFormats]::Pbgra32)
    $bitmap.Render($Window)
    $encoder = [System.Windows.Media.Imaging.PngBitmapEncoder]::new()
    $encoder.Frames.Add([System.Windows.Media.Imaging.BitmapFrame]::Create($bitmap))
    $path = Join-Path $OutputDirectory $Name
    $stream = [System.IO.File]::Create($path)
    try { $encoder.Save($stream) } finally { $stream.Dispose() }
    Write-Output $path
}

$app = [Word2Sentence.App]::new()
$app.InitializeComponent()
$window = [Word2Sentence.MainWindow]::new()
$window.Width = 1600
$window.Height = 1024
$window.Left = -10000
$window.Top = -10000
$window.Show()
Wait-ForDispatcher 900
[Word2Sentence.Services.LocalizationService]::Instance.SetLanguage($UiLanguage)
Invoke-PrivateMethod $window "RefreshAll" | Out-Null
Wait-ForDispatcher 100

Save-WindowPng $window "today-zh.png"

Invoke-PrivateMethod $window "LibraryNav_Click" @($null, [System.Windows.RoutedEventArgs]::new()) | Out-Null
Save-WindowPng $window "library-zh.png"

Invoke-PrivateMethod $window "StatisticsNav_Click" @($null, [System.Windows.RoutedEventArgs]::new()) | Out-Null
Wait-ForDispatcher 100
Save-WindowPng $window "statistics-zh.png"
$window.FindName("StatisticsPage").ScrollToVerticalOffset(650)
Wait-ForDispatcher 100
Save-WindowPng $window "statistics-lower-zh.png"

Invoke-PrivateMethod $window "PracticeNav_Click" @($null, [System.Windows.RoutedEventArgs]::new()) | Out-Null
Save-WindowPng $window "practice-chooser-zh.png"

$practicePage = $window.FindName("PracticePage")
$practiceNav = $window.FindName("PracticeNav")
Invoke-PrivateMethod $window "ShowPage" @($practicePage, $practiceNav) | Out-Null
$window.FindName("PracticeChooserPanel").Visibility = [System.Windows.Visibility]::Collapsed
$window.FindName("PracticeSessionPanel").Visibility = [System.Windows.Visibility]::Visible

$demo = Get-Content -Raw -LiteralPath $demoPath | ConvertFrom-Json
$window.FindName("PracticeWordText").Text = $demo.word
$window.FindName("PracticeMeaningText").Text = $demo.meaning
$window.FindName("PracticeStageText").Text = $demo.stage
$window.FindName("ScenarioText").Text = $demo.scenario
$window.FindName("GoalText").Text = $demo.goal
$window.FindName("PracticeStatusText").Text = $demo.readyStatus
$window.FindName("HintText").Visibility = [System.Windows.Visibility]::Collapsed

$usageItems = [System.Collections.Generic.List[Word2Sentence.Models.UsagePatternItem]]::new()
foreach ($item in $demo.usageItems) {
    $usage = [Word2Sentence.Models.UsagePatternItem]::new()
    $usage.Pattern = $item.pattern
    $usage.Meaning = $item.meaning
    $usage.Example = $item.example
    $usageItems.Add($usage)
}
$evaluation = [Word2Sentence.Models.SentenceEvaluation]::new()
$evaluation.Score = [int]$demo.evaluation.score
$evaluation.Summary = $demo.evaluation.summary
$evaluation.CorrectedSentence = $demo.evaluation.correctedSentence
$evaluation.BetterSentence = $demo.evaluation.betterSentence
foreach ($item in $demo.evaluation.segments) {
    $segment = [Word2Sentence.Models.FeedbackSegment]::new()
    $segment.Text = $item.text
    $segment.Rating = $item.rating
    $segment.Reason = $item.reason
    $evaluation.Segments.Add($segment)
}
$decision = [Word2Sentence.Services.MemoryGradeDecision]::new(
    [Word2Sentence.Services.AutomaticMemoryGrade]::Hard,
    $demo.evaluation.memoryReason,
    0.96,
    $true)
$practicePage.ScrollToTop()
Wait-ForDispatcher 100
$window.FindName("SentenceInput").Text = ""
Save-WindowPng $window "practice-session-empty-zh.png"
$window.FindName("SentenceInput").Text = $demo.sentence
Wait-ForDispatcher 100
Save-WindowPng $window "practice-session-zh.png"

$window.FindName("PracticeUsageItems").ItemsSource = $usageItems
$window.FindName("PracticeUsageCard").Visibility = [System.Windows.Visibility]::Visible
Invoke-PrivateMethod $window "RenderEvaluation" @($evaluation, $decision) | Out-Null
$window.FindName("PracticeStatusText").Text = $demo.status
$window.FindName("AutoAddedWordsText").Text = $demo.autoAdded
$practicePage.ScrollToTop()
Wait-ForDispatcher 100
Save-WindowPng $window "practice-feedback-top-zh.png"
$practicePage.ScrollToVerticalOffset(610)
Wait-ForDispatcher 100
Save-WindowPng $window "practice-feedback-zh.png"

Invoke-PrivateMethod $window "SettingsNav_Click" @($null, [System.Windows.RoutedEventArgs]::new()) | Out-Null
Save-WindowPng $window "settings-zh.png"

Invoke-PrivateMethod $window "AboutNav_Click" @($null, [System.Windows.RoutedEventArgs]::new()) | Out-Null
Save-WindowPng $window "about-zh.png"

$detectedWords = [System.Collections.Generic.List[Word2Sentence.Models.DetectedWordError]]::new()
$detected = [Word2Sentence.Models.DetectedWordError]::new()
$detected.ObservedForm = "resiliant"
$detected.Word = "resilient"
$detected.PartOfSpeech = "adj."
$detected.Meaning = "有韧性的；能迅速恢复的"
$detected.Reason = "单词拼写有误，建议加入词库继续练习。"
$detectedWords.Add($detected)
$dialog = [Word2Sentence.WordSelectionDialog]::new($detectedWords)
$dialog.Owner = $window
$dialog.Left = -10000
$dialog.Top = -10000
$dialog.Show()
Wait-ForDispatcher 100
Save-WindowPng $dialog "detected-words-dialog-zh.png"
$dialog.Close()

$window.Close()
$app.Shutdown()
