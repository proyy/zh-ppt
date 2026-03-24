# zh-ppt

基于 banana-slides 和阿里云 Qwen 模型的 PPT 自动生成技能，适用于 OpenClaw 平台。

## 项目结构

```
zh-ppt/                          # 一级目录：技能根目录
├── SKILL.md                     # OpenClaw 技能说明书
├── README.md                    # 使用说明
├── config.json                  # 配置文件（API Key、模型等）
├── .gitignore
├── scripts/
│   ├── generate.py              # Qwen-Image 生图脚本
│   ├── ppt_generator.py         # PPT 生成主脚本（整合流程）
│   └── requirements.txt         # Python 依赖
├── banana-slides/               # 二级目录：banana-slides 源码
│   ├── backend/
│   │   ├── app.py               # Flask 后端入口
│   │   ├── controllers/
│   │   │   ├── project_controller.py    # 项目/大纲/描述生成
│   │   │   ├── page_controller.py       # 单页编辑
│   │   │   └── export_controller.py     # PPTX 导出
│   │   ├── services/
│   │   │   ├── ai_service.py            # AI 调度
│   │   │   ├── prompts.py               # 提示词中心
│   │   │   ├── file_parser_service.py   # 文档解析
│   │   │   └── export_service.py        # PPTX 组装
│   │   └── services/ai_providers/
│   │       ├── text/qwen_provider.py    # Qwen 文本模型
│   │       └── image/qwen_provider.py   # Qwen 文生图
│   └── frontend/
│       └── src/store/useProjectStore.ts # 前端流程编排（参考）
├── output/                      # 输出目录（运行时创建）
│   ├── ppt_*.pptx
│   ├── images/
│   └── metadata.json
└── logs/                        # 日志目录（运行时创建）
```

## 边界说明

| 模块 | 职责 | 位置 |
|------|------|------|
| **banana-slides** | PPT 结构规划、内容生成、页面排版、导出 | `./banana-slides/` |
| **zh-ppt 技能** | 调用调度、Qwen-Image 生图、流程整合 | `./scripts/` |
| **Qwen-Image** | 根据页面描述生成高质量配图 | 阿里云百炼 API |

## 快速开始

### 1. 获取 API Key

访问 [阿里云百炼控制台](https://bailian.console.aliyun.com/) 获取 API Key。

### 2. 配置

编辑 `config.json`：

```json
{
  "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxx",
  "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "models": {
    "text": "qwen-max",
    "image": "qwen-image-2.0-pro",
    "vision": "qwen-vl-max"
  }
}
```

### 3. 同步配置到 banana-slides

```bash
# 自动同步配置到 banana-slides/.env 和数据库
python scripts/sync_config.py

# 只检查配置，不同步
python scripts/sync_config.py --check
```

### 4. 安装依赖

```bash
cd scripts
pip install -r requirements.txt
```

### 5. 启动服务

```bash
# 启动 banana-slides 后端
# 默认端口：15280 (谐音"我要爱 PPT")
python banana-slides/backend/app.py
```

### 6. 生成 PPT

```bash
# 根据主题生成
python scripts/ppt_generator.py --mode theme --prompt "人工智能发展史"

# 文档转 PPT
python scripts/ppt_generator.py --mode document --file report.pdf

# PPT 翻新
python scripts/ppt_generator.py --mode refresh --file old.pptx
```

## 核心流程

```
┌─────────────────────────────────────────────────────────────┐
│                      用户请求                                │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              zh-ppt/scripts/ppt_generator.py                │
│                    （技能调度层）                             │
└─────────────────────────────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            │               │               │
            ▼               ▼               ▼
    ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
    │  主题生成     │ │  文档转 PPT    │ │  PPT 翻新      │
    └───────────────┘ └───────────────┘ └───────────────┘
            │               │               │
            └───────────────┼───────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              banana-slides/backend/                         │
│   - project_controller.py (大纲/描述生成)                    │
│   - ai_service.py (AI 调度)                                  │
│   - prompts.py (提示词)                                      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              scripts/generate.py                            │
│           (Qwen-Image 生图)                                  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              banana-slides/backend/                         │
│   - export_controller.py (导出接口)                          │
│   - export_service.py (PPTX 组装)                            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   输出 PPTX 文件                              │
└─────────────────────────────────────────────────────────────┘
```

## 支持的模型

| 类型 | 模型 | 说明 |
|------|------|------|
| 文本生成 | qwen-max, qwen-plus, qwen-turbo | 大纲与描述生成 |
| 视觉理解 | qwen-vl-max, qwen-vl-plus | 图片分析（可选） |
| 文生图 | qwen-image-2.0-pro, qwen-image-2.0 | 页面配图生成 |

## 输出说明

```
output/
├── ppt_20250324_143022.pptx      # 最终 PPT 文件
├── images/
│   ├── page_1_20250324_143025.png
│   ├── page_2_20250324_143030.png
│   └── ...
└── metadata.json                  # 项目元数据
```

## OpenClaw 集成

本技能已按照 OpenClaw 规范编写 `SKILL.md`，包含：
- 元数据（名称、版本、标签、能力）
- 触发条件（主题/文档/PPT 翻新）
- 调度规则（完整流程）
- 源码映射（清晰边界）

在 OpenClaw 中配置后，用户可直接发送：
- "帮我做一个关于 XX 的 PPT"
- "[上传文档] 把这个做成 PPT"
- "[上传 PPT] 帮我美化一下"

## 许可证

遵循 banana-slides 项目许可证。
