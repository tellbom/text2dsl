# APM Text2DSL API

一个基于FastAPI的服务，用于将自然语言查询转换为Elasticsearch DSL，专门针对APM（应用性能监控）数据进行优化。支持中英文混合查询，智能时间范围分析，可与Dify等LLM平台集成。

## 功能特性

- 🌐 **多语言支持**：支持中英文混合查询，智能语义理解
- 🕐 **时区感知**：支持多时区时间范围解析，智能时间上下文分析
- 📊 **APM优化**：专门针对Elastic APM数据结构设计，覆盖所有监控场景
- 🔄 **多格式支持**：支持JSON、Markdown等多种DSL输入格式
- 🐳 **容器化部署**：完整的Docker支持，生产级配置
- 🔍 **调试友好**：提供完整的调试和诊断API
- 🧠 **智能DSL生成**：高质量的提示词工程，避免常见语法错误
- ⚡ **高性能查询**：优化的ES查询性能和聚合策略

## 系统架构

### 简化工作流程
```
用户查询 → /generate-dsl → LLM生成DSL → /execute-query → LLM分析结果 → 最终回复
```

### 智能时间感知工作流程
```
用户查询 → /analyze-time-context → LLM分析时间需求 → /process-time-analysis 
    ↓
/generate-dsl → LLM生成DSL → /execute-query → LLM分析结果 → 最终回复
```

### 核心组件

1. **时间上下文分析**：智能判断查询所需的最佳时间范围
2. **DSL生成引擎**：基于APM最佳实践的高质量DSL生成
3. **查询执行引擎**：优化的Elasticsearch查询执行
4. **结果分析引擎**：专业的APM数据解读和建议

## 快速开始

### 环境要求

- Docker & Docker Compose
- Elasticsearch 7.x+ (已配置APM数据)
- Python 3.10+ (本地开发)
- 内存: 最少512MB，推荐1GB+

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

# 生产环境配置
docker run -d \
  --name apm-text2dsl \
  --restart unless-stopped \
  --memory=1g \
  --cpus=1.0 \
  -p 8000:8000 \
  -e ES_HOST=http://your-elasticsearch:9200 \
  -e TZ=Asia/Shanghai \
  apm-text2dsl:latest
```

### 4. 验证部署

```bash
# 健康检查
curl http://localhost:8000/health

# 检查ES连接
curl http://localhost:8000/debug/indices

# API文档
打开浏览器访问: http://localhost:8000/docs
```

## API 文档

### 时间感知API

#### 1. 分析时间上下文

**POST** `/analyze-time-context`

智能分析用户查询，生成时间范围分析提示词。

**请求体：**
```json
{
  "query": "最近用户服务有什么异常吗？",
  "timezone": "Asia/Shanghai"
}
```

**响应：**
```json
{
  "prompt": "你是一个专业的APM监控时间范围分析专家...",
  "query_type": "error",
  "original_query": "最近用户服务有什么异常吗？"
}
```

#### 2. 处理时间分析结果

**POST** `/process-time-analysis`

处理LLM返回的时间分析结果，验证并结构化。

**请求体：**
```json
{
  "content": "```json\n{\"time_range\": \"2h\", \"reasoning\": \"异常查询需要足够的数据样本\", \"confidence\": \"high\"}\n```"
}
```

**响应：**
```json
{
  "time_range": "2h",
  "reasoning": "异常查询需要足够的数据样本",
  "confidence": "high",
  "original_query": ""
}
```

### 核心API

#### 3. 生成DSL提示词

**POST** `/generate-dsl`

根据用户查询生成专业的Elasticsearch DSL提示词。

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
  "prompt": "你是一个专业的APM Elasticsearch DSL生成专家...",
  "query_type": "performance",
  "time_range_info": "时间范围: 5m (2025-06-16 11:55 到 2025-06-16 12:00 (Asia/Shanghai))",
  "schema_info": {
    "transaction_index": "apm-*-transaction-*",
    "error_index": "apm-*-error-*",
    "common_fields": {...}
  }
}
```

#### 4. 执行DSL查询

**POST** `/execute-query`

