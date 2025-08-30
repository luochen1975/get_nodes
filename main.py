import requests
import re
import os
import yaml
from urllib.parse import urlparse

import urllib3
# 禁用不安全的请求警告，因为在某些代理环境下可能会遇到证书问题
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


github_urls = [
    "https://github.com/abshare/abshare.github.io/blob/main/README.md",
    "https://github.com/mkshare3/mkshare3.github.io/blob/main/README.md",
    "https://github.com/toshare5/toshare5.github.io/blob/main/README.md",
    "https://github.com/abshare3/abshare3.github.io/blob/main/README.md",
    "https://github.com/tolinkshare2/tolinkshare2.github.io/blob/main/README.md",
    "https://github.com/mksshare/mksshare.github.io/blob/main/README.md"
]

# 用于下载订阅的 User-Agent，伪装成 Clash Verge 客户端
CLASH_USER_AGENT = "FlClash/v0.8.87 clash-verge Platform/android"

OUTPUT_FILE = "merged_config.yaml"

def get_raw_url(github_url):
    """
    将 GitHub blob URL 转换为 raw URL，方便下载。
    （注：为了在大陆地区访问，可以切换为 gh.llkk.cc 等加速服务）
    """
    # return "https://gh.llkk.cc/" + github_url
    return github_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")

def get_subscription_link(github_url):
    """
    从指定的 GitHub README 中提取 Clash 订阅链接。
    
    Args:
        github_url (str): GitHub README 的 URL。

    Returns:
        str or None: 找到的订阅链接，如果未找到或请求失败则返回 None。
    """
    raw_url = get_raw_url(github_url)
    print(f"-> 尝试从 {raw_url} 获取订阅链接...")
    try:
        response = requests.get(raw_url, timeout=10, verify=False)
        response.raise_for_status()
        
        # 使用正则表达式匹配“Clash订阅链接”后的第一个 http/https 链接
        # re.S 标志让 '.' 匹配包括换行符在内的所有字符
        match = re.search(r'Clash订阅链接.*?((?:https?|http)://\S+)', response.text, re.S)
        if match:
            link = match.group(1).strip()
            print(f"  ✓ 成功找到链接: {link}")
            return link
        else:
            print(f"  ✗ 在 {raw_url} 中未找到 Clash 订阅链接。")
            return None
    except requests.exceptions.RequestException as e:
        print(f"  ✗ 请求 {raw_url} 失败: {e}")
        return None

def download_and_extract_data(link):
    """
    下载并解析 Clash 配置文件，提取代理节点列表。
    
    Args:
        link (str): Clash 订阅链接。
        
    Returns:
        dict or None: 包含 'proxies' 和 'proxy-groups' 的配置数据，如果下载或解析失败则返回 None。
    """
    try:
        headers = {'User-Agent': CLASH_USER_AGENT}
        response = requests.get(link, headers=headers, timeout=20, verify=False)
        response.raise_for_status()
        
        config_data = yaml.safe_load(response.text)
        
        if not config_data:
            print(f"  ✗ 警告: YAML 解析为空，链接: {link}")
            return None
        
        return config_data
    except (requests.exceptions.RequestException, yaml.YAMLError) as e:
        print(f"  ✗ 下载或解析 {link} 失败: {e}")
        return None

def get_current_ip():
    """获取当前网络的出口 IP 地址。"""
    print("--- 检查网络连接 ---")
    try:
        response = requests.get('http://httpbin.org/ip', timeout=5)
        print(f"当前访问 IP: {response.json().get('origin')}")
    except requests.exceptions.RequestException as e:
        print(f"无法获取当前 IP，网络可能存在问题: {e}")
    print("--------------------")

def merge_configs():
    """
    主函数：遍历所有 GitHub URL，下载订阅，合并所有代理节点，并更新代理组。
    """
    get_current_ip()
    print("\n--- 开始合并 Clash 订阅 ---")
    
    base_config = None
    all_proxies = []
    seen_proxy_names = set()
    success_count = 0

    for url in github_urls:
        # 从 URL 中提取作者名作为代理名称的后缀
        # 匹配 /作者/仓库/ 格式
        author_match = re.search(r'github\.com/([a-zA-Z0-9_-]+)/', url)
        author = author_match.group(1) if author_match else "unknown"

        link = get_subscription_link(url)
        
        if link:
            config_data = download_and_extract_data(link)
            
            if config_data and 'proxies' in config_data:
                # 首次成功获取的配置作为合并的基础模板
                if not base_config:
                    base_config = config_data
                    print("  ✓ 已成功获取第一个有效的基础配置。")

                proxies_to_add = config_data.get('proxies', [])
                
                # 遍历当前获取的代理，并处理名称重复问题
                for proxy in proxies_to_add:
                    if isinstance(proxy, dict) and 'name' in proxy:
                        new_name = f"{proxy['name']} | {author}"  
                        proxy['name'] = new_name
                        seen_proxy_names.add(new_name)
                        all_proxies.append(proxy)
                
                print(f"  ✓ 从此订阅中获取了 {len(proxies_to_add)} 个代理节点。")
                success_count += 1
        print("-" * 20)
    
    # 检查是否成功下载了任何配置
    if not base_config:
        print("\n✗ 所有订阅链接都无法下载或解析，将生成一个空的配置文件。")
        base_config = {'proxies': [], 'proxy-groups': [], 'rules': []}
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(base_config, f, sort_keys=False, allow_unicode=True)
        return

    # 过滤掉包含特定关键字的无效节点
    filtered_proxies = [
        p for p in all_proxies
        if isinstance(p, dict) and 'name' in p and
        "剩余流量" not in p['name'] and "套餐到期" not in p['name']
    ]

    # 获取过滤后的所有代理的名称列表
    all_proxy_names = [p['name'] for p in filtered_proxies]

    # 更新基础配置中的代理列表和代理组
    base_config['proxies'] = filtered_proxies
    
    # 更新代理组中的代理列表
    if 'proxy-groups' in base_config:
        updated_groups = []
        for group in base_config['proxy-groups']:
            # 只修改 select 和 url-test 类型的代理组
            if group.get('type') in ['select', 'url-test']:
                group['proxies'] = all_proxy_names
                updated_groups.append(group['name'])
        
        if updated_groups:
            print(f"\n已更新以下代理组的节点列表：{', '.join(updated_groups)}")

    # 写入最终的合并配置
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        yaml.dump(base_config, f, sort_keys=False, allow_unicode=True)

    print("\n--- 合并完成！ ---")
    print(f"成功获取了 {success_count} 个有效订阅。")
    print(f"最终配置文件 '{OUTPUT_FILE}' 共包含 {len(filtered_proxies)} 个有效代理节点。")

if __name__ == "__main__":
    merge_configs()