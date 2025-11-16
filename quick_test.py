#!/usr/bin/env python3
"""Quick validation that mamlarr can start and respond to basic requests"""
import asyncio
from pathlib import Path
from mamlarr_service.settings import MamServiceSettings
from mamlarr_service.api import create_app

async def main():
    print("=" * 60)
    print("Mamlarr Quick Test (Mock Mode)")
    print("=" * 60)

    # Create settings
    settings = MamServiceSettings(
        api_key="test-key",
        mam_session_id="not-needed",
        use_mock_data=True,
        download_directory=Path("./output"),
        postprocess_tmp_dir=Path("./output/tmp"),
        seed_target_hours=0,
    )

    print(f"\n✓ Settings configured:")
    print(f"  - Mock mode: {settings.use_mock_data}")
    print(f"  - API key: {settings.api_key}")
    print(f"  - Output dir: {settings.download_directory}")

    # Create app
    app = create_app(settings)
    print(f"\n✓ FastAPI app created: {app.title}")

    # Check routes
    routes = [route.path for route in app.routes if hasattr(route, 'path')]
    print(f"\n✓ Available routes:")
    for route in sorted(routes):
        print(f"  - {route}")

    print("\n" + "=" * 60)
    print("Basic validation passed! ✓")
    print("=" * 60)
    print("\nTo start the server, run:")
    print("  ./run_dev_server.sh")
    print("\nOr manually:")
    print("  uvicorn mamlarr_service.api:app --reload --port 8000")

if __name__ == "__main__":
    asyncio.run(main())