执行Elasticsearch DSL查询并生成分析提示词。

**支持三种输入格式：**

**格式1：标准DSL格式**
```json
{
  "dsl": {
    "size": 0,
    "query": {
      "bool": {
        "filter": [
          {
            "range": {
              "@timestamp": {
                "gte": "2025-06-16T11:55:00Z",
                "lte": "2025-06-16T12:00:00Z"
              }
            }
          }
        ]
      }
    },
    "aggs": {
      "services": {
        "terms": {
          "field": "service.name",
          "size": 10,
          "order": {"avg_duration": "desc"}
        },
        "aggs": {
          "avg_duration": {"avg": {"field": "transaction.duration.us"}}
        }
      }
    }
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
  "content": "```json\n{\"size\": 0, \"query\": {...}}\n```",
  "original_query": "最近5分钟哪个服务最慢?",
  "format": "summary"
}
```

**响应：**
```json
{
  "raw_results": {
    "took": 15,
    "hits": {"total": {"value": 1250}},
    "aggregations": {
      "services": {
        "buckets": [
          {
            "key": "user-service",
            "doc_count": 320,
            "avg_duration": {"value": 145000.5}
          }
        ]
      }
    }
  },
  "analysis_prompt": "你是一个APM数据分析专家。用户询问了关于系统性能的问题...",
  "query_executed_at": "2025-06-16T12:00:15.123456",
  "execution_success": true,
  "error_message": null
}
```

### 辅助API

#### 5. 清理Markdown格式

**POST** `/clean-dsl`

从LLM返回的Markdown中提取纯JSON。

**请求体：**
```json
{
  "content": "```json\n{\"query\": {\"match_all\": {}}}\n```"
}
```

**响应：**
```json
{
  "cleaned_dsl": {"query": {"match_all": {}}},
  "original_content": "```json\n{\"query\": {\"match_all\": {}}}\n```"
}
```

#### 6. 健康检查

**GET** `/health`

检查服务和Elasticsearch连接状态。

**响应：**
```json
{
  "status": "healthy",
  "elasticsearch": "connected",
  "es_version": "7.17.0",
  "cluster_name": "elasticsearch"
}
```

#### 7. 调试API

- **GET** `/debug/indices` - 查看所有ES索引
- **GET** `/debug/mappings` - 查看APM索引字段映射  
- **POST** `/debug/simple-query` - 执行简单测试查询

## 时间范围支持

### 支持格式

| 格式类型 | 示例 | 说明 |
|----------|------|------|
| 分钟 | `5m`, `30min`, `15分钟` | 最近N分钟 |
| 小时 | `1h`, `2hour`, `3小时` | 最近N小时 |
| 天 | `1d`, `7day`, `30天` | 最近N天 |

### 智能时间词汇理解

| 时间词汇 | 自动映射 | 说明 |
|----------|----------|------|
| "刚才"、"刚刚" | 5-10分钟 | 实时问题排查 |
| "最近"、"近期" | 15分钟-2小时 | 根据查询类型智能判断 |
| "今天" | 1天 | 当日数据分析 |
| "昨天" | 查看昨天全天 | 历史对比分析 |
| "这周"、"本周" | 7天 | 趋势分析 |

### 查询类型时间策略

| 查询类型 | 默认时间范围 | 策略说明 |
|----------|--------------|----------|
| 性能问题 | 15-30分钟 | 实时性要求高 |
| 错误分析 | 1-2小时 | 需要足够样本 |
| 趋势分析 | 1-7天 | 长期模式识别 |
| 实时监控 | 5-15分钟 | 即时状态 |

## APM数据结构

### 支持的索引

| 索引模式 | 数据类型 | 用途 |
|----------|----------|------|
| `apm-*-transaction-*` | 事务/请求数据 | 性能分析主要数据源 |
| `apm-*-error-*` | 错误/异常数据 | 错误分析和故障排查 |
| `apm-*-span-*` | 分布式追踪数据 | 链路追踪分析 |
| `apm-*-metric-*` | 系统指标数据 | 基础设施监控 |

### 核心字段详解

#### 事务字段
| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `service.name` | keyword | 服务名称 | `user-service` |
| `service.version` | keyword | 服务版本 | `1.2.3` |
| `transaction.name` | keyword | 接口名称 | `GET /api/users` |
| `transaction.type` | keyword | 事务类型 | `request` |
| `transaction.duration.us` | long | 响应时间(微秒) | `150000` |
| `transaction.result` | keyword | 事务结果 | `success` |

#### 时间和状态字段
| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `@timestamp` | date | 时间戳 | `2025-06-16T12:00:00.000Z` |
| `event.outcome` | keyword | 事件结果 | `success/failure` |
| `http.response.status_code` | long | HTTP状态码 | `200` |
| `http.request.method` | keyword | HTTP方法 | `GET` |
| `url.path` | keyword | 请求路径 | `/api/users` |

#### 错误字段
| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `error.id` | keyword | 错误ID | `abc123` |
| `error.exception.type` | keyword | 异常类型 | `NullPointerException` |
| `error.exception.message` | text | 错误信息 | `Connection timeout` |
| `error.culprit` | keyword | 错误位置 | `UserService.getUser` |

#### 基础设施字段
| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `host.name` | keyword | 主机名 | `app-server-01` |
| `host.ip` | ip | 主机IP | `192.168.1.100` |
| `container.id` | keyword | 容器ID | `abc123def456` |
| `kubernetes.pod.name` | keyword | K8s Pod名称 | `user-service-pod-1` |

## 查询示例与最佳实践

### 1. 性能分析查询

#### 服务性能排名
```bash
curl -X POST "http://localhost:8000/generate-dsl" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "最近1小时哪个服务响应最慢?",
    "time_range": "1h",
    "timezone": "Asia/Shanghai"
  }'
