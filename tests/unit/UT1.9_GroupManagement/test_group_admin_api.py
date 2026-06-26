# @pytest.mark.req("UC-011")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
#!/usr/bin/env python3
"""
Tests for Group Admin API routes — W28D-441 snag coverage.

Covers:
- Create group through API (MCP path)
- Update existing group through PATCH by numeric id
- Update group with existing members, verify memberships persist
- List members after update
- Seed migration creates expected Ukraine digest groups
"""

import pytest
import asyncio
from src.database.db_manager import DatabaseManager
from src.database.repositories import (
    GroupRepository,
    GroupMemberRepository,
    UserRepository,
)
from src.core.groups.group_manager import GroupManager


@pytest.fixture
def manager(db):
    return GroupManager(db)


@pytest.fixture
def group_repo(db):
    return GroupRepository(db)


@pytest.fixture
def member_repo(db):
    return GroupMemberRepository(db)


@pytest.fixture
def user_repo(db):
    return UserRepository(db)
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


@pytest.fixture
def test_user(db, user_repo, test_email_domain):
    import hashlib
    existing = user_repo.get_by_username("w441_testuser")
    if existing:
        return existing["id"]
    pw = hashlib.sha256(b"testpass").hexdigest()
    return user_repo.create(
        username="w441_testuser",
        email=f"w441_test{test_email_domain}",
        password_hash=pw,
        display_name="W441 Test User",
    )


@pytest.fixture
def second_user(db, user_repo, test_email_domain):
    import hashlib
    existing = user_repo.get_by_username("w441_testuser2")
    if existing:
        return existing["id"]
    pw = hashlib.sha256(b"testpass2").hexdigest()
    return user_repo.create(
        username="w441_testuser2",
        email=f"w441_test2{test_email_domain}",
        password_hash=pw,
        display_name="W441 Test User 2",
    )


class TestGroupUpdateByNumericId:
    """Snag 1: admin_update_group must update existing groups by numeric ID."""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_create_and_update_group(self, manager, group_repo):
        """Create a group, then update it by numeric id. Verify fields changed."""
        gid = manager.create_group(
            name="W441 Test Group",
            description="Original description",
            language="en",
            preferred_channel="email",
        )
        assert gid > 0

        manager.update_group(
            group_id=gid,
            description="Updated description",
            enabled=True,
        )

        updated = group_repo.get_by_id(gid)
        assert updated is not None
        assert updated["description"] == "Updated description"
        assert updated["name"] == "W441 Test Group"
        assert updated["language"] == "en"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_update_nonexistent_group_returns_none(self, group_repo):
        """Update on a non-existent group id should not crash."""
        # GroupRepository.update silently does nothing for missing IDs
        group_repo.update(group_id=999999, description="should not exist")
        result = group_repo.get_by_id(999999)
        assert result is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_update_preserves_members(self, manager, member_repo, test_user, second_user):
        """Updating a group must not remove existing members."""
        gid = manager.create_group(
            name="W441 Members Test",
            description="Before update",
        )
        manager.add_member(gid, test_user, "admin")
        manager.add_member(gid, second_user, "member")

        members_before = member_repo.get_group_members(gid)
        assert len(members_before) == 2

        manager.update_group(
            group_id=gid,
            description="After update",
            enabled=True,
        )

        members_after = member_repo.get_group_members(gid)
        assert len(members_after) == 2
        user_ids = {m["user_id"] for m in members_after}
        assert test_user in user_ids
        assert second_user in user_ids
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_list_members_after_update(self, manager, test_user):
        """List members after a group update returns correct data."""
        gid = manager.create_group(name="W441 List After Update")
        manager.add_member(gid, test_user, "admin")
        manager.update_group(group_id=gid, description="Post-update")

        members = manager.get_group_members(gid)
        assert len(members) >= 1
        assert any(m["user_id"] == test_user for m in members)


class TestUkraineDigestSeedMigration:
    """Snag 2: Durable group state via seed migration."""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_seed_migration_creates_client_group(self, db, group_repo):
        """Ukraine Digest Clients Group exists after schema init (migration 007)."""
        group = group_repo.get_by_name("Ukraine Digest Clients Group")
        assert group is not None
        assert group["enabled"] == 1
        assert group["description"] == "Final client-ready Ukraine digest reports only"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_seed_migration_creates_admin_group(self, db, group_repo):
        """Ukraine Digest Admin Group exists after schema init."""
        group = group_repo.get_by_name("Ukraine Digest Admin Group")
        assert group is not None
        assert group["enabled"] == 1
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_seed_migration_creates_legacy_group(self, db, group_repo):
        """Ukraine Digest Demo Group exists as legacy marker."""
        group = group_repo.get_by_name("Ukraine Digest Demo Group")
        assert group is not None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_seed_migration_idempotent(self, db, group_repo):
        """Running the seed SQL twice does not duplicate groups."""
        from pathlib import Path
        seed_file = Path(__file__).resolve().parents[3] / "database" / "migrations" / "007_ukraine_digest_groups.sql"
        db.apply_migration_file(seed_file)
        groups = group_repo.list_all()
        ukraine_client = [g for g in groups if g["name"] == "Ukraine Digest Clients Group"]
        assert len(ukraine_client) == 1


pytestmark = [pytest.mark.unit, pytest.mark.db, pytest.mark.fast]
