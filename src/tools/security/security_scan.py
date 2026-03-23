"""
安全扫描模块

本模块负责安全相关的扫描和检查功能，包括：
1. Docker 镜像漏洞扫描（集成 Trivy）
2. 安全配置检查
3. 敏感信息检测
4. 安全基线检查

主要功能：
    - 扫描镜像漏洞
    - 检查 Docker 安全配置
    - 检测敏感信息泄露
    - 生成安全报告

依赖：
    - Trivy: 镜像漏洞扫描工具（可选，如未安装则提示安装）
    - Docker: 容器运行时
"""

import subprocess
import re
import json
import os
from typing import Dict, List, Optional
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.core.logger import logger
from src.core.config import CONFIG_DIR

console = Console()


@dataclass
class Vulnerability:
    """漏洞信息数据类"""
    id: str
    severity: str
    package: str
    installed_version: str
    fixed_version: str
    description: str


@dataclass
class SecurityScanResult:
    """安全扫描结果数据类"""
    success: bool
    image: str
    total_vulnerabilities: int
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    unknown: int = 0
    vulnerabilities: List[Vulnerability] = None
    raw_output: str = ""
    error: str = ""


# ============ Trivy 镜像扫描 ============

def check_trivy_installed() -> bool:
    """
    检查 Trivy 是否已安装
    
    返回:
        True 如果已安装
    """
    try:
        result = subprocess.run(
            ["trivy", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def install_trivy_guide() -> str:
    """
    返回 Trivy 安装指南
    
    返回:
        安装指南字符串
    """
    guide = """
Trivy 安装指南:

macOS:
  brew install trivy

Linux (Ubuntu/Debian):
  sudo apt-get install wget apt-transport-https gnupg lsb-release
  wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | sudo apt-key add -
  echo deb https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main | sudo tee -a /etc/apt/sources.list.d/trivy.list
  sudo apt-get update
  sudo apt-get install trivy

Linux (RHEL/CentOS):
  sudo yum install -y yum-utils
  sudo yum-config-manager --add-repo https://aquasecurity.github.io/trivy-repo/rpm/releases/$releasever/$basearch/
  sudo yum -y update
  sudo yum -y install trivy

Docker:
  docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:latest image <image_name>

详细文档: https://aquasecurity.github.io/trivy/latest/getting-started/installation/
"""
    return guide


def scan_image_with_trivy(
    image_name: str,
    severity: str = "CRITICAL,HIGH,MEDIUM",
    output_format: str = "json"
) -> SecurityScanResult:
    """
    使用 Trivy 扫描镜像漏洞
    
    参数:
        image_name: 镜像名称（如 nginx:latest）
        severity: 扫描的严重级别（默认 CRITICAL,HIGH,MEDIUM）
        output_format: 输出格式（json/table）
    
    返回:
        SecurityScanResult 对象
    """
    if not check_trivy_installed():
        return SecurityScanResult(
            success=False,
            image=image_name,
            total_vulnerabilities=0,
            error="Trivy 未安装。请先安装 Trivy:\n" + install_trivy_guide()
        )
    
    try:
        cmd = [
            "trivy", "image",
            "--quiet",
            "--severity", severity,
            "--format", output_format,
            image_name
        ]
        
        logger.info(f"Scanning image: {image_name}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5分钟超时
        )
        
        if result.returncode != 0 and "no such host" not in result.stderr.lower():
            return SecurityScanResult(
                success=False,
                image=image_name,
                total_vulnerabilities=0,
                error=f"扫描失败: {result.stderr}"
            )
        
        # 解析 JSON 输出
        if output_format == "json":
            return parse_trivy_json_output(image_name, result.stdout)
        else:
            return SecurityScanResult(
                success=True,
                image=image_name,
                total_vulnerabilities=0,
                raw_output=result.stdout
            )
            
    except subprocess.TimeoutExpired:
        return SecurityScanResult(
            success=False,
            image=image_name,
            total_vulnerabilities=0,
            error="扫描超时，镜像可能过大或网络问题"
        )
    except Exception as e:
        return SecurityScanResult(
            success=False,
            image=image_name,
            total_vulnerabilities=0,
            error=f"扫描异常: {str(e)}"
        )


def parse_trivy_json_output(image_name: str, json_output: str) -> SecurityScanResult:
    """
    解析 Trivy JSON 输出
    
    参数:
        image_name: 镜像名称
        json_output: Trivy JSON 输出
    
    返回:
        SecurityScanResult 对象
    """
    try:
        data = json.loads(json_output)
        
        vulnerabilities = []
        severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNKNOWN": 0}
        
        # Trivy 输出结构: [{"Results": [{"Vulnerabilities": [...]}]}]
        results = data if isinstance(data, list) else [data]
        
        for result in results:
            for r in result.get("Results", []):
                for vuln in r.get("Vulnerabilities", []):
                    severity = vuln.get("Severity", "UNKNOWN").upper()
                    if severity in severity_counts:
                        severity_counts[severity] += 1
                    
                    vulnerabilities.append(Vulnerability(
                        id=vuln.get("VulnerabilityID", "N/A"),
                        severity=severity,
                        package=vuln.get("PkgName", "N/A"),
                        installed_version=vuln.get("InstalledVersion", "N/A"),
                        fixed_version=vuln.get("FixedVersion", "N/A"),
                        description=vuln.get("Description", "N/A")[:200]
                    ))
        
        total = sum(severity_counts.values())
        
        return SecurityScanResult(
            success=True,
            image=image_name,
            total_vulnerabilities=total,
            critical=severity_counts["CRITICAL"],
            high=severity_counts["HIGH"],
            medium=severity_counts["MEDIUM"],
            low=severity_counts["LOW"],
            unknown=severity_counts["UNKNOWN"],
            vulnerabilities=vulnerabilities,
            raw_output=json_output
        )
        
    except json.JSONDecodeError as e:
        return SecurityScanResult(
            success=False,
            image=image_name,
            total_vulnerabilities=0,
            error=f"解析 Trivy 输出失败: {str(e)}"
        )


def format_scan_result(result: SecurityScanResult, show_details: bool = False) -> str:
    """
    格式化扫描结果为可读字符串
    
    参数:
        result: 扫描结果对象
        show_details: 是否显示详细漏洞信息
    
    返回:
        格式化的结果字符串
    """
    if not result.success:
        return f"镜像扫描失败: {result.error}"
    
    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"镜像安全扫描报告: {result.image}")
    lines.append(f"{'='*60}")
    
    lines.append(f"\n漏洞统计:")
    lines.append(f"  总计: {result.total_vulnerabilities}")
    if result.critical > 0:
        lines.append(f"  严重 (CRITICAL): {result.critical}")
    if result.high > 0:
        lines.append(f"  高危 (HIGH): {result.high}")
    if result.medium > 0:
        lines.append(f"  中危 (MEDIUM): {result.medium}")
    if result.low > 0:
        lines.append(f"  低危 (LOW): {result.low}")
    if result.unknown > 0:
        lines.append(f"  未知 (UNKNOWN): {result.unknown}")
    
    if show_details and result.vulnerabilities:
        lines.append(f"\n漏洞详情 (前20个):")
        for i, vuln in enumerate(result.vulnerabilities[:20], 1):
            lines.append(f"\n  [{i}] {vuln.id} ({vuln.severity})")
            lines.append(f"      包: {vuln.package}")
            lines.append(f"      已安装: {vuln.installed_version}")
            if vuln.fixed_version and vuln.fixed_version != "N/A":
                lines.append(f"      修复版本: {vuln.fixed_version}")
            lines.append(f"      描述: {vuln.description[:100]}...")
    
    # 安全建议
    lines.append(f"\n安全建议:")
    if result.critical > 0 or result.high > 0:
        lines.append("  [!] 发现高危漏洞，建议立即更新镜像或使用更安全的版本")
    if result.medium > 0:
        lines.append("  [*] 存在中危漏洞，建议尽快修复")
    if result.total_vulnerabilities == 0:
        lines.append("  [OK] 未发现漏洞，镜像安全")
    
    lines.append(f"\n{'='*60}")
    
    return "\n".join(lines)


# ============ Docker 安全配置检查 ============

def check_docker_security_config() -> Dict:
    """
    检查 Docker 安全配置
    
    返回:
        安全配置检查结果字典
    """
    results = {
        "passed": [],
        "warnings": [],
        "errors": []
    }
    
    try:
        # 1. 检查 Docker 版本
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            results["passed"].append({
                "item": "Docker 版本",
                "message": result.stdout.strip()
            })
        else:
            results["errors"].append({
                "item": "Docker 版本",
                "message": "无法获取 Docker 版本"
            })
        
        # 2. 检查 Docker 守护进程配置
        daemon_config_path = "/etc/docker/daemon.json"
        if os.path.exists(daemon_config_path):
            try:
                with open(daemon_config_path, 'r') as f:
                    config = json.load(f)
                
                # 检查是否启用 live-restore
                if config.get("live-restore", False):
                    results["passed"].append({
                        "item": "live-restore",
                        "message": "已启用 live-restore，容器在守护进程重启时保持运行"
                    })
                else:
                    results["warnings"].append({
                        "item": "live-restore",
                        "message": "建议启用 live-restore 以提高可用性"
                    })
                
                # 检查日志配置
                if "log-opts" in config:
                    results["passed"].append({
                        "item": "日志配置",
                        "message": "已配置日志选项"
                    })
                else:
                    results["warnings"].append({
                        "item": "日志配置",
                        "message": "建议配置日志大小限制以防止磁盘占满"
                    })
                
                # 检查是否禁用 inter-container communication
                if config.get("icc", True) == False:
                    results["passed"].append({
                        "item": "容器间通信",
                        "message": "已禁用默认容器间通信，提高安全性"
                    })
                else:
                    results["warnings"].append({
                        "item": "容器间通信",
                        "message": "建议禁用默认容器间通信 (icc: false)"
                    })
                    
            except json.JSONDecodeError:
                results["warnings"].append({
                    "item": "daemon.json",
                    "message": "Docker 守护进程配置文件格式错误"
                })
        
        # 3. 检查是否使用 rootless 模式
        result = subprocess.run(
            ["docker", "context", "ls"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if "rootless" in result.stdout:
            results["passed"].append({
                "item": "Rootless 模式",
                "message": "使用 rootless 模式运行 Docker，安全性更高"
            })
        else:
            results["warnings"].append({
                "item": "Rootless 模式",
                "message": "建议考虑使用 rootless 模式以提高安全性"
            })
        
        # 4. 检查 Docker 用户组
        result = subprocess.run(
            ["groups"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if "docker" in result.stdout:
            results["warnings"].append({
                "item": "Docker 用户组",
                "message": "当前用户在 docker 用户组中，具有 root 等效权限，注意安全"
            })
        
        # 5. 检查是否有容器以特权模式运行
        result = subprocess.run(
            ["docker", "ps", "--quiet", "--filter", "privileged=true"],
            capture_output=True,
            text=True,
            timeout=10
        )
        privileged_containers = result.stdout.strip().split('\n')
        privileged_containers = [c for c in privileged_containers if c]
        
        if privileged_containers:
            results["warnings"].append({
                "item": "特权容器",
                "message": f"发现 {len(privileged_containers)} 个特权容器运行中"
            })
        else:
            results["passed"].append({
                "item": "特权容器",
                "message": "没有特权容器运行"
            })
        
    except Exception as e:
        results["errors"].append({
            "item": "检查异常",
            "message": str(e)
        })
    
    return results


def format_security_config_result(results: Dict) -> str:
    """
    格式化安全配置检查结果
    
    参数:
        results: 检查结果字典
    
    返回:
        格式化的结果字符串
    """
    lines = []
    lines.append(f"\n{'='*60}")
    lines.append("Docker 安全配置检查报告")
    lines.append(f"{'='*60}")
    
    if results["passed"]:
        lines.append(f"\n[通过] ({len(results['passed'])} 项):")
        for item in results["passed"]:
            lines.append(f"  ✓ {item['item']}: {item['message']}")
    
    if results["warnings"]:
        lines.append(f"\n[警告] ({len(results['warnings'])} 项):")
        for item in results["warnings"]:
            lines.append(f"  ! {item['item']}: {item['message']}")
    
    if results["errors"]:
        lines.append(f"\n[错误] ({len(results['errors'])} 项):")
        for item in results["errors"]:
            lines.append(f"  ✗ {item['item']}: {item['message']}")
    
    lines.append(f"\n{'='*60}")
    
    return "\n".join(lines)


# ============ 敏感信息检测 ============

SENSITIVE_PATTERNS = [
    (r'(?i)(password|passwd|pwd)\s*[=:]\s*[\'"]?([^\s\'"]+)', '密码'),
    (r'(?i)(api[_-]?key)\s*[=:]\s*[\'"]?([^\s\'"]+)', 'API Key'),
    (r'(?i)(secret[_-]?key)\s*[=:]\s*[\'"]?([^\s\'"]+)', 'Secret Key'),
    (r'(?i)(access[_-]?key)\s*[=:]\s*[\'"]?([^\s\'"]+)', 'Access Key'),
    (r'(?i)(token)\s*[=:]\s*[\'"]?([^\s\'"]+)', 'Token'),
    (r'sk-[a-zA-Z0-9]{20,}', 'OpenAI API Key'),
    (r'AKIA[0-9A-Z]{16}', 'AWS Access Key'),
    (r'(?i)(mysql|postgres|mongodb)://[^\s]+:[^\s]+@', '数据库连接字符串'),
    (r'-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----', '私钥'),
]


def detect_sensitive_info(content: str) -> List[Dict]:
    """
    检测文本中的敏感信息
    
    参数:
        content: 要检测的文本内容
    
    返回:
        检测到的敏感信息列表
    """
    findings = []
    
    for pattern, info_type in SENSITIVE_PATTERNS:
        matches = re.finditer(pattern, content)
        for match in matches:
            findings.append({
                "type": info_type,
                "match": match.group(0)[:50] + "..." if len(match.group(0)) > 50 else match.group(0),
                "position": match.start()
            })
    
    return findings


def scan_file_for_secrets(file_path: str) -> Dict:
    """
    扫描文件中的敏感信息
    
    参数:
        file_path: 文件路径
    
    返回:
        扫描结果字典
    """
    result = {
        "file": file_path,
        "findings": [],
        "error": None
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        result["findings"] = detect_sensitive_info(content)
        
    except Exception as e:
        result["error"] = str(e)
    
    return result


# ============ 综合安全检查 ============

def comprehensive_security_check(image_name: Optional[str] = None) -> Dict:
    """
    执行综合安全检查
    
    参数:
        image_name: 可选的镜像名称，如果提供则进行镜像扫描
    
    返回:
        综合检查结果字典
    """
    report = {
        "timestamp": __import__('time').strftime("%Y-%m-%d %H:%M:%S"),
        "docker_config": None,
        "image_scan": None
    }
    
    # Docker 安全配置检查
    report["docker_config"] = check_docker_security_config()
    
    # 镜像漏洞扫描
    if image_name:
        report["image_scan"] = scan_image_with_trivy(image_name)
    
    return report


def format_comprehensive_report(report: Dict) -> str:
    """
    格式化综合安全报告
    
    参数:
        report: 综合检查报告
    
    返回:
        格式化的报告字符串
    """
    lines = []
    lines.append(f"\n{'='*60}")
    lines.append("综合安全检查报告")
    lines.append(f"时间: {report['timestamp']}")
    lines.append(f"{'='*60}")
    
    # Docker 配置检查
    if report.get("docker_config"):
        lines.append(format_security_config_result(report["docker_config"]))
    
    # 镜像扫描
    if report.get("image_scan"):
        lines.append(format_scan_result(report["image_scan"]))
    
    return "\n".join(lines)