```

#### 接口性能分析
```bash
curl -X POST "http://localhost:8000/generate-dsl" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "用户服务的接口响应时间分析",
    "time_range": "30m"
  }'
```

#### 响应时间分布
```bash
curl -X POST "http://localhost:8000/generate-dsl" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "显示所有服务的P95响应时间",
    "time_range": "2h"
  }'
```

### 2. 错误分析查询

#### 错误统计
```bash
curl -X POST "http://localhost:8000/generate-dsl" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "今天哪个接口报错最多?",
    "time_range": "1d"
  }'
```

#### 错误类型分析
```bash
curl -X POST "http://localhost:8000/generate-dsl" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "最近2小时的错误类型分布",
    "time_range": "2h"
  }'
```

#### 错误率分析
```bash
curl -X POST "http://localhost:8000/generate-dsl" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "用户服务的错误率趋势",
    "time_range": "4h"
  }'
```

### 3. 流量分析查询

#### 请求量统计
```bash
curl -X POST "http://localhost:8000/generate-dsl" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "用户服务过去30分钟的请求量趋势",
    "time_range": "30m"
  }'
```

#### QPS分析
```bash
curl -X POST "http://localhost:8000/generate-dsl" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "各服务的QPS排名",
    "time_range": "15m"
  }'
```

### 4. 状态码分析

#### HTTP状态码分布
```bash
curl -X POST "http://localhost:8000/generate-dsl" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "最近1小时4xx和5xx状态码统计",
    "time_range": "1h"
  }'
```

### 5. 复合查询

#### 综合健康度分析
```bash
curl -X POST "http://localhost:8000/generate-dsl" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "用户服务的综合性能指标：响应时间、错误率、请求量",
    "time_range": "1h"
  }'
```

## 与Dify集成

### 1. 简化工作流配置

#### 节点配置
1. **节点1 - 生成DSL**：调用 `/generate-dsl` API
2. **节点2 - LLM处理**：使用返回的prompt生成DSL
3. **节点3 - 执行查询**：调用 `/execute-query` API
4. **节点4 - 结果分析**：使用返回的analysis_prompt分析结果
5. **节点5 - 返回答案**：返回最终分析结果

#### Dify HTTP节点配置

**生成DSL节点：**
```yaml
URL: http://your-api-host:8000/generate-dsl
Method: POST
Headers: 
  Content-Type: application/json
