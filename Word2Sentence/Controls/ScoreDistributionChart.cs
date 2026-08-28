using System.Globalization;
using System.Windows;
using System.Windows.Media;
using Word2Sentence.Models;

namespace Word2Sentence.Controls;

public sealed class ScoreDistributionChart : FrameworkElement
{
    public static readonly DependencyProperty ItemsSourceProperty = DependencyProperty.Register(
        nameof(ItemsSource), typeof(IEnumerable<ScoreBucket>), typeof(ScoreDistributionChart),
        new FrameworkPropertyMetadata(null, FrameworkPropertyMetadataOptions.AffectsRender));

    public IEnumerable<ScoreBucket>? ItemsSource
    {
        get => (IEnumerable<ScoreBucket>?)GetValue(ItemsSourceProperty);
        set => SetValue(ItemsSourceProperty, value);
    }

    protected override void OnRender(DrawingContext dc)
    {
        base.OnRender(dc);
        var buckets = ItemsSource?.ToList() ?? [];
        if (ActualWidth < 180 || ActualHeight < 100 || buckets.Count == 0) return;
        var text = new SolidColorBrush(Color.FromRgb(104, 106, 100));
        var track = new SolidColorBrush(Color.FromRgb(238, 236, 230));
        var colors = new[]
        {
            Color.FromRgb(184, 60, 55), Color.FromRgb(197, 121, 75), Color.FromRgb(143, 177, 210),
            Color.FromRgb(95, 154, 119), Color.FromRgb(47, 96, 72)
        };
        var rowHeight = ActualHeight / buckets.Count;
        for (var index = 0; index < buckets.Count; index++)
        {
            var bucket = buckets[index];
            var y = index * rowHeight + 7;
            DrawText(dc, bucket.Label, new Point(0, y + 2), 11, text, TextAlignment.Left);
            var trackRect = new Rect(58, y + 3, Math.Max(20, ActualWidth - 105), Math.Max(8, rowHeight - 18));
            dc.DrawRoundedRectangle(track, null, trackRect, 4, 4);
            var width = trackRect.Width * Math.Clamp(bucket.Percentage, 0, 100) / 100.0;
            if (width > 0)
                dc.DrawRoundedRectangle(new SolidColorBrush(colors[index % colors.Length]), null,
                    new Rect(trackRect.Left, trackRect.Top, width, trackRect.Height), 4, 4);
            DrawText(dc, bucket.Count.ToString(CultureInfo.CurrentCulture), new Point(ActualWidth - 4, y + 2), 11, text, TextAlignment.Right);
        }
    }

    private void DrawText(DrawingContext dc, string value, Point origin, double size, Brush brush, TextAlignment alignment)
    {
        var formatted = new FormattedText(value, CultureInfo.CurrentUICulture, FlowDirection.LeftToRight,
            new Typeface("Segoe UI Variable Text"), size, brush, VisualTreeHelper.GetDpi(this).PixelsPerDip)
        {
            TextAlignment = alignment
        };
        dc.DrawText(formatted, origin);
    }
}
