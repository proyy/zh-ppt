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
        api_base = self.config.get('banana_slides', {}).get('api_base', 'http://localhost:15280')
        timeout = self.config.get('banana_slides', {}).get('timeout', 300)
        url = f"{api_base}{endpoint}"
        
        logger.debug(f"Calling banana-slides API: {method} {url}")
        
        try:
            if method == 'GET':
                response = self.session.get(url, timeout=timeout)
            elif method == 'POST':
                response = self.session.post(url, json=data or {}, timeout=timeout)
            elif method == 'PUT':
                response = self.session.put(url, json=data or {}, timeout=timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            response_data = response.json()
            
            # banana-slides 响应格式：{"success": true, "data": {...}}
            # 自动提取 data 字段，方便上层调用
            if isinstance(response_data, dict) and 'data' in response_data:
                return response_data['data']
            return response_data
            
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
                
                # 任务状态可能为 COMPLETED/completed 或 PROCESSING/processing
                if task_status.upper() == 'COMPLETED':
                    logger.info("任务完成！")
                    break
                elif task_status.upper() in ['FAILED', 'ERROR']:
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
                
                # 项目状态可能为 COMPLETED/completed 或 PROCESSING/processing
                if status.upper() == 'COMPLETED':
                    logger.info("项目完成！")
                    break
                elif status.upper() in ['FAILED', 'ERROR']:
                    error_msg = project.get('error_message', 'Unknown error')
                    logger.error(f"项目失败：{error_msg}")
                    raise RuntimeError(f"Project failed: {error_msg}")
                
                time.sleep(poll_interval)
            else:
                raise TimeoutError(f"Project timeout after {timeout} seconds")
        
        # 返回最新项目数据
        return self._call_banana_api(f'/api/projects/{project_id}')
    
    def _generate_images(self, project_id: int, pages: List[dict], requirements: str = None) -> List[str]:
        """
        为 PPT 页面生成配图（使用 banana-slides 原生 API）
        
        Args:
            project_id: 项目 ID
            pages: 页面列表
            requirements: 详细要求（包含风格要求）
             
        Returns:
            生成的图片路径列表
        """
        image_paths = []
        api_base = self.config.get('banana_slides', {}).get('api_base', 'http://localhost:15280')
        
        logger.info(f"开始生成配图（使用 banana-slides 原生 API），页面数量：{len(pages)}")
        
        # 从 requirements 中提取风格描述
        style_description = '简洁专业的商务风格，清晰的视觉层次'
        if requirements:
            if '风格要求：' in requirements:
                style_start = requirements.find('风格要求：') + len('风格要求：')
                style_end = requirements.find('\n', style_start)
                if style_end == -1:
                    style_end = len(requirements)
                style_description = requirements[style_start:style_end].strip()
                logger.info(f"使用风格描述：{style_description}")
        
        for i, page in enumerate(pages, 1):
            page_id = page.get('page_id')
            if not page_id:
                logger.warning(f"第 {i} 页缺少 page_id，跳过")
                continue
            
            logger.info(f"生成第 {i} 页配图，page_id: {page_id}")
            
            try:
                # 调用 banana-slides 原生 API 生成页面图片
                url = f"{api_base}/api/projects/{project_id}/pages/{page_id}/generate/image"
                
                # 获取页面描述作为风格参考
                desc_content = page.get('description_content', {})
                page_style_desc = ""
                if isinstance(desc_content, dict):
                    extra_fields = desc_content.get('extra_fields', {})
                    if isinstance(extra_fields, dict):
                        page_style_desc = extra_fields.get('视觉建议', '') or extra_fields.get('视觉风格', '')
                
                final_style = page_style_desc if page_style_desc else style_description
                
                response = self.session.post(url, json={
                    'use_template': False,
                    'force_regenerate': True,
                    'style_description': final_style
                }, timeout=300)
                
                # 202 表示任务已提交（异步），200 表示已完成
                if response.status_code in [200, 202]:
                    result = response.json()
                    data = result.get('data', {})
                    task_id = data.get('task_id')
                    
                    # 如果是异步任务，轮询等待完成
                    if task_id and response.status_code == 202:
                        logger.info(f"第 {i} 页图片生成任务已提交，Task ID: {task_id}，等待完成...")
                        
                        # 轮询任务状态（最多等待 5 分钟）
                        for attempt in range(60):
                            time.sleep(5)
                            task_response = self.session.get(
                                f"{api_base}/api/projects/{project_id}/tasks/{task_id}",
                                timeout=30
                            )
                            if task_response.status_code == 200:
                                task_data = task_response.json().get('data', {})
                                task_status = task_data.get('status', '')
                                
                                if task_status == 'COMPLETED':
                                    logger.info(f"第 {i} 页图片生成完成")
                                    break
                                elif task_status in ['FAILED', 'ERROR']:
                                    error_msg = task_data.get('error_message', 'Unknown error')
                                    logger.error(f"第 {i} 页图片生成失败：{error_msg}")
                                    break
                                else:
                                    logger.debug(f"第 {i} 页图片生成中：{task_status}")
                    
                    # 获取页面数据，提取图片路径
                    page_response = self.session.get(
                        f"{api_base}/api/projects/{project_id}/pages/{page_id}",
                        timeout=30
                    )
                    if page_response.status_code == 200:
                        page_data = page_response.json().get('data', {})
                        generated_image_path = page_data.get('generated_image_path')
                        
                        if generated_image_path:
                            image_paths.append(generated_image_path)
                            logger.info(f"第 {i} 页图片路径：{generated_image_path}")
                        else:
                            logger.warning(f"第 {i} 页图片生成成功但未返回路径")
                    else:
                        logger.error(f"获取第 {i} 页数据失败：{page_response.status_code}")
                        
                else:
                    logger.error(f"第 {i} 页图片生成失败：{response.status_code} - {response.text[:200]}")
                    
            except Exception as e:
                logger.error(f"第 {i} 页图片生成异常：{e}")
        
        logger.info(f"配图生成完成，成功：{len(image_paths)}/{len(pages)}")
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
    
    def generate_from_text(self, text: str) -> dict:
        """
        根据大段文本自动生成 PPT
        
        自动分析文本内容，提取主题和要求，调用 banana-slides 生成 PPT
        
        特点：
        - 完整保留文本中的所有关键细节
        - 分段处理长文本避免 token 限制
        - 使用结构化 prompt 确保信息不丢失
        - 提取的要求直接用于 outline_requirements
        
        Args:
            text: 大段文本内容（可以是需求描述、文档内容等）
            
        Returns:
            生成结果
        """
        logger.info(f"开始从文本生成 PPT，文本长度：{len(text)} 字符")
        
        # 使用 Qwen 文本模型分析文本，提取主题和要求
        logger.info("步骤 1: 分析文本内容，提取主题和要求")
        
        # 分段处理长文本（每段 4000 字符，避免 token 限制）
        text_segments = []
        max_segment_length = 4000
        
        if len(text) <= max_segment_length:
            text_segments.append(text)
        else:
            # 按段落分割，尽量保持语义完整
            paragraphs = text.split('\n')
            current_segment = ""
            for para in paragraphs:
                if len(current_segment) + len(para) + 1 <= max_segment_length:
                    current_segment += para + '\n'
                else:
                    if current_segment:
                        text_segments.append(current_segment.strip())
                    current_segment = para + '\n'
            if current_segment.strip():
                text_segments.append(current_segment.strip())
        
        logger.info(f"文本已分段：{len(text_segments)} 段")
        
        # 构建详细的分析 prompt，确保保留所有细节
        analysis_prompt = f"""你是一个专业的 PPT 需求分析专家。请仔细分析以下文本，完整提取所有关键细节。

## 分析要求

1. **主题提取**：用简洁准确的语言概括 PPT 核心主题（20-50 字）

2. **详细要求提取**：
   - 列出文本中明确提到的所有内容要求
   - 列出文本中提到的风格要求（如科技感、简洁、商务等）
   - 列出文本中提到的页数要求
   - 列出文本中提到的特殊要求（如必须包含的内容、避免的内容等）
   - **重要**：保留原文中的关键术语、数据、名称等具体信息，不要概括或省略

3. **结构建议**：根据文本内容建议 PPT 的章节结构

## 文本内容

{text[:8000] if len(text) <= 8000 else text[:8000] + "...（内容过长，已截断）"}

## 返回格式

请严格按照以下 JSON 格式返回：

```json
{{
    "theme": "PPT 主题（一句话，20-50 字）",
    "detailed_requirements": "详细要求，分条列出，保留所有关键细节和具体信息",
    "style_requirements": "风格要求（如科技感、简洁、商务、学术等）",
    "page_count": 建议页数（数字，根据内容复杂度建议 10-30 页）",
    "key_points": ["关键要点 1", "关键要点 2", "关键要点 3", "..."],
    "must_include": ["必须包含的内容 1", "必须包含的内容 2", "..."],
    "mode": "theme 或 document（根据内容判断）"
}}
```

**重要提示**：
- detailed_requirements 必须完整保留文本中的所有具体要求，不要概括或省略
- 如果文本中有具体的数据、名称、术语等，必须在要求中保留
- 如果文本中有明确的章节/部分划分，必须在 key_points 中体现
- 如果文本中有明确的页数要求，使用文本中提到的页数"""
        
        try:
            # 调用 Qwen API 分析文本
            from openai import OpenAI
            
            client = OpenAI(
                api_key=self.config.get('api_key', ''),
                base_url=self.config.get('api_url', 'https://dashscope.aliyuncs.com/compatible-mode/v1'),
                timeout=120  # 增加超时时间处理长文本
            )
            
            response = client.chat.completions.create(
                model=self.config.get('models', {}).get('text', 'qwen-max'),
                messages=[
                    {"role": "system", "content": "你是一个专业的 PPT 需求分析专家，擅长从复杂文本中提取完整、准确的需求信息，不遗漏任何关键细节。"},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.3,  # 降低温度提高准确性
                max_tokens=4096   # 增加输出长度限制
            )
            
            analysis_result = response.choices[0].message.content
            logger.info(f"文本分析结果：{analysis_result[:1000]}...")
            
            # 解析 JSON（尝试多种格式）
            import re
            import json
            
            # 尝试提取 JSON 代码块
            json_match = re.search(r'```json\s*(.*?)\s*```', analysis_result, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group(1))
            else:
                # 尝试直接解析
                json_match = re.search(r'\{.*\}', analysis_result, re.DOTALL)
                if json_match:
                    analysis = json.loads(json_match.group())
                else:
                    analysis = json.loads(analysis_result)
            
            # 提取分析结果
            theme = analysis.get('theme', text[:100])
            detailed_requirements = analysis.get('detailed_requirements', '')
            style_requirements = analysis.get('style_requirements', '')
            page_count = analysis.get('page_count', 15)
            key_points = analysis.get('key_points', [])
            must_include = analysis.get('must_include', [])
            mode = analysis.get('mode', 'theme')
            
            # 合并要求为完整的 outline_requirements
            requirements_parts = []
            if detailed_requirements:
                requirements_parts.append(f"内容要求：{detailed_requirements}")
            if style_requirements:
                requirements_parts.append(f"风格要求：{style_requirements}")
            if must_include:
                requirements_parts.append(f"必须包含：{'；'.join(must_include)}")
            if key_points:
                requirements_parts.append(f"关键要点：{'；'.join(key_points)}")
            if page_count:
                requirements_parts.append(f"页数要求：{page_count} 页左右")
            
            requirements = '\n'.join(requirements_parts) if requirements_parts else ''
            
            logger.info(f"提取的主题：{theme}")
            logger.info(f"提取的详细要求：{requirements[:500] if requirements else '无'}...")
            logger.info(f"建议页数：{page_count}")
            logger.info(f"关键要点数量：{len(key_points)}")
            logger.info(f"必须包含内容数量：{len(must_include)}")
            logger.info(f"生成模式：{mode}")
            
        except Exception as e:
            logger.warning(f"文本分析失败：{e}，使用原文本作为主题")
            theme = text[:500]
            requirements = text[500:1500] if len(text) > 500 else ''
            mode = 'theme'
            page_count = 15
            key_points = []
            must_include = []
        
        # 根据分析结果调用相应的生成方法
        logger.info(f"步骤 2: 调用生成方法（mode={mode}）")
        
        if mode == 'document':
            # 如果是文档类型，保存为临时文件后处理
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write(text)
                temp_file = f.name
            
            try:
                result = self.generate_from_document(temp_file, requirements)
            finally:
                os.unlink(temp_file)
        else:
            # 默认使用主题生成，传入详细要求
            result = self.generate_from_theme(theme, requirements)
        
        # 添加分析结果到返回
        result['analysis'] = {
            'theme': theme,
            'detailed_requirements': detailed_requirements,
            'style_requirements': style_requirements,
            'requirements': requirements,
            'mode': mode,
            'page_count': page_count,
            'key_points': key_points,
            'must_include': must_include,
            'original_length': len(text),
            'text_segments': len(text_segments)
        }
        
        return result
    
    def generate_from_theme(self, prompt: str, requirements: str = None) -> dict:
        """
        根据主题生成 PPT
        
        注意：banana-slides API 使用蛇形命名（creation_type, idea_prompt）
        
        Args:
            prompt: 主题/想法
            requirements: 额外要求（包含详细内容要求、风格要求、必须包含内容等）
             
        Returns:
            生成结果
        """
        logger.info(f"开始从主题生成 PPT：{prompt}")
        if requirements:
            logger.info(f"详细要求：{requirements[:1000]}...")
            logger.info(f"要求长度：{len(requirements)} 字符")
        
        # 1. 创建项目
        logger.info("步骤 1: 创建项目")
        project_data = {
            'idea_prompt': prompt,
            'creation_type': 'idea',
        }
        if requirements:
            project_data['outline_requirements'] = requirements
            # 提取风格描述用于图片生成
            style_desc = ''
            if '风格要求：' in requirements:
                style_start = requirements.find('风格要求：') + len('风格要求：')
                style_end = requirements.find('\n', style_start)
                if style_end == -1:
                    style_end = len(requirements)
                style_desc = requirements[style_start:style_end].strip()
            
            if style_desc:
                project_data['template_style'] = style_desc
                logger.info(f"提取风格描述：{style_desc}")
            logger.info(f"已设置 outline_requirements：{len(requirements)} 字符")
        else:
            logger.warning("未提供 outline_requirements，PPT 内容可能不符合预期")
        
        logger.info(f"调用 banana-slides API: POST /api/projects")
        logger.debug(f"project_data: {json.dumps(project_data, ensure_ascii=False)[:500]}...")
        
        project = self._call_banana_api('/api/projects', 'POST', project_data)
        project_id = project.get('project_id') or project.get('id')
        if not project_id:
            raise RuntimeError(f"创建项目失败，未返回 project_id: {project}")
        logger.info(f"项目创建成功，ID: {project_id}")
        
        # 2. 生成大纲（触发后台任务）
        logger.info("步骤 2: 生成大纲")
        outline_task = self._call_banana_api(f'/api/projects/{project_id}/generate/outline', 'POST', {})
        task_id = outline_task.get('task_id')
        if task_id:
            logger.info(f"大纲生成任务已提交，Task ID: {task_id}")
            self._wait_for_task(project_id, task_id)
        
        # 3. 获取项目（包含大纲结果）
        project = self._call_banana_api(f'/api/projects/{project_id}', 'GET')
        
        # 4. 生成页面描述（触发后台任务）
        logger.info("步骤 3: 生成页面描述")
        desc_task = self._call_banana_api(f'/api/projects/{project_id}/generate/descriptions', 'POST', {})
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
        image_paths = self._generate_images(project_id, pages, requirements)
        
        if not image_paths:
            logger.warning("没有生成任何图片，跳过 PPTX 导出")
            logger.info("请检查 banana-slides 是否正确生成了页面描述")
            return {
                'success': False,
                'project_id': project_id,
                'message': '没有生成图片，无法导出 PPTX',
                'pages': len(pages),
            }
        
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
            requirements: 额外要求（包含详细内容要求、风格要求等）
             
        Returns:
            生成结果
        """
        logger.info(f"开始从文档生成 PPT：{file_path}")
        if requirements:
            logger.info(f"详细要求：{requirements[:500]}...")
        
        # 1. 上传文件到 /api/reference-files/upload
        logger.info("步骤 1: 上传文件")
        api_base = self.config.get('banana_slides', {}).get('api_base', 'http://localhost:15280')
        upload_url = f"{api_base}/api/reference-files/upload"
        
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
            logger.info(f"已设置 outline_requirements：{len(requirements)} 字符")
        else:
            logger.warning("未提供 outline_requirements，PPT 内容可能不符合预期")
        
        logger.info(f"调用 banana-slides API: POST /api/projects")
        logger.debug(f"project_data: {json.dumps(project_data, ensure_ascii=False)[:500]}...")
        
        project = self._call_banana_api('/api/projects', 'POST', project_data)
        project_id = project.get('project_id') or project.get('id')
        
        if not project_id:
            raise RuntimeError(f"创建项目失败：{project}")
        
        # 3. 后续步骤同 theme 模式，传入 requirements
        return self._continue_generation(project_id, requirements)
    
    def refresh_ppt(self, file_path: str, requirements: str = None) -> dict:
        """
        翻新已有 PPT
        
        Args:
            file_path: PPT 文件路径
            requirements: 翻新要求（包含详细风格要求、必须保留的内容等）
             
        Returns:
            生成结果
        """
        logger.info(f"开始翻新 PPT：{file_path}")
        if requirements:
            logger.info(f"翻新要求：{requirements[:500]}...")
        
        # 1. 上传文件到 /api/reference-files/upload
        logger.info("步骤 1: 上传文件")
        api_base = self.config.get('banana_slides', {}).get('api_base', 'http://localhost:15280')
        upload_url = f"{api_base}/api/reference-files/upload"
        
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
            logger.info(f"已设置 outline_requirements：{len(requirements)} 字符")
        else:
            logger.warning("未提供 outline_requirements，PPT 翻新可能不符合预期")
        
        logger.info(f"调用 banana-slides API: POST /api/projects")
        logger.debug(f"project_data: {json.dumps(project_data, ensure_ascii=False)[:500]}...")
        
        project = self._call_banana_api('/api/projects', 'POST', project_data)
        project_id = project.get('project_id') or project.get('id')
        
        if not project_id:
            raise RuntimeError(f"创建项目失败：{project}")
        
        # 3. 后续步骤同 theme 模式，传入 requirements
        return self._continue_generation(project_id, requirements)
    
    def _continue_generation(self, project_id: int, requirements: str = None) -> dict:
        """继续生成流程（等待任务、生成描述、配图、导出）
        
        Args:
            project_id: 项目 ID
            requirements: 额外要求（包含风格要求）
        """
        # 1. 生成大纲（触发后台任务）
        logger.info("步骤 1: 生成大纲")
        outline_task = self._call_banana_api(f'/api/projects/{project_id}/generate/outline', 'POST', {})
        task_id = outline_task.get('task_id')
        if task_id:
            logger.info(f"大纲生成任务已提交，Task ID: {task_id}")
            self._wait_for_task(project_id, task_id)
        
        # 2. 获取项目（包含大纲结果）
        project = self._call_banana_api(f'/api/projects/{project_id}', 'GET')
        
        # 3. 生成页面描述（触发后台任务）
        logger.info("步骤 2: 生成页面描述")
        desc_task = self._call_banana_api(f'/api/projects/{project_id}/generate/descriptions', 'POST', {})
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
        image_paths = self._generate_images(project_id, pages, requirements)
        
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
    if not result.get('success'):
        print("\n" + "=" * 60)
        print("⚠️  PPT 生成未完成")
        print("=" * 60)
        print(f"项目 ID: {result.get('project_id', 'N/A')}")
        print(f"消息：{result.get('message', 'Unknown error')}")
        print(f"页数：{result.get('pages', 0)}")
        print("=" * 60)
        return
    
    print("\n" + "=" * 60)
    print("✅ PPT 生成完成！")
    print("=" * 60)
    print(f"📁 PPT 文件：{result['pptx_path']}")
    print(f"🖼️ 配图数量：{len(result['image_paths'])} 张")
    print(f"📄 页数：{result['page_count']} 页")
    print(f"📋 元数据：{result['metadata_path']}")
    
    # 显示分析结果（如果是 auto 模式）
    if 'analysis' in result:
        print("\n📊 智能分析结果:")
        analysis = result['analysis']
        print(f"   主题：{analysis.get('theme', 'N/A')}")
        print(f"   模式：{analysis.get('mode', 'N/A')}")
        print(f"   原文长度：{analysis.get('original_length', 0)} 字符")
        if analysis.get('requirements'):
            print(f"   要求：{analysis['requirements'][:100]}...")
    
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
  
  # 根据大段文本自动生成（智能分析）
  python ppt_generator.py --mode auto --text "我需要做一个关于...的 PPT，要求包括..."
  
  # 从文件读取大段文本
  python ppt_generator.py --mode auto --text-file requirements.txt
        """
    )
    
    parser.add_argument(
        '--mode', '-m',
        required=True,
        help='生成模式',
        choices=['theme', 'document', 'refresh', 'auto']
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
        '--text', '-t',
        help='大段文本内容（auto 模式使用）'
    )
    parser.add_argument(
        '--text-file',
        help='包含大段文本的文件路径（auto 模式使用）'
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
    
    if args.mode == 'auto' and not args.text and not args.text_file:
        logger.error("auto 模式需要指定 --text 或 --text-file")
        sys.exit(1)
    
    if args.file and not os.path.exists(args.file):
        logger.error(f"文件不存在：{args.file}")
        sys.exit(1)
    
    if args.text_file and not os.path.exists(args.text_file):
        logger.error(f"文本文件不存在：{args.text_file}")
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
        elif args.mode == 'auto':
            # 从文件或命令行获取文本
            if args.text_file:
                with open(args.text_file, 'r', encoding='utf-8') as f:
                    text = f.read()
                logger.info(f"从文件读取文本：{args.text_file} ({len(text)} 字符)")
            else:
                text = args.text
                logger.info(f"使用命令行文本 ({len(text)} 字符)")
            
            result = generator.generate_from_text(text)
        
        print_result(result)
        
    except Exception as e:
        logger.error(f"生成失败：{e}", exc_info=True)
        print(f"\n❌ 生成失败：{e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
