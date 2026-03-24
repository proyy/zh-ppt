#!/usr/bin/env python3
"""
zh-ppt 技能 - 图片生成脚本

调用 Qwen-Image API 生成 PPT 配图，支持多种模型：
- qwen-image-2.0-pro
- qwen-image-2.0
- qwen-image-max

用法：
    python scripts/generate.py --prompt "描述文字" --model qwen-image-2.0-pro
    python scripts/generate.py --prompt "描述文字" --ref-image reference.png
"""
import os
import sys
import json
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import base64
from io import BytesIO

import requests
from PIL import Image

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config(config_path: str = None) -> dict:
    """
    读取 config.json 配置文件
    
    Args:
        config_path: 配置文件路径，默认为 ../config.json
        
    Returns:
        配置字典
    """
    if config_path is None:
        script_dir = Path(__file__).parent
        config_path = script_dir.parent / 'config.json'
    
    config_path = Path(config_path)
    
    if not config_path.exists():
        logger.error(f"配置文件不存在：{config_path}")
        sys.exit(1)
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 验证必填配置
    if not config.get('api_key'):
        logger.error("config.json 中缺少必填配置：api_key")
        sys.exit(1)
    
    return config


def resolve_settings(config: dict) -> dict:
    """
    从 config.json / 环境变量获取配置
    
    优先级：config.json > 环境变量 > 默认值
    
    Args:
        config: config.json 配置字典
        
    Returns:
        合并后的配置字典
    """
    # 从 models.image 获取模型配置（正确路径）
    models_config = config.get('models', {})
    
    settings = {
        'api_key': config.get('api_key') or os.getenv('QWEN_API_KEY'),
        'api_url': config.get('api_url') or os.getenv('QWEN_API_BASE', 'https://dashscope.aliyuncs.com/compatible-mode/v1'),
        'model': models_config.get('image') or os.getenv('QWEN_IMAGE_MODEL', 'qwen-image-2.0-pro'),
        'output_dir': config.get('output_dir') or './output',
    }
    
    # 图片生成设置
    image_settings = config.get('image_settings', {})
    settings['aspect_ratio'] = image_settings.get('aspect_ratio', '16:9')
    settings['resolution'] = image_settings.get('resolution', '2K')
    
    # 验证 - 支持通过环境变量传入 API Key（便于从 sync_config.py 同步）
    if not settings['api_key']:
        # 尝试从 banana-slides .env 读取
        env_file = Path(__file__).parent.parent / 'banana-slides' / '.env'
        if env_file.exists():
            from dotenv import dotenv_values
            env_vars = dotenv_values(env_file)
            settings['api_key'] = env_vars.get('QWEN_API_KEY', '')
    
    if not settings['api_key']:
        logger.error("未配置 API Key，请在 config.json 中设置 api_key 或设置 QWEN_API_KEY 环境变量")
        sys.exit(1)
    
    return settings


