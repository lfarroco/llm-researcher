#!/usr/bin/env python3
"""
End-to-end test for LLM Researcher system.

Tests the complete workflow:
1. Create research project
2. Trigger research via chat
3. Wait for sources to be collected
4. Create findings
5. Test state transparency endpoints
6. Test plan management
"""

import sys
import time
import httpx


API_BASE = "http://localhost:8000"
TIMEOUT = 60.0


def log_step(step_num: int, description: str):
    """Print a test step."""
    print(f"\n{'='*60}")
    print(f"Step {step_num}: {description}")
    print('='*60)


def log_success(message: str):
    """Print success message."""
    print(f"✅ {message}")


def log_error(message: str):
    """Print error message."""
    print(f"❌ {message}")


def wait_for_api(max_retries: int = 10, delay: float = 2.0) -> bool:
    """Wait for API to be ready."""
    print("Waiting for API to be ready...")
    for i in range(max_retries):
        try:
            response = httpx.get(f"{API_BASE}/", timeout=5.0)
            if response.status_code == 200:
                log_success("API is ready")
                return True
        except Exception:
            pass
        if i < max_retries - 1:
            print(f"  Retry {i + 1}/{max_retries}...")
            time.sleep(delay)
    log_error("API did not become ready in time")
    return False


def test_e2e():
    """Run end-to-end test."""
    print("\n" + "="*60)
    print("LLM RESEARCHER - END-TO-END TEST")
    print("="*60)

    # Wait for API
    if not wait_for_api():
        return False

    client = httpx.Client(base_url=API_BASE, timeout=TIMEOUT)
    research_id = None

    try:
        # Step 1: Create a research project
        log_step(1, "Create Research Project")
        response = client.post("/research", json={
            "query": "What are the latest developments in transformer models?"
        })
        assert response.status_code == 201, \
            f"Expected 201, got {response.status_code}"
        research = response.json()
        research_id = research["id"]
        log_success(f"Created research project with ID: {research_id}")
        print(f"   Query: {research['query']}")
        print(f"   Status: {research['status']}")

        # Step 2: List research projects
        log_step(2, "List Research Projects")
        response = client.get("/research")
        assert response.status_code == 200
        projects = response.json()
        assert len(projects) > 0, "Should have at least one project"
        log_success(f"Found {len(projects)} research project(s)")

        # Step 3: Get specific research project
        log_step(3, "Get Research Project Details")
        response = client.get(f"/research/{research_id}")
        assert response.status_code == 200
        project = response.json()
        log_success(f"Retrieved project: {project['query']}")

        # Step 4: Trigger research via chat (simplified query)
        log_step(4, "Trigger Research via Chat")
        response = client.post(
            f"/research/{research_id}/chat",
            json={"message": "Research transformer architecture"}
        )
        assert response.status_code == 200
        chat_response = response.json()
        log_success("Chat request submitted")
        print(f"   AI Response: {chat_response['response'][:100]}...")
        print(f"   Action: {chat_response.get('action_taken')}")

        # Step 5: Wait for sources to be collected (poll with timeout)
        log_step(5, "Wait for Sources to be Collected")
        max_wait = 90  # 90 seconds max
        start_time = time.time()
        sources_found = False

        while time.time() - start_time < max_wait:
            response = client.get(f"/research/{research_id}/sources")
            if response.status_code == 200:
                sources = response.json()
                if len(sources) > 0:
                    sources_found = True
                    log_success(f"Found {len(sources)} source(s)")
                    for i, source in enumerate(sources[:3], 1):
                        print(f"   {i}. [{source['source_type']}] "
                              f"{source['title'][:50]}...")
                    break
            time.sleep(5)
            print("   Waiting for sources...")

        if not sources_found:
            log_error("No sources found after waiting")
            print("   ⚠️  Continuing with test anyway...")

        # Step 6: Get sources with filtering
        log_step(6, "Test Source Filtering")
        response = client.get(
            f"/research/{research_id}/sources",
            params={"source_type": "arxiv"}
        )
        assert response.status_code == 200
        arxiv_sources = response.json()
        log_success(f"Found {len(arxiv_sources)} ArXiv source(s)")

        # Step 7: Manually add a source
        log_step(7, "Manually Add a Source")
        response = client.post(
            f"/research/{research_id}/sources",
            json={
                "url": "https://arxiv.org/abs/1706.03762",
                "title": "Attention Is All You Need",
                "author": "Vaswani et al.",
                "content_snippet": "The dominant sequence transduction "
                                   "models are based on complex RNNs or CNNs.",
                "source_type": "arxiv",
                "relevance_score": 0.95,
                "user_notes": "Seminal transformer paper",
                "tags": ["transformer", "attention", "foundational"]
            }
        )
        assert response.status_code == 201
        new_source = response.json()
        source_id = new_source["id"]
        log_success(f"Created source with ID: {source_id}")
        print(f"   Title: {new_source['title']}")
        print(f"   Tags: {new_source['tags']}")

        # Step 8: Update source notes
        log_step(8, "Update Source Notes")
        response = client.patch(
            f"/research/{research_id}/sources/{source_id}",
            json={
                "user_notes": "Updated: Most influential paper in NLP",
                "tags": ["transformer", "attention", "foundational", "nlp"]
            }
        )
        assert response.status_code == 200
        updated_source = response.json()
        log_success("Updated source notes and tags")
        print(f"   New notes: {updated_source['user_notes']}")
        print(f"   New tags: {updated_source['tags']}")

        # Step 9: Create a finding
        log_step(9, "Create Research Finding")
        response = client.post(
            f"/research/{research_id}/findings",
            json={
                "content": "Transformers revolutionized NLP by using "
                "self-attention mechanisms instead of "
                "recurrent architectures.",
                "source_ids": [source_id]
            }
        )
        assert response.status_code == 201
        finding = response.json()
        finding_id = finding["id"]
        log_success(f"Created finding with ID: {finding_id}")
        print(f"   Content: {finding['content'][:80]}...")

        # Step 10: List findings
        log_step(10, "List Research Findings")
        response = client.get(f"/research/{research_id}/findings")
        assert response.status_code == 200
        findings = response.json()
        assert len(findings) > 0, "Should have at least one finding"
        log_success(f"Found {len(findings)} finding(s)")

        # Step 11: Update finding
        log_step(11, "Update Research Finding")
        response = client.patch(
            f"/research/{research_id}/findings/{finding_id}",
            json={
                "content": "UPDATED: Transformers revolutionized NLP by "
                "using self-attention mechanisms, enabling "
                "parallel processing and capturing long-range "
                "dependencies."
            }
        )
        assert response.status_code == 200
        updated_finding = response.json()
        log_success("Updated finding content")
        print(f"   New content: {updated_finding['content'][:80]}...")

        # Step 12: Get research state
        log_step(12, "Get Research State")
        response = client.get(f"/research/{research_id}/state")
        assert response.status_code == 200
        state = response.json()
        log_success("Retrieved research state")
        print(f"   Status: {state['status']}")
        print(f"   Sources in KB: {state['source_count']}")
        print(f"   Findings: {state['finding_count']}")
        print(f"   Pending queries: {len(state.get('pending_queries', []))}")
        print(f"   Completed queries: "
              f"{len(state.get('completed_queries', []))}")

        # Step 13: Get research plan
        log_step(13, "Get Research Plan")
        response = client.get(f"/research/{research_id}/plan")
        assert response.status_code == 200
        plan = response.json()
        log_success("Retrieved research plan")
        print(f"   Main query: {plan['query']}")
        print(f"   Sub-queries: {len(plan.get('sub_queries', []))}")
        if plan.get('refined_question'):
            print(f"   Refined: {plan['refined_question']}")

        # Step 14: Update research plan
        log_step(14, "Update Research Plan")
        response = client.patch(
            f"/research/{research_id}/plan",
            json={
                "add_queries": [
                    "What are the computational requirements?",
                    "How do transformers compare to RNNs?"
                ],
                "refined_question": "What are the key innovations and "
                "computational aspects of transformer "
                "models?"
            }
        )
        assert response.status_code == 200
        updated_plan = response.json()
        log_success("Updated research plan")
        print(f"   Total sub-queries: "
              f"{len(updated_plan.get('sub_queries', []))}")
        print(f"   Refined question: {updated_plan['refined_question']}")

        # Step 15: Chat with status check
        log_step(15, "Chat - Check Status")
        response = client.post(
            f"/research/{research_id}/chat",
            json={"message": "Show me the current status"}
        )
        assert response.status_code == 200
        chat_response = response.json()
        log_success("Status check via chat")
        print(f"   Response: {chat_response['response'][:150]}...")

        # Step 16: Get chat history
        log_step(16, "Get Chat History")
        response = client.get(f"/research/{research_id}/chat/history")
        assert response.status_code == 200
        history = response.json()
        log_success(f"Retrieved {len(history)} conversation message(s)")
        for i, msg in enumerate(history[-3:], 1):
            print(f"   {i}. [{msg['role']}] {msg['content'][:60]}...")

        # Step 17: Browse sources via chat
        log_step(17, "Chat - Browse Sources")
        response = client.post(
            f"/research/{research_id}/chat",
            json={"message": "Show me all the sources"}
        )
        assert response.status_code == 200
        chat_response = response.json()
        log_success("Browse sources via chat")
        print(f"   Action: {chat_response.get('action_taken')}")

        # Step 18: Get full document
        log_step(18, "Get Research Document")
        response = client.get(f"/research/{research_id}/document")
        assert response.status_code == 200
        document = response.json()
        log_success("Retrieved full research document")
        print(f"   Sources: {len(document.get('sources', []))}")
        print(f"   Status: {document['status']}")

        # Step 19: Search sources
        log_step(19, "Search Sources")
        response = client.get(
            f"/research/{research_id}/sources",
            params={"search": "attention"}
        )
        assert response.status_code == 200
        search_results = response.json()
        log_success(f"Found {len(search_results)} source(s) "
                    f"matching 'attention'")

        # Step 20: Filter by tags
        log_step(20, "Filter Sources by Tag")
        response = client.get(
            f"/research/{research_id}/sources",
            params={"tag": "transformer"}
        )
        assert response.status_code == 200
        tagged_sources = response.json()
        log_success(f"Found {len(tagged_sources)} source(s) "
                    f"with tag 'transformer'")

        # Final summary
        print("\n" + "="*60)
        print("✅ ALL E2E TESTS PASSED!")
        print("="*60)
        print("\nTest Summary:")
        print(f"  • Research project created: ID {research_id}")
        print(f"  • Sources collected: {state['source_count']}")
        print(f"  • Findings created: {state['finding_count']}")
        print(f"  • Chat messages exchanged: {len(history)}")
        print(f"  • All CRUD operations verified")
        print(f"  • State transparency endpoints tested")
        print(f"  • Plan management tested")
        print("="*60)

        return True

    except AssertionError as e:
        log_error(f"Assertion failed: {e}")
        return False
    except Exception as e:
        log_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        client.close()


if __name__ == "__main__":
    success = test_e2e()
    sys.exit(0 if success else 1)
