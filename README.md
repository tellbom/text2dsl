# APM Text2DSL API

一个基于FastAPI的服务，用于将自然语言查询转换为Elasticsearch DSL，专门针对APM（应用性能监控）数据进行优化。支持中英文混合查询，可与Dify平台集成。

## 功能特性

- 🌐 **多语言支持**：支持中英文混合查询
- 🕐 **时区感知**：支持多时区时间范围解析
- 📊 **APM优化**：专门针对Elastic APM数据结构设计
- 🔄 **多格式支持**：支持JSON、Markdown等多种DSL输入格式
- 🐳 **容器化部署**：完整的Docker支持
- 🔍 **调试友好**：提供完整的调试和诊断API

## 系统架构

```
用户查询 → /generate-dsl → LLM生成DSL → /execute-query → LLM分析结果 → 最终回复
```

### 工作流程

1. **生成提示词**：用户查询 → API生成专业的DSL提示词
2. **LLM处理**：Dify调用LLM根据提示词生成Elasticsearch DSL
3. **执行查询**：API执行DSL查询并获取ES结果
4. **结果分析**：API生成分析提示词，LLM进行最终分析

## 快速开始

### 环境要求

- Docker & Docker Compose
- Elasticsearch 7.x+ (已配置APM数据)
- Python 3.10+ (本地开发)

### 1. 克隆项目

```bash
git clone <your-repo-url>
cd apm-text2dsl
```

### 2. 配置环境

修改 `main.py` 中的ES配置：

```python
ES_HOST = "http://your-elasticsearch-host:9200"
```

或使用环境变量：

```bash
export ES_HOST="http://your-elasticsearch-host:9200"
```

### 3. Docker部署

#### 构建镜像

```bash
docker build -t apm-text2dsl:latest .
```

#### 运行容器

```bash
# 基本运行
docker run -d \
  --name apm-text2dsl \
  -p 8000:8000 \
  -e ES_HOST=http://your-elasticsearch:9200 \
  apm-text2dsl:latest

# 开发模式（代码映射）
docker run -d \
  --name apm-text2dsl \
  -p 8000:8000 \
  -v $(pwd):/app \
  -e ES_HOST=http://your-elasticsearch:9200 \
  apm-text2dsl:latest

# 使用宿主机网络（推荐）
docker run -d \
  --name apm-text2dsl \
  --network host \
  -v $(pwd):/app \
  -e ES_HOST=http://localhost:9200 \
  apm-text2dsl:latest
```

### 4. 验证部署

```bash
# 健康检查
curl http://localhost:8000/health

# API文档
打开浏览器访问: http://localhost:8000/docs
```

## API 文档

### 核心API

#### 1. 生成DSL提示词

**POST** `/generate-dsl`

根据用户查询生成专业的Elasticsearch DSL提示词，返回给Dify平台。

**请求体：**
```json
{
  "query": "最近5分钟哪个服务最慢?",
  "time_range": "5m",
  "timezone": "Asia/Shanghai",
  "language": "auto"
}
```

**响应：**
```json
{
  "prompt": "你是一个专业的Elasticsearch DSL生成专家...",
  "query_type": "performance",
  "time_range_info": "2025-06-12 10:55 到 2025-06-12 11:00 (Asia/Shanghai)",
  "schema_info": {...}
}
```

#### 2. 执行DSL查询

**POST** `/execute-query`

执行Elasticsearch DSL查询并生成分析提示词。

**支持三种输入格式：**

**格式1：标准DSL格式**
```json
{
  "dsl": {
    "size": 0,
    "query": {...},
    "aggs": {...}
  },
  "original_query": "最近5分钟哪个服务最慢?",
  "format": "summary"
}
```

**格式2：LLM标准格式**
```json
{
  "query": {
    "size": 0,
    "query": {...},
    "aggs": {...}
  },
  "original_query": "最近5分钟哪个服务最慢?",
  "format": "summary"
}
```

**格式3：Markdown格式**
```json
{
  "content": "```json\n{...}\n```",
  "original_query": "最近5分钟哪个服务最慢?",
  "format": "summary"
}
```

**响应：**
```json
{
  "raw_results": {...},
  "analysis_prompt": "你是一个APM数据分析专家...",
  "query_executed_at": "2025-06-12T11:00:15.123456",
  "execution_success": true,
  "error_message": null
}
```

### 辅助API

#### 3. 清理Markdown格式

**POST** `/clean-dsl`

从LLM返回的Markdown中提取纯JSON。

#### 4. 健康检查

**GET** `/health`

检查服务和Elasticsearch连接状态。

#### 5. 调试API

- **GET** `/debug/indices` - 查看所有ES索引
- **GET** `/debug/mappings` - 查看APM索引字段映射
- **POST** `/debug/simple-query` - 执行简单测试查询

## 时间范围支持

支持多种时间范围格式：

| 格式 | 示例 | 说明 |
|------|------|------|
| 分钟 | `5m`, `30min`, `15分钟` | 最近N分钟 |
| 小时 | `1h`, `2hour`, `3小时` | 最近N小时 |
| 天 | `1d`, `7day`, `30天` | 最近N天 |

## APM数据结构

### 支持的索引