Body: |
  {
    "query": "{{user_input}}",
    "time_range": "15m",
    "timezone": "Asia/Shanghai"
  }
Output Variables:
  - dsl_prompt: {{response.prompt}}
  - query_type: {{response.query_type}}
```

**执行查询节点：**
```yaml
URL: http://your-api-host:8000/execute-query
Method: POST
Headers:
  Content-Type: application/json
Body: |
  {
    "content": "{{llm_dsl_output}}",
    "original_query": "{{user_input}}",
    "format": "summary"
  }
Output Variables:
  - analysis_prompt: {{response.analysis_prompt}}
  - execution_success: {{response.execution_success}}
  - error_message: {{response.error_message}}
```

### 2. 时间感知工作流配置

#### 完整节点流程
1. **时间分析**: `/analyze-time-context`
2. **LLM时间处理**: 分析时间需求
3. **时间结果处理**: `/process-time-analysis`
4. **DSL生成**: `/generate-dsl` (使用分析的时间范围)
5. **LLM DSL生成**: 生成查询DSL
6. **执行查询**: `/execute-query`
7. **结果分析**: LLM最终分析

#### 节点配置示例

**时间分析节点：**
```yaml
URL: http://your-api-host:8000/analyze-time-context
Method: POST
Body: |
  {
    "query": "{{user_input}}",
    "timezone": "Asia/Shanghai"
  }
```

**时间结果处理节点：**
```yaml
URL: http://your-api-host:8000/process-time-analysis
Method: POST
Body: |
  {
    "content": "{{llm_time_analysis_result}}"
  }
```

### 3. 错误处理配置

在Dify中添加条件判断节点：

```yaml
# 检查执行是否成功
IF: {{execution_success}} == true
THEN: 继续结果分析
ELSE: 返回错误信息 "查询执行失败: {{error_message}}"
```

## 生产环境部署

### 1. 环境变量配置

```bash
# .env 文件
ES_HOST=http://your-production-elasticsearch:9200
TZ=Asia/Shanghai
PYTHONPATH=/app
WORKERS=4
```

### 2. Docker Compose部署

```yaml
# docker-compose.yml
version: '3.8'

services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:7.17.0
    container_name: elasticsearch
    environment:
      - discovery.type=single-node
      - "ES_JAVA_OPTS=-Xms2g -Xmx2g"
      - xpack.security.enabled=false
    ports:
      - "9200:9200"
      - "9300:9300"
    volumes:
      - es_data:/usr/share/elasticsearch/data
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:9200/_cluster/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s

  apm-text2dsl:
    build: .
    container_name: apm-text2dsl
    ports:
      - "8000:8000"
    environment:
      - ES_HOST=http://elasticsearch:9200
      - TZ=Asia/Shanghai
    restart: unless-stopped
    depends_on:
      elasticsearch:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
        reservations:
          memory: 512M
          cpus: '0.5'

volumes:
  es_data:
    driver: local

networks:
  default:
    driver: bridge
```

### 3. 反向代理配置

#### Nginx配置
```nginx
upstream apm_text2dsl {
    server localhost:8000 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name apm-api.yourdomain.com;

    # API路由
    location /apm-api/ {
        proxy_pass http://apm_text2dsl/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 超时配置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # 缓冲配置
        proxy_buffering on;
        proxy_buffer_size 8k;
        proxy_buffers 16 8k;
        
        # 错误页面
        proxy_intercept_errors on;
        error_page 502 503 504 /50x.html;
    }

    # 健康检查
    location /health {
        proxy_pass http://apm_text2dsl/health;
        access_log off;
    }

    # 静态错误页面
    location = /50x.html {
        root /usr/share/nginx/html;
    }
}
```

#### Apache配置
```apache
<VirtualHost *:80>
    ServerName apm-api.yourdomain.com
    
    ProxyPreserveHost On
    ProxyRequests Off
    
    ProxyPass /apm-api/ http://localhost:8000/
    ProxyPassReverse /apm-api/ http://localhost:8000/
    
    ProxyTimeout 60
    ProxyBadHeader Ignore
