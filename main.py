import requests
import re
import yaml
import datetime
import urllib3
# 禁用不安全的请求警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


github_urls = [
    "https://github.com/abshare/abshare.github.io/blob/main/README.md",
    "https://github.com/mkshare3/mkshare3.github.io/blob/main/README.md",
    "https://github.com/toshare5/toshare5.github.io/blob/main/README.md",
    "https://github.com/abshare3/abshare3.github.io/blob/main/README.md",
    "https://github.com/tolinkshare2/tolinkshare2.github.io/blob/main/README.md",
    "https://github.com/mksshare/mksshare.github.io/blob/main/README.md"
]

CLASH_USER_AGENT = "clash-verge/v1.6.6"
TEMPLATE_FILE = "template.yaml"
OUTPUT_FILE = "merged_config.yaml"

def get_raw_url(github_url):
    """
    将 GitHub blob URL 转换为 raw URL，方便下载。
    （注：为了在大陆地区访问，可以切换为 gh.llkk.cc 等加速服务）
    """
    # return "https://gh.llkk.cc/" + github_url
    return github_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")

def get_subscription_link(github_url):
    """从 GitHub README 中提取 Clash 订阅链接。"""
    raw_url = get_raw_url(github_url)
    print(f"-> 尝试从 {raw_url} 获取订阅链接...")
    try:
        response = requests.get(raw_url, timeout=10, verify=False)
        response.raise_for_status()
        # 使用正则表达式匹配“Clash订阅链接”后的第一个 http/https 链接，re.S 标志让 '.' 匹配包括换行符在内的所有字符
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
    
def get_current_ip():
    """获取当前网络的出口 IP 地址。"""
    print("--- 检查网络连接 ---")
    try:
        response = requests.get('http://httpbin.org/ip', timeout=5)
        print(f"当前访问 IP: {response.json().get('origin')}")
    except requests.exceptions.RequestException as e:
        print(f"无法获取当前 IP，网络可能存在问题: {e}")
    print("--------------------")

def download_and_extract_proxies(link):
    """下载并解析 Clash 配置文件，仅提取代理节点列表。"""
    try:
        headers = {'User-Agent': CLASH_USER_AGENT}
        response = requests.get(link, headers=headers, timeout=20, verify=False)
        response.raise_for_status()
        config_data = yaml.safe_load(response.text)
        if not config_data or 'proxies' not in config_data:
            print(f"  ✗ 警告: YAML 解析为空或缺少 'proxies' 部分, 链接: {link}")
            return None
        return config_data.get('proxies', [])
    except (requests.exceptions.RequestException, yaml.YAMLError) as e:
        print(f"  ✗ 下载或解析 {link} 失败: {e}")
        return None

def merge_configs():
    """
    主函数：加载模板，下载并追加所有新代理节点，然后更新模板中的代理组。
    """
    get_current_ip()
    
    # 1. 加载本地模板文件
    try:
        with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
            base_config = yaml.safe_load(f)
        print(f"\n✓ 成功加载模板文件 '{TEMPLATE_FILE}'")
    except Exception as e:
        print(f"\n✗ 错误: 加载或解析模板文件 '{TEMPLATE_FILE}' 失败: {e}")
        return
    
    print("\n--- 开始获取并合并 Clash 订阅 ---")
    
    all_new_proxies = []
    success_count = 0

    # 2. 遍历URL，获取所有代理节点
    for url in github_urls:
        author_match = re.search(r'github\.com/([a-zA-Z0-9_-]+)/', url)
        author = author_match.group(1) if author_match else "unknown"

        link = get_subscription_link(url)
        if link:
            proxies_from_sub = download_and_extract_proxies(link)
            if proxies_from_sub:
                for proxy in proxies_from_sub:
                    if isinstance(proxy, dict) and 'name' in proxy:
                        proxy['name'] = f"{proxy['name']} | {author}"
                        all_new_proxies.append(proxy)
                print(f"  ✓ 从此订阅中获取了 {len(proxies_from_sub)} 个代理节点。")
                success_count += 1
        print("-" * 20)
    
    if success_count == 0:
        print("\n✗ 所有订阅链接均无法获取")

    # 3. 过滤无效节点
    filtered_new_proxies = [
        p for p in all_new_proxies
        if "剩余流量" not in p.get('name', '') and "套餐到期" not in p.get('name', '')
    ]
    new_proxy_names = [p['name'] for p in filtered_new_proxies]

    # 4. 保留模板原有节点，将新节点追加到后面
    original_proxies = base_config['proxies']
    base_config['proxies'] = original_proxies + filtered_new_proxies
    
    # 5. 直接查找'手动选择'代理组并追加新节点名称
    if 'proxy-groups' in base_config and base_config['proxy-groups']:
        anchor_group_name = "手动选择"
        for group in base_config['proxy-groups']:
            if group.get('name') == anchor_group_name:
                group['proxies'].extend(new_proxy_names)
                break

    # 6. 写入最终的合并配置
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f.write(f"# 配置合并于 {timestamp}\n")
        yaml.dump(base_config, f, sort_keys=False, allow_unicode=True)

    print("\n--- 合并完成！ ---")
    print(f"已从{success_count}个订阅链接中成功合并了 {len(new_proxy_names)} 个节点。")
    print(f"最终配置文件 '{OUTPUT_FILE}' 已生成。")


if __name__ == "__main__":
    merge_configs()