# Notion MCP Server

让 AI Agent 直接管理你的 Notion 工作区。基于 [Model Context Protocol](https://modelcontextprotocol.io) 标准。

## 功能

| 工具 | 描述 |
|------|------|
| `notion_search` | 搜索页面和数据库 |
| `notion_get_page` | 获取页面内容 |
| `notion_create_page` | 创建新页面 |
| `notion_append_content` | 向页面追加内容 |
| `notion_list_databases` | 列出所有数据库 |
| `notion_query_database` | 查询数据库条目 |
| `notion_create_database_item` | 创建数据库条目 |

## 安装

```bash
pip install notion-mcp
# 或
uv pip install notion-mcp
```

## 配置

### 1. 获取 Notion Token

1. 访问 [Notion Integrations](https://www.notion.so/my-integrations)
2. 创建新的 Integration
3. 复制 Internal Integration Token

### 2. 授权 Integration

在 Notion 中，打开你想让 Agent 访问的页面/数据库，点击右上角 `...` → `Connections` → 添加你的 Integration。

### 3. 配置 Claude Desktop

编辑 `~/Library/Application Support/Claude/claude_desktop_config.json`（macOS）：

```json
{
  "mcpServers": {
    "notion": {
      "command": "notion-mcp",
      "env": {
        "NOTION_TOKEN": "secret_xxx..."
      }
    }
  }
}
```

重启 Claude Desktop。

## 使用示例

对 Claude 说：

- "搜索我 Notion 里关于项目计划的页面"
- "帮我在 Notion 创建一个今日待办清单"
- "把这段会议记录添加到我的笔记页面"
- "查看我的任务数据库里有哪些未完成的任务"

## 开发

```bash
cd notion-mcp
uv venv && source .venv/bin/activate
uv pip install -e .

# 测试（需要设置 NOTION_TOKEN）
export NOTION_TOKEN="secret_xxx"
python -m notion_mcp
```

## License

MIT
