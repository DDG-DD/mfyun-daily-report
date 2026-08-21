#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
梦飞道科技（梦想科技云）每日收益推送脚本 - GitHub Actions 云端版
从环境变量读取配置，适合在GitHub Actions等云端环境运行
"""

import requests
import json
import datetime
import sys
import os
import base64

# ============== 从环境变量读取配置 ==============

ACCOUNTS = [
    {
        "name": "账号1",
        "username": os.environ.get("ACCOUNT1_USERNAME", ""),
        "password": os.environ.get("ACCOUNT1_PASSWORD", "")
    },
    {
        "name": "账号2",
        "username": os.environ.get("ACCOUNT2_USERNAME", ""),
        "password": os.environ.get("ACCOUNT2_PASSWORD", "")
    }
]

PUSH_CONFIG = {
    "method": "serverchan",
    "serverchan_key": os.environ.get("SERVERCHAN_KEY", ""),
}

USAGE_RATE_THRESHOLD = int(os.environ.get("USAGE_RATE_THRESHOLD", "75"))
API_URL = "https://api.mfyun.top/graphql"


def login(username, password):
    query = """
    mutation login($loginForm: LoginInput!) {
      login(loginInput: $loginForm) {
        access_token
        refresh_token
        user_id
      }
    }
    """
    variables = {"loginForm": {"username": username, "password": password}}
    try:
        resp = requests.post(API_URL, json={"query": query, "variables": variables}, timeout=30)
        data = resp.json()
        if "errors" in data:
            print(f"登录失败: {data['errors']}")
            return None
        return data["data"]["login"]["access_token"]
    except Exception as e:
        print(f"登录异常: {e}")
        return None


def get_machine_statistic(token):
    query = """
    query getMachineStatistic {
      online: machines(where: {online: {_eq: 1}}) { data { uuid } total }
      offline: machines(where: {online: {_eq: 0}}) { data { uuid } total }
      total: machines { data { uuid } total }
    }
    """
    headers = {"Authorization": token}
    try:
        resp = requests.post(API_URL, json={"query": query}, headers=headers, timeout=30)
        data = resp.json()
        if "errors" in data:
            print(f"获取节点统计失败: {data['errors']}")
            return None
        result = data["data"]
        return {"total": result["total"]["total"], "online": result["online"]["total"], "offline": result["offline"]["total"]}
    except Exception as e:
        print(f"获取节点统计异常: {e}")
        return None


def get_machine_list(token, date=None):
    if date is None:
        date = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    query = """
    query getMachinePage($page: Int!, $pageSize: Int!, $where: MachineBoolExp, $order_by: [MachineOrderBy!]) {
      result: machines(page: $page, page_size: $pageSize, where: $where, order_by: $order_by) {
        data {
          host uuid usage_rate online online_desc max_bandwidth province operator deployed_at remark
          user_bills { profit bill_date total_traffic }
          user { name }
        }
        total
      }
    }
    """
    variables = {
        "page": 1, "pageSize": 100,
        "where": {"user_bills": {"bill_date": {"_eq": date}}},
        "order_by": [{"field": "usage_rate", "order": "desc"}]
    }
    headers = {"Authorization": token}
    try:
        resp = requests.post(API_URL, json={"query": query, "variables": variables}, headers=headers, timeout=30)
        data = resp.json()
        if "errors" in data:
            print(f"获取节点列表失败: {data['errors']}")
            return None
        machines = data["data"]["result"]["data"]
        node_list = []
        for m in machines:
            bills = m.get("user_bills", [])
            profit = bills[0].get("profit") if bills else 0
            traffic = bills[0].get("total_traffic") if bills else 0
            usage_rate = m.get("usage_rate", 0) or 0
            node_list.append({
                "remark": m.get("remark") or "未命名",
                "host": m.get("host", ""),
                "usage_rate": round(usage_rate * 100, 1),
                "online": m.get("online_desc", "未知"),
                "profit": round(profit, 2) if profit else 0,
                "traffic": round(traffic, 3) if traffic else 0,
            })
        return node_list
    except Exception as e:
        print(f"获取节点列表异常: {e}")
        return None


def get_daily_profit(token, user_id, date=None):
    if date is None:
        date = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    query = """
    query getBillsPage($page: Int!, $pageSize: Int!, $where: UserBillBoolExp) {
      result: userBills(page: $page, page_size: $pageSize, where: $where) {
        data { id bill_date total_traffic penalty_traffic profit cost }
        total
      }
    }
    """
    variables = {"page": 1, "pageSize": 200, "where": {"bill_date": {"_eq": date}, "user_id": {"_eq": user_id}}}
    headers = {"Authorization": token}
    try:
        resp = requests.post(API_URL, json={"query": query, "variables": variables}, headers=headers, timeout=30)
        data = resp.json()
        if "errors" in data:
            print(f"获取收益失败: {data['errors']}")
            return None
        bills = data["data"]["result"]["data"]
        total_profit = sum(b["profit"] for b in bills if b["profit"])
        total_traffic = sum(b["total_traffic"] for b in bills if b["total_traffic"])
        return {"date": date, "total_profit": round(total_profit, 2), "total_traffic": round(total_traffic, 3), "bill_count": len(bills)}
    except Exception as e:
        print(f"获取收益异常: {e}")
        return None


def get_user_id_from_token(token):
    parts = token.split('.')
    if len(parts) >= 2:
        payload = parts[1] + '=' * (4 - len(parts[1]) % 4)
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded).get("id")
    return None


def push_message(title, content):
    key = PUSH_CONFIG["serverchan_key"]
    if not key:
        print("未配置Server酱 key")
        print(f"标题: {title}\n内容:\n{content}")
        return False
    try:
        url = f"https://sctapi.ftqq.com/{key}.send"
        resp = requests.post(url, data={"title": title, "desp": content}, timeout=30)
        result = resp.json()
        if result.get("code") == 0:
            print("Server酱推送成功")
            return True
        print(f"Server酱推送失败: {result}")
        return False
    except Exception as e:
        print(f"推送异常: {e}")
        return False


def main():
    print("=" * 50)
    print(f"梦飞道科技每日报告 - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    account_results = []
    total_profit_all = 0
    total_nodes_all = 0
    total_online_all = 0
    total_offline_all = 0
    all_low_usage_nodes = []
    
    for account in ACCOUNTS:
        name, username, password = account["name"], account["username"], account["password"]
        if not username or not password:
            print(f"{name} 未配置，跳过")
            continue
        print(f"\n--- {name} ({username}) ---")
        token = login(username, password)
        if not token:
            account_results.append({"name": name, "username": username, "error": "登录失败"})
            continue
        user_id = get_user_id_from_token(token)
        print(f"user_id: {user_id}")
        stats = get_machine_statistic(token)
        if stats:
            print(f"节点: 总数{stats['total']} 在线{stats['online']} 离线{stats['offline']}")
            total_nodes_all += stats["total"]
            total_online_all += stats["online"]
            total_offline_all += stats["offline"]
        profit = get_daily_profit(token, user_id, yesterday)
        if profit:
            print(f"昨日收益: ¥{profit['total_profit']} 流量: {profit['total_traffic']}G")
            total_profit_all += profit["total_profit"]
        node_list = get_machine_list(token, yesterday)
        avg_usage_rate = 0
        low_usage_nodes = []
        if node_list:
            online_nodes = [n for n in node_list if n["online"] == "在线"]
            if online_nodes:
                avg_usage_rate = round(sum(n["usage_rate"] for n in online_nodes) / len(online_nodes), 1)
            low_usage_nodes = [n for n in node_list if n["online"] == "在线" and n["usage_rate"] < USAGE_RATE_THRESHOLD]
            print(f"平均利用率: {avg_usage_rate}% 低利用率: {len(low_usage_nodes)}个")
            for n in low_usage_nodes:
                all_low_usage_nodes.append({"account": name, **n})
        account_results.append({"name": name, "username": username, "stats": stats, "profit": profit, "avg_usage_rate": avg_usage_rate, "low_usage_nodes": low_usage_nodes})
    
    print("\n" + "=" * 50)
    title = f"【梦想云日报】{yesterday} 收益¥{round(total_profit_all, 2)}"
    content_lines = [f"📅 报告日期: {today}", f"📊 统计周期: {yesterday} 收益数据", ""]
    for result in account_results:
        name = result["name"]
        if "error" in result:
            content_lines.append(f"❌ {name}: {result['error']}")
            continue
        line = f"📱 {name} ({result['username']})"
        if result.get("stats"):
            s = result["stats"]
            line += f"\n   节点: {s['total']}台 (在线{s['online']}/离线{s['offline']})"
        if result.get("profit"):
            line += f"\n   昨日收益: ¥{result['profit']['total_profit']} | 流量: {result['profit']['total_traffic']}G"
        if result.get("avg_usage_rate", 0) > 0:
            line += f"\n   平均利用率: {result['avg_usage_rate']}%"
        content_lines.append(line)
        content_lines.append("")
    if all_low_usage_nodes:
        content_lines.append(f"⚠️ 低利用率节点告警 (<{USAGE_RATE_THRESHOLD}%)")
        content_lines.append("─────────────────────")
        for n in all_low_usage_nodes:
            content_lines.append(f"  [{n['account']}] {n['remark']}: 利用率{n['usage_rate']}% | 收益¥{n['profit']} | IP:{n['host']}")
        content_lines.append("")
    content_lines.append("━━━━━━━━━━━━━━━━━")
    content_lines.append(f"💰 两账号总收益: ¥{round(total_profit_all, 2)}")
    content_lines.append(f"🖥️ 节点总数: {total_nodes_all}台 (在线{total_online_all}/离线{total_offline_all})")
    if all_low_usage_nodes:
        content_lines.append(f"🔔 低利用率节点: {len(all_low_usage_nodes)}个需关注")
    if total_offline_all > 0:
        content_lines.append(f"⚠️ 离线节点: {total_offline_all}台，请检查")
    content = "\n".join(content_lines)
    print(content)
    print("\n" + "=" * 50)
    if push_message(title, content):
        print("报告推送完成！")
    else:
        print("报告推送失败！")
        sys.exit(1)


if __name__ == "__main__":
    main()
