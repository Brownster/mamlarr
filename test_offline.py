#!/usr/bin/env python3
"""
Offline testing script for mamlarr service.
Runs the service with use_mock_data=True and tests the full workflow.
"""
import asyncio
import httpx
from mamlarr_service.settings import MamServiceSettings
from mamlarr_service.api import create_app
from pathlib import Path


async def test_offline():
    """Test the mamlarr service in offline/mock mode"""

    # Configure for offline testing
    settings = MamServiceSettings(
        api_key="test-api-key",
        mam_session_id="not-needed-in-mock-mode",
        use_mock_data=True,
        download_directory=Path("./output"),
        postprocess_tmp_dir=Path("./output/tmp"),
        enable_audio_merge=False,  # Disable for simple testing
        seed_target_hours=0,  # Skip seeding delay for testing
    )

    # Create the app
    app = create_app(settings)

    # Use TestClient for testing
    from fastapi.testclient import TestClient
    client = TestClient(app)

    headers = {"X-Api-Key": "test-api-key"}

    print("=" * 60)
    print("Testing Mamlarr in Offline Mode")
    print("=" * 60)

    # Test 1: Health check
    print("\n1. Testing health endpoint...")
    response = client.get("/health")
    assert response.status_code == 200
    print(f"   ✓ Health check: {response.json()}")

    # Test 2: Get indexers
    print("\n2. Testing indexer endpoint...")
    response = client.get("/api/v1/indexer", headers=headers)
    assert response.status_code == 200
    indexers = response.json()
    print(f"   ✓ Indexers: {indexers}")

    # Test 3: Search
    print("\n3. Testing search endpoint...")
    response = client.get(
        "/api/v1/search",
        params={"query": "test audiobook", "limit": 10, "offset": 0},
        headers=headers,
    )
    assert response.status_code == 200
    results = response.json()
    print(f"   ✓ Search returned {len(results)} results")

    if results:
        result = results[0]
        print(f"   - Title: {result['title']}")
        print(f"   - GUID: {result['guid']}")
        print(f"   - Size: {result['size']} bytes")
        print(f"   - Seeders: {result['seeders']}")

        # Test 4: Download
        print("\n4. Testing download endpoint...")
        download_payload = {
            "guid": result["guid"],
            "indexerId": result["indexerId"]
        }
        response = client.post(
            "/api/v1/search",
            json=download_payload,
            headers=headers,
        )
        assert response.status_code == 200
        download_response = response.json()
        print(f"   ✓ Download queued: {download_response}")
        job_id = download_response["jobId"]

        # Test 5: Check job status
        print("\n5. Checking job status...")
        await asyncio.sleep(2)  # Give it time to process
        response = client.get(f"/api/v1/jobs/{job_id}", headers=headers)
        assert response.status_code == 200
        job = response.json()["job"]
        print(f"   ✓ Job status: {job['status']}")
        print(f"   - Message: {job.get('message', 'N/A')}")
        if job.get("destination_path"):
            print(f"   - Destination: {job['destination_path']}")

    print("\n" + "=" * 60)
    print("Offline test completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_offline())
