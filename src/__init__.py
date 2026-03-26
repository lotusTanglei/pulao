"""
Pulao - AI 智能运维助手

本项目是一个基于 AI 的智能运维工具，旨在帮助运维人员通过自然语言完成
Docker 中间件部署和系统日常运维任务。

主要功能：
    - 使用自然语言描述部署需求，AI 自动生成 Docker Compose 配置
    - 支持单机和集群部署模式
    - 支持多 AI 提供商（DeepSeek、OpenAI、Azure 等）
    - 内置官方验证的 Docker 模板库
    - 支持 SSH 远程节点管理
    - 交互式 CLI 界面

版本：1.0.0
作者：Pulao Team
"""

# 定义项目版本号，供其他模块导入使用
__version__ = "1.0.0"
