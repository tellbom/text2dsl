from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from elasticsearch import Elasticsearch
from datetime import datetime, timedelta
import json
import re
import os

app = FastAPI(title="APM Text2DSL API", version="1.0.0")

# 配置
ES_HOST = "http://192.168.48.128:9200"  # 修改为你的ES地址

# 初始化ES客户端 - 支持环境变量配置
ES_URL = os.getenv("ES_HOST", ES_HOST)
es_client = Elasticsearch([ES_URL], verify_certs=False)


# 请求响应模型
class QueryRequest(BaseModel):
    query: str
    time_range: Optional[str] = "15m"  # 恢复默认值，也可以传入LLM分析的结果
    language: Optional[str] = "auto"
    timezone: Optional[str] = "UTC"


class DSLRequest(BaseModel):
    dsl: Optional[Dict[Any, Any]] = None
    query: Optional[Dict[Any, Any]] = None  # 兼容LLM生成的格式
    content: Optional[str] = None  # 支持Markdown格式的DSL
    original_query: str
    format: Optional[str] = "summary"

    def get_query_body(self) -> Dict[Any, Any]:
        """获取查询体，支持多种输入格式"""
        # 优先级：dsl > query > content(markdown)
        if self.dsl is not None:
            return self.dsl
        elif self.query is not None:
            return self.query
        elif self.content is not None:
            # 从Markdown中提取JSON
            return extract_json_from_markdown(self.content)
        else:
            raise ValueError("必须提供dsl、query或content字段之一")


class PromptResponse(BaseModel):
    prompt: str
    query_type: str
    time_range_info: str
    schema_info: Dict[str, Any]


class ExecuteResponse(BaseModel):
    raw_results: Dict[Any, Any]
    analysis_prompt: str
    query_executed_at: str
    execution_success: bool
    error_message: Optional[str] = None


class MarkdownRequest(BaseModel):
    content: str


class CleanResponse(BaseModel):
    cleaned_dsl: Dict[Any, Any]
    original_content: str


class TimeContextRequest(BaseModel):
    query: str
    timezone: Optional[str] = "UTC"


class TimeContextResponse(BaseModel):
    prompt: str  # 返回给LLM的提示词
    query_type: str
    original_query: str


class TimeAnalysisResponse(BaseModel):
    time_range: str
    reasoning: str
    confidence: str
    original_query: str


# APM 索引和字段映射
APM_SCHEMA = {
    "transaction_index": "apm-*-transaction-*",
    "error_index": "apm-*-error-*",
    "metric_index": "apm-*-metric-*",
    "common_fields": {
        "service.name": "服务名称",
        "transaction.name": "事务名称/接口名称",
        "transaction.duration.us": "响应时间(微秒)",
        "@timestamp": "时间戳",
        "http.response.status_code": "HTTP状态码",
        "error.exception.message": "错误信息",
        "host.name": "主机名",
        "labels.*": "标签字段"
    }
}


def generate_time_context_prompt(query: str, timezone: str = "UTC") -> str:
    """生成时间上下文分析提示词"""

    prompt = f"""
你是一个专业的APM监控时间范围分析专家。根据用户的查询内容，判断最合适的时间范围。

当前时区: {timezone}

用户查询: {query}

请分析用户查询中的时间意图，并返回最合适的时间范围。考虑以下因素：

1. 查询类型判断：
   - 错误/异常查询：通常需要较长时间范围来发现问题模式
   - 性能问题：实时性要求高，时间范围相对较短
   - 趋势分析：需要较长时间范围
   - 实时监控：需要很短的时间范围

2. 时间词汇理解：
   - "刚才"、"刚刚" → 5-10分钟
   - "最近"、"近期" → 根据查询类型：性能15-30分钟，错误1-2小时
   - "今天" → 1天
   - "昨天" → 查看昨天全天数据
   - "这周"、"本周" → 7天
   - "上周" → 14天（包含对比）
   - 无明确时间词汇 → 根据查询类型推断

3. 业务常识：
   - 性能问题通常在短时间内暴露
   - 错误分析需要足够的数据样本
   - 容量规划需要长期数据
   - 故障排查需要事件发生前后的数据

请返回JSON格式，包含：
- time_range: 时间范围（格式：5m, 30m, 1h, 2h, 1d, 7d等）
- reasoning: 判断理由
- confidence: 置信度（high/medium/low）

只返回JSON，不要其他解释。

示例输出：
```json
{{
  "time_range": "1h",
  "reasoning": "性能问题查询，需要足够数据但保持实时性",
  "confidence": "high"
}}
```

分析结果：
"""
    return prompt


