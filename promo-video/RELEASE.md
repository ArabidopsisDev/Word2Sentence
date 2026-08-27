# Word2Sentence 宣传片发布记录

- 构建日期：2026-08-28
- 成片：`word2sentence-promo-final.mp4`
- 画布：1920 × 1080
- 帧率：25 fps
- 时长：94.880 秒
- 总帧数：2372
- 视频：H.264 High / yuv420p
- 音频：AAC LC / 48 kHz / 双声道
- 配音：无；使用烧录式单行中文字幕，并保留外部 SRT
- 章节：5 个，连续覆盖全片
- 字幕：20 条，全部单行

## 音乐

- 文件：`Jacoo - Towards the Light.mp3`
- 来源：用户从 `D:\Videos\Publish\anc` 提供，项目内保存工作副本
- SHA-256：`70E4C0138230EACF9D4340E4E8B46170655564515D9C6AF250CE6DDB70321274`
- 使用范围：97.9407–192.8207 秒，连续截取，无循环拼接
- 节拍：约 73.36 BPM
- 淡出：最后 4 秒；处理顺序为 loudnorm → volume → afade
- 发布授权：由发布者确认用户所提供音乐的使用权限

## 成片验收

- SHA-256：`583C488EE6C2412B1A95C2F486F341EBAD3F062BF1F8B8834A3F0C90CD342B3D`
- 文件大小：8,087,170 bytes
- 实测综合响度：-17.97 LUFS
- 实测真峰值：-3.14 dBTP
- LRA：6.30 LU
- 淡出分段平均电平：-20.9 → -21.3 → -21.5 → -30.2 → -35.4 dB
- 完整解码：通过
- 软字幕流：0；容器中的 data track 仅用于章节
- 最终证明帧：5 项全部从正式 MP4 抽取
- 独立审阅：文案、首次观看、技术、视觉几何全部通过

## 构建环境

- Python 3.12.13
- Pillow 12.3.0
- FFmpeg 9.0.1 essentials build
- 渲染：Python / Pillow / FFmpeg
- 项目与所有大型缓存、素材、预览和成片均位于 D 盘

## 封面

- 文件：`word2sentence-promo-cover.png`
- 尺寸：1920 × 1080
- SHA-256：`E1B85A3C458D352FAE7DEE576D0322EBCE0CAC0E7E0F74A942782E8C9A47919A`
- 320 × 180 缩略图 SHA-256：`06DB9015A26FE0B71337907219971B86789C9FF991400B5BEA43AB49A5DADE7C`

## 主要文件

- 成片：`word2sentence-promo-final.mp4`
- 封面：`word2sentence-promo-cover.png`
- 字幕：`project/content/subtitles.srt`
- 屏幕文案：`project/content/script.md`
- 时间线：`project/content/timeline.json`
- 分镜：`project/content/storyboard.md`
- 音乐卡点：`project/content/music-cues.csv`
- 技术依据：`project/docs/TECHNICAL_RESEARCH.md`
- 媒体 QA：`project/docs/QA_REPORT.md`
- 发布简介：`project/content/bilibili-description.md`

## 已知边界

Word2Sentence 当前仍为 prototype。结尾的“前往 GitHub 下载”表示前往仓库获取源码与 README 中的使用方式，不代表项目已经提供一键安装包。
