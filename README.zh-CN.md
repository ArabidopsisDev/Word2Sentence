<div align="center">
  <img src="docs/images/logo.svg" width="128" height="128" alt="Word2Sentence Logo" />
  <h1>Word2Sentence</h1>
  <p><strong>不是盯着单词看，而是在句子里真正使用它。</strong></p>
  <p><a href="README.md">English</a></p>
</div>

Word2Sentence 是一款本地优先的 Windows 桌面单词学习软件。用户主动添加不会的词，AI 生成真实造句情境，并为句子提供逐段标注、仅修错版本、更自然版本和实用用法卡。

复习完全自动调度。软件不会要求用户选择“好 / 中 / 差”，也不会显示 Again / Hard / Good / Easy 自评按钮。独立的 AI 证据调用只核验目标词的拼写、词义、词形、搭配和局部语法，再由本地确定性规则输入经过参考向量验证的 FSRS-6 调度器。

## 软件截图

### 首页

![英文首页：最近用法卡与到期单词](docs/images/dashboard.png)

### 两种练习模式

![英文练习模式选择页](docs/images/practice.png)

可以直接采用调度器最紧急的自动推荐，也可以从同一近期复习队列中自由选择。进入练习后，用法卡在提交前保持隐藏，避免泄露独立回忆所需的搭配和例句。

### 语言、模型与复习设置

![英文设置页](docs/images/settings.png)

### 单词库

![英文自定义单词库列表](docs/images/library.png)

## 主要功能

- 主动添加目标语言单词或短语；
- 自动推荐与近期候选自由选择两种造句模式；
- 自绘、可拖动、可缩放的统一窗口标题栏；
- AI 生成贴近日常或工作的造句情境；
- 绿色、蓝色和红色逐段反馈；
- 同时提供“只修正错误”和“表达更自然”两个版本；
- 提交后生成核心搭配、解释和例句组成的用法卡；
- 最近 10 张用法卡在首页横向轮播；
- 错词候选规范化、去重，独立显示词性和释义，并由用户确认是否收录；
- AI 多维证据自动映射内部记忆等级；
- 低置信度自动二次核验，冲突时不污染 FSRS 长期状态；
- 简体中文与 English 界面；
- 目标语言和 AI 解释语言分别配置；
- Unicode 词项输入，不把学习范围锁死在英语；
- 本地 JSON 持久化，API 密钥不落盘。

## 自动复习原理

整句 0–100 分只用于写作反馈，不直接改变复习间隔。系统另行获取以下目标词证据：是否出现、拼写、词义、词形、搭配、局部语法、自然度、是否需要核心修正和置信度。

查看提示或粘贴输入会被记录，不能得到 Easy。Easy 也不依赖拍脑袋的固定秒数：至少积累 10 条个人成功记录后，才依据个人响应时间中位数、修改次数和 AI 证据自动产生。

调度器与 `py-fsrs 6.3.1` 对齐：

- FSRS-6 官方 21 参数；
- 90% 目标留存率；
- 1 分钟、10 分钟学习步骤；
- 10 分钟重学步骤；
- 没有自定义间隔倍率；
- 关闭随机 fuzz，确保桌面端结果可复现。

参考：[FSRS 算法公式](https://github.com/open-spaced-repetition/awesome-fsrs/wiki/The-Algorithm)、[Anki FSRS 文档](https://docs.ankiweb.net/deck-options)。

## 运行要求

- Windows 10/11
- [.NET 10 SDK](https://dotnet.microsoft.com/download/dotnet/10.0)
- OpenRouter API 密钥

```powershell
git clone <你的仓库地址>
cd Word2Sentence

[Environment]::SetEnvironmentVariable('OR_KEY', 'sk-or-...', 'User')

dotnet run --project .\Word2Sentence\Word2Sentence.csproj
```

默认模型是 `stealth/ox-alpha`，可在设置中改为其他 OpenRouter 模型。密钥依次从进程、当前用户和系统环境变量读取，不会写入项目或数据文件。

## 构建与算法检查

```powershell
dotnet restore .\Word2Sentence.slnx
dotnet build .\Word2Sentence.slnx -c Release --no-restore
dotnet run --project .\Word2Sentence.AlgorithmChecks\Word2Sentence.AlgorithmChecks.csproj -c Release --no-build
```

预期输出：

```text
FSRS_6_3_1_CONFORMANCE_OK
AUTOMATIC_MEMORY_GRADE_OK
```

## 本地数据与隐私

默认数据文件：

```text
%LocalAppData%\Word2Sentence\wordbook.json
```

设置 `WORD2SENTENCE_DATA_DIR` 可使用隔离的开发或截图数据目录。启用 AI 后，目标词、个人备注、题目情境和提交的句子会发送给 OpenRouter 及实际模型提供方；完整单词库和历史记录仍保存在本机。

## 路线图

- [x] 中英双语界面
- [x] 可配置学习目标语言与解释语言
- [x] AI 逐段反馈与双版本改写
- [x] 用法卡和首页轮播
- [x] 全自动 AI 证据到 FSRS-6 调度
- [x] JSON 提取、修复和重试
- [ ] 导入导出学习包
- [ ] 多义词按具体用法分别维护记忆状态
- [ ] 在积累足够历史后优化个性化 FSRS 参数
- [ ] Windows 安装包与正式 Release

## 参与贡献

欢迎提交 Issue 和 Pull Request。请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。任何调度算法修改都必须附带参考向量或留出数据验证，不接受新增未经验证的手调间隔常数。

## 致谢

- [Project-MethodBox/GalReview](https://github.com/Project-MethodBox/GalReview)
- [Open Spaced Repetition](https://github.com/open-spaced-repetition)
- [OpenRouter](https://openrouter.ai/docs/quickstart)
- [Microsoft Fluent 2](https://fluent2.microsoft.design/)

当前项目处于积极开发阶段，首次正式打包发布前数据结构和设置项仍可能变化。

## 许可证

Copyright © 2026 Word2Sentence contributors.

Word2Sentence 采用 **GNU Affero General Public License v3.0 only**（`AGPL-3.0-only`）授权。完整条款请参阅 [LICENSE](LICENSE)；软件按许可证所述不提供担保。