def parse_time_range(time_str: str, timezone: str = "UTC") -> tuple:
    """解析时间范围，支持中英文和时区"""
    import pytz

    # 获取时区对象
    try:
        tz = pytz.timezone(timezone)
    except:
        tz = pytz.UTC  # 默认UTC

    # 获取当前时间（带时区）
    now = datetime.now(tz)

    # 正则匹配数字和单位
    pattern = r'(\d+)\s*(m|min|分钟|h|hour|小时|d|day|天)'
    match = re.search(pattern, time_str.lower())

    if not match:
        # 默认15分钟
        return now - timedelta(minutes=15), now

    num = int(match.group(1))
    unit = match.group(2)

    if unit in ['m', 'min', '分钟']:
        delta = timedelta(minutes=num)
    elif unit in ['h', 'hour', '小时']:
        delta = timedelta(hours=num)
    elif unit in ['d', 'day', '天']:
        delta = timedelta(days=num)
    else:
        delta = timedelta(minutes=15)

    return now - delta, now


def generate_dsl_prompt(query: str, time_range: str, timezone: str = "UTC") -> str:
    """生成完整的APM专用LLM提示词"""
    start_time, end_time = parse_time_range(time_range, timezone)

    prompt = """
你是一个专业的APM (Application Performance Monitoring) Elasticsearch DSL生成专家。
根据用户的APM监控查询需求，生成高质量的Elasticsearch DSL查询。
=== APM数据结构详解 ===
索引模式:

apm--transaction-  # 事务/请求数据（性能分析主要数据源）
apm--error-        # 错误/异常数据
apm--span-         # 分布式追踪span数据
apm--metric-       # 系统/应用指标数据

核心字段映射:
【事务字段】

service.name: 服务名称 (keyword)
service.version: 服务版本 (keyword)
transaction.name: 事务/接口名称 (keyword)
transaction.type: 事务类型 (request/page-load/task等)
transaction.duration.us: 响应时间(微秒) (long)
transaction.result: 事务结果 (success/failure/timeout等)
transaction.sampled: 是否采样 (boolean)

【时间和状态】

@timestamp: 时间戳 (date)
event.outcome: 事件结果 (success/failure/unknown)
http.response.status_code: HTTP状态码 (long)
http.request.method: HTTP方法 (keyword)
url.path: 请求路径 (keyword)
url.full: 完整URL (keyword)

【错误字段】

error.id: 错误ID (keyword)
error.exception.type: 异常类型 (keyword)
error.exception.message: 错误信息 (text)
error.culprit: 错误位置 (keyword)
error.grouping_key: 错误分组键 (keyword)

【基础设施字段】

host.name: 主机名 (keyword)
host.ip: 主机IP (ip)
container.id: 容器ID (keyword)
kubernetes.pod.name: K8s Pod名称 (keyword)
cloud.instance.id: 云实例ID (keyword)

【业务字段】

user.id: 用户ID (keyword)
user.name: 用户名 (keyword)
labels.*: 自定义标签 (keyword/text)
tags.*: 标签 (keyword)

【分布式追踪】

trace.id: 链路ID (keyword)
parent.id: 父span ID (keyword)
span.id: span ID (keyword)

=== 时间范围配置 ===
查询时间范围: {start_time.isoformat()} 到 {end_time.isoformat()}
时区: {timezone}
用户查询: {query}
=== DSL生成规则与最佳实践 ===
【1. 时间过滤 - 必须包含】
固定模板:
{{
"range": {{
"@timestamp": {{
"gte": "{start_time.isoformat()}",
"lte": "{end_time.isoformat()}",
"format": "strict_date_optional_time"
}}
}}
}}
【2. 聚合排序限制 - 重要】
✅ 可用于排序的单值聚合:

avg: 平均值
max: 最大值
min: 最小值
sum: 总和
cardinality: 唯一值计数
value_count: 文档计数
bucket_count: 桶计数

❌ 禁止用于排序的多值聚合:

percentiles: 百分位数
stats: 统计信息
extended_stats: 扩展统计
histogram: 直方图
date_histogram: 时间直方图

正确排序示例: "order": {{"avg_duration": "desc"}}
错误排序示例: "order": {{"p95_duration": "desc"}}
【3. 性能优化配置】

size: 0  # 不返回原始文档，只要聚合结果
track_total_hits: false  # 不精确计算总数，提升性能
"timeout": "30s"  # 设置查询超时

【4. 常见APM查询模式】
A. 服务性能排名:
{{
"aggs": {{
"services": {{
"terms": {{
"field": "service.name",
"size": 10,
"order": {{"avg_duration": "desc"}}
}},
"aggs": {{
"avg_duration": {{"avg": {{"field": "transaction.duration.us"}}}},
"max_duration": {{"max": {{"field": "transaction.duration.us"}}}},
"request_count": {{"value_count": {{"field": "@timestamp"}}}},
"error_rate": {{
"filter": {{"term": {{"event.outcome": "failure"}}}},
"aggs": {{
"error_count": {{"value_count": {{"field": "@timestamp"}}}}
}}
}}
}}
}}
}}
}}
B. 接口性能分析:
{{
"aggs": {{
"transactions": {{
"terms": {{
"field": "transaction.name",
"size": 10,
"order": {{"avg_duration": "desc"}}
}},
"aggs": {{
"avg_duration": {{"avg": {{"field": "transaction.duration.us"}}}},
"request_count": {{"value_count": {{"field": "@timestamp"}}}},
"percentiles_duration": {{
"percentiles": {{
"field": "transaction.duration.us",
"percents": [50, 90, 95, 99]
}}
}}
}}
}}
}}
}}
C. 错误分析:
{{
"query": {{
"bool": {{
"filter": [
{{"term": {{"event.outcome": "failure"}}}},
时间过滤
]
}}
}},
"aggs": {{
"error_types": {{
"terms": {{
"field": "error.exception.type",
"size": 10,
"order": {{"error_count": "desc"}}
}},
"aggs": {{
"error_count": {{"value_count": {{"field": "@timestamp"}}}},
"affected_services": {{
"cardinality": {{"field": "service.name"}}
}},
"sample_message": {{
"top_hits": {{
"size": 1,
"_source": ["error.exception.message", "service.name"]
}}
}}
}}
}}
}}
}}
D. 时间趋势分析:
{{
"aggs": {{
"timeline": {{
"date_histogram": {{
"field": "@timestamp",
"fixed_interval": "1m",
"extended_bounds": {{
"min": "{start_time.isoformat()}",
"max": "{end_time.isoformat()}"
}}
}},
"aggs": {{
"avg_duration": {{"avg": {{"field": "transaction.duration.us"}}}},
"request_count": {{"value_count": {{"field": "@timestamp"}}}},
"error_count": {{
"filter": {{"term": {{"event.outcome": "failure"}}}}
}}
}}
}}
}}
}}
E. 状态码分布:
{{
"aggs": {{
"status_codes": {{
"terms": {{
"field": "http.response.status_code",
"size": 10,
"order": {{"request_count": "desc"}}
}},
"aggs": {{
"request_count": {{"value_count": {{"field": "@timestamp"}}}},
"avg_duration": {{"avg": {{"field": "transaction.duration.us"}}}}
}}
}}
}}
}}
【5. 复杂过滤条件】
服务过滤:
{{"term": {{"service.name": "服务名"}}}}
多服务过滤:
{{"terms": {{"service.name": ["service1", "service2"]}}}}
响应时间范围:
{{"range": {{"transaction.duration.us": {{"gte": 100000, "lte": 5000000}}}}}}
状态码过滤:
{{"range": {{"http.response.status_code": {{"gte": 400}}}}}}
路径模糊匹配:
{{"wildcard": {{"url.path": "api"}}}}
正则表达式:
{{"regexp": {{"transaction.name": ".login."}}}}
存在性检查:
{{"exists": {{"field": "user.id"}}}}
【6. 高级聚合技巧】
分桶后再聚合:
{{
"aggs": {{
"duration_ranges": {{
"range": {{
"field": "transaction.duration.us",
"ranges": [
{{"to": 100000}},
{{"from": 100000, "to": 500000}},
{{"from": 500000, "to": 1000000}},
{{"from": 1000000}}
]
}},
"aggs": {{
"request_count": {{"value_count": {{"field": "@timestamp"}}}}
}}
}}
}}
}}
嵌套条件聚合:
{{
"aggs": {{
"services": {{
"terms": {{"field": "service.name"}},
"aggs": {{
"fast_requests": {{
"filter": {{"range": {{"transaction.duration.us": {{"lt": 100000}}}}}},
"aggs": {{
"count": {{"value_count": {{"field": "@timestamp"}}}}
}}
}},
"slow_requests": {{
"filter": {{"range": {{"transaction.duration.us": {{"gte": 1000000}}}}}},
"aggs": {{
"count": {{"value_count": {{"field": "@timestamp"}}}}
}}
}}
}}
}}
}}
}}
【7. 查询类型智能识别】
根据用户查询内容智能选择索引和字段:
性能相关关键词: "慢", "slow", "响应时间", "latency", "duration", "性能"
→ 主要查询 transaction.duration.us 字段
错误相关关键词: "错误", "error", "异常", "exception", "失败", "failure"
→ 查询 apm--error- 索引，关注 event.outcome=failure
流量相关关键词: "请求量", "QPS", "调用", "访问", "流量", "traffic"
→ 重点统计文档计数和时间分布
状态码相关关键词: "状态码", "4xx", "5xx", "500", "404"
→ 聚合 http.response.status_code 字段
服务相关关键词: "服务", "service", 具体服务名
→ 按 service.name 分组
接口相关关键词: "接口", "API", "endpoint", 具体路径
→ 按 transaction.name 或 url.path 分组
【8. 输出要求】

只返回完整的JSON格式DSL查询语句
必须包含时间范围过滤
合理设置聚合大小 (size: 10-20)
选择合适的排序方式
根据查询类型优化字段选择
确保所有语法正确，可直接执行
不要包含任何解释文字或markdown格式

请根据以上规则和用户查询，生成专业的APM Elasticsearch DSL查询：
""".format(start=start_time.isoformat(), end=end_time.isoformat(), tz=timezone, query=query)

    return prompt