def build_output_dir(output_dir: str) -> Path:
    """
    创建并返回 output 输出目录
    
    Args:
        output_dir: 输出目录路径
        
    Returns:
        输出目录 Path 对象
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 创建 images 子目录
    images_dir = output_path / 'images'
    images_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"输出目录：{output_path.absolute()}")
    return output_path


def encode_image_to_base64(image: Image.Image) -> str:
    """
    将 PIL Image 编码为 base64 字符串
    
    Args:
        image: PIL Image 对象
        
    Returns:
        base64 编码字符串
    """
    buffered = BytesIO()
    if image.mode in ('RGBA', 'LA', 'P'):
        image = image.convert('RGB')
    image.save(buffered, format="JPEG", quality=95)
    return base64.b64encode(buffered.getvalue()).decode('utf-8')


def calculate_size(aspect_ratio: str, resolution: str) -> str:
    """
    计算 Qwen-Image 所需的 size 参数（格式："width*height"）
    
    Args:
        aspect_ratio: 宽高比，如 "16:9"
        resolution: 分辨率，如 "1K", "2K", "4K"
        
    Returns:
        size 字符串，如 "2048*1152"
    """
    aspect_ratios = {
        "16:9": (16, 9),
        "9:16": (9, 16),
        "4:3": (4, 3),
        "3:4": (3, 4),
        "3:2": (3, 2),
        "2:3": (2, 3),
        "1:1": (1, 1),
    }
    resolution_base = {
        "1K": 1024,
        "2K": 2048,
        "4K": 4096,
    }
    
    ratio = aspect_ratios.get(aspect_ratio, (16, 9))
    base = resolution_base.get(resolution, 2048)
    
    if ratio[0] >= ratio[1]:
        w = base
        h = int(base * ratio[1] / ratio[0])
    else:
        h = base
        w = int(base * ratio[0] / ratio[1])
    
    # 对齐到 64 的倍数
    w = max(64, ((w + 63) // 64) * 64)
    h = max(64, ((h + 63) // 64) * 64)
    
    return f"{w}*{h}"


def request_image(
    prompt: str,
    api_key: str,
    api_url: str,
    model: str,
    size: str = "2048*1152",
    ref_images: Optional[List[Image.Image]] = None
) -> Optional[Image.Image]:
    """
    发送 prompt 到生图接口，解析返回结果
    
    Args:
        prompt: 图片描述
        api_key: API Key
        api_url: API 地址
        model: 模型名称
        size: 图片尺寸，格式 "width*height"
        ref_images: 参考图片列表（可选）
        
    Returns:
        生成的 PIL Image 对象，失败返回 None
    """
    from openai import OpenAI
    
    logger.info(f"调用 Qwen-Image API，模型：{model}, 尺寸：{size}")
    logger.debug(f"Prompt: {prompt[:200]}...")
    
    try:
        client = OpenAI(
            api_key=api_key,
            base_url=api_url,
            timeout=300.0,
            max_retries=2
        )
        
        # Qwen-Image 使用 images 接口
        logger.info(f"使用 OpenAI SDK 调用 Qwen-Image，base_url: {api_url}")
        
        # 构建请求参数
        kwargs = {
            'model': model,
            'prompt': prompt,
            'size': size,
            'n': 1,
            'response_format': 'url',
        }
        
        # 如果有参考图片，添加额外头信息
        if ref_images:
            kwargs['extra_headers'] = {
                'X-DashScope-Image-Reference': 'true',
            }
        
        try:
            response = client.images.generate(**kwargs)
        except Exception as gen_error:
            # 如果 images.generate 失败，尝试 chat.completions 方式
            logger.warning(f"images.generate 失败：{gen_error}")
            logger.info("尝试使用 wanx 模型格式...")
            
            # 阿里云 DashScope 的 wanx 模型使用不同格式
            response = client.images.generate(
                model='wanx2.1-t2i-turbo',  # 尝试通义万相
                prompt=prompt,
                size=size,
                n=1,
            )
        
        # 提取图片 URL
        if hasattr(response, 'data') and response.data:
            image_url = response.data[0].url
            logger.info(f"获取到图片 URL: {image_url[:80]}...")
            
            # 下载图片
            img_response = requests.get(image_url, timeout=60, stream=True)
            img_response.raise_for_status()
            
            image = Image.open(BytesIO(img_response.content))
            image.load()
            logger.info(f"成功下载图片：{image.size}, {image.mode}")
            return image
        else:
            logger.error("API 返回数据中没有图片 URL")
            return None
            
        except Exception as e:
            error_detail = f"调用生图接口失败：{type(e).__name__}: {str(e)}"
            logger.error(error_detail, exc_info=True)
            # 提供更详细的错误信息
            if hasattr(e, 'response'):
                logger.error(f"API Response: {e.response.text if hasattr(e.response, 'text') else e.response}")
            return None


def download_image(image: Image.Image, output_dir: Path, prefix: str = "page") -> str:
    """
    保存图片到本地
    
    Args:
        image: PIL Image 对象
        output_dir: 输出目录
        prefix: 文件名前缀
        
    Returns:
        保存的文件路径
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.png"
    output_path = output_dir / 'images' / filename
    
    image.save(output_path, 'PNG')
    logger.info(f"图片已保存：{output_path}")
    return str(output_path)


