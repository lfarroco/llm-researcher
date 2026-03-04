#!/usr/bin/env python3
"""
Test script for LLM Researcher API endpoints
Usage: python test_api.py
"""
import requests
import time
from typing import Optional

BASE_URL = "http://localhost:8000"


def health_check():
    """Test the health check endpoint"""
    print("Testing health check...")
    response = requests.get(f"{BASE_URL}/")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}\n")
    return response.json()


def create_research(query: str):
    """Create a new research request"""
    print(f"Creating research for query: '{query}'")
    payload = {"query": query}
    response = requests.post(f"{BASE_URL}/research", json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}\n")
    return response.json()


def list_research(skip: int = 0, limit: int = 20):
    """List all research records"""
    print(f"Listing research (skip={skip}, limit={limit})...")
    response = requests.get(f"{BASE_URL}/research", params={"skip": skip, "limit": limit})
    print(f"Status: {response.status_code}")
    records = response.json()
    print(f"Found {len(records)} records")
    for record in records:
        print(f"  - ID: {record['id']}, Query: {record['query']}, Status: {record['status']}")
    print()
    return records


def get_research(research_id: int):
    """Get a specific research by ID"""
    print(f"Getting research ID: {research_id}")
    response = requests.get(f"{BASE_URL}/research/{research_id}")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Query: {data['query']}")
        print(f"Status: {data['status']}")
        print(f"Result: {data['result'][:200] if data['result'] else 'None'}...")
    else:
        print(f"Error: {response.text}")
    print()
    return response.json() if response.status_code == 200 else None


def main():
    """Run a complete test workflow"""
    print("=" * 60)
    print("LLM Researcher API Test Script")
    print("=" * 60 + "\n")

    # 1. Health check
    health_check()

    # 2. Create a research request
    research = create_research("What are the latest developments in quantum computing?")
    research_id = research.get("id")

    # 3. Check its status immediately
    time.sleep(1)
    get_research(research_id)

    # 4. List all research
    list_research()

    # 5. Check status again after some time (research runs in background)
    print("Waiting 5 seconds for research to complete...")
    time.sleep(5)
    get_research(research_id)

    print("=" * 60)
    print("Test complete!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to API. Is the server running at http://localhost:8000?")
    except Exception as e:
        print(f"Error: {e}")
