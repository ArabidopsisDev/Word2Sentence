# 视觉几何审阅（promo_visual_v5）

结论：**PASS，无阻断项**。只读取第 5 版 MP4、接触表及从该 MP4 生成的抽帧；以 1 fps 扫描全片，并对五个 proof 做 ±1.2 秒前、中、后及 320×180 缩小复核。

- `proof-open-and-problem`（00:21.810）：20.610–22.610 主构图稳定。盲转录 `<PackageLicenseExpression>AGPL-3.0-only</PackageLicenseExpression>`、`distract`、`be distracted by sth`。标识框不压单词或搭配，面板边缘与基线正常。
- `proof-sentence-flow`（00:34.298）：33.098–35.498 稳定。盲转录 `CreateChallengeAsync`、`EvaluateAsync` 与学习者句子。上方标识框位于背景留白，按钮、正文和字幕互不相撞。
- `proof-feedback-artifacts`（00:45.147）：43.947–46.347 稳定。盲转录 `CorrectedSentence`、`BetterSentence`、`UsagePatternItem`。框线不遮英文 token，降亮原句与前景卡没有同基线重影。
- `proof-automatic-fsrs`（01:09.914）：约 69.514–71.114 稳定。盲转录 `ReviewScheduler.Apply`；四条证据连线从标签边缘进入“自动安排复习”，没有穿字或短身大箭头。
- `proof-data-boundary`（01:22.069）：80.869–83.269 稳定。盲转录 `wordbook.json`、`TargetLanguage`、“本机保存”“AI 功能可选”与三类语言设置。82.069 恰处字幕交替，但逐 0.1 秒检查确认旧字幕退净后新字幕淡入，没有双字幕重叠；proof 不依赖字幕。

目录在约 00:06.5–00:09.2 完整出现，01–05 唯一连续。章节切换约在 09.840、22.920、36.000、62.160、75.280 秒，85.080 秒进入尾板；未见旧新整页互压。同章内部均是局部揭示，没有翻 PPT 式黑场。字幕为单行，安全区、最长字幕、CJK 字形和混排基线正常。

320×180 下，章节标题、字幕、`distract`、核心英文句和主要流程框仍可读；XML、artifact 名和 `ReviewScheduler.Apply` 等小标识不适合在缩略尺寸可靠盲抄，但在 960×540 proof 中完整可转录，也不是小尺寸下承载结论的唯一对象，属于非阻断风险。75.280–85.080 的设置页被降为背景，右侧大框承担边界结论，不像配置教程；85.080–94.880 为发布尾板，几何干净。
