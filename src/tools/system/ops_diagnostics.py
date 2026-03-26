"""
运维诊断与修复模块

本模块负责运维诊断和自动修复功能，包括：
1. 日志查看与分析
2. 容器健康状态检查
3. 网络连通性诊断
4. 资源使用监控
5. 服务自动修复

主要功能：
    - 获取容器日志并支持过滤
    - 检查容器健康状态
    - 诊断网络连通性问题
    - 监控系统资源使用
    - 自动重启故障容器
    - 服务回滚操作

依赖模块：
    - docker_ops: Docker 操作
    - cluster: 集群管理
    - remote_ops: 远程操作
"""

import subprocess
import re
import json
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.core.logger import logger
from src.core.config import CONFIG_DIR
from src.tools.cluster.cluster import ClusterManager
from src.tools.cluster.remote_ops import RemoteExecutor
from src.tools.registry import registry

console = Console()


@dataclass
class DiagnosticResult:
    """诊断结果数据类"""
    success: bool
    status: str  # healthy, unhealthy, warning, error
    message: str
    details: Optional[Dict] = None
    recommendations: Optional[List[str]] = None


# ============ 日志查看工具 ============

@registry.register
def get_container_logs(container_name: str, tail: int = 50) -> str:
    """
    获取容器日志
    
    参数:
        container_name: 容器名称或ID
        tail: 显示的日志行数（默认50行）
    
    返回:
        日志内容字符串
    """
    try:
        cmd = ["docker", "logs", "--tail", str(tail), container_name]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            logs = result.stdout or result.stderr
            if not logs:
                return f"容器 {container_name} 暂无日志输出"
            return logs
        else:
            return f"获取日志失败: {result.stderr}"
            
    except subprocess.TimeoutExpired:
        return f"获取日志超时: 容器 {container_name} 可能正在持续输出大量日志"
    except Exception as e:
        return f"获取日志异常: {str(e)}"


def analyze_logs(logs: str, keywords: Optional[List[str]] = None) -> Dict:
    """
    分析日志内容，提取关键信息
    
    参数:
        logs: 日志内容
        keywords: 需要关注的关键词列表
    
    返回:
        分析结果字典，包含错误统计、警告统计等
    """
    result = {
        "total_lines": 0,
        "error_count": 0,
        "warning_count": 0,
        "errors": [],
        "warnings": [],
        "keyword_matches": {}
    }
    
    if not logs:
        return result
    
    lines = logs.strip().split("\n")
    result["total_lines"] = len(lines)
    
    # 错误模式
    error_patterns = [
        r"(?i)error",
        r"(?i)exception",
        r"(?i)failed",
        r"(?i)fatal",
        r"(?i)critical"
    ]
    
    # 警告模式
    warning_patterns = [
        r"(?i)warn",
        r"(?i)warning",
        r"(?i)deprecated"
    ]
    
    for line in lines:
        # 检查错误
        for pattern in error_patterns:
            if re.search(pattern, line):
                result["error_count"] += 1
                if len(result["errors"]) < 20:  # 最多保存20条错误
                    result["errors"].append(line[:500])
                break
        
        # 检查警告
        for pattern in warning_patterns:
            if re.search(pattern, line):
                result["warning_count"] += 1
                if len(result["warnings"]) < 20:
                    result["warnings"].append(line[:500])
                break
        
        # 检查关键词
        if keywords:
            for keyword in keywords:
                if keyword.lower() in line.lower():
                    if keyword not in result["keyword_matches"]:
                        result["keyword_matches"][keyword] = []
                    if len(result["keyword_matches"][keyword]) < 10:
                        result["keyword_matches"][keyword].append(line[:500])
    
    return result


# ============ 容器状态检查工具 ============

