#!/usr/bin/env python3
"""
配置同步脚本 - 将 zh-ppt/config.json 同步到 banana-slides

用途：
1. 首次部署时初始化 banana-slides 配置
2. 更新配置时同步到 banana-slides

用法：
    python sync_config.py
    python sync_config.py --check  # 只检查，不同步
"""
import os
import sys
import json
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('config-sync')


def load_zh_ppt_config():
    """加载 zh-ppt/config.json"""
    config_path = Path(__file__).parent / 'config.json'
    
    if not config_path.exists():
        logger.error(f"配置文件不存在：{config_path}")
        sys.exit(1)
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def generate_env_content(zh_ppt_config: dict) -> str:
    """
    根据 zh-ppt 配置生成 .env 内容
    
    Args:
        zh_ppt_config: zh-ppt/config.json 内容
        
    Returns:
        .env 文件内容
    """
    models = zh_ppt_config.get('models', {})
    image_settings = zh_ppt_config.get('image_settings', {})
    banana_slides = zh_ppt_config.get('banana_slides', {})
    
    env_content = f"""# 自动生成的配置文件
# 由 zh-ppt/scripts/sync_config.py 生成
# 请勿手动修改，运行 sync_config.py 会自动覆盖

# AI Provider 格式
AI_PROVIDER_FORMAT=qwen

# Qwen API 配置（所有 Qwen 模型共用一个 API Key）
QWEN_API_KEY={zh_ppt_config.get('api_key', '')}
QWEN_API_BASE={zh_ppt_config.get('api_url', 'https://dashscope.aliyuncs.com/compatible-mode/v1')}

# 文本生成模型
TEXT_MODEL_SOURCE=qwen
TEXT_MODEL={models.get('text', 'qwen-max')}

# 图像生成模型
IMAGE_MODEL_SOURCE=qwen
IMAGE_MODEL={models.get('image', 'qwen-image-2.0-pro')}

# 图像生成设置
DEFAULT_RESOLUTION={image_settings.get('resolution', '2K')}
DEFAULT_ASPECT_RATIO={image_settings.get('aspect_ratio', '16:9')}

# 视觉理解模型（image caption）
IMAGE_CAPTION_MODEL_SOURCE=qwen
IMAGE_CAPTION_MODEL={models.get('vision', 'qwen-vl-max')}

# 端口配置
BACKEND_PORT={banana_slides.get('api_base', 'http://localhost:15280').split(':')[-1].split('/')[0]}

# 其他配置
LOG_LEVEL=INFO
FLASK_ENV=development
OUTPUT_LANGUAGE=zh
"""
    return env_content


def sync_to_env(zh_ppt_config: dict, dry_run: bool = False):
    """
    同步配置到 banana-slides/.env
    
    Args:
        zh_ppt_config: zh-ppt 配置
        dry_run: 如果 True，只显示不写入
    """
    env_path = Path(__file__).parent.parent / 'banana-slides' / '.env'
    env_content = generate_env_content(zh_ppt_config)
    
    if dry_run:
        logger.info("=== 预览 .env 内容 ===")
        print(env_content)
        logger.info("=== 预览结束 ===")
        return
    
    # 备份现有 .env
    if env_path.exists():
        backup_path = env_path.with_suffix('.env.bak')
        with open(env_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(original_content)
        logger.info(f"已备份原 .env 到：{backup_path}")
    
    # 写入新配置
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    logger.info(f"配置已同步到：{env_path}")


def sync_via_api(zh_ppt_config: dict, dry_run: bool = False):
    """
    通过 API 同步配置到 banana-slides 数据库 settings 表
    
    Args:
        zh_ppt_config: zh-ppt 配置
        dry_run: 如果 True，只检查不同步
    """
    import requests
    
    api_base = zh_ppt_config.get('banana_slides', {}).get('api_base', 'http://localhost:15280')
    models = zh_ppt_config.get('models', {})
    image_settings = zh_ppt_config.get('image_settings', {})
    
    # 构建 settings API 请求
    settings_data = {
        'text_model': models.get('text', 'qwen-max'),
        'text_model_source': 'qwen',
        'image_model': models.get('image', 'qwen-image-2.0-pro'),
        'image_model_source': 'qwen',
        'image_caption_model': models.get('vision', 'qwen-vl-max'),
        'image_caption_model_source': 'qwen',
        'image_resolution': image_settings.get('resolution', '2K'),
        'image_aspect_ratio': image_settings.get('aspect_ratio', '16:9'),
        'api_key': zh_ppt_config.get('api_key', ''),
        'api_base_url': zh_ppt_config.get('api_url', ''),
    }
    
    if dry_run:
        logger.info("=== 预览 API 同步内容 ===")
        logger.info(f"API Base: {api_base}")
        logger.info(f"Settings: {json.dumps(settings_data, indent=2, ensure_ascii=False)}")
        logger.info("=== 预览结束 ===")
        return
    
    try:
        # 更新 settings
        response = requests.put(
            f'{api_base}/api/settings',
            json=settings_data,
            timeout=30
        )
        
        if response.status_code == 200:
            logger.info("配置已通过 API 同步到 banana-slides 数据库")
        else:
            logger.warning(f"API 同步失败：{response.status_code} - {response.text}")
            logger.info("请确保 banana-slides 服务已启动")
            
    except requests.exceptions.ConnectionError:
        logger.warning("无法连接到 banana-slides 服务")
        logger.info("请确保 banana-slides 服务已启动：python banana-slides/backend/app.py")
    except Exception as e:
        logger.error(f"API 同步失败：{e}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='同步 zh-ppt 配置到 banana-slides'
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='只检查配置，不同步'
    )
    parser.add_argument(
        '--api-only',
        action='store_true',
        help='只通过 API 同步（不同步 .env）'
    )
    parser.add_argument(
        '--env-only',
        action='store_true',
        help='只同步 .env（不通过 API）'
    )
    
    args = parser.parse_args()
    
    # 加载配置
    logger.info("加载 zh-ppt 配置...")
    config = load_zh_ppt_config()
    
    # 验证配置
    if not config.get('api_key'):
        logger.error("config.json 中缺少 api_key")
        sys.exit(1)
    
    logger.info(f"API Key: {config['api_key'][:10]}...{config['api_key'][-4:]}")
    logger.info(f"文本模型：{config.get('models', {}).get('text', 'qwen-max')}")
    logger.info(f"图像模型：{config.get('models', {}).get('image', 'qwen-image-2.0-pro')}")
    logger.info(f"视觉模型：{config.get('models', {}).get('vision', 'qwen-vl-max')}")
    
    if args.check:
        logger.info("=== 配置检查完成 ===")
        return
    
    # 同步到 .env
    if not args.api_only:
        logger.info("同步配置到 .env...")
        sync_to_env(config, dry_run=False)
    
    # 通过 API 同步
    if not args.env_only:
        logger.info("通过 API 同步配置...")
        sync_via_api(config, dry_run=False)
    
    logger.info("=== 配置同步完成 ===")
    logger.info("重启 banana-slides 服务使配置生效：")
    logger.info("  cd banana-slides && python backend/app.py")


if __name__ == '__main__':
    main()
