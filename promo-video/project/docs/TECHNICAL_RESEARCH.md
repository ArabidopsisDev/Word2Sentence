# 技术研究

## 审校日期与版本

- 审校日期：2026-08-27。
- 应用目标：`.NET 10 / WPF / Windows 10–11`，以当前仓库 `main` 为事实基线。
- 调度器标识：`py-fsrs-6.3.1-default-dr0.90`，21 个 FSRS-6 参数，目标留存率 0.90。
- 项目状态：积极开发中，当前仓库尚未承诺正式安装包；视频不出现“成熟商业产品”或“零门槛永久免费 AI”一类承诺。

## Claim ledger

| ID | 画面/字幕结论 | 一手来源 | 状态 | 示例验证 | 风险 |
|---|---|---|---|---|---|
| C01 | Word2Sentence 是 AGPL-3.0-only 开源项目 | `LICENSE`、`Word2Sentence.csproj`、https://www.gnu.org/licenses/agpl.html | 稳定 | Release 构建读取许可证字段 | “自由”不等于 AI 推理没有外部成本 |
| C02 | 用户主动加入生词，AI 生成情境并批改句子 | `MainWindow.xaml.cs`、`OpenRouterService.cs` | 当前实现 | `dotnet build` | 不声称 AI 永远正确 |
| C03 | 反馈包含逐段颜色、修正版、更自然版本和用法卡 | `MainWindow.xaml`、`AiModels.cs` | 当前实现 | UI 渲染 + build | 颜色表示表达质量，不是记忆等级 |
| C04 | FSRS-6 使用 21 个默认参数 | `ReviewScheduler.cs`、https://github.com/open-spaced-repetition/awesome-fsrs/wiki/The-Algorithm | 当前实现与官方公式对齐 | `FSRS_6_3_1_CONFORMANCE_OK` | 不在短片中展开公式 |
| C05 | 用户不选择好 / 中 / 差，内部等级来自多维证据 | `AutomaticMemoryGradeService.cs`、`MainWindow.xaml.cs` | 当前实现 | `AUTOMATIC_MEMORY_GRADE_OK` | 整句 0–100 分不直接修改间隔；低置信或冲突证据只安排 10 分钟后复测，长期 FSRS 状态不变 |
| C06 | 完整单词库和历史默认保存在本机 JSON | `DataStore.cs` | 当前实现 | `DataPath => ...wordbook.json` | 启用 AI 后，目标词、个人备注、当前练习，以及同一词最近最多 5 条历史情境会发送给 OpenRouter 和实际模型提供方 |
| C07 | OpenRouter 通过 Bearer API key 调用模型 | `OpenRouterService.cs`、https://openrouter.ai/docs/quickstart | 当前 API | 验证请求自动检查 | 外部模型可用性、价格和隐私政策可能变化 |
| C08 | 界面语言、目标语言和解释语言可以分别配置 | `AppData.cs`、`MainWindow.xaml` | 当前实现 | 中英文 UI 渲染 | 本片只用英语词汇作为演示，不宣称所有语言质量相同 |

## 容易误讲的边界

- 开源解释：程序源码公开并按 AGPL-3.0-only 授权；不要把“开源”简化为“所有相关服务永久免费”。
- 评分解释：整句分数服务于写作反馈；复习间隔读取目标词证据、提示/粘贴、响应时间、修改次数和历史基线。
- 隐私解释：完整词库和历史记录留在本机；启用 AI 后，目标词、个人备注、情境/目标、提交句子和同一词最近最多 5 条历史情境会发送给 OpenRouter 及实际模型提供方。
- 算法解释：证据可信且内部一致时才映射到 FSRS 所需等级；低置信或冲突时安排 10 分钟自动复测且不更新长期状态，用户界面始终不提供自评按钮。

## 示例复现

```text
dotnet build Word2Sentence.slnx -c Release
已成功生成。0 个警告，0 个错误。

dotnet run --project Word2Sentence.AlgorithmChecks/Word2Sentence.AlgorithmChecks.csproj -c Release --no-build
FSRS_6_3_1_CONFORMANCE_OK
AUTOMATIC_MEMORY_GRADE_OK
SCENARIO_DIVERSITY_OK
OPENROUTER_ONBOARDING_OK
```

## 未解决风险

- 精确模型名称、价格和免费额度不进入画面，避免外部服务变化导致成片过时。
- BGM 已由用户提供并在 D 盘工程内完成节拍分析；时间线锁定为 117.76 秒。
- FFmpeg/FFprobe 9.0.1 已配置；正式媒体 QA 将针对最终 AAC mux 复测。