</VirtualHost>
```

### 4. 监控配置

#### 日志配置
```yaml
# docker-compose.yml 中添加日志配置
services:
  apm-text2dsl:
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "5"
```

#### Prometheus监控
```yaml
# 在应用中添加metrics端点
@app.get("/metrics")
async def metrics():
    return {
        "requests_total": request_count,
        "requests_failed": failed_count,
        "avg_response_time": avg_response_time
    }
```

## 故障排除

### 常见问题诊断

#### 1. ES连接问题

**症状：**
- `{"status": "unhealthy", "elasticsearch": "disconnected"}`
- Connection refused错误

**诊断步骤：**
```bash
# 1. 检查ES服务状态
curl http://your-elasticsearch:9200
curl http://your-elasticsearch:9200/_cluster/health

# 2. 检查网络连通性
docker exec apm-text2dsl ping elasticsearch
docker exec apm-text2dsl nslookup elasticsearch

# 3. 检查容器网络
docker network ls
docker network inspect bridge

# 4. 检查ES配置
docker logs elasticsearch | tail -50
```

**解决方案：**
```bash
# 重启ES服务
docker restart elasticsearch

# 检查ES内存配置
docker stats elasticsearch

# 修正ES_HOST配置
docker stop apm-text2dsl
docker run -d --name apm-text2dsl -p 8000:8000 \
  -e ES_HOST=http://correct-elasticsearch-host:9200 \
  apm-text2dsl:latest
```

#### 2. APM索引问题

**症状：**
- `index_not_found_exception`
- 空的查询结果

**诊断步骤：**
```bash
# 1. 检查APM索引
curl http://localhost:8000/debug/indices
curl "http://your-elasticsearch:9200/_cat/indices/apm*?v"

# 2. 检查索引结构
curl http://localhost:8000/debug/mappings

# 3. 测试简单查询
curl -X POST http://localhost:8000/debug/simple-query
```

**解决方案：**
```bash
# 如果没有APM数据，创建测试数据
curl -X POST "http://your-elasticsearch:9200/apm-test-transaction-2025.06.16/_doc" \
-H "Content-Type: application/json" \
-d '{
  "service.name": "test-service",
  "transaction.name": "GET /test",
  "transaction.duration.us": 150000,
  "@timestamp": "2025-06-16T12:00:00.000Z",
  "event.outcome": "success"
}'
```

#### 3. DSL语法错误

**症状：**
- `search_phase_execution_exception`
- `parsing_exception`

**常见错误及解决：**

**错误1：百分位数排序**
```json
// ❌ 错误
"order": {"p95_duration": "desc"}

// ✅ 正确  
"order": {"avg_duration": "desc"}
```

**错误2：时间格式问题**
```json
// ❌ 错误
"@timestamp": {"gte": "now-1h"}

// ✅ 正确
"@timestamp": {
  "gte": "2025-06-16T11:00:00Z",
  "lte": "2025-06-16T12:00:00Z",
  "format": "strict_date_optional_time"
}
```

**错误3：字段名错误**
```bash
# 检查正确的字段名
curl http://localhost:8000/debug/mappings
```

#### 4. 性能问题

**症状：**
- 查询超时
- 响应缓慢

**优化方案：**
```json
// 查询优化
{
  "size": 0,  // 不返回原始文档
  "track_total_hits": false,  // 不精确计算总数
  "timeout": "30s",  // 设置超时
  "query": {
    "bool": {
      "filter": [  // 使用filter而非must，提升性能
        {"range": {"@timestamp": {"gte": "now-1h"}}}
      ]
    }
  }
}
```

**ES集群优化：**
```bash
# 增加ES内存
docker run -d \
  --name elasticsearch \
  -e "ES_JAVA_OPTS=-Xms4g -Xmx4g" \
  elasticsearch:7.17.0

# 优化ES配置
curl -X PUT "http://your-elasticsearch:9200/_cluster/settings" \
-H "Content-Type: application/json" \
-d '{
  "persistent": {
    "search.max_buckets": 65536,
    "indices.queries.cache.size": "20%"
  }
}'
```

#### 5. 内存问题

**症状：**
- 容器重启
- Out of Memory错误

**解决方案：**
```bash
# 增加容器内存限制
docker run -d \
  --name apm-text2dsl \
  --memory=2g \
  --memory-swap=4g \
  -p 8000:8000 \
  apm-text2dsl:latest

