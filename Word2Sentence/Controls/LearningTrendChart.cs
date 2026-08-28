using System.Globalization;
using System.Windows;
using System.Windows.Media;
using Word2Sentence.Models;

namespace Word2Sentence.Controls;

public sealed class LearningTrendChart : FrameworkElement
{
    public static readonly DependencyProperty ItemsSourceProperty = DependencyProperty.Register(
        nameof(ItemsSource), typeof(IEnumerable<DailyLearningPoint>), typeof(LearningTrendChart),
        new FrameworkPropertyMetadata(null, FrameworkPropertyMetadataOptions.AffectsRender));

    public IEnumerable<DailyLearningPoint>? ItemsSource
    {
        get => (IEnumerable<DailyLearningPoint>?)GetValue(ItemsSourceProperty);
        set => SetValue(ItemsSourceProperty, value);
    }

    protected override void OnRender(DrawingContext dc)
    {
        base.OnRender(dc);
        var points = ItemsSource?.ToList() ?? [];
        if (ActualWidth < 160 || ActualHeight < 100 || points.Count == 0) return;

        var muted = new SolidColorBrush(Color.FromRgb(217, 216, 210));
        var text = new SolidColorBrush(Color.FromRgb(104, 106, 100));
        var reviewBrush = new SolidColorBrush(Color.FromRgb(47, 96, 72));
        var scoreBrush = new SolidColorBrush(Color.FromRgb(53, 106, 160));
        var newWordBrush = new SolidColorBrush(Color.FromRgb(179, 196, 147));
        var plot = new Rect(42, 14, Math.Max(1, ActualWidth - 62), Math.Max(1, ActualHeight - 48));

        for (var index = 0; index <= 4; index++)
        {
            var y = plot.Top + plot.Height * index / 4.0;
            dc.DrawLine(new Pen(muted, 1), new Point(plot.Left, y), new Point(plot.Right, y));
        }

        var maxCount = Math.Max(1, points.Max(point => point.Reviews + point.NewWords));
        var step = points.Count == 1 ? plot.Width : plot.Width / (points.Count - 1);
        var barWidth = Math.Max(3, Math.Min(12, step * 0.36));
        var reviewGeometry = new StreamGeometry();
        var scoreGeometry = new StreamGeometry();
        using (var review = reviewGeometry.Open())
        using (var score = scoreGeometry.Open())
        {
            for (var index = 0; index < points.Count; index++)
            {
                var point = points[index];
                var x = plot.Left + step * index;
                var reviewsY = plot.Bottom - plot.Height * point.Reviews / maxCount;
                var scoreY = plot.Bottom - plot.Height * (point.AverageScore ?? 0) / 100.0;
                if (index == 0)
                {
                    review.BeginFigure(new Point(x, reviewsY), false, false);
                    score.BeginFigure(new Point(x, scoreY), false, false);
                }
                else
                {
                    review.LineTo(new Point(x, reviewsY), true, false);
                    score.LineTo(new Point(x, scoreY), true, false);
                }

                if (point.NewWords > 0)
                {
                    var height = plot.Height * point.NewWords / maxCount;
                    dc.DrawRoundedRectangle(newWordBrush, null, new Rect(x - barWidth / 2, plot.Bottom - height, barWidth, height), 2, 2);
                }
            }
        }
        reviewGeometry.Freeze();
        scoreGeometry.Freeze();
        dc.DrawGeometry(null, new Pen(reviewBrush, 2.5), reviewGeometry);
        dc.DrawGeometry(null, new Pen(scoreBrush, 2.5), scoreGeometry);

        foreach (var index in new[] { 0, points.Count / 2, points.Count - 1 }.Distinct())
        {
            var x = plot.Left + step * index;
            DrawText(dc, points[index].Date.ToString("M/d"), new Point(x, plot.Bottom + 9), 10, text, TextAlignment.Center);
        }
        DrawText(dc, maxCount.ToString(CultureInfo.CurrentCulture), new Point(plot.Left - 8, plot.Top - 5), 10, text, TextAlignment.Right);
        DrawText(dc, "0", new Point(plot.Left - 8, plot.Bottom - 7), 10, text, TextAlignment.Right);
        DrawText(dc, "100", new Point(plot.Right + 6, plot.Top - 5), 10, scoreBrush, TextAlignment.Left);
        DrawText(dc, "0", new Point(plot.Right + 6, plot.Bottom - 7), 10, scoreBrush, TextAlignment.Left);
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
