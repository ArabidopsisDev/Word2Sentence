# 制作说明

本文件只保存 production notes，任何一句都不得直接渲染。

- 渲染技术栈：Python 3.12 + Pillow 12.3；FFmpeg/FFprobe 待配置。
- 输出规格：1920×1080、25fps、H.264；默认无旁白，BGM-only。
- 暂定时长：70–90 秒；收到 BGM 后按乐句锁定。
- BGM：等待用户提供；未确认路径、哈希、授权、BPM、downbeat 和 phrase。
- 章节转场预算：只在四个主章节边界做约 0.7–1.0 秒重排，同章内不整页淡出。
- 主构图：开场 1 个、每章 1 个、总结 1 个；实机窗口保持稳定，局部裁切和高亮演进。
- 大文件与缓存：全部放在 `D:\Projects\Word2Sentence\promo-video\renders` 与 `work`。
- 截图：重新生成中文当前版本截图；README 英文截图仅作布局证据，不直接作为中文成片素材。
- proof 计划：许可证/GitHub、情境与输入、双版本改写与用法卡、FSRS 与本地数据各抽一组稳定帧。
- 已知限制：FFmpeg/FFprobe 缺失；BGM 缺失；精确时间线和最终渲染保持 blocking。