- `apm-*-transaction-*` - 事务/请求数据
- `apm-*-error-*` - 错误数据
- `apm-*-metric-*` - 系统指标数据

### 主要字段

| 字段名 | 说明 | 示例 |
|--------|------|------|
| `service.name` | 服务名称 | `user-service` |
| `transaction.name` | 接口名称 | `GET /api/users` |
| `transaction.duration.us` | 响应时间(微秒) | `150000` |
| `@timestamp` | 时间戳 | `2025-06-12T10:30:00.000Z` |
| `http.response.status_code` | HTTP状态码 | `200` |
| `error.exception.message` | 错误信息 | `Connection timeout` |

## 常见查询示例

### 1. 性能查询

```bash
# 查询最慢的服务
curl -X POST "http://localhost:8000/generate-dsl" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "最近1小时哪个服务响应最慢?",
    "time_range": "1h",
    "timezone": "Asia/Shanghai"
  }'
```

### 2. 错误查询

```bash
# 查询错误最多的接口
curl -X POST "http://localhost:8000/generate-dsl" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "今天哪个接口报错最多?",
    "time_range": "1d"
  }'
```

### 3. 流量查询

```bash
# 查询请求量
curl -X POST "http://localhost:8000/generate-dsl" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "用户服务过去30分钟的请求量趋势",
    "time_range": "30m"
  }'
```

## 与Dify集成

### 1. 配置Dify工作流

1. **节点1**：调用 `/generate-dsl` API
2. **节点2**：将返回的prompt发送给LLM
3. **节点3**：调用 `/execute-query` API，传入LLM生成的DSL
4. **节点4**：将返回的analysis_prompt发送给LLM
5. **节点5**：返回最终分析结果

### 2. Dify HTTP节点配置

**生成DSL节点：**
```
URL: http://your-api-host:8000/generate-dsl
Method: POST
Headers: Content-Type: application/json
Body: {
  "query": "{{user_input}}",
  "time_range": "15m",
  "timezone": "Asia/Shanghai"
}
```

**执行查询节点：**
```
URL: http://your-api-host:8000/execute-query
Method: POST
Headers: Content-Type: application/json
Body: {
  "content": "{{llm_dsl_output}}",
  "original_query": "{{user_input}}",
  "format": "summary"
}
```

## 生产环境部署

### 1. 环境变量配置

```bash
# .env 文件
ES_HOST=http://your-production-elasticsearch:9200
TZ=Asia/Shanghai
```

### 2. Docker Compose部署

```yaml
# docker-compose.yml
version: '3.8'
services:
  apm-text2dsl:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ES_HOST=http://elasticsearch:9200
      - TZ=Asia/Shanghai
    restart: unless-stopped
    depends_on:
      - elasticsearch
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### 3. 反向代理配置

**Nginx配置示例：**
```nginx
location /apm-api/ {
    proxy_pass http://localhost:8000/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_timeout 60s;
}
```

## 故障排除

### 常见问题

#### 1. ES连接失败

**症状：** `{"status": "unhealthy", "elasticsearch": "disconnected"}`

**解决方案：**
- 检查ES地址配置
- 确认ES服务正常运行
- 检查网络连接和防火墙

#### 2. 找不到APM索引

**症状：** `"error_message": "ES查询执行失败: index_not_found_exception"`

**解决方案：**
```bash
# 检查可用索引
curl http://localhost:8000/debug/indices

# 确认APM数据已生成
curl -X GET "http://your-elasticsearch:9200/_cat/indices/apm*"
```

#### 3. DSL验证失败

**症状：** `"error_message": "DSL验证失败: ..."`

**解决方案：**
- 检查LLM生成的DSL格式
- 使用 `/clean-dsl` API预处理Markdown格式
- 查看详细错误信息调整DSL结构

#### 4. 时区问题

**症状：** 查询结果时间不正确

**解决方案：**
```bash
# 设置正确的时区
export TZ=Asia/Shanghai

# 在API调用中指定时区
{
  "query": "...",
  "timezone": "Asia/Shanghai"
}
```

### 调试模式

启用详细日志：

```bash
# 查看容器日志
docker logs -f apm-text2dsl

# 在代码中，所有ES查询都会输出详细信息
```

### 性能优化

1. **ES查询优化**：
   - 合理设置 `size` 参数
   - 使用适当的时间范围
   - 优化聚合查询

2. **容器资源**：
   ```bash
   docker run -d \
     --name apm-text2dsl \
     --memory=512m \
     --cpus=1.0 \
     -p 8000:8000 \
     apm-text2dsl:latest
   ```

## 开发指南

### 本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 运行开发服务器
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 代码结构

```
├── main.py              # 主程序文件
├── requirements.txt     # Python依赖
├── Dockerfile          # Docker构建文件
└── README.md           # 说明文档
```

### 扩展开发

1. **添加新的查询类型**：修改 `determine_query_type()` 函数
2. **支持新的时间格式**：扩展 `parse_time_range()` 函数
3. **优化结果分析**：改进 `generate_analysis_prompt()` 函数

## 许可证

[MIT License](LICENSE)

## 支持

如有问题，请提交Issue或联系维护团队。

---

**版本：** 1.0.0  
**维护者：** 内网开发团队  
**最后更新：** 2025-06-12