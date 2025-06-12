from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any
import httpx
import redis
import json
import time
import asyncio

app = FastAPI()

# Redis 客户端
redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)

# MCP 响应模型
class MCPResponse(BaseModel):
    jsonrpc: str = "2.0"
    result: Any = None
    error: Any = None
    id: int

# 心跳注册模型
class HeartbeatRequest(BaseModel):
    host_slice: str
    url: str
    tools: List[str]
    describe: List[str]
    inputSchema: List[Dict[str, Any]]

# 心跳注册端点
@app.post("/heartbeat")
async def register_server(heartbeat: HeartbeatRequest):
    server_data = {
        "url": heartbeat.url,
        "tools": json.dumps(heartbeat.tools),
        "describe": json.dumps(heartbeat.describe),
        "inputSchema": json.dumps(heartbeat.inputSchema),
        "last_heartbeat": time.time()
    }
    print("server_data:", server_data)
    redis_client.hset(f"mcp:server:{heartbeat.host_slice}", mapping=server_data)
    redis_client.expire(f"mcp:server:{heartbeat.host_slice}", 900)
    return {"status": "registered", "url": heartbeat.url}

# 启动服务器
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8013)