def check_container_status(container_name: str, host: Optional[str] = None) -> DiagnosticResult:
    """
    检查容器状态
    
    参数:
        container_name: 容器名称或ID
        host: 远程主机地址（可选）
    
    返回:
        DiagnosticResult 对象
    """
    try:
        cmd = ["docker", "inspect", "--format", 
               "{{.State.Status}}|{{.State.Running}}|{{.State.Health.Status}}|{{.State.ExitCode}}",
               container_name]
        
        if host:
            output = RemoteExecutor.execute_command(host, " ".join(cmd))
        else:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            output = result.stdout if result.returncode == 0 else result.stderr
        
        if "No such object" in output or "Error" in output:
            return DiagnosticResult(
                success=False,
                status="error",
                message=f"容器 {container_name} 不存在",
                recommendations=["请检查容器名称是否正确", "使用 docker ps -a 查看所有容器"]
            )
        
        parts = output.strip().split("|")
        if len(parts) >= 4:
            status, running, health, exit_code = parts
            
            details = {
                "status": status,
                "running": running == "true",
                "health": health if health and health != "<nil>" else "none",
                "exit_code": int(exit_code) if exit_code.isdigit() else 0
            }
            
            if status == "running" and (health == "healthy" or health == "none"):
                return DiagnosticResult(
                    success=True,
                    status="healthy",
                    message=f"容器 {container_name} 运行正常",
                    details=details
                )
            elif status == "running" and health == "unhealthy":
                return DiagnosticResult(
                    success=False,
                    status="unhealthy",
                    message=f"容器 {container_name} 运行中但健康检查失败",
                    details=details,
                    recommendations=["查看容器日志排查问题", "检查健康检查配置"]
                )
            elif status == "exited":
                return DiagnosticResult(
                    success=False,
                    status="error",
                    message=f"容器 {container_name} 已退出，退出码: {exit_code}",
                    details=details,
                    recommendations=["查看容器日志了解退出原因", "尝试重启容器"]
                )
            else:
                return DiagnosticResult(
                    success=False,
                    status=status,
                    message=f"容器 {container_name} 状态: {status}",
                    details=details
                )
        else:
            return DiagnosticResult(
                success=False,
                status="error",
                message=f"无法解析容器状态: {output}"
            )
            
    except subprocess.TimeoutExpired:
        return DiagnosticResult(
            success=False,
            status="error",
            message=f"检查容器状态超时"
        )
    except Exception as e:
        return DiagnosticResult(
            success=False,
            status="error",
            message=f"检查容器状态异常: {str(e)}"
        )


def list_containers(all: bool = False, host: Optional[str] = None) -> List[Dict]:
    """
    列出容器列表
    
    参数:
        all: 是否显示所有容器（包括停止的）
        host: 远程主机地址
    
    返回:
        容器信息列表
    """
    try:
        cmd = ["docker", "ps", "--format", "json"]
        if all:
            cmd.append("-a")
        
        if host:
            output = RemoteExecutor.execute_command(host, " ".join(cmd))
        else:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            output = result.stdout
        
        containers = []
        for line in output.strip().split("\n"):
            if line:
                try:
                    container = json.loads(line)
                    containers.append(container)
                except json.JSONDecodeError:
                    continue
        
        return containers
        
    except Exception as e:
        logger.error(f"列出容器失败: {e}")
        return []


def get_container_stats(container_name: Optional[str] = None, host: Optional[str] = None) -> str:
    """
    获取容器资源使用统计
    
    参数:
        container_name: 容器名称（可选，不指定则显示所有）
        host: 远程主机地址
    
    返回:
        资源使用统计字符串
    """
    try:
        cmd = ["docker", "stats", "--no-stream", "--format", 
               "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}"]
        
        if container_name:
            cmd.append(container_name)
        
        if host:
            return RemoteExecutor.execute_command(host, " ".join(cmd))
        else:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return result.stdout if result.returncode == 0 else result.stderr
            
    except Exception as e:
        return f"获取资源统计失败: {str(e)}"


# ============ 网络诊断工具 ============

def check_port_status(port: int, host: str = "localhost") -> DiagnosticResult:
    """
    检查端口占用状态
    
    参数:
        port: 端口号
        host: 主机地址（默认localhost）
    
    返回:
        DiagnosticResult 对象
    """
    try:
        # 使用 netstat 或 ss 检查端口
        cmd = f"ss -tlnp | grep ':{port} ' || netstat -tlnp | grep ':{port} '"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        
        if result.stdout:
            # 端口被占用
            lines = result.stdout.strip().split("\n")
            processes = []
            for line in lines:
                parts = line.split()
                if len(parts) >= 7:
                    processes.append({
                        "protocol": parts[0],
                        "local_address": parts[3],
                        "process": parts[6] if len(parts) > 6 else "unknown"
                    })
            
            return DiagnosticResult(
                success=True,
                status="warning",
                message=f"端口 {port} 已被占用",
                details={"port": port, "processes": processes},
                recommendations=["更换端口", "停止占用端口的进程"]
            )
        else:
            return DiagnosticResult(
                success=True,
                status="healthy",
                message=f"端口 {port} 可用",
                details={"port": port}
            )
            
    except Exception as e:
        return DiagnosticResult(
            success=False,
            status="error",
            message=f"检查端口失败: {str(e)}"
        )