def validate_dsl(dsl: Dict[Any, Any]) -> tuple[bool, str]:
    """验证DSL查询的基本结构"""
    try:
        # 检查必需的字段
        if not isinstance(dsl, dict):
            return False, "DSL必须是JSON对象"

        # 放宽验证条件：只要是合法的ES查询结构即可
        # 可以有query、aggs、size、sort等任意组合
        valid_top_level_fields = {'query', 'aggs', 'size', 'sort', '_source', 'from', 'highlight', 'script_fields'}
        if not any(field in dsl for field in valid_top_level_fields):
            return False, "DSL必须包含query、aggs、size、sort等ES查询字段之一"

        return True, "DSL验证通过"

    except Exception as e:
        return False, f"DSL验证失败: {str(e)}"


def has_time_filter(query_part: Dict[Any, Any]) -> bool:
    """递归检查是否包含时间过滤"""
    if isinstance(query_part, dict):
        if 'range' in query_part and '@timestamp' in str(query_part):
            return True
        for value in query_part.values():
            if has_time_filter(value):
                return True
    elif isinstance(query_part, list):
        for item in query_part:
            if has_time_filter(item):
                return True
    return False


def execute_es_query(dsl: Dict[Any, Any]) -> Dict[Any, Any]:
    """执行Elasticsearch查询"""
    try:
        # 确定查询的索引
        index_pattern = determine_index_pattern(dsl)

        print(f"使用索引: {index_pattern}")  # 调试信息
        print(f"查询DSL: {json.dumps(dsl, indent=2)}")  # 调试信息

        # 执行查询
        response = es_client.search(
            index=index_pattern,
            body=dsl,
            timeout='30s',
            ignore_unavailable=True,  # 忽略不可用的索引
            allow_no_indices=True  # 允许没有匹配的索引
        )

        print(f"ES响应类型: {type(response)}")  # 调试信息

        # 将ES响应转换为可序列化的字典
        if hasattr(response, 'body'):
            result = response.body  # 新版本elasticsearch客户端
        elif hasattr(response, 'to_dict'):
            result = response.to_dict()
        else:
            # 手动转换为字典
            result = {}
            for key in ['took', 'timed_out', '_shards', 'hits', 'aggregations']:
                if hasattr(response, key):
                    result[key] = getattr(response, key)
                elif isinstance(response, dict) and key in response:
                    result[key] = response[key]

            # 如果结果为空，直接返回response
            if not result and isinstance(response, dict):
                result = response

        print(f"处理后结果: {json.dumps(result, indent=2, default=str)}")  # 调试信息
        return result

    except Exception as e:
        print(f"ES查询详细错误: {str(e)}")  # 调试信息
        print(f"错误类型: {type(e)}")  # 调试信息
        raise Exception(f"ES查询执行失败: {str(e)}")