def main():
    """
    主函数
    
    流程：
    1. 读取命令行参数
    2. 解析配置
    3. 创建输出目录
    4. 调用生图接口
    5. 下载图片到 output
    6. 输出文件路径
    """
    parser = argparse.ArgumentParser(
        description='zh-ppt 技能 - Qwen-Image 图片生成脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/generate.py --prompt "一只可爱的卡通熊猫在吃竹子"
  python scripts/generate.py --prompt "科技感的未来城市" --model qwen-image-max
  python scripts/generate.py --prompt "办公室场景" --ref-image reference.png
        """
    )
    
    parser.add_argument(
        '--prompt', '-p',
        required=True,
        help='图片描述文字'
    )
    parser.add_argument(
        '--model', '-m',
        default=None,
        help='模型名称 (默认：qwen-image-2.0-pro)',
        choices=['qwen-image-2.0-pro', 'qwen-image-2.0', 'qwen-image-max']
    )
    parser.add_argument(
        '--ref-image', '-r',
        nargs='+',
        help='参考图片路径（可选，支持多张）'
    )
    parser.add_argument(
        '--config', '-c',
        default=None,
        help='配置文件路径（默认：../config.json）'
    )
    parser.add_argument(
        '--aspect-ratio',
        default=None,
        help='图片宽高比 (默认：16:9)',
        choices=['16:9', '9:16', '4:3', '3:4', '3:2', '2:3', '1:1']
    )
    parser.add_argument(
        '--resolution',
        default=None,
        help='图片分辨率 (默认：2K)',
        choices=['1K', '2K', '4K']
    )
    parser.add_argument(
        '--prefix',
        default='page',
        help='输出文件名前缀 (默认：page)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='显示详细日志'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='使用 JSON 格式输出（便于脚本调用）'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 1. 读取配置
    logger.info("加载配置文件...")
    config = load_config(args.config)
    settings = resolve_settings(config)
    
    # 命令行参数覆盖配置文件
    if args.model:
        settings['model'] = args.model
    if args.aspect_ratio:
        settings['aspect_ratio'] = args.aspect_ratio
    if args.resolution:
        settings['resolution'] = args.resolution
    
    logger.info(f"使用模型：{settings['model']}")
    logger.info(f"图片比例：{settings['aspect_ratio']}, 分辨率：{settings['resolution']}")
    
    # 2. 创建输出目录
    output_path = build_output_dir(settings['output_dir'])
    
    # 3. 计算图片尺寸
    size = calculate_size(settings['aspect_ratio'], settings['resolution'])
    logger.info(f"计算得到的图片尺寸：{size}")
    
    # 4. 加载参考图片（如果有）
    ref_images = []
    if args.ref_image:
        for ref_path in args.ref_image:
            if os.path.exists(ref_path):
                try:
                    ref_img = Image.open(ref_path)
                    ref_images.append(ref_img)
                    logger.info(f"加载参考图片：{ref_path} ({ref_img.size})")
                except Exception as e:
                    logger.warning(f"加载参考图片失败 {ref_path}: {e}")
            else:
                logger.warning(f"参考图片不存在：{ref_path}")
    
    # 5. 调用生图接口
    logger.info("正在生成图片...")
    generated_image = request_image(
        prompt=args.prompt,
        api_key=settings['api_key'],
        api_url=settings['api_url'],
        model=settings['model'],
        size=size,
        ref_images=ref_images if ref_images else None
    )
    
    if generated_image is None:
        logger.error("图片生成失败")
        sys.exit(1)
    
    # 6. 保存图片
    saved_path = download_image(generated_image, output_path, args.prefix)
    
    # 7. 输出结果
    result = {
        'success': True,
        'model': settings['model'],
        'size': list(generated_image.size),
        'path': saved_path,
    }
    
    if args.json:
        # JSON 模式：只输出 JSON，便于脚本解析
        print(f"JSON 输出：{json.dumps(result, ensure_ascii=False)}")
    else:
        # 人类可读模式
        print("\n" + "=" * 50)
        print("图片生成成功！")
        print("=" * 50)
        print(f"模型：{settings['model']}")
        print(f"尺寸：{generated_image.size[0]}x{generated_image.size[1]}")
        print(f"保存路径：{saved_path}")
        print("=" * 50)
        print(f"\nJSON 输出：{json.dumps(result, ensure_ascii=False)}")


if __name__ == '__main__':
    main()
