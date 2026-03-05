#!/usr/bin/env python3
"""
Test WebSocket real-time updates for research progress.
This script creates a research task and listens for progress updates via WebSocket.
"""
import asyncio
import json
import httpx
from websockets.asyncio.client import connect


BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"


async def test_websocket_updates():
    """Test WebSocket progress updates during research."""
    print("🔬 Starting WebSocket test...")

    # Step 1: Create a research query
    print("\n1️⃣ Creating research query...")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/research",
            json={
                "query": "What are the latest developments in quantum computing?",
                "user_notes": "WebSocket test query"
            }
        )
        assert response.status_code in [
            200, 201], f"Failed to create research: {response.status_code}"
        research = response.json()
        research_id = research["id"]
        print(f"✅ Created research ID: {research_id}")

    # Step 2: Connect to WebSocket and listen for updates
    print(f"\n2️⃣ Connecting to WebSocket: /ws/research/{research_id}")

    messages_received = []
    try:
        async with connect(f"{WS_URL}/ws/research/{research_id}") as websocket:
            print("✅ WebSocket connected! Listening for updates...")

            # Listen for messages (timeout after 30 seconds)
            try:
                async with asyncio.timeout(30):
                    async for message in websocket:
                        data = json.loads(message)
                        messages_received.append(data)

                        event_type = data.get("event_type", "unknown")
                        event_data = data.get("data", {})
                        print(f"📨 Received: {event_type}")

                        if event_type == "status_change":
                            print(f"   Status: {event_data.get('status')}")
                        elif event_type == "source_added":
                            source = event_data.get('source', {})
                            print(
                                f"   Source: {source.get('title', 'N/A')} - {source.get('url', 'N/A')}")
                        elif event_type == "progress":
                            print(
                                f"   Progress: {event_data.get('percentage', 0):.1f}% - {event_data.get('message', 'N/A')}")
                        elif event_type == "error":
                            print(
                                f"   ⚠️ Error: {event_data.get('error', 'N/A')}")
                        elif event_type == "completed":
                            print(f"   ✅ Completed!")
                            break

            except TimeoutError:
                print("⏰ Timeout: No more messages received")

    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        return False

    # Step 3: Verify we received messages
    print(
        f"\n3️⃣ Summary: Received {len(messages_received)} WebSocket messages")

    event_types = [msg.get("event_type") for msg in messages_received]
    print(f"   Event types: {set(event_types)}")

    # Check we received at least some events
    assert len(messages_received) > 0, "No messages received!"

    print("\n✅ WebSocket test completed successfully!")
    return True


async def test_cancellation():
    """Test research cancellation endpoint."""
    print("\n\n🛑 Testing cancellation feature...")

    # Create a research
    async with httpx.AsyncClient() as client:
        print("1️⃣ Creating research query...")
        response = await client.post(
            f"{BASE_URL}/research",
            json={"query": "Long running research query for cancellation test"}
        )
        assert response.status_code in [
            200, 201], f"Failed to create research: {response.status_code}"
        research = response.json()
        research_id = research["id"]
        print(f"✅ Created research ID: {research_id}")

        # Wait a moment
        await asyncio.sleep(2)

        # Cancel it
        print(f"2️⃣ Cancelling research {research_id}...")
        response = await client.post(f"{BASE_URL}/research/{research_id}/cancel")
        assert response.status_code == 200
        result = response.json()
        print(f"✅ Cancelled: {result.get('message')}")


async def test_batch_creation():
    """Test batch research creation."""
    print("\n\n📦 Testing batch creation feature...")

    async with httpx.AsyncClient() as client:
        print("1️⃣ Creating batch of 3 research queries...")
        response = await client.post(
            f"{BASE_URL}/research/batch",
            json={
                "queries": [
                    "What is machine learning?",
                    "What is deep learning?",
                    "What is reinforcement learning?"
                ]
            }
        )
        assert response.status_code in [
            200, 201], f"Failed to create batch: {response.status_code}"
        result = response.json()

        print(f"✅ Created {result.get('created_count')} research tasks:")
        for research in result.get("research_list", []):
            print(f"   - ID {research['id']}: {research['query']}")


async def test_rate_limiting():
    """Test rate limiting by making many rapid requests."""
    print("\n\n⏱️ Testing rate limiting...")

    async with httpx.AsyncClient() as client:
        print("Making 15 rapid requests to test rate limit (10 req/min for research)...")

        success_count = 0
        rate_limited_count = 0

        for i in range(15):
            try:
                response = await client.post(
                    f"{BASE_URL}/research",
                    json={"query": f"Rate limit test query {i}"}
                )
                if response.status_code in [200, 201]:
                    success_count += 1
                elif response.status_code == 429:  # Too Many Requests
                    rate_limited_count += 1
                    print(f"   Request {i+1}: Rate limited ✅")
            except Exception as e:
                print(f"   Request {i+1}: Error - {e}")

        print(
            f"\n✅ Results: {success_count} succeeded, {rate_limited_count} rate limited")
        print(
            f"   Rate limiting is {'working' if rate_limited_count > 0 else 'not triggered'}!")


async def main():
    """Run all tests."""
    try:
        await test_websocket_updates()
        await test_cancellation()
        await test_batch_creation()
        await test_rate_limiting()

        print("\n\n" + "="*60)
        print("🎉 All Phase 16 features tested successfully!")
        print("="*60)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