# 监控内存使用
docker stats apm-text2dsl
```

#### 6. 时区问题

**症状：**
- 查询结果时间不正确
- 时间范围错误

**解决方案：**
```bash
# 设置容器时区
docker run -d \
  --name apm-text2dsl \
  -e TZ=Asia/Shanghai \
  -p 8000:8000 \
  apm-text2dsl:latest

# 在API调用中明确指定时区
{
  "query": "最近1小时的数据",
  "timezone": "Asia/Shanghai"
}
```

### 调试工具

#### 1. 日志分析
```bash
# 查看详细日志
docker logs -f apm-text2dsl

# 查看ES查询日志
docker logs -f apm-text2dsl | grep "查询DSL"

# 查看错误日志
docker logs apm-text2dsl 2>&1 | grep -i error
```

#### 2. 性能监控
```bash
# 容器资源使用
docker stats

# ES集群状态
curl "http://your-elasticsearch:9200/_cluster/stats?pretty"

# API响应时间测试
time curl -X POST "http://localhost:8000/execute-query" \
  -H "Content-Type: application/json" \
  -d '{"dsl": {...}, "original_query": "test"}'
```

#### 3. 网络诊断
```bash
# 测试网络连通性
docker exec apm-text2dsl ping elasticsearch
docker exec apm-text2dsl telnet elasticsearch 9200

# 检查DNS解析
docker exec apm-text2dsl nslookup elasticsearch
```

## 性能优化指南

### 1. ES查询优化

#### 查询结构优化
```json
{
  "size": 0,
  "_source": false,
  "track_total_hits": false,
  "timeout": "30s",
  "query": {
    "bool": {
      "filter": [  // 使用filter，不计算相关性分数
        {"term": {"service.name": "user-service"}},
        {"range": {"@timestamp": {"gte": "now-1h"}}}
      ]
    }
  }
}
```

#### 聚合优化
```json
{
  "aggs": {
    "services": {
      "terms": {
        "field": "service.name",
        "size": 10,  // 限制聚合大小
        "execution_hint": "map"  // 优化执行方式
      }
    }
  }
}
```

### 2. 应用层优化

#### 连接池配置
```python
# 在main.py中优化ES客户端
es_client = Elasticsearch(
    [ES_URL],
    verify_certs=False,
    timeout=30,
    max_retries=3,
    retry_on_timeout=True,
    http_compress=True,
    maxsize=25  // 连接池大小
)
```

#### 缓存策略
```python
import functools
import time
from typing import Dict, Any

# 简单的内存缓存
cache = {}
CACHE_TTL = 300  # 5分钟

def cached_query(cache_key: str, ttl: int = CACHE_TTL):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            if cache_key in cache:
                result, timestamp = cache[cache_key]
                if now - timestamp < ttl:
                    return result
            
            result = func(*args, **kwargs)
            cache[cache_key] = (result, now)
            return result
        return wrapper
    return decorator
```

### 3. 部署优化

#### 资源配置
```yaml
# docker-compose.yml
services:
  elasticsearch:
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2.0'
        reservations:
          memory: 2G
          cpus: '1.0'
    environment:
      - "ES_JAVA_OPTS=-Xms2g -Xmx2g"

  apm-text2dsl:
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
        reservations:
          memory: 512M
          cpus: '0.5'
```

#### 负载均衡
```nginx
upstream apm_backend {
    server apm-text2dsl-1:8000 weight=1 max_fails=3 fail_timeout=30s;
    server apm-text2dsl-2:8000 weight=1 max_fails=3 fail_timeout=30s;
    keepalive 32;
}