def check_network_connectivity(
    target: str,
    port: Optional[int] = None,
    timeout: int = 5
) -> DiagnosticResult:
    """
    检查网络连通性
    
    参数:
        target: 目标地址（IP或域名）
        port: 目标端口（可选）
        timeout: 超时时间（秒）
    
    返回:
        DiagnosticResult 对象
    """
    try:
        # ICMP ping 测试
        ping_cmd = ["ping", "-c", "3", "-W", str(timeout), target]
        ping_result = subprocess.run(ping_cmd, capture_output=True, text=True, timeout=timeout + 5)
        
        ping_success = ping_result.returncode == 0
        
        details = {
            "target": target,
            "ping_success": ping_success,
            "port_check": None
        }
        
        # 如果指定了端口，进行端口连通性测试
        if port:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            try:
                result = sock.connect_ex((target, port))
                details["port_check"] = {
                    "port": port,
                    "connected": result == 0
                }
            finally:
                sock.close()
        
        if ping_success and (not port or details["port_check"]["connected"]):
            return DiagnosticResult(
                success=True,
                status="healthy",
                message=f"网络连通正常: {target}" + (f":{port}" if port else ""),
                details=details
            )
        elif ping_success and port and not details["port_check"]["connected"]:
            return DiagnosticResult(
                success=False,
                status="warning",
                message=f"目标可达但端口 {port} 无法连接",
                details=details,
                recommendations=["检查目标服务是否运行", "检查防火墙规则"]
            )
        else:
            return DiagnosticResult(
                success=False,
                status="error",
                message=f"无法连接到目标: {target}",
                details=details,
                recommendations=["检查网络连接", "检查目标地址是否正确", "检查防火墙规则"]
            )
            
    except subprocess.TimeoutExpired:
        return DiagnosticResult(
            success=False,
            status="error",
            message=f"网络测试超时: {target}",
            recommendations=["检查网络连接", "增加超时时间"]
        )
    except Exception as e:
        return DiagnosticResult(
            success=False,
            status="error",
            message=f"网络测试异常: {str(e)}"
        )


def check_dns_resolution(domain: str) -> DiagnosticResult:
    """
    检查 DNS 解析
    
    参数:
        domain: 域名
    
    返回:
        DiagnosticResult 对象
    """
    try:
        import socket
        ip = socket.gethostbyname(domain)
        
        return DiagnosticResult(
            success=True,
            status="healthy",
            message=f"DNS 解析成功: {domain} -> {ip}",
            details={"domain": domain, "ip": ip}
        )
    except socket.gaierror as e:
        return DiagnosticResult(
            success=False,
            status="error",
            message=f"DNS 解析失败: {domain}",
            details={"domain": domain, "error": str(e)},
            recommendations=["检查 DNS 配置", "检查域名是否正确"]
        )
    except Exception as e:
        return DiagnosticResult(
            success=False,
            status="error",
            message=f"DNS 解析异常: {str(e)}"
        )


# ============ 系统资源监控 ============

