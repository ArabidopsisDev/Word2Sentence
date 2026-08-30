# Word2Sentence 宣传图

四张图片均为 1920 × 1080 PNG。AI 只用于生成无文字背景，软件窗口、Logo 和全部中文文案由构建脚本确定性合成，避免 UI 文字失真。

## 图片

1. `output/01-overview.png`：总体功能主视觉。覆盖主动词库、情境造句、AI 批改、用法卡、错词确认、自动复习、学习统计、本地优先和多语言。
2. `output/02-sentence-practice.png`：从生词到情境造句。
3. `output/03-feedback-and-usage.png`：逐段反馈、两个改写版本、用法卡和错词确认。
4. `output/04-statistics-and-review.png`：自动复习、打卡、分数、掌握度和待强化词。

## 设计研究摘要

- Raycast 发布页：真实桌面窗口占主视觉，短标题配大面积留白。
- Linear Changelog：每张图只建立一个主要信息层级，避免窗口与长文案争夺注意力。
- Mac App Store 宣传截图：产品截图必须保持可读，标题负责收益，截图负责可信度。
- 用户参考图：只吸收多窗口建立产品体量和空间深度的方式；不使用手机模型、动漫角色、霓虹城市或强烈商业广告质感。

## 重新生成

```powershell
python promo-images/build_promo_images.py
```

脚本读取 `promo-images/assets/app` 下的真实中文界面截图，并写入 `promo-images/output`。宣传图工程不依赖任何视频剪辑目录。