def determine_index_pattern(dsl: Dict[Any, Any]) -> str:
    """根据DSL内容确定索引模式"""
    dsl_str = json.dumps(dsl).lower()

    if 'error' in dsl_str:
        return APM_SCHEMA["error_index"]
    elif 'transaction' in dsl_str or 'duration' in dsl_str:
        return APM_SCHEMA["transaction_index"]
    else:
        return APM_SCHEMA["transaction_index"]  # 默认使用transaction索引


def process_aggregation_results(aggs: Dict[Any, Any], query_type: str) -> str:
    """处理聚合结果"""
    try:
        # 处理服务性能排名类查询
        if 'services' in aggs or 'service_stats' in aggs:
            service_key = 'services' if 'services' in aggs else 'service_stats'
            buckets = aggs[service_key].get('buckets', [])

            if buckets:
                results = []
                for bucket in buckets[:5]:  # 取前5个
                    service_name = bucket.get('key', '未知服务')
                    if 'avg_duration' in bucket:
                        avg_duration = bucket['avg_duration'].get('value', 0)
                        avg_duration_ms = round(avg_duration / 1000, 2)  # 转换为毫秒
                        results.append(f"{service_name}: 平均响应时间 {avg_duration_ms}ms")
                    else:
                        doc_count = bucket.get('doc_count', 0)
                        results.append(f"{service_name}: {doc_count} 次调用")

                return "查询结果:\n" + "\n".join(results)

        # 处理简单统计
        if 'avg_duration' in aggs:
            avg_duration = aggs['avg_duration'].get('value', 0)
            avg_duration_ms = round(avg_duration / 1000, 2)
            return f"平均响应时间: {avg_duration_ms}ms"

        return "查询完成，但结果格式需要进一步处理"

    except Exception as e:
        return f"聚合结果处理失败: {str(e)}"


