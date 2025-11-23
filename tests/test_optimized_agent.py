"""
Testing và Benchmarking cho Optimized Agent

So sánh performance giữa:
- Original Agent (OpenAI tools agent)
- Optimized Agent (LangGraph với query routing, parallel tools, caching)
"""

import asyncio
import time
import logging
from typing import Dict, Any, List
from tabulate import tabulate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def benchmark_agent(
    test_queries: List[str],
    sender_id: str = "test_sender_123",
    page_id: str = "test_page_456",
    bot_id: str = None,
    use_optimized: bool = True
) -> Dict[str, Any]:
    """
    Benchmark agent với danh sách queries
    
    Args:
        test_queries: Danh sách queries để test
        sender_id: Test sender ID
        page_id: Test page ID
        bot_id: Bot ID
        use_optimized: True = dùng optimized agent, False = dùng original
        
    Returns:
        Dict chứa metrics
    """
    try:
        from bot.bot_facebook_messenger import bot_facebook_messenger
        
        # Initialize
        if not bot_facebook_messenger.factory:
            await bot_facebook_messenger.initialize()
        
        results = []
        total_time = 0
        
        for idx, query in enumerate(test_queries, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"Test {idx}/{len(test_queries)}: {query[:50]}...")
            logger.info(f"{'='*60}")
            
            start_time = time.time()
            
            try:
                if use_optimized:
                    # Use optimized agent
                    from bot.integration import process_message_with_optimized_agent
                    response = await process_message_with_optimized_agent(
                        bot_agent=bot_facebook_messenger,
                        sender_id=sender_id,
                        page_id=page_id,
                        bot_id=bot_id,
                        message=query,
                        company_id=None
                    )
                else:
                    # Use original agent
                    response = await bot_facebook_messenger.process_message_immediate(
                        sender_id=sender_id,
                        page_id=page_id,
                        bot_id=bot_id,
                        message=query,
                        send_facebook=False,
                        company_id=None
                    )
                
                processing_time = time.time() - start_time
                total_time += processing_time
                
                # Extract metadata
                metadata = response.metadata if hasattr(response, 'metadata') else {}
                intent = metadata.get("intent", "unknown")
                tools_called = metadata.get("tools_called", [])
                performance = metadata.get("performance", {})
                
                results.append({
                    "query": query[:50] + "..." if len(query) > 50 else query,
                    "time": processing_time,
                    "intent": intent,
                    "tools": ", ".join(tools_called) if tools_called else "none",
                    "success": "error" not in metadata,
                    "cache_hit_rate": performance.get("cache_stats", {}).get("hit_rate", 0)
                })
                
                logger.info(f"✅ Completed in {processing_time:.2f}s | Intent: {intent} | Tools: {tools_called}")
                
            except Exception as e:
                processing_time = time.time() - start_time
                total_time += processing_time
                
                results.append({
                    "query": query[:50] + "..." if len(query) > 50 else query,
                    "time": processing_time,
                    "intent": "error",
                    "tools": "error",
                    "success": False,
                    "cache_hit_rate": 0
                })
                
                logger.error(f"❌ Error: {e}")
        
        # Calculate metrics
        avg_time = total_time / len(test_queries)
        success_rate = sum(1 for r in results if r["success"]) / len(results)
        avg_cache_hit = sum(r["cache_hit_rate"] for r in results) / len(results)
        
        return {
            "agent_type": "Optimized" if use_optimized else "Original",
            "total_queries": len(test_queries),
            "total_time": total_time,
            "avg_time": avg_time,
            "success_rate": success_rate,
            "avg_cache_hit_rate": avg_cache_hit,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"❌ Benchmark error: {e}")
        return {
            "agent_type": "Error",
            "total_queries": 0,
            "total_time": 0,
            "avg_time": 0,
            "success_rate": 0,
            "avg_cache_hit_rate": 0,
            "results": []
        }


