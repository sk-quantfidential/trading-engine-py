#!/usr/bin/env python3
"""
Performance Monitoring

This module provides performance monitoring and metrics collection
for trading system infrastructure components.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from collections import deque

import structlog

from .constants import STATS_COLLECTION_INTERVAL

logger = structlog.get_logger()


@dataclass
class PerformanceMetrics:
    """Performance metrics data structure."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time: float = 0.0
    min_response_time: float = float('inf')
    max_response_time: float = 0.0
    last_request_time: Optional[float] = None
    throughput_per_second: float = 0.0


@dataclass
class RequestMetric:
    """Individual request metric."""
    timestamp: float
    duration: float
    success: bool
    operation: str


class PerformanceMonitor:
    """Performance monitor for tracking service metrics."""

    def __init__(self, service_name: str, window_size: int = 1000):
        self.service_name = service_name
        self.window_size = window_size

        # Rolling window of recent requests
        self._request_history: deque = deque(maxlen=window_size)

        # Aggregate metrics
        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._total_duration = 0.0
        self._min_duration = float('inf')
        self._max_duration = 0.0
        self._last_request_time: Optional[float] = None

        # Window for throughput calculation
        self._throughput_window = deque(maxlen=60)  # 60 seconds
        self._last_throughput_update = time.time()

        self._logger = logger.bind(
            component="performance_monitor",
            service=service_name
        )

    def record_request(self, duration: float, success: bool, operation: str = "unknown"):
        """Record a request metric."""
        current_time = time.time()

        # Create request metric
        metric = RequestMetric(
            timestamp=current_time,
            duration=duration,
            success=success,
            operation=operation
        )

        # Add to rolling window
        self._request_history.append(metric)

        # Update aggregate metrics
        self._total_requests += 1
        self._total_duration += duration
        self._last_request_time = current_time

        if success:
            self._successful_requests += 1
        else:
            self._failed_requests += 1

        # Update min/max duration
        if duration < self._min_duration:
            self._min_duration = duration
        if duration > self._max_duration:
            self._max_duration = duration

        # Update throughput tracking
        self._update_throughput()

        self._logger.debug(
            "Request recorded",
            operation=operation,
            duration_ms=duration * 1000,
            success=success
        )

    def _update_throughput(self):
        """Update throughput calculation."""
        current_time = time.time()

        # Add current timestamp
        self._throughput_window.append(current_time)

        # Clean up old timestamps (older than 60 seconds)
        cutoff_time = current_time - 60
        while self._throughput_window and self._throughput_window[0] < cutoff_time:
            self._throughput_window.popleft()

    def get_metrics(self) -> PerformanceMetrics:
        """Get current performance metrics."""
        # Calculate average response time
        avg_response_time = (
            self._total_duration / self._total_requests
            if self._total_requests > 0 else 0.0
        )

        # Calculate throughput (requests per second in last 60 seconds)
        throughput = len(self._throughput_window) / 60.0

        return PerformanceMetrics(
            total_requests=self._total_requests,
            successful_requests=self._successful_requests,
            failed_requests=self._failed_requests,
            average_response_time=avg_response_time,
            min_response_time=self._min_duration if self._min_duration != float('inf') else 0.0,
            max_response_time=self._max_duration,
            last_request_time=self._last_request_time,
            throughput_per_second=throughput
        )

    def get_recent_metrics(self, seconds: int = 60) -> PerformanceMetrics:
        """Get metrics for recent requests within specified time window."""
        cutoff_time = time.time() - seconds
        recent_requests = [
            req for req in self._request_history
            if req.timestamp >= cutoff_time
        ]

        if not recent_requests:
            return PerformanceMetrics()

        # Calculate metrics for recent requests
        total_requests = len(recent_requests)
        successful_requests = sum(1 for req in recent_requests if req.success)
        failed_requests = total_requests - successful_requests

        durations = [req.duration for req in recent_requests]
        total_duration = sum(durations)
        avg_response_time = total_duration / total_requests
        min_response_time = min(durations)
        max_response_time = max(durations)

        last_request_time = max(req.timestamp for req in recent_requests)
        throughput = total_requests / seconds

        return PerformanceMetrics(
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            average_response_time=avg_response_time,
            min_response_time=min_response_time,
            max_response_time=max_response_time,
            last_request_time=last_request_time,
            throughput_per_second=throughput
        )

    def get_operation_metrics(self) -> Dict[str, PerformanceMetrics]:
        """Get metrics broken down by operation."""
        operation_groups: Dict[str, List[RequestMetric]] = {}

        # Group requests by operation
        for req in self._request_history:
            if req.operation not in operation_groups:
                operation_groups[req.operation] = []
            operation_groups[req.operation].append(req)

        # Calculate metrics for each operation
        operation_metrics = {}
        for operation, requests in operation_groups.items():
            total_requests = len(requests)
            successful_requests = sum(1 for req in requests if req.success)
            failed_requests = total_requests - successful_requests

            durations = [req.duration for req in requests]
            total_duration = sum(durations)
            avg_response_time = total_duration / total_requests
            min_response_time = min(durations)
            max_response_time = max(durations)

            last_request_time = max(req.timestamp for req in requests)

            # Calculate throughput for this operation
            window_seconds = 60
            recent_requests = [
                req for req in requests
                if req.timestamp >= time.time() - window_seconds
            ]
            throughput = len(recent_requests) / window_seconds

            operation_metrics[operation] = PerformanceMetrics(
                total_requests=total_requests,
                successful_requests=successful_requests,
                failed_requests=failed_requests,
                average_response_time=avg_response_time,
                min_response_time=min_response_time,
                max_response_time=max_response_time,
                last_request_time=last_request_time,
                throughput_per_second=throughput
            )

        return operation_metrics

    def reset_metrics(self):
        """Reset all metrics."""
        self._request_history.clear()
        self._throughput_window.clear()

        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._total_duration = 0.0
        self._min_duration = float('inf')
        self._max_duration = 0.0
        self._last_request_time = None

        self._logger.info("Performance metrics reset")

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status based on performance metrics."""
        metrics = self.get_recent_metrics(60)  # Last 60 seconds

        # Calculate success rate
        success_rate = (
            metrics.successful_requests / metrics.total_requests
            if metrics.total_requests > 0 else 1.0
        )

        # Determine health status
        if success_rate >= 0.95:
            status = "healthy"
        elif success_rate >= 0.90:
            status = "degraded"
        else:
            status = "unhealthy"

        return {
            "status": status,
            "success_rate": success_rate,
            "average_response_time": metrics.average_response_time,
            "throughput": metrics.throughput_per_second,
            "total_requests": metrics.total_requests
        }