def generate_analysis_prompt(original_query: str, es_results: Dict[Any, Any], query_type: str) -> str:
    """生成结果分析提示词给LLM"""

    # 提取关键信息
    hits = es_results.get('hits', {})
    total = hits.get('total', {}).get('value', 0)
    aggregations = es_results.get('aggregations', {})
    took = es_results.get('took', 0)

    prompt = f"""
你是一个APM数据分析专家。用户询问了关于系统性能的问题，我已经执行了Elasticsearch查询并获得了结果。请根据查询结果给出专业的分析和建议。

用户原始问题: {original_query}

查询结果概述:
- 查询耗时: {took}ms
- 总记录数: {total}
- 查询类型: {query_type}

详细查询结果:
{json.dumps(es_results, ensure_ascii=False, indent=2)}

请根据以上结果提供:
1. 直接回答用户的问题
2. 关键数据的解读和分析
3. 如果发现异常情况，提供可能的原因和建议
4. 用中文回复，语言要简洁易懂

分析回复:
"""
    return prompt


def extract_json_from_markdown(content: str) -> Dict[Any, Any]:
    """从Markdown格式中提取JSON"""
    import json

    # 去除可能的markdown代码块
    content = content.strip()

    # 处理 ```json 格式
    if '```json' in content:
        json_part = content.split('```json')[1].split('```')[0].strip()
    # 处理 ``` 格式
    elif '```' in content:
        json_part = content.split('```')[1].split('```')[0].strip()
    # 处理纯JSON
    else:
        json_part = content.strip()

    # 尝试解析JSON
    try:
        return json.loads(json_part)
    except json.JSONDecodeError as e:
        # 尝试修复常见的JSON问题
        json_part = json_part.replace('，', ',').replace('：', ':')  # 中文标点
        json_part = re.sub(r',\s*}', '}', json_part)  # 移除末尾逗号
        json_part = re.sub(r',\s*]', ']', json_part)  # 移除末尾逗号

        try:
            return json.loads(json_part)
        except json.JSONDecodeError:
            raise ValueError(f"无法解析JSON: {str(e)}")