server {
    location /apm-api/ {
        proxy_pass http://apm_backend/;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }
}
```

## 开发指南

### 本地开发环境

#### 环境搭建
```bash
# 1. 克隆代码
git clone <your-repo-url>
cd apm-text2dsl

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动ES (如果需要)
docker run -d --name dev-elasticsearch \
  -p 9200:9200 \
  -e "discovery.type=single-node" \
  elasticsearch:7.17.0

# 5. 运行开发服务器
export ES_HOST=http://localhost:9200
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

#### 开发工具配置

**VSCode配置 (.vscode/settings.json):**
```json
{
  "python.defaultInterpreterPath": "./venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "python.formatting.provider": "black",
  "python.formatting.blackArgs": ["--line-length", "100"]
}
```

**pytest配置 (pytest.ini):**
```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

### 代码结构

```
apm-text2dsl/
├── main.py                 # 主程序文件
├── requirements.txt        # Python依赖
├── Dockerfile             # Docker构建文件
├── docker-compose.yml     # 容器编排配置
├── README.md              # 项目文档
├── .env.example           # 环境变量示例
├── .gitignore             # Git忽略文件
├── tests/                 # 测试文件
│   ├── __init__.py
│   ├── test_api.py
│   ├── test_dsl_generation.py
│   └── test_time_parsing.py
├── docs/                  # 详细文档
│   ├── api.md
│   ├── deployment.md
│   └── troubleshooting.md
└── scripts/               # 工具脚本
    ├── setup.sh
    ├── test_data.py
    └── health_check.sh
```

### 扩展开发

#### 1. 添加新的查询类型

**修改查询类型识别：**
```python
def determine_query_type(query: str) -> str:
    """根据用户查询确定查询类型"""
    query_lower = query.lower()

    # 添加新的查询类型
    if any(word in query_lower for word in ['吞吐量', 'throughput', 'tps']):
        return "throughput"
    elif any(word in query_lower for word in ['容量', 'capacity', '负载']):
        return "capacity"
    # ... 现有逻辑
```

**添加对应的DSL模板：**
```python
def generate_dsl_prompt(query: str, time_range: str, timezone: str = "UTC") -> str:
    # 在prompt中添加新的查询模板
    throughput_template = """
F. 吞吐量分析:
{
  "aggs": {
    "timeline": {
      "date_histogram": {
        "field": "@timestamp",
        "fixed_interval": "1m"
      },
      "aggs": {
        "tps": {
          "rate": {
            "field": "@timestamp",
            "unit": "second"
          }
        }
      }
    }
  }
}
"""
```

#### 2. 支持新的时间格式

**扩展时间解析函数：**
```python
def parse_time_range(time_str: str, timezone: str = "UTC") -> tuple:
    """解析时间范围，支持更多格式"""
    
    # 添加新的时间格式
    week_pattern = r'(\d+)\s*(w|week|周)'
    month_pattern = r'(\d+)\s*(M|month|月)'
    
    if re.search(week_pattern, time_str.lower()):
        match = re.search(week_pattern, time_str.lower())
        weeks = int(match.group(1))
        delta = timedelta(weeks=weeks)
    elif re.search(month_pattern, time_str.lower()):
        match = re.search(month_pattern, time_str.lower())
        months = int(match.group(1))
        delta = timedelta(days=months * 30)  # 近似值
    
    # ... 现有逻辑
```

#### 3. 优化结果分析

**增强分析提示词：**
```python
def generate_analysis_prompt(original_query: str, es_results: Dict[Any, Any], query_type: str) -> str:
    """生成更智能的分析提示词"""
    
    # 根据查询类型提供专业建议
    analysis_context = {
        "performance": "关注响应时间分布、异常值检测、性能瓶颈识别",
        "error": "分析错误模式、影响范围、根因分析建议",
        "throughput": "评估系统容量、流量趋势、扩容建议",
        # ... 添加更多上下文
    }
    
    context = analysis_context.get(query_type, "通用APM数据分析")
    
    prompt = f"""
你是一个专业的APM数据分析专家。
分析重点: {context}

用户原始问题: {original_query}
...
"""
```

### 测试开发

#### 单元测试示例
```python
# tests/test_time_parsing.py
import pytest
from datetime import datetime, timedelta
from main import parse_time_range

class TestTimeParsing:
    def test_minute_parsing(self):
        start, end = parse_time_range("5m")
        duration = end - start
        assert duration.total_seconds() == 300  # 5 minutes

    def test_chinese_time_parsing(self):
        start, end = parse_time_range("30分钟")
        duration = end - start
        assert duration.total_seconds() == 1800  # 30 minutes

    def test_timezone_awareness(self):
        start, end = parse_time_range("1h", "Asia/Shanghai")
        # 验证时区正确性
        assert start.tzinfo is not None
```

#### 集成测试示例
```python
# tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

class TestAPI:
    def test_health_check(self):
        response = client.get("/health")
        assert response.status_code == 200

    def test_generate_dsl(self):
        response = client.post("/generate-dsl", json={
            "query": "最近5分钟哪个服务最慢",
            "time_range": "5m"
        })
        assert response.status_code == 200
        data = response.json()
        assert "prompt" in data
        assert "query_type" in data
```

#### 性能测试
```python
# tests/test_performance.py
import time
import pytest
from fastapi.testclient import TestClient

def test_api_response_time():
    start_time = time.time()
    response = client.post("/generate-dsl", json={
        "query": "性能测试查询"
    })
    end_time = time.time()
    
    assert response.status_code == 200
    assert (end_time - start_time) < 1.0  # 响应时间小于1秒
```

## 高级特性

### 1. 智能时间范围推荐

系统会根据查询内容智能推荐最合适的时间范围：

- **实时监控类查询**: 5-15分钟
- **性能问题排查**: 15-30分钟  
- **错误分析**: 1-2小时
- **趋势分析**: 1-7天
- **容量规划**: 7-30天

### 2. 多维度查询支持

支持复合查询条件：
- 服务 + 接口 + 时间范围
- 错误类型 + 影响范围 + 趋势分析
- 性能指标 + 业务指标 + 对比分析

### 3. 自适应聚合策略

根据数据量自动调整聚合策略：
- 小数据量: 详细分析
- 中等数据量: 采样分析
- 大数据量: 智能降采样

### 4. 错误恢复机制

- 自动重试机制
- 降级查询策略
- 缓存容错机制

## 路线图

### v1.1 (计划中)
- [ ] 支持多ES集群
- [ ] 增加查询缓存
- [ ] 支持自定义聚合模板
- [ ] API密钥认证

### v1.2 (计划中)
- [ ] 支持Grafana集成
- [ ] 实时流式查询
- [ ] 机器学习异常检测
- [ ] 多租户支持

### v2.0 (远期规划)
- [ ] 可视化查询构建器
- [ ] 自动化报告生成
- [ ] 告警规则生成
- [ ] 完整的RBAC权限体系

## 许可证

MIT License

Copyright (c) 2025 APM Text2DSL Project

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## 贡献指南

### 如何贡献

1. **Fork项目**
2. **创建特性分支** (`git checkout -b feature/AmazingFeature`)
3. **提交更改** (`git commit -m 'Add some AmazingFeature'`)
4. **推送到分支** (`git push origin feature/AmazingFeature`)
5. **开启Pull Request**

### 贡献规范

- 遵循PEP 8代码规范
- 添加适当的测试用例
- 更新相关文档
- 确保所有测试通过

### 问题报告

使用GitHub Issues报告问题时，请包含：
- 问题详细描述
- 重现步骤
- 预期结果 vs 实际结果
- 环境信息 (OS, Python版本, ES版本等)
- 相关日志信息

## 支持与社区

### 获取帮助

- **文档**: 查看本README和docs/目录
- **Issues**: GitHub Issues页面
- **讨论**: GitHub Discussions
- **邮件**: 发送邮件至 support@yourcompany.com

### 社区资源

- **示例项目**: [examples/](examples/)
- **最佳实践**: [docs/best-practices.md](docs/best-practices.md)
- **常见问题**: [docs/faq.md](docs/faq.md)
- **视频教程**: [待添加]

---

**版本：** 1.0.0  
**维护者：** 内网开发团队  
**最后更新：** 2025-06-16  
**文档版本：** 完整版 v1.0

---

### 快速链接

- [API文档](#api-文档)
- [部署指南](#生产环境部署)
- [故障排除](#故障排除)
- [开发指南](#开发指南)
- [性能优化](#性能优化指南)