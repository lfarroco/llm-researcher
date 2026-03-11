#!/usr/bin/env python3
"""
Test script for Finding CRUD operations.
"""
import requests
import sys

BASE_URL = "http://localhost:8000"


def test_finding_crud():
    """Test creating, updating, and deleting a finding."""
    print("Testing Finding CRUD operations...")

    # Step 1: Create a research
    print("\n1. Creating test research...")
    res = requests.post(f"{BASE_URL}/research", json={
        "query": "Testing finding CRUD operations",
    })

    if res.status_code not in [200, 201]:
        print(f"❌ Failed to create research: {res.status_code} - {res.text}")
        return False

    research_id = res.json()["id"]
    print(f"✓ Created research with ID: {research_id}")

    # Step 2: Create a source (to link to finding later)
    print("\n2. Creating a test source...")
    source_data = {
        "url": "https://example.com/test-source",
        "title": "Test Source for Findings",
        "source_type": "web",
    }

    res = requests.post(
        f"{BASE_URL}/research/{research_id}/sources", json=source_data)

    if res.status_code != 201:
        print(f"❌ Failed to create source: {res.status_code} - {res.text}")
        return False

    source_id = res.json()["id"]
    print(f"✓ Created source with ID: {source_id}")

    # Step 3: Create a finding without sources
    print("\n3. Creating a test finding (no sources)...")
    finding_data = {
        "content": "This is a test finding to validate CRUD operations.",
    }

    res = requests.post(
        f"{BASE_URL}/research/{research_id}/findings", json=finding_data)

    if res.status_code != 201:
        print(f"❌ Failed to create finding: {res.status_code} - {res.text}")
        return False

    finding = res.json()
    finding_id = finding["id"]
    print(f"✓ Created finding with ID: {finding_id}")
    print(f"  Content: {finding['content']}")
    print(f"  Sources: {finding.get('source_ids', [])}")

    # Step 4: Create a finding with sources
    print("\n4. Creating a finding linked to source...")
    finding_data2 = {
        "content": "This finding is linked to a source.",
        "source_ids": [source_id]
    }

    res = requests.post(
        f"{BASE_URL}/research/{research_id}/findings", json=finding_data2)

    if res.status_code != 201:
        print(
            f"❌ Failed to create finding with source: {res.status_code} - {res.text}")
        return False

    finding2 = res.json()
    finding2_id = finding2["id"]
    print(f"✓ Created finding with ID: {finding2_id}")
    print(f"  Linked sources: {finding2.get('source_ids', [])}")

    # Step 5: Get findings
    print("\n5. Fetching findings...")
    res = requests.get(f"{BASE_URL}/research/{research_id}/findings")

    if res.status_code != 200:
        print(f"❌ Failed to get findings: {res.status_code} - {res.text}")
        return False

    findings = res.json()
    print(f"✓ Found {len(findings)} finding(s)")

    # Step 6: Update finding content
    print("\n6. Updating finding content...")
    update_data = {
        "content": "This is the updated content for the finding.",
    }

    res = requests.patch(
        f"{BASE_URL}/research/{research_id}/findings/{finding_id}", json=update_data)

    if res.status_code != 200:
        print(f"❌ Failed to update finding: {res.status_code} - {res.text}")
        return False

    updated_finding = res.json()
    print(f"✓ Updated finding")
    print(f"  New content: {updated_finding['content']}")

    # Step 7: Update finding to link to source
    print("\n7. Updating finding to link to source...")
    update_data2 = {
        "source_ids": [source_id]
    }

    res = requests.patch(
        f"{BASE_URL}/research/{research_id}/findings/{finding_id}", json=update_data2)

    if res.status_code != 200:
        print(
            f"❌ Failed to update finding sources: {res.status_code} - {res.text}")
        return False

    updated_finding2 = res.json()
    print(f"✓ Updated finding sources")
    print(f"  New sources: {updated_finding2.get('source_ids', [])}")

    # Step 8: Delete first finding
    print("\n8. Deleting first finding...")
    res = requests.delete(
        f"{BASE_URL}/research/{research_id}/findings/{finding_id}")

    if res.status_code != 204:
        print(f"❌ Failed to delete finding: {res.status_code} - {res.text}")
        return False

    print(f"✓ Deleted finding")

    # Step 9: Delete second finding
    print("\n9. Deleting second finding...")
    res = requests.delete(
        f"{BASE_URL}/research/{research_id}/findings/{finding2_id}")

    if res.status_code != 204:
        print(f"❌ Failed to delete finding: {res.status_code} - {res.text}")
        return False

    print(f"✓ Deleted finding")

    # Step 10: Verify deletion
    print("\n10. Verifying findings were deleted...")
    res = requests.get(f"{BASE_URL}/research/{research_id}/findings")

    if res.status_code != 200:
        print(f"❌ Failed to verify deletion: {res.status_code} - {res.text}")
        return False

    findings = res.json()
    if len(findings) == 0:
        print(f"✓ Findings successfully deleted (0 findings remaining)")
    else:
        print(f"❌ Findings not deleted (still {len(findings)} finding(s))")
        return False

    # Cleanup: Delete test research
    print("\n11. Cleaning up test research...")
    res = requests.delete(f"{BASE_URL}/research/{research_id}")

    if res.status_code not in [200, 204]:
        print(f"⚠ Warning: Failed to delete test research: {res.status_code}")
    else:
        print(f"✓ Cleaned up test research")

    print("\n" + "="*50)
    print("✅ All Finding CRUD tests passed!")
    print("="*50)
    return True


if __name__ == "__main__":
    try:
        success = test_finding_crud()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