def determine_query_type(query: str) -> str:
    """根据用户查询确定查询类型"""
    query_lower = query.lower()

    if any(word in query_lower for word in ['慢', 'slow', '响应时间', 'response time', 'duration']):
        return "performance"
    elif any(word in query_lower for word in ['错误', 'error', '异常', 'exception']):
        return "error"
    elif any(word in query_lower for word in ['调用', 'request', '请求', 'call']):
        return "traffic"
    else:
        return "general"


def determine_query_type_from_dsl(dsl: Dict[Any, Any]) -> str:
    """从DSL确定查询类型"""
    dsl_str = json.dumps(dsl).lower()

    if 'duration' in dsl_str:
        return "performance"
    elif 'error' in dsl_str:
        return "error"
    else:
        return "general"


# API 端点
@app.post("/analyze-time-context", response_model=TimeContextResponse)
async def analyze_time_context(request: TimeContextRequest):
    """API: LLM上下文感知时间范围分析"""
    try:
        # 生成时间分析提示词
        prompt = generate_time_context_prompt(request.query, request.timezone)

        # 确定查询类型
        query_type = determine_query_type(request.query)

        return TimeContextResponse(
            prompt=prompt,
            query_type=query_type,
            original_query=request.query
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"时间上下文分析失败: {str(e)}")


@app.post("/process-time-analysis", response_model=TimeAnalysisResponse)
async def process_time_analysis(request: MarkdownRequest):
    """API: 处理LLM返回的时间分析结果"""
    try:
        # 从Markdown中提取JSON
        analysis_result = extract_json_from_markdown(request.content)

        # 验证必需字段
        required_fields = ['time_range', 'reasoning', 'confidence']
        for field in required_fields:
            if field not in analysis_result:
                raise ValueError(f"LLM返回结果缺少必需字段: {field}")

        # 验证时间格式
        time_range = analysis_result['time_range']
        if not re.match(r'^\d+[mhd]$', time_range):
            raise ValueError(f"时间格式不正确: {time_range}")

        return TimeAnalysisResponse(
            time_range=analysis_result['time_range'],
            reasoning=analysis_result['reasoning'],
            confidence=analysis_result['confidence'],
            original_query=analysis_result.get('original_query', '')
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"时间分析结果处理失败: {str(e)}")


