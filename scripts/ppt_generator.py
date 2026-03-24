#!/usr/bin/env python3
"""
zh-ppt 技能 - PPT 生成主脚本

整合 banana-slides 和 Qwen 模型，实现完整的 PPT 自动生成流程。

支持三种模式：
1. theme: 根据主题生成 PPT
2. document: 文档转 PPT
3. refresh: PPT 翻新

用法：
    # 根据主题生成
    python ppt_generator.py --mode theme --prompt "人工智能发展史"
    
    # 文档转 PPT
    python ppt_generator.py --mode document --file report.pdf
    
    # PPT 翻新
    python ppt_generator.py --mode refresh --file old.pptx --requirement "做得更现代"
"""
import os
import sys
import json
import time
import logging
import argparse
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

import requests

# 配置日志
# 确保 logs 目录存在
logs_dir = Path(__file__).parent.parent / 'logs'
logs_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(logs_dir / 'ppt_generator.log', encoding='utf-8')
    ]
)
logger = logging.getLogger('zh-ppt')


class PPTGenerator:
    """PPT 生成器 - 整合 banana-slides 和 Qwen 模型"""
    
    def __init__(self, config_path: str = None):
        """
        初始化 PPT 生成器
        
        Args:
            config_path: 配置文件路径，默认为脚本同级的 config.json
        """
        self.config = self._load_config(config_path)
        self.session = self._create_session()
        self.output_dir = Path(self.config.get('output_dir', './output'))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 确保 logs 目录存在
        logs_dir = Path(__file__).parent / 'logs'
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"PPT 生成器初始化完成，输出目录：{self.output_dir.absolute()}")
    
    def _load_config(self, config_path: str = None) -> dict:
        """加载配置文件"""
        if config_path is None:
            # 配置路径：scripts/config.json 或 ../config.json
            config_path = Path(__file__).parent.parent / 'config.json'
        
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
    
    def _create_session(self):
        """创建 HTTP Session"""
        session = requests.Session()
        session.headers.update({
            'Content-Type': 'application/json',
        })
        return session
    
    def _call_banana_api(self, endpoint: str, method: str = 'GET', data: dict = None) -> dict:
        """
        调用 banana-slides API
        
        Args:
            endpoint: API 端点（如 /api/projects）
            method: HTTP 方法
            data: 请求数据
            
        Returns:
            API 响应数据
        """
        api_base = self.config.get('banana_slides', {}).get('api_base', 'http://localhost:5000')
        timeout = self.config.get('banana_slides', {}).get('timeout', 300)
        url = f"{api_base}{endpoint}"
        
        logger.debug(f"Calling banana-slides API: {method} {url}")
        
        try:
            if method == 'GET':
                response = self.session.get(url, timeout=timeout)
            elif method == 'POST':
                response = self.session.post(url, json=data, timeout=timeout)
            elif method == 'PUT':
                response = self.session.put(url, json=data, timeout=timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"API call failed: {method} {url} - {e}")
            raise
    
    def _wait_for_task(self, project_id: int, task_id: str = None, timeout: int = 600, poll_interval: int = 5) -> dict:
        """
        等待任务完成
        
        Args:
            project_id: 项目 ID
            task_id: 任务 ID（可选，如果有则轮询任务状态）
            timeout: 超时时间（秒）
            poll_interval: 轮询间隔（秒）
            
        Returns:
            项目数据
        """
        start_time = time.time()
        
        if task_id:
            # 轮询任务状态
            logger.info(f"等待任务完成，Task ID: {task_id}")
            while time.time() - start_time < timeout:
                task = self._call_banana_api(f'/api/projects/{project_id}/tasks/{task_id}')
                task_status = task.get('status', 'unknown')
                
                logger.info(f"任务状态：{task_status}")
                
                if task_status == 'completed':
                    logger.info("任务完成！")
                    break
                elif task_status in ['failed', 'error']:
                    error_msg = task.get('error_message', 'Unknown error')
                    logger.error(f"任务失败：{error_msg}")
                    raise RuntimeError(f"Task failed: {error_msg}")
                
                time.sleep(poll_interval)
            else:
                raise TimeoutError(f"Task timeout after {timeout} seconds")
        else:
            # 轮询项目状态（旧方式，兼容）
            logger.info(f"等待项目状态更新，项目 ID: {project_id}")
            while time.time() - start_time < timeout:
                project = self._call_banana_api(f'/api/projects/{project_id}')
                status = project.get('status', 'unknown')
                
                logger.info(f"项目状态：{status}")
                
                if status == 'completed':
                    logger.info("项目完成！")
                    break
                elif status in ['failed', 'error']:
                    error_msg = project.get('error_message', 'Unknown error')
                    logger.error(f"项目失败：{error_msg}")
                    raise RuntimeError(f"Project failed: {error_msg}")
                
                time.sleep(poll_interval)
            else:
                raise TimeoutError(f"Project timeout after {timeout} seconds")
        
        # 返回最新项目数据
        return self._call_banana_api(f'/api/projects/{project_id}')
    
    def _generate_images(self, project_id: int, pages: List[dict]) -> List[str]:
        """
        为 PPT 页面生成配图
        
        Args:
            project_id: 项目 ID
            pages: 页面列表
            
        Returns:
            生成的图片路径列表
        """
        image_paths = []
        models = self.config.get('models', {})
        image_model = models.get('image', 'qwen-image-2.0-pro')
        image_settings = self.config.get('image_settings', {})
        aspect_ratio = image_settings.get('aspect_ratio', '16:9')
        resolution = image_settings.get('resolution', '2K')
        
        logger.info(f"开始生成配图，使用模型：{image_model}")
        
        for i, page in enumerate(pages, 1):
            prompt = page.get('image_prompt', '')
            if not prompt:
                # 尝试从 description 生成 prompt
                description = page.get('description', '')
                if description:
                    prompt = description[:200]  # 使用描述作为 prompt
                    logger.info(f"第 {i} 页使用 description 作为 prompt")
                else:
                    logger.warning(f"第 {i} 页缺少 image_prompt 和 description，跳过")
                    continue
            
            logger.info(f"生成第 {i} 页配图：{prompt[:50]}...")
            
            prefix = f"page_{i}"
            
            cmd = [
                sys.executable,
                str(Path(__file__).parent / 'generate.py'),
                '--prompt', prompt,
                '--model', image_model,
                '--aspect-ratio', aspect_ratio,
                '--resolution', resolution,
                '--prefix', prefix,
                '--json',
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # 解析 JSON 输出获取图片路径
                for line in result.stdout.split('\n'):
                    if line.startswith('JSON 输出：'):
                        try:
                            json_str = line.replace('JSON 输出：', '').strip()
                            output = json.loads(json_str)
                            if output.get('success') and output.get('path'):
                                image_path = output['path']
                                image_paths.append(image_path)
                                logger.info(f"图片已保存：{image_path}")
                            break
                        except json.JSONDecodeError:
                            logger.warning("无法解析 JSON 输出，尝试其他方式")
                            continue
            else:
                logger.error(f"图片生成失败：{result.stderr}")
        
        return image_paths
    
    def _export_pptx(self, project_id: int) -> str:
        """
        导出 PPTX 文件
        
        Args:
            project_id: 项目 ID
            
        Returns:
            PPTX 文件路径
        """
        logger.info(f"导出 PPTX 文件，项目 ID: {project_id}")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self.output_dir / f'ppt_{timestamp}.pptx'
        
        api_base = self.config.get('banana_slides', {}).get('api_base', 'http://localhost:15280')
        # 注意：banana-slides 的导出接口路径是 /export/pptx，不是 /export
        url = f"{api_base}/api/projects/{project_id}/export/pptx"
        
        response = self.session.get(url, stream=True)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"PPTX 已保存：{output_path}")
        return str(output_path)
    
    def _save_metadata(self, project: dict, image_paths: List[str], pptx_path: str) -> str:
        """
        保存项目元数据
        
        Args:
            project: 项目数据
            image_paths: 图片路径列表
            pptx_path: PPTX 文件路径
            
        Returns:
            元数据文件路径
        """
        metadata = {
            'project_id': project.get('id'),
            'theme': project.get('idea_prompt', ''),
            'created_at': datetime.now().isoformat(),
            'page_count': len(project.get('pages', [])),
            'images': [
                {'page': i + 1, 'path': path}
                for i, path in enumerate(image_paths)
            ],
            'pptx_path': pptx_path,
            'models_used': self.config.get('models', {}),
        }
        
        metadata_path = self.output_dir / 'metadata.json'
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        logger.info(f"元数据已保存：{metadata_path}")
        return str(metadata_path)
    
    def generate_from_theme(self, prompt: str, requirements: str = None) -> dict:
        """
        根据主题生成 PPT
        
        注意：banana-slides API 使用蛇形命名（creation_type, idea_prompt）
        
        Args:
            prompt: 主题/想法
            requirements: 额外要求
            
        Returns:
            生成结果
        """
        logger.info(f"开始从主题生成 PPT：{prompt}")
        
        # 1. 创建项目
        logger.info("步骤 1: 创建项目")
        project_data = {
            'idea_prompt': prompt,
            'creation_type': 'idea',
        }
        if requirements:
            project_data['outline_requirements'] = requirements
        
        project = self._call_banana_api('/api/projects', 'POST', project_data)
        project_id = project.get('project_id') or project.get('id')
        if not project_id:
            raise RuntimeError(f"创建项目失败，未返回 project_id: {project}")
        logger.info(f"项目创建成功，ID: {project_id}")
        
        # 2. 生成大纲（触发后台任务）
        logger.info("步骤 2: 生成大纲")
        outline_task = self._call_banana_api(f'/api/projects/{project_id}/generate/outline', 'POST')
        task_id = outline_task.get('task_id')
        if task_id:
            logger.info(f"大纲生成任务已提交，Task ID: {task_id}")
            self._wait_for_task(project_id, task_id)
        
        # 3. 获取项目（包含大纲结果）
        project = self._call_banana_api(f'/api/projects/{project_id}', 'GET')
        
        # 4. 生成页面描述（触发后台任务）
        logger.info("步骤 3: 生成页面描述")
        desc_task = self._call_banana_api(f'/api/projects/{project_id}/generate/descriptions', 'POST')
        task_id = desc_task.get('task_id')
        if task_id:
            logger.info(f"描述生成任务已提交，Task ID: {task_id}")
            self._wait_for_task(project_id, task_id)
        
        # 5. 获取项目（包含描述结果）
        project = self._call_banana_api(f'/api/projects/{project_id}', 'GET')
        
        # 6. 生成配图
        logger.info("步骤 4: 生成配图")
        pages = project.get('pages', [])
        if not pages:
            raise RuntimeError(f"项目 {project_id} 没有页面数据")
        image_paths = self._generate_images(project_id, pages)
        
        # 7. 导出 PPTX
        logger.info("步骤 5: 导出 PPTX")
        pptx_path = self._export_pptx(project_id)
        
        # 8. 保存元数据
        logger.info("步骤 6: 保存元数据")
        metadata_path = self._save_metadata(project, image_paths, pptx_path)
        
        result = {
            'success': True,
            'project_id': project_id,
            'pptx_path': pptx_path,
            'image_paths': image_paths,
            'metadata_path': metadata_path,
            'page_count': len(pages),
        }
        
        logger.info(f"PPT 生成完成：{pptx_path}")
        return result
    
    def generate_from_document(self, file_path: str, requirements: str = None) -> dict:
        """
        从文档生成 PPT
        
        Args:
            file_path: 文档路径
            requirements: 额外要求
            
        Returns:
            生成结果
        """
        logger.info(f"开始从文档生成 PPT：{file_path}")
        
        # 1. 上传文件
        logger.info("步骤 1: 上传文件")
        api_base = self.config.get('banana_slides', {}).get('api_base', 'http://localhost:15280')
        upload_url = f"{api_base}/api/files"
        
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = self.session.post(upload_url, files=files)
            response.raise_for_status()
            file_data = response.json()
            file_id = file_data.get('id') or file_data.get('file_id')
        
        if not file_id:
            raise RuntimeError(f"文件上传失败：{file_data}")
        logger.info(f"文件上传成功，ID: {file_id}")
        
        # 2. 创建项目
        logger.info("步骤 2: 创建项目")
        project_data = {
            'reference_file_ids': [file_id],
            'creation_type': 'idea',  # banana-slides 通过 reference_file_ids 自动识别为文档模式
        }
        if requirements:
            project_data['outline_requirements'] = requirements
        
        project = self._call_banana_api('/api/projects', 'POST', project_data)
        project_id = project.get('project_id') or project.get('id')
        
        if not project_id:
            raise RuntimeError(f"创建项目失败：{project}")
        
        # 3. 后续步骤同 theme 模式
        return self._continue_generation(project_id)
    
    def refresh_ppt(self, file_path: str, requirements: str = None) -> dict:
        """
        翻新已有 PPT
        
        Args:
            file_path: PPT 文件路径
            requirements: 翻新要求
            
        Returns:
            生成结果
        """
        logger.info(f"开始翻新 PPT：{file_path}, 要求：{requirements}")
        
        # 1. 上传文件
        logger.info("步骤 1: 上传文件")
        api_base = self.config.get('banana_slides', {}).get('api_base', 'http://localhost:15280')
        upload_url = f"{api_base}/api/files"
        
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = self.session.post(upload_url, files=files)
            response.raise_for_status()
            file_data = response.json()
            file_id = file_data.get('id') or file_data.get('file_id')
        
        if not file_id:
            raise RuntimeError(f"文件上传失败：{file_data}")
        logger.info(f"文件上传成功，ID: {file_id}")
        
        # 2. 创建项目
        logger.info("步骤 2: 创建项目")
        project_data = {
            'reference_file_ids': [file_id],
            'creation_type': 'idea',  # banana-slides 会自动识别 PPT 文件并处理
        }
        if requirements:
            project_data['outline_requirements'] = requirements
        
        project = self._call_banana_api('/api/projects', 'POST', project_data)
        project_id = project.get('project_id') or project.get('id')
        
        if not project_id:
            raise RuntimeError(f"创建项目失败：{project}")
        
        # 3. 后续步骤同 theme 模式
        return self._continue_generation(project_id)
    
    def _continue_generation(self, project_id: int) -> dict:
        """继续生成流程（等待任务、生成描述、配图、导出）"""
        # 1. 生成大纲（触发后台任务）
        logger.info("步骤 1: 生成大纲")
        outline_task = self._call_banana_api(f'/api/projects/{project_id}/generate/outline', 'POST')
        task_id = outline_task.get('task_id')
        if task_id:
            logger.info(f"大纲生成任务已提交，Task ID: {task_id}")
            self._wait_for_task(project_id, task_id)
        
        # 2. 获取项目（包含大纲结果）
        project = self._call_banana_api(f'/api/projects/{project_id}', 'GET')
        
        # 3. 生成页面描述（触发后台任务）
        logger.info("步骤 2: 生成页面描述")
        desc_task = self._call_banana_api(f'/api/projects/{project_id}/generate/descriptions', 'POST')
        task_id = desc_task.get('task_id')
        if task_id:
            logger.info(f"描述生成任务已提交，Task ID: {task_id}")
            self._wait_for_task(project_id, task_id)
        
        # 4. 获取项目（包含描述结果）
        project = self._call_banana_api(f'/api/projects/{project_id}', 'GET')
        
        # 5. 生成配图
        logger.info("步骤 3: 生成配图")
        pages = project.get('pages', [])
        if not pages:
            raise RuntimeError(f"项目 {project_id} 没有页面数据")
        image_paths = self._generate_images(project_id, pages)
        
        # 6. 导出 PPTX
        logger.info("步骤 4: 导出 PPTX")
        pptx_path = self._export_pptx(project_id)
        
        # 7. 保存元数据
        logger.info("步骤 5: 保存元数据")
        metadata_path = self._save_metadata(project, image_paths, pptx_path)
        
        result = {
            'success': True,
            'project_id': project_id,
            'pptx_path': pptx_path,
            'image_paths': image_paths,
            'metadata_path': metadata_path,
            'page_count': len(pages),
        }
        
        return result


