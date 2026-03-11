#!/usr/bin/env python3
"""
Test script for Source CRUD operations.
"""
import requests
import sys
import time

BASE_URL = "http://localhost:8000"

def test_source_crud():
    """Test creating, updating, and deleting a source."""
    print("Testing Source CRUD operations...")
    
    # Step 1: Create a research
    print("\n1. Creating test research...")
    res = requests.post(f"{BASE_URL}/research", json={
        "query": "Testing source CRUD operations",
        "user_notes": "Test research for source management"
    })
    
    if res.status_code not in [200, 201]:
        print(f"❌ Failed to create research: {res.status_code} - {res.text}")
        return False
    
    research_id = res.json()["id"]
    print(f"✓ Created research with ID: {research_id}")
    
    # Step 2: Create a source
    print("\n2. Creating a test source...")
    source_data = {
        "url": "https://example.com/test-article",
        "title": "Test Article for CRUD Operations",
        "author": "Test Author",
        "content_snippet": "This is a test article snippet for validating CRUD operations.",
        "source_type": "web",
        "relevance_score": 0.8,
        "user_notes": "Initial test notes",
        "tags": ["test", "crud"]
    }
    
    res = requests.post(f"{BASE_URL}/research/{research_id}/sources", json=source_data)
    
    if res.status_code != 201:
        print(f"❌ Failed to create source: {res.status_code} - {res.text}")
        return False
    
    source = res.json()
    source_id = source["id"]
    print(f"✓ Created source with ID: {source_id}")
    print(f"  Title: {source['title']}")
    print(f"  Tags: {source.get('tags', [])}")
    print(f"  Notes: {source.get('user_notes', '')}")
    
    # Step 3: Get sources
    print("\n3. Fetching sources...")
    res = requests.get(f"{BASE_URL}/research/{research_id}/sources")
    
    if res.status_code != 200:
        print(f"❌ Failed to get sources: {res.status_code} - {res.text}")
        return False
    
    sources = res.json()
    print(f"✓ Found {len(sources)} source(s)")
    
    # Step 4: Update source
    print("\n4. Updating source notes and tags...")
    update_data = {
        "user_notes": "Updated test notes after edit",
        "tags": ["test", "crud", "updated"],
        "title": "Updated Test Article Title"
    }
    
    res = requests.patch(f"{BASE_URL}/research/{research_id}/sources/{source_id}", json=update_data)
    
    if res.status_code != 200:
        print(f"❌ Failed to update source: {res.status_code} - {res.text}")
        return False
    
    updated_source = res.json()
    print(f"✓ Updated source")
    print(f"  New title: {updated_source['title']}")
    print(f"  New tags: {updated_source.get('tags', [])}")
    print(f"  New notes: {updated_source.get('user_notes', '')}")
    
    # Step 5: Delete source
    print("\n5. Deleting source...")
    res = requests.delete(f"{BASE_URL}/research/{research_id}/sources/{source_id}")
    
    if res.status_code != 204:
        print(f"❌ Failed to delete source: {res.status_code} - {res.text}")
        return False
    
    print(f"✓ Deleted source")
    
    # Step 6: Verify deletion
    print("\n6. Verifying source was deleted...")
    res = requests.get(f"{BASE_URL}/research/{research_id}/sources")
    
    if res.status_code != 200:
        print(f"❌ Failed to verify deletion: {res.status_code} - {res.text}")
        return False
    
    sources = res.json()
    if len(sources) == 0:
        print(f"✓ Source successfully deleted (0 sources remaining)")
    else:
        print(f"❌ Source not deleted (still {len(sources)} source(s))")
        return False
    
    # Cleanup: Delete test research
    print("\n7. Cleaning up test research...")
    res = requests.delete(f"{BASE_URL}/research/{research_id}")
    
    if res.status_code != 200:
        print(f"⚠ Warning: Failed to delete test research: {res.status_code}")
    else:
        print(f"✓ Cleaned up test research")
    
    print("\n" + "="*50)
    print("✅ All Source CRUD tests passed!")
    print("="*50)
    return True

if __name__ == "__main__":
    try:
        success = test_source_crud()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
