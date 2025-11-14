"""Detailed memory profiling to find memory hogs"""
import sys
import gc
import json
from collections import defaultdict


class MemoryProfiler:
    """Profile memory usage by object type"""

    @staticmethod
    def get_deep_size(obj, seen=None):
        """Recursively calculate deep size of an object"""
        if seen is None:
            seen = set()

        obj_id = id(obj)
        if obj_id in seen:
            return 0

        seen.add(obj_id)
        size = sys.getsizeof(obj)

        if isinstance(obj, dict):
            size += sum(MemoryProfiler.get_deep_size(k, seen) + MemoryProfiler.get_deep_size(v, seen)
                       for k, v in obj.items())
        elif isinstance(obj, (list, tuple, set, frozenset)):
            size += sum(MemoryProfiler.get_deep_size(item, seen) for item in obj)

        return size

    @staticmethod
    def get_object_memory_breakdown():
        """Get memory usage breakdown by object type"""
        gc.collect()  # Force garbage collection first

        type_count = defaultdict(int)
        type_size = defaultdict(int)

        # Get all objects in memory
        all_objects = gc.get_objects()

        for obj in all_objects:
            obj_type = type(obj).__name__
            type_count[obj_type] += 1
            try:
                type_size[obj_type] += sys.getsizeof(obj)
            except:
                pass

        # Sort by size
        sorted_types = sorted(type_size.items(), key=lambda x: x[1], reverse=True)

        breakdown = []
        for obj_type, size_bytes in sorted_types[:20]:  # Top 20
            breakdown.append({
                'type': obj_type,
                'count': type_count[obj_type],
                'size_mb': round(size_bytes / 1024 / 1024, 2),
                'avg_size_kb': round(size_bytes / type_count[obj_type] / 1024, 2)
            })

        return breakdown

    @staticmethod
    def get_crawler_data_size(crawl_results, links, issues):
        """Estimate actual data size with DEEP measurement"""

        # Deep size calculation
        crawl_results_deep = MemoryProfiler.get_deep_size(crawl_results)
        links_deep = MemoryProfiler.get_deep_size(links)
        issues_deep = MemoryProfiler.get_deep_size(issues)

        # Also get JSON size for comparison
        try:
            crawl_json_size = len(json.dumps(crawl_results, default=str))
            links_json_size = len(json.dumps(links, default=str))
            issues_json_size = len(json.dumps(issues, default=str))
        except:
            crawl_json_size = 0
            links_json_size = 0
            issues_json_size = 0

        return {
            'crawl_results_deep_mb': round(crawl_results_deep / 1024 / 1024, 2),
            'crawl_results_json_mb': round(crawl_json_size / 1024 / 1024, 2),
            'crawl_results_count': len(crawl_results),
            'avg_per_url_kb': round(crawl_results_deep / len(crawl_results) / 1024, 2) if crawl_results else 0,

            'links_deep_mb': round(links_deep / 1024 / 1024, 2),
            'links_json_mb': round(links_json_size / 1024 / 1024, 2),
            'links_count': len(links),

            'issues_deep_mb': round(issues_deep / 1024 / 1024, 2),
            'issues_json_mb': round(issues_json_size / 1024 / 1024, 2),
            'issues_count': len(issues),

            'total_deep_mb': round((crawl_results_deep + links_deep + issues_deep) / 1024 / 1024, 2),
            'total_json_mb': round((crawl_json_size + links_json_size + issues_json_size) / 1024 / 1024, 2)
        }
