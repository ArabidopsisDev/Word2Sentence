# 技术审阅（Lagrange）

结论：**PASS，无阻断项**。审阅当前第 5 版预览、内容合同、真实 WPF 源码和验证示例；运行 `verify_repository.py --build --algorithm` 后，Release 构建为 0 warning / 0 error，并得到 `WORD2SENTENCE_SOURCE_PROOFS_OK`、`FSRS_6_3_1_CONFORMANCE_OK`、`AUTOMATIC_MEMORY_GRADE_OK`、`SCENARIO_DIVERSITY_OK`、`OPENROUTER_ONBOARDING_OK`。

- `proof-open-and-problem`（00:21.81）：`Word2Sentence.csproj`、根目录 `LICENSE` 与 README 证明 AGPL-3.0-only；画面能辨认许可证表达式和 `distract`。字幕没有把程序免费延伸成 AI 服务免费。
- `proof-sentence-flow`（00:34.30）：`OpenRouterService.CreateChallengeAsync` 先生成不泄露完整答案的情境，随后 `EvaluateAsync` 接收用户句子；画面方法名与真实流程一致。
- `proof-feedback-artifacts`（00:45.15）：`AiModels.cs`、`MainWindow.xaml` 与 `MainWindow.xaml.cs` 证明逐段反馈、`CorrectedSentence`、`BetterSentence`、`UsagePatternItem` 和确认后加入错词的流程。
- `proof-automatic-fsrs`（01:09.91）：`AutomaticMemoryGradeService.cs` 根据目标词使用、表达与作答过程产生内部等级，`ReviewScheduler.cs` 使用 FSRS-6；界面没有用户好、中、差或 Again/Hard/Good/Easy 自评按钮。不确定时仅安排 10 分钟后复测，不修改长期状态。
- `proof-data-boundary`（01:22.07）：`DataStore.cs` 与 `AppData.cs` 证明词库、历史、卡片和设置写入本机 `wordbook.json`；OpenRouter 仅在启用 AI 时用于当前练习。实际所需文本还包括为避免重复而选取的同词最近最多 5 条情境，因此当前“发送当前练习所需文本”准确，但不应继续简化成“历史绝不发送”。三种语言设置在 `AppData.cs` 中相互独立。

末尾“前往 GitHub 下载”可理解为获取源码并按 README 构建；当前仓库仍是 prototype，不应宣传成已有一键安装包。