def get_system_resources(host: Optional[str] = None) -> Dict:
    """
    获取系统资源使用情况
    
    参数:
        host: 远程主机地址
    
    返回:
        资源使用字典
    """
    resources = {
        "cpu": {},
        "memory": {},
        "disk": {},
        "load": {}
    }
    
    try:
        # CPU 使用率
        cmd = "top -bn1 | grep 'Cpu(s)' || echo 'CPU info unavailable'"
        if host:
            output = RemoteExecutor.execute_command(host, cmd)
        else:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            output = result.stdout
        
        cpu_match = re.search(r'(\d+\.?\d*)\s*id', output)
        if cpu_match:
            resources["cpu"]["idle"] = float(cpu_match.group(1))
            resources["cpu"]["used"] = 100 - float(cpu_match.group(1))
        
        # 内存使用
        cmd = "free -m | grep Mem"
        if host:
            output = RemoteExecutor.execute_command(host, cmd)
        else:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            output = result.stdout
        
        mem_parts = output.split()
        if len(mem_parts) >= 4:
            resources["memory"]["total_mb"] = int(mem_parts[1])
            resources["memory"]["used_mb"] = int(mem_parts[2])
            resources["memory"]["available_mb"] = int(mem_parts[6]) if len(mem_parts) > 6 else int(mem_parts[3])
            resources["memory"]["used_percent"] = round(int(mem_parts[2]) / int(mem_parts[1]) * 100, 1)
        
        # 磁盘使用
        cmd = "df -h / | tail -1"
        if host:
            output = RemoteExecutor.execute_command(host, cmd)
        else:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            output = result.stdout
        
        disk_parts = output.split()
        if len(disk_parts) >= 5:
            resources["disk"]["total"] = disk_parts[1]
            resources["disk"]["used"] = disk_parts[2]
            resources["disk"]["available"] = disk_parts[3]
            resources["disk"]["used_percent"] = int(disk_parts[4].replace('%', ''))
        
        # 系统负载
        cmd = "cat /proc/loadavg"
        if host:
            output = RemoteExecutor.execute_command(host, cmd)
        else:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            output = result.stdout
        
        load_parts = output.split()
        if len(load_parts) >= 3:
            resources["load"]["1min"] = float(load_parts[0])
            resources["load"]["5min"] = float(load_parts[1])
            resources["load"]["15min"] = float(load_parts[2])
        
        return resources
        
    except Exception as e:
        logger.error(f"获取系统资源失败: {e}")
        return resources


def check_disk_space(path: str = "/", threshold: int = 80, host: Optional[str] = None) -> DiagnosticResult:
    """
    检查磁盘空间
    
    参数:
        path: 检查路径
        threshold: 告警阈值（百分比）
        host: 远程主机地址
    
    返回:
        DiagnosticResult 对象
    """
    try:
        cmd = f"df -h {path} | tail -1"
        if host:
            output = RemoteExecutor.execute_command(host, cmd)
        else:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            output = result.stdout
        
        parts = output.split()
        if len(parts) >= 5:
            used_percent = int(parts[4].replace('%', ''))
            
            details = {
                "path": path,
                "total": parts[1],
                "used": parts[2],
                "available": parts[3],
                "used_percent": used_percent
            }
            
            if used_percent >= threshold:
                return DiagnosticResult(
                    success=False,
                    status="warning",
                    message=f"磁盘空间不足: {path} 已使用 {used_percent}%",
                    details=details,
                    recommendations=["清理无用文件", "扩展磁盘空间", "检查大文件占用"]
                )
            else:
                return DiagnosticResult(
                    success=True,
                    status="healthy",
                    message=f"磁盘空间充足: {path} 已使用 {used_percent}%",
                    details=details
                )
        else:
            return DiagnosticResult(
                success=False,
                status="error",
                message=f"无法获取磁盘信息: {output}"
            )
            
    except Exception as e:
        return DiagnosticResult(
            success=False,
            status="error",
            message=f"检查磁盘空间失败: {str(e)}"
        )


# ============ 自动修复工具 ============

def restart_container(container_name: str, host: Optional[str] = None) -> str:
    """
    重启容器
    
    参数:
        container_name: 容器名称或ID
        host: 远程主机地址
    
    返回:
        操作结果字符串
    """
    try:
        cmd = ["docker", "restart", container_name]
        
        if host:
            output = RemoteExecutor.execute_command(host, " ".join(cmd))
            return f"远程主机 {host} 上容器 {container_name} 重启完成: {output}"
        else:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                return f"容器 {container_name} 重启成功"
            else:
                return f"容器 {container_name} 重启失败: {result.stderr}"
                
    except subprocess.TimeoutExpired:
        return f"重启容器超时: {container_name}"
    except Exception as e:
        return f"重启容器异常: {str(e)}"


