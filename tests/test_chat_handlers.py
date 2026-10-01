"""Tests for the chat intent handlers.

Focuses on the ``research`` intent, which used to strand items: the handler set
``status = "researching"`` while the worker's atomic claim only accepts
``pending``, so the queued run no-opped and the item never reached a terminal
status again. ``POST /resume`` refuses ``complete``, so there was no recovery
path either.
"""

from unittest.mock import patch

import pytest
from fastapi import BackgroundTasks

from app import models
from app.database import Base
import app.database as db_module
from app.memory.research_state import Citation, ResearchState, SourceType
from app.services import chat_handlers


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=db_module.engine)
    session = db_module.SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=db_module.engine)


def make_item(db, **kwargs):
    defaults = dict(query="original query", status="complete", result="report")
    defaults.update(kwargs)
    item = models.Research(**defaults)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def queued_research_id(tasks: BackgroundTasks) -> int:
    """The research id handed to the background task worker."""
    assert len(tasks.tasks) == 1, "expected exactly one queued background task"
    task = tasks.tasks[0]
    assert task.func is chat_handlers.process_research
    return task.args[0]


class TestResearchIntentOnFinishedItem:
    """A finished report must survive a chat that re-triggers research."""

    @pytest.mark.asyncio
    async def test_status_and_result_are_left_alone(self, db):
        item = make_item(db, status="complete", result="the finished report")
        tasks = BackgroundTasks()

        await chat_handlers.handle_research_intent(
            item,
            "Summarize the key challenges of citizen reporting in 3 bullets.",
            {},
            tasks,
            db,
        )

        db.refresh(item)
        assert item.status == "complete"
        assert item.result == "the finished report"

    @pytest.mark.asyncio
    async def test_a_new_pending_item_is_created_instead(self, db):
        item = make_item(db)
        tasks = BackgroundTasks()

        result = await chat_handlers.handle_research_intent(
            item, "a brand new topic", {}, tasks, db
        )

        new_id = result.state_changes["new_research_id"]
        assert new_id != item.id

        new_item = db.get(models.Research, new_id)
        assert new_item.query == "a brand new topic"
        assert new_item.status == "pending"

    @pytest.mark.asyncio
    async def test_worker_is_pointed_at_the_new_item(self, db):
        item = make_item(db)
        tasks = BackgroundTasks()

        result = await chat_handlers.handle_research_intent(
            item, "a brand new topic", {}, tasks, db
        )

        # The worker must be given the new item, never the finished one.
        assert queued_research_id(tasks) == result.state_changes["new_research_id"]

    @pytest.mark.asyncio
    async def test_notes_and_tags_carry_over(self, db):
        item = make_item(db, user_notes="keep me", tags=["smart-cities"])
        tasks = BackgroundTasks()

        result = await chat_handlers.handle_research_intent(
            item, "a brand new topic", {}, tasks, db
        )

        new_item = db.get(models.Research, result.state_changes["new_research_id"])
        assert new_item.user_notes == "keep me"
        assert new_item.tags == ["smart-cities"]


class TestResearchIntentOnUnfinishedItem:
    """Items that never finished are re-queued in place."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", ["error", "failed", "cancelled", "pending"])
    async def test_item_is_requeued_as_pending(self, db, status):
        item = make_item(db, status=status, result=None)
        tasks = BackgroundTasks()

        await chat_handlers.handle_research_intent(
            item, "retry this", {}, tasks, db
        )

        db.refresh(item)
        # "pending" is the only status the worker's claim accepts.
        assert item.status == "pending"
        assert queued_research_id(tasks) == item.id

    @pytest.mark.asyncio
    async def test_stranded_researching_item_is_recovered(self, db):
        """Items already stuck in ``researching`` become runnable again."""
        item = make_item(db, status="researching", result=None)
        tasks = BackgroundTasks()

        await chat_handlers.handle_research_intent(
            item, "recover me", {}, tasks, db
        )

        db.refresh(item)
        assert item.status == "pending"


class TestRequeuedItemIsActuallyClaimable:
    """The requeued status must survive the worker's atomic claim.

    This is the end-to-end guard for the original bug: the item was marked
    ``researching``, the claim (``WHERE status = 'pending'``) matched nothing,
    and the run silently did nothing. Here the claim must match and the item
    must reach a terminal status.
    """

    @pytest.mark.asyncio
    async def test_run_reaches_a_terminal_status(self, db):
        from app.services import research_service

        item = make_item(db, status="error", result=None)
        tasks = BackgroundTasks()

        await chat_handlers.handle_research_intent(
            item, "retry this", {}, tasks, db
        )
        research_id = queued_research_id(tasks)

        citation = Citation(
            id="[1]",
            url="https://arxiv.org/abs/2301.12345",
            title="A Paper",
            snippet="abstract",
            source_type=SourceType.ARXIV,
            relevance_score=0.8,
        )
        final_state = ResearchState(research_id=research_id, query="retry this")
        final_state.citations = [citation]
        final_state.final_document = "body [1]"
        final_state.status = "complete"

        async def fake_workflow(rid, q, **kwargs):
            return final_state

        async def fake_collect(db, research_id, query, citations):
            return []

        with patch.object(
            research_service, "run_research_workflow", fake_workflow
        ), patch.object(
            research_service, "collect_fulltext_evidence", fake_collect
        ):
            await research_service.process_research_async(research_id, "retry this")

        db.expire_all()
        refreshed = db.get(models.Research, research_id)
        # Not "researching": the claim matched and the run finished.
        assert refreshed.status == "complete"
