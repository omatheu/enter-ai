"""Performance test script for extraction endpoint."""

import asyncio
import json
import time
from pathlib import Path

import aiohttp

BASE_DIR = Path(__file__).resolve().parents[2]
DATASET_PATH = BASE_DIR / "docs" / "data" / "dataset.json"
FILES_DIR = BASE_DIR / "docs" / "files"
API_URL = "http://localhost:8001/extract"


async def single_extraction(session: aiohttp.ClientSession, item: dict) -> dict:
    """Test a single extraction request."""
    pdf_path = FILES_DIR / item["pdf_path"]

    if not pdf_path.exists():
        return {
            "pdf": item["pdf_path"],
            "error": "File not found",
            "duration": 0,
        }

    data = aiohttp.FormData()
    data.add_field("label", item["label"])
    data.add_field("extraction_schema", json.dumps(item["extraction_schema"]))
    data.add_field(
        "pdf_file",
        open(pdf_path, "rb"),
        filename=item["pdf_path"],
        content_type="application/pdf",
    )

    start = time.perf_counter()
    try:
        async with session.post(API_URL, data=data) as response:
            duration = time.perf_counter() - start
            if response.status == 200:
                result = await response.json()
                return {
                    "pdf": item["pdf_path"],
                    "duration": duration,
                    "status": "success",
                    "metadata": result.get("metadata", {}),
                }
            else:
                return {
                    "pdf": item["pdf_path"],
                    "duration": duration,
                    "status": "error",
                    "error": await response.text(),
                }
    except Exception as e:
        duration = time.perf_counter() - start
        return {
            "pdf": item["pdf_path"],
            "duration": duration,
            "status": "error",
            "error": str(e),
        }


async def run_sequential():
    """Test sequential processing."""
    print("\n=== Sequential Processing Test ===")

    with open(DATASET_PATH) as f:
        dataset = json.load(f)

    # Limit to first 5 items for testing
    test_items = dataset[:5]

    async with aiohttp.ClientSession() as session:
        total_start = time.perf_counter()
        results = []

        for item in test_items:
            result = await single_extraction(session, item)
            results.append(result)
            print(
                f"  {result['pdf']}: {result['duration']:.2f}s ({result['status']})"
            )

        total_duration = time.perf_counter() - total_start

    print(f"\nTotal time: {total_duration:.2f}s")
    print(f"Average per PDF: {total_duration / len(test_items):.2f}s")

    return results, total_duration


async def run_parallel():
    """Test parallel processing."""
    print("\n=== Parallel Processing Test ===")

    with open(DATASET_PATH) as f:
        dataset = json.load(f)

    # Limit to first 5 items for testing
    test_items = dataset[:5]

    async with aiohttp.ClientSession() as session:
        total_start = time.perf_counter()

        # Launch all requests in parallel
        tasks = [single_extraction(session, item) for item in test_items]
        results = await asyncio.gather(*tasks)

        total_duration = time.perf_counter() - total_start

    for result in results:
        print(f"  {result['pdf']}: {result['duration']:.2f}s ({result['status']})")

    print(f"\nTotal time: {total_duration:.2f}s")
    print(f"Average per PDF: {total_duration / len(test_items):.2f}s")
    print(f"Speedup: {(sum(r['duration'] for r in results) / total_duration):.2f}x")

    return results, total_duration


async def run_cache_performance():
    """Test cache performance with same PDF."""
    print("\n=== Cache Performance Test ===")

    with open(DATASET_PATH) as f:
        dataset = json.load(f)

    test_item = dataset[0]

    async with aiohttp.ClientSession() as session:
        # First call (no cache)
        print("First call (cold):")
        result1 = await single_extraction(session, test_item)
        print(f"  Duration: {result1['duration']:.2f}s")

        # Second call (should hit cache)
        print("\nSecond call (cached):")
        result2 = await single_extraction(session, test_item)
        print(f"  Duration: {result2['duration']:.2f}s")
        print(f"  Speedup: {result1['duration'] / result2['duration']:.2f}x")
        print(
            f"  Source: {result2.get('metadata', {}).get('source', 'unknown')}"
        )


async def main():
    """Run all performance tests."""
    print("Performance Testing for Enter AI Extraction API")
    print("=" * 50)

    # Test cache
    await run_cache_performance()

    # Test sequential
    seq_results, seq_time = await run_sequential()

    # Test parallel
    par_results, par_time = await run_parallel()

    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Sequential: {seq_time:.2f}s total")
    print(f"Parallel: {par_time:.2f}s total")
    print(f"Speedup: {seq_time / par_time:.2f}x")

    # Check if meets 10 second goal
    if par_time < 10:
        print(f"\n✓ Goal achieved! Parallel processing under 10s: {par_time:.2f}s")
    else:
        print(
            f"\n✗ Goal not met. Parallel processing took {par_time:.2f}s (target: <10s)"
        )


if __name__ == "__main__":
    asyncio.run(main())