def print_result(result: dict):
    """打印生成结果"""
    print("\n" + "=" * 60)
    print("✅ PPT 生成完成！")
    print("=" * 60)
    print(f"📁 PPT 文件：{result['pptx_path']}")
    print(f"🖼️ 配图数量：{len(result['image_paths'])} 张")
    print(f"📄 页数：{result['page_count']} 页")
    print(f"📋 元数据：{result['metadata_path']}")
    print("=" * 60)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='zh-ppt 技能 - PPT 生成主脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 根据主题生成
  python ppt_generator.py --mode theme --prompt "人工智能发展史"
  
  # 文档转 PPT
  python ppt_generator.py --mode document --file report.pdf
  
  # PPT 翻新
  python ppt_generator.py --mode refresh --file old.pptx --requirement "做得更现代简洁"
        """
    )
    
    parser.add_argument(
        '--mode', '-m',
        required=True,
        help='生成模式',
        choices=['theme', 'document', 'refresh']
    )
    parser.add_argument(
        '--prompt', '-p',
        help='主题/想法（theme 模式必填）'
    )
    parser.add_argument(
        '--file', '-f',
        help='输入文件路径（document/refresh 模式必填）'
    )
    parser.add_argument(
        '--requirement', '-r',
        help='额外要求'
    )
    parser.add_argument(
        '--config', '-c',
        default=None,
        help='配置文件路径（默认：../config.json）'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='显示详细日志'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 验证参数
    if args.mode == 'theme' and not args.prompt:
        logger.error("theme 模式需要指定 --prompt")
        sys.exit(1)
    
    if args.mode in ['document', 'refresh'] and not args.file:
        logger.error(f"{args.mode} 模式需要指定 --file")
        sys.exit(1)
    
    if args.file and not os.path.exists(args.file):
        logger.error(f"文件不存在：{args.file}")
        sys.exit(1)
    
    # 创建生成器并执行
    generator = PPTGenerator(args.config)
    
    try:
        if args.mode == 'theme':
            result = generator.generate_from_theme(args.prompt, args.requirement)
        elif args.mode == 'document':
            result = generator.generate_from_document(args.file, args.requirement)
        elif args.mode == 'refresh':
            result = generator.refresh_ppt(args.file, args.requirement)
        
        print_result(result)
        
    except Exception as e:
        logger.error(f"生成失败：{e}", exc_info=True)
        print(f"\n❌ 生成失败：{e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
