"""Memory usage monitoring for crawler instances"""
import psutil
import sys
import threading
from datetime import datetime


class MemoryMonitor:
    """Monitors memory usage for the crawler and system"""

    def __init__(self):
        self.process = psutil.Process()
        self.peak_memory_mb = 0
        self.current_memory_mb = 0
        self.start_memory_mb = 0
        self.monitor_lock = threading.Lock()

    def start_monitoring(self):
        """Start monitoring - record baseline memory"""
        with self.monitor_lock:
            self.start_memory_mb = self._get_process_memory_mb()
            self.peak_memory_mb = self.start_memory_mb
            self.current_memory_mb = self.start_memory_mb

    def update(self):
        """Update current memory usage and track peak"""
        with self.monitor_lock:
            self.current_memory_mb = self._get_process_memory_mb()
            if self.current_memory_mb > self.peak_memory_mb:
                self.peak_memory_mb = self.current_memory_mb

    def get_stats(self):
        """Get memory statistics"""
        with self.monitor_lock:
            # Update before returning stats
            self.current_memory_mb = self._get_process_memory_mb()
            if self.current_memory_mb > self.peak_memory_mb:
                self.peak_memory_mb = self.current_memory_mb

            # System memory
            system_memory = psutil.virtual_memory()

            return {
                'process': {
                    'current_mb': round(self.current_memory_mb, 2),
                    'peak_mb': round(self.peak_memory_mb, 2),
                    'start_mb': round(self.start_memory_mb, 2),
                    'delta_mb': round(self.current_memory_mb - self.start_memory_mb, 2)
                },
                'system': {
                    'total_mb': round(system_memory.total / 1024 / 1024, 2),
                    'available_mb': round(system_memory.available / 1024 / 1024, 2),
                    'used_mb': round(system_memory.used / 1024 / 1024, 2),
                    'percent': system_memory.percent
                },
                'timestamp': datetime.now().isoformat()
            }

    def _get_process_memory_mb(self):
        """Get current process memory usage in MB"""
        try:
            # Get RSS (Resident Set Size) - actual physical memory used
            memory_info = self.process.memory_info()
            return memory_info.rss / 1024 / 1024  # Convert bytes to MB
        except Exception as e:
            print(f"Error getting memory info: {e}")
            return 0

    def estimate_crawl_memory(self, num_urls):
        """Estimate memory needed for a crawl based on current usage per URL"""
        with self.monitor_lock:
            if self.start_memory_mb == 0 or num_urls == 0:
                # No baseline yet, use default estimate
                mb_per_url = 0.002  # ~2KB per URL (conservative)
            else:
                # Calculate from actual delta (memory growth since start)
                delta = self.current_memory_mb - self.start_memory_mb
                if delta > 0 and num_urls > 0:
                    # Estimate based on actual data growth
                    mb_per_url = delta / num_urls
                else:
                    mb_per_url = 0.002

            # Add 20% buffer for safety
            estimated_mb = (num_urls * mb_per_url) * 1.2

            return {
                'estimated_total_mb': round(estimated_mb, 2),
                'mb_per_url': round(mb_per_url, 4),
                'kb_per_url': round(mb_per_url * 1024, 2),
                'estimated_for_1m_urls': round(mb_per_url * 1_000_000, 2),
                'estimated_for_5m_urls': round(mb_per_url * 5_000_000, 2),
                'estimated_for_10m_urls': round(mb_per_url * 10_000_000, 2)
            }

    def reset(self):
        """Reset monitoring"""
        with self.monitor_lock:
            self.start_memory_mb = self._get_process_memory_mb()
            self.peak_memory_mb = self.start_memory_mb
            self.current_memory_mb = self.start_memory_mb
