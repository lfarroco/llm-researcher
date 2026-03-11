#!/usr/bin/env python3
"""
Test research list filtering functionality
"""
import requests
import time

BASE_URL = "http://localhost:8000"


def test_research_filtering():
    """Test the filtering capabilities of the research list endpoint"""
    print("=== Testing Research Filtering ===\n")

# Step 1: Create test researches with unique searchable text (limited to 3 to respect rate limit)
    print("Step 1: Creating test researches with unique text...")
    research_ids = []
    
    test_queries = [
        ("FILTERTEST_machine_learning basics", "Test notes for ML"),
        ("FILTERTEST_neural_networks explained", "Important neural notes"),
        ("FILTERTEST_quantum_computing basics", "Quantum test notes")
    ]

    for i, (query, notes) in enumerate(test_queries):
        # Add delay every 3 requests to respect rate limit (burst_size=3)
        if i > 0 and i % 3 == 0:
            print("   (waiting for rate limit...)")
            time.sleep(7)

        response = requests.post(
            f"{BASE_URL}/research",
            json={"query": query, "user_notes": notes}
        )
        assert response.status_code in [
            200, 201], f"Failed to create research: {response.text}"
        research = response.json()
        research_id = research["id"]
        research_ids.append(research_id)
        print(f"   ✓ Created research ID {research_id}: {query[:50]}...")

    # Step 2: Test search filter by query text
    print("\nStep 2: Testing search filter (FILTERTEST_machine)...")
    response = requests.get(f"{BASE_URL}/research?search=FILTERTEST_machine")
    assert response.status_code == 200
    filtered = response.json()
    machine_count = len([r for r in filtered if r["id"] in research_ids and "FILTERTEST_machine" in r["query"]])
    print(f"   ✓ Found {machine_count} of our researches containing 'FILTERTEST_machine' (expected 1)")
    assert machine_count == 1, f"Expected 1 match, got {machine_count}"

    # Step 3: Test search filter by notes text
    print("\nStep 3: Testing search filter in notes (Important)...")
    response = requests.get(f"{BASE_URL}/research?search=Important")
    assert response.status_code == 200
    filtered = response.json()
    notes_count = len([r for r in filtered if r["id"] in research_ids and r.get("user_notes") and "Important" in r["user_notes"]])
    print(f"   ✓ Found {notes_count} of our researches with 'Important' in notes (expected 1)")
    assert notes_count == 1, f"Expected 1 match, got {notes_count}"

    # Step 4: Test search filter with broader match
    print("\nStep 4: Testing search filter (FILTERTEST - should match all)...")
    response = requests.get(f"{BASE_URL}/research?search=FILTERTEST")
    assert response.status_code == 200
    filtered = response.json()
    filtertest_count = len([r for r in filtered if r["id"] in research_ids])
    print(
        f"   ✓ Found {filtertest_count} of our researches with 'FILTERTEST' (expected 3)")
    assert filtertest_count == 3, f"Expected 3 matches, got {filtertest_count}"

    # Step 5: Test status filter (use actual status of created researches)
    print("\nStep 5: Testing status filter...")
    # Wait a bit for researches to start processing
    time.sleep(3)
    # Get actual status of our first research
    response = requests.get(f"{BASE_URL}/research")
    all_researches = response.json()
    our_first_research = next((r for r in all_researches if r["id"] == research_ids[0]), None)
    actual_status = our_first_research["status"] if our_first_research else "error"
    print(f"   Testing filter for status: {actual_status}")
    
    # Filter by that status
    response = requests.get(f"{BASE_URL}/research?status={actual_status}")
    assert response.status_code == 200
    filtered = response.json()
    status_ids = [r["id"] for r in filtered if r["id"] in research_ids]
    print(
        f"   ✓ Found {len(status_ids)} of our test researches with '{actual_status}' status")
    # At least some should match
    assert len(status_ids) >= 1, f"Expected at least 1 with status '{actual_status}', got {len(status_ids)}"

    # Step 6: Test combined filters (status + search)
    print(f"\nStep 6: Testing combined filters ({actual_status} + quantum)...")
    response = requests.get(
        f"{BASE_URL}/research?status={actual_status}&search=quantum")
    assert response.status_code == 200
    filtered = response.json()
    combined_count = len([r for r in filtered if r["id"]
                         in research_ids and "quantum" in r["query"]])
    print(
        f"   ✓ Found {combined_count} '{actual_status}' researches matching 'quantum' (expected 1)")
    assert combined_count == 1, f"Expected 1 match, got {combined_count}"

    # Step 7: Test case insensitivity
    print("\nStep 7: Testing case-insensitive search (MACHINE - uppercase)...")
    response = requests.get(f"{BASE_URL}/research?search=MACHINE")
    assert response.status_code == 200
    filtered = response.json()
    machine_count = len([r for r in filtered if r["id"] in research_ids])
    print(
        f"   ✓ Found {machine_count} researches matching 'MACHINE' (case-insensitive, expected 1)")
    assert machine_count == 1, f"Expected 1 match, got {machine_count}"

    # Step 8: Test no filters (should include all our test entries)
    print("\nStep 8: Testing no filters (all researches)...")
    response = requests.get(f"{BASE_URL}/research")
    assert response.status_code == 200
    all_researches = response.json()
    our_researches = [r for r in all_researches if r["id"] in research_ids]
    print(
        f"   ✓ Found all {len(our_researches)} test researches in unfiltered list")
    assert len(our_researches) == 3, f"Expected 3 test researches"

    # Cleanup: Delete test researches
    print("\nCleaning up test researches...")
    for research_id in research_ids:
        response = requests.delete(f"{BASE_URL}/research/{research_id}")
        assert response.status_code == 204, f"Failed to delete research {research_id}"
        print(f"   ✓ Deleted research ID {research_id}")

    print("\n✅ All Research Filtering Tests Passed!")


if __name__ == "__main__":
    try:
        test_research_filtering()
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        exit(1)
