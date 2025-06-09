from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from elasticsearch import Elasticsearch
from datetime import datetime, timedelta
import json
import re

app = FastAPI(title="APM Text2DSL API", version="1.0.0")

# 配置
ES_HOST = "localhost:9200"  # 修改为你的ES地址
# 初始化ES客户端
es_client = Elasticsearch([ES_HOST])


# 请求响应模型
class QueryRequest(BaseModel):
    query: str
    time_range: Optional[str] = "15m"
    language: Optional[str] = "auto"


class DSLRequest(BaseModel):
    dsl: Dict[Any, Any]
    original_query: str
    format: Optional[str] = "summary"


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


def parse_time_range(time_str: str) -> tuple:
    """解析时间范围，支持中英文"""
    now = datetime.utcnow()

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


def generate_dsl_prompt(query: str, time_range: str) -> str:
    """生成LLM提示词"""
    start_time, end_time = parse_time_range(time_range)

    prompt = f"""
你是一个专业的Elasticsearch DSL生成专家。根据用户的APM查询需求，生成对应的Elasticsearch DSL查询。

APM数据结构:
- 事务数据索引: apm-*-transaction-*
- 错误数据索引: apm-*-error-*  
- 指标数据索引: apm-*-metric-*

主要字段:
- service.name: 服务名称
- transaction.name: 接口/事务名称
- transaction.duration.us: 响应时间(微秒)
- @timestamp: 时间戳
- http.response.status_code: HTTP状态码
- error.exception.message: 错误信息

时间范围: {start_time.isoformat()} 到 {end_time.isoformat()}

用户查询: {query}

请生成标准的Elasticsearch DSL查询，要求:
1. 包含正确的时间范围过滤
2. 根据查询类型选择合适的索引
3. 包含必要的聚合查询
4. 只返回JSON格式的DSL，不要其他解释

DSL查询:
"""
    return prompt


def validate_dsl(dsl: Dict[Any, Any]) -> tuple[bool, str]:
    """验证DSL查询的基本结构"""
    try:
        # 检查必需的字段
        if not isinstance(dsl, dict):
            return False, "DSL必须是JSON对象"

        # 检查是否有query或aggs字段
        if 'query' not in dsl and 'aggs' not in dsl:
            return False, "DSL缺少query或aggs字段"

        # 检查时间范围
        if 'query' in dsl:
            query_part = dsl['query']
            if not has_time_filter(query_part):
                return False, "DSL缺少时间范围过滤"

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

        # 执行查询
        response = es_client.search(
            index=index_pattern,
            body=dsl,
            timeout='30s'
        )

        return response

    except Exception as e:
        raise HTTPException(500, detail=f"ES查询执行失败: {str(e)}")


def determine_index_pattern(dsl: Dict[Any, Any]) -> str:
    """根据DSL内容确定索引模式"""
    dsl_str = json.dumps(dsl).lower()

    if 'error' in dsl_str:
        return APM_SCHEMA["error_index"]
    elif 'transaction' in dsl_str or 'duration' in dsl_str:
        return APM_SCHEMA["transaction_index"]
    else:
        return APM_SCHEMA["transaction_index"]  # 默认使用transaction索引


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


@app.post("/generate-dsl", response_model=PromptResponse)
async def generate_dsl(request: QueryRequest):
    """API 1: 根据用户查询生成提示词返回给Dify"""
    try:
        # 生成提示词
        prompt = generate_dsl_prompt(request.query, request.time_range)

        # 确定查询类型
        query_type = determine_query_type(request.query)

        # 生成时间范围信息
        start_time, end_time = parse_time_range(request.time_range)
        time_info = f"{start_time.strftime('%Y-%m-%d %H:%M')} 到 {end_time.strftime('%Y-%m-%d %H:%M')}"

        return PromptResponse(
            prompt=prompt,
            query_type=query_type,
            time_range_info=time_info,
            schema_info=APM_SCHEMA
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提示词生成失败: {str(e)}")


@app.post("/execute-query", response_model=ExecuteResponse)
async def execute_query(request: DSLRequest):
    """API 2: 执行DSL查询并生成分析提示词返回给Dify"""
    try:
        # 验证DSL
        is_valid, validation_msg = validate_dsl(request.dsl)
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
            es_response = execute_es_query(request.dsl)

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
                error_message=f"ES查询执行失败: {str(e)}"
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询处理失败: {str(e)}")


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


@app.get("/health")
async def health_check():
    """健康检查"""
    try:
        # 检查ES连接
        es_client.ping()
        return {"status": "healthy", "elasticsearch": "connected"}
    except:
        return {"status": "unhealthy", "elasticsearch": "disconnected"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)