@app.post("/generate-dsl", response_model=PromptResponse)
async def generate_dsl(request: QueryRequest):
    """API 1: 根据用户查询生成提示词返回给Dify"""
    try:
        # 使用传入的时间范围（可能来自LLM分析）
        time_range = request.time_range

        # 生成提示词
        prompt = generate_dsl_prompt(request.query, time_range, request.timezone)

        # 确定查询类型
        query_type = determine_query_type(request.query)

        # 生成时间范围信息
        start_time, end_time = parse_time_range(time_range, request.timezone)
        time_info = f"{start_time.strftime('%Y-%m-%d %H:%M')} 到 {end_time.strftime('%Y-%m-%d %H:%M')} ({request.timezone})"

        return PromptResponse(
            prompt=prompt,
            query_type=query_type,
            time_range_info=f"时间范围: {time_range} ({time_info})",
            schema_info=APM_SCHEMA
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提示词生成失败: {str(e)}")


@app.post("/execute-query", response_model=ExecuteResponse)
async def execute_query(request: DSLRequest):
    """API 2: 执行DSL查询并生成分析提示词返回给Dify"""
    try:
        # 获取查询体（支持dsl或query字段）
        try:
            query_body = request.get_query_body()
        except ValueError as e:
            return ExecuteResponse(
                raw_results={},
                analysis_prompt="",
                query_executed_at=datetime.utcnow().isoformat(),
                execution_success=False,
                error_message=f"输入格式错误: {str(e)}"
            )
        except Exception as e:
            return ExecuteResponse(
                raw_results={},
                analysis_prompt="",
                query_executed_at=datetime.utcnow().isoformat(),
                execution_success=False,
                error_message=f"JSON解析失败: {str(e)}"
            )

        # 验证DSL
        is_valid, validation_msg = validate_dsl(query_body)
        if not is_valid:
            return ExecuteResponse(
                raw_results={},
                analysis_prompt="",
                query_executed_at=datetime.utcnow().isoformat(),
                execution_success=False,
                error_message=f"DSL验证失败: {validation_msg}"
            )

        # 执行ES查询
        try:
            es_response = execute_es_query(query_body)

            # 生成分析提示词
            query_type = determine_query_type(request.original_query)
            analysis_prompt = generate_analysis_prompt(
                request.original_query,
                es_response,
                query_type
            )

            return ExecuteResponse(
                raw_results=es_response,
                analysis_prompt=analysis_prompt,
                query_executed_at=datetime.utcnow().isoformat(),
                execution_success=True
            )

        except Exception as e:
            return ExecuteResponse(
                raw_results={},
                analysis_prompt="",
                query_executed_at=datetime.utcnow().isoformat(),
                execution_success=False,
                error_message=str(e)  # 直接返回异常信息
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询处理失败: {str(e)}")


@app.post("/clean-dsl", response_model=CleanResponse)
async def clean_dsl(request: MarkdownRequest):
    """API 3: 清理LLM返回的Markdown格式，提取纯JSON"""
    try:
        cleaned_dsl = extract_json_from_markdown(request.content)

        return CleanResponse(
            cleaned_dsl=cleaned_dsl,
            original_content=request.content
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"JSON提取失败: {str(e)}")


@app.get("/health")
async def health_check():
    """健康检查"""
    try:
        # 检查ES连接
        es_info = es_client.info()
        return {
            "status": "healthy",
            "elasticsearch": "connected",
            "es_version": es_info.get("version", {}).get("number", "unknown"),
            "cluster_name": es_info.get("cluster_name", "unknown")
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "elasticsearch": "disconnected",
            "error": str(e)
        }


@app.get("/debug/indices")
async def debug_indices():
    """调试：查看可用的索引"""
    try:
        # 获取所有索引
        indices = es_client.cat.indices(format="json")

        # 过滤APM相关索引
        apm_indices = [idx for idx in indices if 'apm' in idx.get('index', '').lower()]

        return {
            "total_indices": len(indices),
            "apm_indices": apm_indices,
            "all_indices": [idx.get('index') for idx in indices]
        }
    except Exception as e:
        return {"error": f"获取索引失败: {str(e)}"}


@app.get("/debug/mappings")
async def debug_mappings():
    """调试：查看APM索引的字段映射"""
    try:
        # 尝试获取APM索引的映射
        patterns = ["apm-*-transaction-*", "apm-*-error-*", "apm-*"]
        results = {}

        for pattern in patterns:
            try:
                mapping = es_client.indices.get_mapping(index=pattern, ignore_unavailable=True)
                results[pattern] = mapping
            except Exception as e:
                results[pattern] = f"错误: {str(e)}"

        return results
    except Exception as e:
        return {"error": f"获取映射失败: {str(e)}"}


@app.post("/debug/simple-query")
async def debug_simple_query():
    """调试：执行最简单的查询"""
    try:
        # 最简单的查询
        simple_query = {
            "size": 1,
            "query": {"match_all": {}}
        }

        patterns = ["apm-*", "apm-*-transaction-*", "*"]
        results = {}

        for pattern in patterns:
            try:
                response = es_client.search(
                    index=pattern,
                    body=simple_query,
                    ignore_unavailable=True,
                    allow_no_indices=True
                )

                if hasattr(response, 'body'):
                    results[pattern] = response.body
                elif hasattr(response, 'to_dict'):
                    results[pattern] = response.to_dict()
                else:
                    results[pattern] = dict(response) if isinstance(response, dict) else str(response)

            except Exception as e:
                results[pattern] = f"错误: {str(e)}"

        return results
    except Exception as e:
        return {"error": f"简单查询失败: {str(e)}"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)