async def compare_agents(test_queries: List[str]) -> None:
    """
    So sánh performance giữa Original và Optimized agent
    
    Args:
        test_queries: Danh sách queries để test
    """
    logger.info("\n" + "="*80)
    logger.info("🏁 STARTING AGENT COMPARISON BENCHMARK")
    logger.info("="*80)
    
    # Test Original Agent
    logger.info("\n📊 Testing ORIGINAL Agent...")
    original_results = await benchmark_agent(test_queries, use_optimized=False)
    
    # Wait a bit
    await asyncio.sleep(2)
    
    # Test Optimized Agent
    logger.info("\n📊 Testing OPTIMIZED Agent...")
    optimized_results = await benchmark_agent(test_queries, use_optimized=True)
    
    # Print comparison
    logger.info("\n" + "="*80)
    logger.info("📊 COMPARISON RESULTS")
    logger.info("="*80)
    
    comparison_table = [
        ["Metric", "Original", "Optimized", "Improvement"],
        ["Total Time (s)", f"{original_results['total_time']:.2f}", 
         f"{optimized_results['total_time']:.2f}",
         f"{((original_results['total_time'] - optimized_results['total_time']) / original_results['total_time'] * 100):.1f}%"],
        ["Avg Time (s)", f"{original_results['avg_time']:.2f}",
         f"{optimized_results['avg_time']:.2f}",
         f"{((original_results['avg_time'] - optimized_results['avg_time']) / original_results['avg_time'] * 100):.1f}%"],
        ["Success Rate", f"{original_results['success_rate']:.1%}",
         f"{optimized_results['success_rate']:.1%}",
         f"+{(optimized_results['success_rate'] - original_results['success_rate']) * 100:.1f}%"],
        ["Cache Hit Rate", f"{original_results['avg_cache_hit_rate']:.1%}",
         f"{optimized_results['avg_cache_hit_rate']:.1%}",
         f"+{(optimized_results['avg_cache_hit_rate'] - original_results['avg_cache_hit_rate']) * 100:.1f}%"],
    ]
    
    print("\n" + tabulate(comparison_table, headers="firstrow", tablefmt="grid"))
    
    # Detailed results
    logger.info("\n📋 Detailed Results - Original Agent:")
    original_table = [
        ["Query", "Time (s)", "Intent", "Tools", "Success"]
    ]
    for r in original_results['results']:
        original_table.append([
            r['query'], f"{r['time']:.2f}", r['intent'], 
            r['tools'], "✅" if r['success'] else "❌"
        ])
    print("\n" + tabulate(original_table, headers="firstrow", tablefmt="simple"))
    
    logger.info("\n📋 Detailed Results - Optimized Agent:")
    optimized_table = [
        ["Query", "Time (s)", "Intent", "Tools", "Cache Hit", "Success"]
    ]
    for r in optimized_results['results']:
        optimized_table.append([
            r['query'], f"{r['time']:.2f}", r['intent'],
            r['tools'], f"{r['cache_hit_rate']:.1%}", "✅" if r['success'] else "❌"
        ])
    print("\n" + tabulate(optimized_table, headers="firstrow", tablefmt="simple"))
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("🎯 SUMMARY")
    logger.info("="*80)
    
    if optimized_results['avg_time'] < original_results['avg_time']:
        speedup = original_results['avg_time'] / optimized_results['avg_time']
        logger.info(f"✅ Optimized agent is {speedup:.2f}x FASTER than original!")
    else:
        logger.info(f"⚠️ Optimized agent is slower (needs tuning)")
    
    if optimized_results['success_rate'] >= original_results['success_rate']:
        logger.info(f"✅ Success rate maintained or improved")
    else:
        logger.info(f"⚠️ Success rate decreased (needs investigation)")
    
    if optimized_results['avg_cache_hit_rate'] > 0:
        logger.info(f"✅ Cache is working with {optimized_results['avg_cache_hit_rate']:.1%} hit rate")


# ==================== EXAMPLE USAGE ====================
async def main():
    """Main test function"""
    
    # Danh sách test queries đa dạng
    test_queries = [
        # Product search queries
        "có sản phẩm iphone nào không?",
        "tìm túi giá dưới 500k",
        "show cho em mã sản phẩm 38301",
        "túi maggie còn hàng không?",
        
        # Knowledge queries
        "chính sách đổi trả như thế nào?",
        "shop có ship cod không?",
        "thanh toán qua chuyển khoản được không?",
        
        # Mixed queries
        "cho em xem túi màu đen giá rẻ và cho biết chính sách bảo hành",
        "có giày thể thao nào dưới 1 triệu không và ship mất bao lâu?",
        
        # General queries
        "xin chào shop",
        "cảm ơn nhé",
    ]
    
    # Run comparison
    await compare_agents(test_queries)
    
    # Get performance metrics từ optimized agent
    from bot.optimized_processor import optimized_processor
    
    logger.info("\n" + "="*80)
    logger.info("📊 OPTIMIZED AGENT METRICS")
    logger.info("="*80)
    
    metrics = optimized_processor.get_performance_metrics()
    cache_stats = optimized_processor.get_cache_stats()
    
    metrics_table = [
        ["Metric", "Value"],
        ["Total Requests", metrics['total_requests']],
        ["Successful", metrics['successful_requests']],
        ["Failed", metrics['failed_requests']],
        ["Avg Response Time (s)", f"{metrics['avg_response_time']:.2f}"],
        ["Cache Size", cache_stats['size']],
        ["Cache Hit Rate", f"{cache_stats['hit_rate']:.1%}"],
    ]
    
    print("\n" + tabulate(metrics_table, headers="firstrow", tablefmt="grid"))
    
    # Tool usage distribution
    if metrics['tool_call_counts']:
        logger.info("\n🔧 Tool Usage Distribution:")
        tool_table = [["Tool", "Call Count"]]
        for tool, count in sorted(metrics['tool_call_counts'].items(), key=lambda x: x[1], reverse=True):
            tool_table.append([tool, count])
        print(tabulate(tool_table, headers="firstrow", tablefmt="simple"))
    
    # Intent distribution
    if metrics['intent_distribution']:
        logger.info("\n🎯 Intent Distribution:")
        intent_table = [["Intent", "Count"]]
        for intent, count in sorted(metrics['intent_distribution'].items(), key=lambda x: x[1], reverse=True):
            intent_table.append([intent, count])
        print(tabulate(intent_table, headers="firstrow", tablefmt="simple"))


if __name__ == "__main__":
    asyncio.run(main())
