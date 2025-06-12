import asyncio
from mcp.client.sse import sse_client
from mcp import ClientSession
from fastmcp import FastMCP
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
import redis
import json
from typing import List, Dict, Any

mcp = FastMCP(name="hello-test-server", require_session=False)

# Redis 客户端
redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)

# MCP 请求和响应模型
class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Any = None
    id: int

class MCPResponse(BaseModel):
    jsonrpc: str = "2.0"
    result: Any = None
    error: Any = None
    id: int

# MCPClient 类
class MCPClient:
    def __init__(self, url: str):
        """初始化 MCPClient，接收服务器 URL"""
        self.url = url

    async def call_method(self, method: str, params: dict):
        """异步调用 MCP 服务器的指定方法"""
        try:
            async with sse_client(self.url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(method, params)
                    return result.content
        except Exception as e:
            return {"error": f"调用工具 '{method}' 失败: {str(e)}"}

# 获取活跃 MCP 服务器
@mcp.tool()
def get_active_servers() -> List[Dict[str, Any]]:
    """获取活跃 MCP 服务器列表"""
    servers = []
    for key in redis_client.keys("mcp:server:*"):
        server_data = redis_client.hgetall(key)
        servers.append({
            "tools": json.loads(server_data["tools"]),
            "describe": json.loads(server_data["describe"]),
            "inputSchema": json.loads(server_data["inputSchema"])
        })
    return servers

# 获取活跃 MCP Url 服务器
def get_active_url_servers() -> List[Dict[str, Any]]:
    """获取带有 URL 的活跃 MCP 服务器列表"""
    servers = []
    for key in redis_client.keys("mcp:server:*"):
        server_data = redis_client.hgetall(key)
        servers.append({
            "tools": json.loads(server_data["tools"]),
            "describe": json.loads(server_data["describe"]),
            "inputSchema": json.loads(server_data["inputSchema"]),
            "url": server_data["url"]  # 直接使用 url，无需 json.loads
        })
    return servers

# 转发请求到目标 MCP 服务器
async def forward_request(server_url: str, request: MCPRequest) -> MCPResponse:
    print(f"转发请求到: {server_url}")
    print(f"参数: {request.dict()['params']}")
    client = MCPClient(server_url)
    result = await client.call_method(request.method, request.params or {})
    print(f"result: ",result)
    return MCPResponse(
        jsonrpc="2.0",
        result=result,
        id=request.id
    )

# SSE 流生成器
async def sse_stream(data: Any, event: str = "message"):
    yield f"event: {event}\n"
    yield f"data: {json.dumps(data)}\n\n"

# 以流形式返回
# 处理 MCP 请求的 SSE 端点
# @mcp.tool()
# async def handle_mcp_request(request: MCPRequest) -> StreamingResponse:
#     """处理 MCP 请求，调用匹配的工具并返回流式响应"""
#     print("开始处理 handle_mcp_request")
#     servers = get_active_url_servers()
#     print(f"可用服务器: {servers}")
    
#     for server in servers:
#         if request.method in server["tools"]:
#             response = await forward_request(server["url"], request)
#             return StreamingResponse(
#                 sse_stream(response.dict(), "message"),
#                 media_type="text/event-stream"
#             )
        
# n8n调用以非流形式直接返回
@mcp.tool()
async def handle_mcp_request(request: MCPRequest) -> str:
    """处理 MCP 请求，调用匹配的工具并返回流式响应"""
    print("开始处理 handle_mcp_request")
    servers = get_active_url_servers()
    print(f"可用服务器: {servers}")
    
    for server in servers:
        if request.method in server["tools"]:
            response = await forward_request(server["url"], request)
            return response
    
    # 未找到匹配的服务器
    error_response = MCPResponse(
        jsonrpc="2.0",
        error={"message": "未找到支持该方法的服务"},
        id=request.id
    )
    return StreamingResponse(
        sse_stream(error_response.dict(), "error"),
        media_type="text/event-stream"
    )

if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=8012, path="/sse")