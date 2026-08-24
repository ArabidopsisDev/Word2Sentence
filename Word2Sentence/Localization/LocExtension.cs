using System.Windows.Data;
using System.Windows.Markup;
using Word2Sentence.Services;

namespace Word2Sentence.Localization;

[MarkupExtensionReturnType(typeof(object))]
public sealed class LocExtension(string key) : MarkupExtension
{
    public string Key { get; } = key;

    public override object ProvideValue(IServiceProvider serviceProvider)
    {
        var binding = new Binding($"[{Key}]")
        {
            Source = LocalizationService.Instance,
            Mode = BindingMode.OneWay
        };
        return binding.ProvideValue(serviceProvider);
    }
}
