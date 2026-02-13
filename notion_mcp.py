"""
Notion MCP Server
Let AI agents manage your Notion workspace via Model Context Protocol
"""

import asyncio
import os
import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, Resource

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

server = Server("notion-mcp")


def get_headers() -> dict:
    """Get Notion API headers with auth token."""
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        raise ValueError("NOTION_TOKEN environment variable not set")
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available Notion tools."""
    return [
        Tool(
            name="notion_search",
            description="搜索 Notion 中的页面和数据库。可以按标题、内容搜索。",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词"
                    },
                    "filter": {
                        "type": "string",
                        "enum": ["page", "database"],
                        "description": "筛选类型：page（页面）或 database（数据库）"
                    },
                    "page_size": {
                        "type": "integer",
                        "description": "返回结果数量，默认 10"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="notion_get_page",
            description="获取 Notion 页面的内容。返回页面标题和正文内容。",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {
                        "type": "string",
                        "description": "页面 ID（可以从 URL 或搜索结果获取）"
                    }
                },
                "required": ["page_id"]
            }
        ),
        Tool(
            name="notion_create_page",
            description="在 Notion 中创建新页面。可以指定父页面或数据库。",
            inputSchema={
                "type": "object",
                "properties": {
                    "parent_id": {
                        "type": "string",
                        "description": "父页面或数据库的 ID"
                    },
                    "parent_type": {
                        "type": "string",
                        "enum": ["page_id", "database_id"],
                        "description": "父级类型：page_id（页面）或 database_id（数据库）"
                    },
                    "title": {
                        "type": "string",
                        "description": "页面标题"
                    },
                    "content": {
                        "type": "string",
                        "description": "页面内容（Markdown 格式）"
                    }
                },
                "required": ["parent_id", "parent_type", "title"]
            }
        ),
        Tool(
            name="notion_append_content",
            description="向现有 Notion 页面追加内容。",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {
                        "type": "string",
                        "description": "页面 ID"
                    },
                    "content": {
                        "type": "string",
                        "description": "要追加的内容（Markdown 格式）"
                    }
                },
                "required": ["page_id", "content"]
            }
        ),
        Tool(
            name="notion_list_databases",
            description="列出你有权限访问的所有 Notion 数据库。",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_size": {
                        "type": "integer",
                        "description": "返回数量，默认 10"
                    }
                }
            }
        ),
        Tool(
            name="notion_query_database",
            description="查询 Notion 数据库，获取其中的条目。支持筛选和排序。",
            inputSchema={
                "type": "object",
                "properties": {
                    "database_id": {
                        "type": "string",
                        "description": "数据库 ID"
                    },
                    "filter_property": {
                        "type": "string",
                        "description": "筛选属性名"
                    },
                    "filter_value": {
                        "type": "string",
                        "description": "筛选值"
                    },
                    "page_size": {
                        "type": "integer",
                        "description": "返回数量，默认 10"
                    }
                },
                "required": ["database_id"]
            }
        ),
        Tool(
            name="notion_create_database_item",
            description="在 Notion 数据库中创建新条目。",
            inputSchema={
                "type": "object",
                "properties": {
                    "database_id": {
                        "type": "string",
                        "description": "数据库 ID"
                    },
                    "properties": {
                        "type": "object",
                        "description": "条目属性，格式为 {属性名: 值}"
                    }
                },
                "required": ["database_id", "properties"]
            }
        ),
    ]


def markdown_to_blocks(content: str) -> list[dict]:
    """Convert simple markdown to Notion blocks."""
    blocks = []
    lines = content.split('\n')
    
    for line in lines:
        line = line.rstrip()
        if not line:
            continue
            
        if line.startswith('# '):
            blocks.append({
                "type": "heading_1",
                "heading_1": {"rich_text": [{"type": "text", "text": {"content": line[2:]}}]}
            })
        elif line.startswith('## '):
            blocks.append({
                "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": line[3:]}}]}
            })
        elif line.startswith('### '):
            blocks.append({
                "type": "heading_3",
                "heading_3": {"rich_text": [{"type": "text", "text": {"content": line[4:]}}]}
            })
        elif line.startswith('- ') or line.startswith('* '):
            blocks.append({
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": line[2:]}}]}
            })
        elif line.startswith('```'):
            continue  # Skip code fence markers
        else:
            blocks.append({
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": line}}]}
            })
    
    return blocks


def blocks_to_markdown(blocks: list[dict]) -> str:
    """Convert Notion blocks to markdown."""
    lines = []
    
    for block in blocks:
        block_type = block.get("type", "")
        
        if block_type == "paragraph":
            text = extract_text(block.get("paragraph", {}).get("rich_text", []))
            lines.append(text)
        elif block_type == "heading_1":
            text = extract_text(block.get("heading_1", {}).get("rich_text", []))
            lines.append(f"# {text}")
        elif block_type == "heading_2":
            text = extract_text(block.get("heading_2", {}).get("rich_text", []))
            lines.append(f"## {text}")
        elif block_type == "heading_3":
            text = extract_text(block.get("heading_3", {}).get("rich_text", []))
            lines.append(f"### {text}")
        elif block_type == "bulleted_list_item":
            text = extract_text(block.get("bulleted_list_item", {}).get("rich_text", []))
            lines.append(f"- {text}")
        elif block_type == "numbered_list_item":
            text = extract_text(block.get("numbered_list_item", {}).get("rich_text", []))
            lines.append(f"1. {text}")
        elif block_type == "code":
            text = extract_text(block.get("code", {}).get("rich_text", []))
            lang = block.get("code", {}).get("language", "")
            lines.append(f"```{lang}\n{text}\n```")
        elif block_type == "quote":
            text = extract_text(block.get("quote", {}).get("rich_text", []))
            lines.append(f"> {text}")
        elif block_type == "to_do":
            text = extract_text(block.get("to_do", {}).get("rich_text", []))
            checked = block.get("to_do", {}).get("checked", False)
            lines.append(f"- [{'x' if checked else ' '}] {text}")
    
    return '\n'.join(lines)


def extract_text(rich_text: list[dict]) -> str:
    """Extract plain text from Notion rich_text array."""
    return ''.join(t.get("plain_text", "") for t in rich_text)


def extract_title(properties: dict) -> str:
    """Extract title from page properties."""
    for key, value in properties.items():
        if value.get("type") == "title":
            return extract_text(value.get("title", []))
    return "Untitled"


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute a Notion tool."""
    
    try:
        headers = get_headers()
    except ValueError as e:
        return [TextContent(type="text", text=f"错误: {str(e)}\n请设置 NOTION_TOKEN 环境变量")]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if name == "notion_search":
                query = arguments.get("query", "")
                filter_type = arguments.get("filter")
                page_size = arguments.get("page_size", 10)
                
                payload: dict[str, Any] = {"query": query, "page_size": page_size}
                if filter_type:
                    payload["filter"] = {"property": "object", "value": filter_type}
                
                resp = await client.post(f"{NOTION_API}/search", headers=headers, json=payload)
                data = resp.json()
                
                if "results" not in data:
                    return [TextContent(type="text", text=f"搜索失败: {json.dumps(data, ensure_ascii=False)}")]
                
                results = []
                for item in data["results"]:
                    obj_type = item.get("object")
                    item_id = item.get("id")
                    
                    if obj_type == "page":
                        title = extract_title(item.get("properties", {}))
                        results.append(f"📄 页面: {title}\n   ID: {item_id}")
                    elif obj_type == "database":
                        title = extract_text(item.get("title", []))
                        results.append(f"📊 数据库: {title}\n   ID: {item_id}")
                
                if not results:
                    return [TextContent(type="text", text="没有找到匹配的结果")]
                
                return [TextContent(type="text", text="\n\n".join(results))]
            
            elif name == "notion_get_page":
                page_id = arguments.get("page_id", "").replace("-", "")
                
                # Get page properties
                page_resp = await client.get(f"{NOTION_API}/pages/{page_id}", headers=headers)
                page_data = page_resp.json()
                
                if "properties" not in page_data:
                    return [TextContent(type="text", text=f"获取页面失败: {json.dumps(page_data, ensure_ascii=False)}")]
                
                title = extract_title(page_data.get("properties", {}))
                
                # Get page content (blocks)
                blocks_resp = await client.get(f"{NOTION_API}/blocks/{page_id}/children", headers=headers)
                blocks_data = blocks_resp.json()
                
                content = blocks_to_markdown(blocks_data.get("results", []))
                
                return [TextContent(type="text", text=f"# {title}\n\n{content}")]
            
            elif name == "notion_create_page":
                parent_id = arguments.get("parent_id", "").replace("-", "")
                parent_type = arguments.get("parent_type", "page_id")
                title = arguments.get("title", "Untitled")
                content = arguments.get("content", "")
                
                payload = {
                    "parent": {parent_type: parent_id},
                    "properties": {
                        "title": {"title": [{"text": {"content": title}}]}
                    }
                }
                
                if content:
                    payload["children"] = markdown_to_blocks(content)
                
                resp = await client.post(f"{NOTION_API}/pages", headers=headers, json=payload)
                data = resp.json()
                
                if "id" in data:
                    return [TextContent(type="text", text=f"✅ 页面创建成功!\n标题: {title}\nID: {data['id']}\nURL: {data.get('url', 'N/A')}")]
                else:
                    return [TextContent(type="text", text=f"创建失败: {json.dumps(data, ensure_ascii=False)}")]
            
            elif name == "notion_append_content":
                page_id = arguments.get("page_id", "").replace("-", "")
                content = arguments.get("content", "")
                
                blocks = markdown_to_blocks(content)
                
                resp = await client.patch(
                    f"{NOTION_API}/blocks/{page_id}/children",
                    headers=headers,
                    json={"children": blocks}
                )
                data = resp.json()
                
                if "results" in data:
                    return [TextContent(type="text", text=f"✅ 内容追加成功! 添加了 {len(data['results'])} 个块")]
                else:
                    return [TextContent(type="text", text=f"追加失败: {json.dumps(data, ensure_ascii=False)}")]
            
            elif name == "notion_list_databases":
                page_size = arguments.get("page_size", 10)
                
                resp = await client.post(
                    f"{NOTION_API}/search",
                    headers=headers,
                    json={"filter": {"property": "object", "value": "database"}, "page_size": page_size}
                )
                data = resp.json()
                
                results = []
                for db in data.get("results", []):
                    title = extract_text(db.get("title", []))
                    db_id = db.get("id")
                    results.append(f"📊 {title}\n   ID: {db_id}")
                
                if not results:
                    return [TextContent(type="text", text="没有找到数据库")]
                
                return [TextContent(type="text", text="\n\n".join(results))]
            
            elif name == "notion_query_database":
                database_id = arguments.get("database_id", "").replace("-", "")
                page_size = arguments.get("page_size", 10)
                
                payload: dict[str, Any] = {"page_size": page_size}
                
                # Simple text filter if provided
                filter_prop = arguments.get("filter_property")
                filter_val = arguments.get("filter_value")
                if filter_prop and filter_val:
                    payload["filter"] = {
                        "property": filter_prop,
                        "rich_text": {"contains": filter_val}
                    }
                
                resp = await client.post(
                    f"{NOTION_API}/databases/{database_id}/query",
                    headers=headers,
                    json=payload
                )
                data = resp.json()
                
                if "results" not in data:
                    return [TextContent(type="text", text=f"查询失败: {json.dumps(data, ensure_ascii=False)}")]
                
                results = []
                for item in data["results"]:
                    title = extract_title(item.get("properties", {}))
                    item_id = item.get("id")
                    results.append(f"• {title} (ID: {item_id})")
                
                if not results:
                    return [TextContent(type="text", text="数据库为空或没有匹配的条目")]
                
                return [TextContent(type="text", text=f"查询结果 ({len(results)} 条):\n" + "\n".join(results))]
            
            elif name == "notion_create_database_item":
                database_id = arguments.get("database_id", "").replace("-", "")
                props = arguments.get("properties", {})
                
                # Convert simple properties to Notion format
                notion_props = {}
                for key, value in props.items():
                    if isinstance(value, str):
                        # Assume title for first property, rich_text for others
                        if not notion_props:
                            notion_props[key] = {"title": [{"text": {"content": value}}]}
                        else:
                            notion_props[key] = {"rich_text": [{"text": {"content": value}}]}
                    elif isinstance(value, bool):
                        notion_props[key] = {"checkbox": value}
                    elif isinstance(value, (int, float)):
                        notion_props[key] = {"number": value}
                
                resp = await client.post(
                    f"{NOTION_API}/pages",
                    headers=headers,
                    json={
                        "parent": {"database_id": database_id},
                        "properties": notion_props
                    }
                )
                data = resp.json()
                
                if "id" in data:
                    return [TextContent(type="text", text=f"✅ 条目创建成功!\nID: {data['id']}")]
                else:
                    return [TextContent(type="text", text=f"创建失败: {json.dumps(data, ensure_ascii=False)}")]
            
            else:
                return [TextContent(type="text", text=f"未知工具: {name}")]
                
        except httpx.HTTPError as e:
            return [TextContent(type="text", text=f"HTTP 错误: {str(e)}")]
        except Exception as e:
            return [TextContent(type="text", text=f"错误: {str(e)}")]


def main():
    """Run the MCP server."""
    asyncio.run(stdio_server(server))


if __name__ == "__main__":
    main()
