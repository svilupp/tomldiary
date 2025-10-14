#!/usr/bin/env python3
"""
Demo of MemoryWriter observability features for production deployments.
Shows how to monitor queue health, throughput, and error rates.
"""

import asyncio
from pathlib import Path

from pydantic import BaseModel

from tomldiary import Diary
from tomldiary.backends import LocalBackend
from tomldiary.models import PreferenceItem
from tomldiary.writer import MemoryWriter


# Simple preference schema
class SimplePrefTable(BaseModel):
    """Simple preference table for demo."""

    likes: dict[str, PreferenceItem] = {}
    dislikes: dict[str, PreferenceItem] = {}


# Mock agent that does nothing (for demo purposes)
class NoOpAgent:
    """No-op agent for observability demo - doesn't need to extract anything."""

    async def run(self, message: str, deps=None):  # noqa: ARG002
        """Do nothing - just for observability demo."""
        await asyncio.sleep(0.01)  # Simulate minimal processing time


async def print_stats(writer: MemoryWriter, label: str = "Stats"):
    """Pretty print writer statistics."""
    stats = writer.stats()
    print(f"\n{'=' * 60}")
    print(f"{label}")
    print(f"{'=' * 60}")
    print(
        f"Queue:      {stats['queue_size']:>4} / {stats['queue_capacity']:>4} "
        f"({stats['queue_utilization']:.1%} full)"
    )
    print(
        f"Workers:    {stats['active_workers']:>4} active, "
        f"{stats['idle_workers']:>4} idle ({stats['total_workers']} total)"
    )
    print(f"Submitted:  {stats['submitted']:>4} tasks")
    print(f"Completed:  {stats['completed']:>4} tasks")
    print(f"Failed:     {stats['failed']:>4} tasks")
    print(f"Pending:    {stats['pending']:>4} tasks")
    print(f"Error rate: {stats['error_rate']:.1%}")
    print(f"Running:    {stats['is_running']}")
    print(f"{'=' * 60}\n")


async def health_check(writer: MemoryWriter) -> tuple[str, dict]:
    """
    Example health check function for production deployments.
    Returns status and detailed metrics.
    """
    stats = writer.stats()

    # Determine health status
    if not stats["is_running"]:
        status = "unhealthy"
    elif stats["queue_utilization"] > 0.9 or stats["error_rate"] > 0.1:
        status = "degraded"
    elif stats["queue_utilization"] > 0.7:
        status = "warning"
    else:
        status = "healthy"

    return status, stats


async def simulate_workload(writer: MemoryWriter, num_tasks: int, delay: float = 0.01):
    """Simulate a workload by submitting tasks."""
    print(f"📤 Submitting {num_tasks} tasks...")
    for i in range(num_tasks):
        await writer.submit(
            f"user_{i % 5}",  # Rotate through 5 users
            f"session_{i}",
            f"User message {i}",
            f"Assistant response {i}",
        )
        await asyncio.sleep(delay)  # Simulate request rate
    print(f"✅ All {num_tasks} tasks submitted")


async def main():
    """Demonstrate observability features."""
    print("\n🔍 MemoryWriter Observability Demo\n")

    # Setup
    backend = LocalBackend(Path("./memory_observability_demo"))
    diary = Diary(backend=backend, pref_table_cls=SimplePrefTable, agent=NoOpAgent())

    # Create writer with small queue for demonstration
    writer = MemoryWriter(diary=diary, workers=4, qsize=20)

    # 1. Initial state
    await print_stats(writer, "1. Initial State")

    # 2. Submit some work
    await simulate_workload(writer, num_tasks=10, delay=0.01)
    await print_stats(writer, "2. After Submitting 10 Tasks")

    # 3. Wait for processing
    await asyncio.sleep(0.5)
    await print_stats(writer, "3. After Processing")

    # 4. Simulate burst load
    print("\n💥 Simulating burst load (30 tasks rapidly)...")
    await simulate_workload(writer, num_tasks=30, delay=0.001)
    await print_stats(writer, "4. During Burst Load")

    # 5. Check health status
    status, stats = await health_check(writer)
    print(f"🏥 Health Check: {status.upper()}")
    if status == "warning":
        print("⚠️  Warning: Queue utilization is high")
    elif status == "degraded":
        print("⚠️  Degraded: Queue near capacity or high error rate")

    # 6. Wait for queue to drain
    print("\n⏳ Waiting for queue to drain...")
    while writer.stats()["pending"] > 0:
        await asyncio.sleep(0.1)

    await print_stats(writer, "5. After Queue Drained")

    # 7. Production monitoring example
    print("\n📊 Production Monitoring Example:")
    print("=" * 60)
    stats = writer.stats()

    # Alert conditions
    alerts = []
    if stats["queue_utilization"] > 0.8:
        alerts.append(f"⚠️  High queue utilization: {stats['queue_utilization']:.1%}")
    if stats["error_rate"] > 0.05:
        alerts.append(f"⚠️  Elevated error rate: {stats['error_rate']:.1%}")
    if stats["idle_workers"] == 0:
        alerts.append("⚠️  All workers busy - consider scaling")

    if alerts:
        print("Active Alerts:")
        for alert in alerts:
            print(f"  {alert}")
    else:
        print("✅ No alerts - system healthy")

    print("\nKey Metrics:")
    print(f"  Throughput: {stats['completed']} tasks completed")
    print(f"  Success rate: {(1 - stats['error_rate']):.1%}")
    print(f"  Worker utilization: {stats['active_workers']} / {stats['total_workers']}")
    print("=" * 60)

    # 8. Demonstrate is_running property
    print("\n🔒 Testing is_running property...")
    print(f"Before close: writer.is_running = {writer.is_running}")

    await writer.close()

    print(f"After close:  writer.is_running = {writer.is_running}")

    # Try to submit after close (will raise error)
    try:
        await writer.submit("user1", "session1", "test", "test")
    except RuntimeError as e:
        print(f"✅ Expected error: {e}")

    print("\n✨ Demo complete!\n")


if __name__ == "__main__":
    asyncio.run(main())