def stop_container(container_name: str, host: Optional[str] = None) -> str:
    """
    停止容器
    
    参数:
        container_name: 容器名称或ID
        host: 远程主机地址
    
    返回:
        操作结果字符串
    """
    try:
        cmd = ["docker", "stop", container_name]
        
        if host:
            output = RemoteExecutor.execute_command(host, " ".join(cmd))
            return f"远程主机 {host} 上容器 {container_name} 已停止"
        else:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                return f"容器 {container_name} 已停止"
            else:
                return f"停止容器失败: {result.stderr}"
                
    except Exception as e:
        return f"停止容器异常: {str(e)}"


def rollback_service(project_name: str, host: Optional[str] = None) -> str:
    """
    回滚服务（停止并删除容器）
    
    参数:
        project_name: 项目名称
        host: 远程主机地址
    
    返回:
        操作结果字符串
    """
    try:
        from src.tools.docker.docker_ops import DEPLOY_DIR
        
        project_dir = DEPLOY_DIR / project_name
        compose_file = project_dir / "docker-compose.yml"
        
        if not compose_file.exists():
            return f"项目 {project_name} 不存在，无法回滚"
        
        cmd = ["docker", "compose", "-f", str(compose_file), "down"]
        
        if host:
            output = RemoteExecutor.execute_command(host, " ".join(cmd))
            return f"远程主机 {host} 上服务 {project_name} 已回滚"
        else:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                return f"服务 {project_name} 已回滚\n{result.stdout}"
            else:
                return f"服务回滚失败: {result.stderr}"
                
    except Exception as e:
        return f"服务回滚异常: {str(e)}"


def diagnose_service(service_name: str, host: Optional[str] = None) -> Dict:
    """
    综合诊断服务
    
    执行多项检查，生成诊断报告
    
    参数:
        service_name: 服务名称（容器名或项目名）
        host: 远程主机地址
    
    返回:
        诊断报告字典
    """
    report = {
        "service": service_name,
        "host": host or "localhost",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "checks": [],
        "overall_status": "unknown",
        "recommendations": []
    }
    
    # 1. 检查容器状态
    status_result = check_container_status(service_name, host)
    report["checks"].append({
        "name": "容器状态",
        "status": status_result.status,
        "message": status_result.message,
        "details": status_result.details
    })
    
    if status_result.recommendations:
        report["recommendations"].extend(status_result.recommendations)
    
    # 2. 获取容器日志（最近50行）
    logs = get_container_logs(service_name, tail=50)
    log_analysis = analyze_logs(logs)
    report["checks"].append({
        "name": "日志分析",
        "status": "warning" if log_analysis["error_count"] > 0 else "healthy",
        "message": f"发现 {log_analysis['error_count']} 个错误, {log_analysis['warning_count']} 个警告",
        "details": log_analysis
    })
    
    # 3. 检查资源使用
    stats = get_container_stats(service_name, host)
    report["checks"].append({
        "name": "资源使用",
        "status": "healthy",
        "message": "资源使用统计",
        "details": {"stats": stats}
    })
    
    # 计算整体状态
    statuses = [c["status"] for c in report["checks"]]
    if "error" in statuses:
        report["overall_status"] = "error"
    elif "unhealthy" in statuses or "warning" in statuses:
        report["overall_status"] = "warning"
    else:
        report["overall_status"] = "healthy"
    
    # 添加通用建议
    if report["overall_status"] == "error":
        report["recommendations"].append("建议查看详细日志定位问题")
        report["recommendations"].append("可以尝试重启容器")
    elif report["overall_status"] == "warning":
        report["recommendations"].append("建议持续监控服务状态")
    
    return report


def format_diagnostic_report(report: Dict) -> str:
    """
    格式化诊断报告为可读字符串
    
    参数:
        report: 诊断报告字典
    
    返回:
        格式化的报告字符串
    """
    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"服务诊断报告: {report['service']}")
    lines.append(f"主机: {report['host']}")
    lines.append(f"时间: {report['timestamp']}")
    lines.append(f"整体状态: {report['overall_status'].upper()}")
    lines.append(f"{'='*60}")
    
    for check in report["checks"]:
        lines.append(f"\n[{check['name']}]")
        lines.append(f"  状态: {check['status']}")
        lines.append(f"  信息: {check['message']}")
    
    if report["recommendations"]:
        lines.append(f"\n[建议操作]")
        for rec in report["recommendations"]:
            lines.append(f"  - {rec}")
    
    lines.append(f"\n{'='*60}")
    
    return "\n".join(lines)
