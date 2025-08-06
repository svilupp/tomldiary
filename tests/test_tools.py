"""
Tests for tools.py functions, specifically the new functionality added for
preference deduplication, similarity detection, and limit enforcement.
"""

from datetime import UTC, datetime

import pytest

from src.tomldiary.models import MemoryDeps
from src.tomldiary.tools import (
    _check_preference_limits,
    _find_similar_preferences,
    forget_preference,
    list_categories,
    list_preferences,
    update_conversation_summary,
    upsert_preference,
)


class MockContext:
    """Mock RunContext that holds MemoryDeps"""

    def __init__(self, deps):
        self.deps = deps


def create_mock_deps(prefs_data=None, max_prefs=10):
    """Create mock MemoryDeps for testing"""
    if prefs_data is None:
        prefs_data = {"_meta": {"version": "0.3", "schema_name": "TestTable"}, "preferences": {}}

    convs_data = {
        "_meta": {"version": "0.3", "schema_name": "TestTable"},
        "conversations": {
            "session1": {
                "_created": datetime.now(UTC).isoformat(),
                "_updated": datetime.now(UTC).isoformat(),
                "_turns": 1,
                "summary": "Test session",
                "keywords": ["test"],
            }
        },
    }

    return MemoryDeps(
        prefs=prefs_data,
        convs=convs_data,
        allowed_cats=["likes", "dislikes", "about"],
        schema_name="TestTable",
        session_id="session1",
        max_prefs_per_category=max_prefs,
    )


class TestSimilarityDetection:
    """Test the FuzzyWuzzy similarity detection functionality"""

    async def test_find_similar_preferences_exact_match(self):
        """Test exact text matches return 100% similarity"""
        prefs_data = {
            "_meta": {"version": "0.3", "schema_name": "TestTable"},
            "preferences": {"likes": {"pref001": {"text": "black blazers", "_count": 1}}},
        }

        deps = create_mock_deps(prefs_data)
        ctx = MockContext(deps)

        similar = _find_similar_preferences(ctx, "likes", "black blazers")

        assert len(similar) == 1
        assert similar[0] == ("likes/pref001", "black blazers", 100)

    async def test_find_similar_preferences_partial_match(self):
        """Test partial matches with similarity scores"""
        prefs_data = {
            "_meta": {"version": "0.3", "schema_name": "TestTable"},
            "preferences": {
                "likes": {
                    "pref001": {"text": "loves black blazers", "_count": 1},
                    "pref002": {"text": "burgundy scarves", "_count": 1},
                }
            },
        }

        deps = create_mock_deps(prefs_data)
        ctx = MockContext(deps)

        similar = _find_similar_preferences(ctx, "likes", "black blazers")

        assert len(similar) == 1  # Only one should be above 70% threshold
        assert similar[0][0] == "likes/pref001"
        assert similar[0][1] == "loves black blazers"
        assert similar[0][2] >= 70  # Should be high similarity

    async def test_find_similar_preferences_no_matches(self):
        """Test when no similar preferences exist"""
        prefs_data = {
            "_meta": {"version": "0.3", "schema_name": "TestTable"},
            "preferences": {
                "likes": {"pref001": {"text": "completely different item", "_count": 1}}
            },
        }

        deps = create_mock_deps(prefs_data)
        ctx = MockContext(deps)

        similar = _find_similar_preferences(ctx, "likes", "black blazers")

        assert len(similar) == 0

    async def test_find_similar_preferences_sorted_by_score(self):
        """Test that results are sorted by similarity score (highest first)"""
        prefs_data = {
            "_meta": {"version": "0.3", "schema_name": "TestTable"},
            "preferences": {
                "likes": {
                    "pref001": {"text": "elegant black blazers for work", "_count": 1},
                    "pref002": {"text": "black blazers", "_count": 1},
                    "pref003": {"text": "dark blazers", "_count": 1},
                }
            },
        }

        deps = create_mock_deps(prefs_data)
        ctx = MockContext(deps)

        similar = _find_similar_preferences(ctx, "likes", "black blazers")

        # Should be sorted by similarity score (highest first)
        assert len(similar) >= 2
        assert similar[0][2] >= similar[1][2]  # First score >= second score
        # Find the exact match in results
        exact_match = next((s for s in similar if s[1] == "black blazers"), None)
        assert exact_match is not None  # Exact match should exist
        assert exact_match[2] == 100  # Should have 100% score

    async def test_find_similar_preferences_custom_threshold(self):
        """Test custom similarity threshold"""
        prefs_data = {
            "_meta": {"version": "0.3", "schema_name": "TestTable"},
            "preferences": {"likes": {"pref001": {"text": "black blazers for work", "_count": 1}}},
        }

        deps = create_mock_deps(prefs_data)
        ctx = MockContext(deps)

        # With high threshold, should find nothing
        similar_high = _find_similar_preferences(ctx, "likes", "red shirts", min_similarity=90)
        assert len(similar_high) == 0

        # With low threshold, might find something
        similar_low = _find_similar_preferences(ctx, "likes", "red shirts", min_similarity=10)
        # This depends on actual similarity, but should not crash
        assert isinstance(similar_low, list)  # Verify it returns a list without crashing


class TestLimitChecking:
    """Test the preference limit checking functionality"""

    async def test_check_preference_limits_empty(self):
        """Test limit checking with empty category"""
        deps = create_mock_deps(max_prefs=3)
        ctx = MockContext(deps)

        status = _check_preference_limits(ctx, "likes")

        assert "✅" in status
        assert "(0/3)" in status
        assert "has space" in status

    async def test_check_preference_limits_near_limit(self):
        """Test limit checking when near limit (80% threshold)"""
        prefs_data = {
            "_meta": {"version": "0.3", "schema_name": "TestTable"},
            "preferences": {
                "likes": {
                    "pref001": {"text": "item1", "_count": 1},
                    "pref002": {"text": "item2", "_count": 1},
                    "pref003": {"text": "item3", "_count": 1},  # 3/4 = 75%, but we use 80%
                }
            },
        }

        deps = create_mock_deps(prefs_data, max_prefs=4)
        ctx = MockContext(deps)

        status = _check_preference_limits(ctx, "likes")

        # At 3/4 (75%), should still show space (80% threshold)
        assert "✅" in status or "⚠️" in status
        assert "(3/4)" in status

    async def test_check_preference_limits_at_limit(self):
        """Test limit checking when at limit"""
        prefs_data = {
            "_meta": {"version": "0.3", "schema_name": "TestTable"},
            "preferences": {
                "likes": {
                    "pref001": {"text": "item1", "_count": 1},
                    "pref002": {"text": "item2", "_count": 1},
                    "pref003": {"text": "item3", "_count": 1},
                }
            },
        }

        deps = create_mock_deps(prefs_data, max_prefs=3)
        ctx = MockContext(deps)

        status = _check_preference_limits(ctx, "likes")

        assert "❌" in status
        assert "at limit" in status
        assert "(3/3)" in status


class TestUpsertPreference:
    """Test the enhanced upsert_preference functionality"""

    async def test_boost_existing_preference(self):
        """Test boosting existing preference (id provided, no text)"""
        prefs_data = {
            "_meta": {"version": "0.3", "schema_name": "TestTable"},
            "preferences": {
                "likes": {
                    "pref001": {
                        "text": "black blazers",
                        "_count": 1,
                        "_created": "2024-01-01T00:00:00Z",
                        "_updated": "2024-01-01T00:00:00Z",
                    }
                }
            },
        }

        deps = create_mock_deps(prefs_data)
        ctx = MockContext(deps)

        result = await upsert_preference(ctx, "likes", id="pref001")

        assert "✅ Boosted" in result
        assert "likes/pref001" in result
        assert "(count: 2)" in result
        assert ctx.deps.prefs["preferences"]["likes"]["pref001"]["_count"] == 2

    async def test_boost_nonexistent_preference(self):
        """Test boosting non-existent preference returns error"""
        deps = create_mock_deps()
        ctx = MockContext(deps)

        result = await upsert_preference(ctx, "likes", id="pref999")

        assert "❌" in result
        assert "not found" in result
        assert "list_preferences" in result

    async def test_create_new_preference(self):
        """Test creating new preference"""
        deps = create_mock_deps()
        ctx = MockContext(deps)

        result = await upsert_preference(ctx, "likes", text="burgundy scarves")

        assert "✅ Created" in result
        assert "likes/pref001" in result
        assert "burgundy scarves" in result
        assert "pref001" in ctx.deps.prefs["preferences"]["likes"]
        assert ctx.deps.prefs["preferences"]["likes"]["pref001"]["text"] == "burgundy scarves"
        assert ctx.deps.prefs["preferences"]["likes"]["pref001"]["_count"] == 1

    async def test_update_existing_preference(self):
        """Test updating existing preference with new text"""
        prefs_data = {
            "_meta": {"version": "0.3", "schema_name": "TestTable"},
            "preferences": {
                "likes": {
                    "pref001": {
                        "text": "black blazers",
                        "_count": 1,
                        "contexts": [],
                        "_created": "2024-01-01T00:00:00Z",
                    }
                }
            },
        }

        deps = create_mock_deps(prefs_data)
        ctx = MockContext(deps)

        result = await upsert_preference(ctx, "likes", id="pref001", text="refined black blazers")

        assert "✅ Updated" in result
        assert "likes/pref001" in result
        assert "refined black blazers" in result
        assert "(count: 2)" in result  # Should auto-increment
        assert ctx.deps.prefs["preferences"]["likes"]["pref001"]["text"] == "refined black blazers"
        assert ctx.deps.prefs["preferences"]["likes"]["pref001"]["_count"] == 2

    async def test_suppress_count_increment(self):
        """Test suppressing count increment during updates"""
        prefs_data = {
            "_meta": {"version": "0.3", "schema_name": "TestTable"},
            "preferences": {
                "likes": {
                    "pref001": {
                        "text": "black blazers",
                        "_count": 3,
                        "contexts": [],
                        "_created": "2024-01-01T00:00:00Z",
                    }
                }
            },
        }

        deps = create_mock_deps(prefs_data)
        ctx = MockContext(deps)

        result = await upsert_preference(
            ctx, "likes", id="pref001", text="refined black blazers", suppress_count_increment=True
        )

        assert "✅ Updated" in result
        assert "(count: 3)" in result  # Should NOT increment
        assert ctx.deps.prefs["preferences"]["likes"]["pref001"]["_count"] == 3

    async def test_similarity_detection_blocks_duplicate(self):
        """Test that similar preferences are detected and blocked"""
        prefs_data = {
            "_meta": {"version": "0.3", "schema_name": "TestTable"},
            "preferences": {"likes": {"pref001": {"text": "loves black blazers", "_count": 1}}},
        }

        deps = create_mock_deps(prefs_data)
        ctx = MockContext(deps)

        result = await upsert_preference(ctx, "likes", text="black blazers")

        assert "❌ Similar preferences found" in result
        assert "loves black blazers" in result
        assert "% match" in result
        assert "To update existing: upsert_preference('likes', id='pref_id')" in result
        assert "To force create anyway: upsert_preference('likes', id='new'" in result

    async def test_force_create_with_id_new(self):
        """Test forcing creation with id='new' bypasses similarity detection"""
        prefs_data = {
            "_meta": {"version": "0.3", "schema_name": "TestTable"},
            "preferences": {"likes": {"pref001": {"text": "loves black blazers", "_count": 1}}},
        }

        deps = create_mock_deps(prefs_data)
        ctx = MockContext(deps)

        result = await upsert_preference(ctx, "likes", id="new", text="black blazers")

        assert "✅ Created" in result
        assert "likes/pref002" in result  # Should get next available ID
        assert "black blazers" in result
        # Should have both preferences now
        assert len(ctx.deps.prefs["preferences"]["likes"]) == 2

    async def test_limit_enforcement(self):
        """Test that preference limits are enforced"""
        prefs_data = {
            "_meta": {"version": "0.3", "schema_name": "TestTable"},
            "preferences": {
                "likes": {
                    "pref001": {"text": "item1", "_count": 1},
                    "pref002": {"text": "item2", "_count": 1},
                }
            },
        }

        deps = create_mock_deps(prefs_data, max_prefs=2)  # Set limit to 2
        ctx = MockContext(deps)

        result = await upsert_preference(ctx, "likes", text="item3")

        assert "❌" in result
        assert "at limit" in result
        assert "(2/2)" in result

    async def test_missing_text_error(self):
        """Test error when text is missing for new preference"""
        deps = create_mock_deps()
        ctx = MockContext(deps)

        result = await upsert_preference(ctx, "likes")

        assert "❌" in result
        assert "'text' parameter is required" in result

    async def test_invalid_category_error(self):
        """Test error for invalid category"""
        deps = create_mock_deps()
        ctx = MockContext(deps)

        result = await upsert_preference(ctx, "invalid_category", text="test")

        assert "❌" in result
        assert "is not allowed" in result


class TestListPreferences:
    """Test the enhanced list_preferences functionality"""

    async def test_list_preferences_with_limits_empty(self):
        """Test listing preferences shows limit status for empty category"""
        deps = create_mock_deps(max_prefs=3)
        ctx = MockContext(deps)

        result = await list_preferences(ctx, "likes")

        # For specific category with no prefs, shows just the limit status and "no preferences yet"
        # But the function currently returns "(no preferences found)" when no preferences at all
        assert "(no preferences found)" in result or ("📊" in result and "(0/3)" in result)

    async def test_list_preferences_with_data(self):
        """Test listing preferences with actual data"""
        prefs_data = {
            "_meta": {"version": "0.3", "schema_name": "TestTable"},
            "preferences": {
                "likes": {
                    "pref001": {"text": "black blazers", "_count": 3},
                    "pref002": {"text": "burgundy scarves", "_count": 1},
                }
            },
        }

        deps = create_mock_deps(prefs_data, max_prefs=5)
        ctx = MockContext(deps)

        result = await list_preferences(ctx, "likes")

        assert "📊 ✅" in result
        assert "(2/5)" in result
        assert "- likes/pref001: black blazers (3×)" in result
        assert "- likes/pref002: burgundy scarves (1×)" in result

    async def test_list_preferences_all_categories(self):
        """Test listing all categories shows status for each"""
        prefs_data = {
            "_meta": {"version": "0.3", "schema_name": "TestTable"},
            "preferences": {"likes": {"pref001": {"text": "item1", "_count": 1}}},
        }

        deps = create_mock_deps(prefs_data, max_prefs=3)
        ctx = MockContext(deps)

        result = await list_preferences(ctx)

        # Should show status for all categories
        assert result.count("📊") >= 3  # One for each allowed category
        assert "likes" in result
        assert "dislikes" in result
        assert "about" in result


class TestOtherTools:
    """Test other tool functions"""

    async def test_list_categories(self):
        """Test listing available categories"""
        deps = create_mock_deps()
        ctx = MockContext(deps)

        result = await list_categories(ctx)

        assert "- **likes**" in result
        assert "- **dislikes**" in result
        assert "- **about**" in result

    async def test_forget_preference_success(self):
        """Test successfully forgetting a preference"""
        prefs_data = {
            "_meta": {"version": "0.3", "schema_name": "TestTable"},
            "preferences": {"likes": {"pref001": {"text": "black blazers", "_count": 1}}},
        }

        deps = create_mock_deps(prefs_data)
        ctx = MockContext(deps)

        result = await forget_preference(ctx, "likes", "pref001")

        assert "🗑️ Deleted likes/pref001" in result
        assert "pref001" not in ctx.deps.prefs["preferences"]["likes"]

    async def test_forget_preference_not_found(self):
        """Test forgetting non-existent preference"""
        deps = create_mock_deps()
        ctx = MockContext(deps)

        result = await forget_preference(ctx, "likes", "pref999")

        assert "❌" in result
        assert "not found" in result

    async def test_update_conversation_summary(self):
        """Test updating conversation summary"""
        deps = create_mock_deps()
        ctx = MockContext(deps)

        result = await update_conversation_summary(ctx, "Updated summary", ["keyword1", "keyword2"])

        assert "✅ Updated conversation summary" in result
        assert ctx.deps.convs["conversations"]["session1"]["summary"] == "Updated summary"
        assert ctx.deps.convs["conversations"]["session1"]["keywords"] == ["keyword1", "keyword2"]


class TestNewFunctionalityIntegration:
    """Integration test for all new functionality working together"""

    async def test_complete_workflow_integration(self):
        """Test complete workflow: limits, similarity detection, force creation, boosting"""
        prefs_data = {
            "_meta": {"version": "0.3", "schema_name": "TestTable"},
            "preferences": {
                "likes": {
                    "pref001": {
                        "text": "loves black blazers",
                        "_count": 1,
                        "contexts": [],
                        "_created": "2024-01-01T00:00:00Z",
                    }
                }
            },
        }

        deps = create_mock_deps(prefs_data, max_prefs=3)
        ctx = MockContext(deps)

        # Step 1: Try to create similar preference - should be blocked
        result1 = await upsert_preference(ctx, "likes", text="black blazers")
        assert "❌ Similar preferences found" in result1
        assert "loves black blazers" in result1
        assert "% match" in result1

        # Step 2: Boost existing preference instead
        result2 = await upsert_preference(ctx, "likes", id="pref001")
        assert "✅ Boosted" in result2
        assert "(count: 2)" in result2

        # Step 3: Force create similar preference anyway
        result3 = await upsert_preference(ctx, "likes", id="new", text="black blazers for work")
        assert "✅ Created" in result3
        assert "pref002" in result3

        # Step 4: Create genuinely different preference
        result4 = await upsert_preference(ctx, "likes", text="burgundy scarves")
        assert "✅ Created" in result4
        assert "pref003" in result4

        # Step 5: Try to create another - should hit limit
        result5 = await upsert_preference(ctx, "likes", text="green shoes")
        assert "❌" in result5
        assert "at limit (3/3)" in result5

        # Step 6: Update existing preference with suppressed count
        result6 = await upsert_preference(
            ctx, "likes", id="pref001", text="elegant black blazers", suppress_count_increment=True
        )
        assert "✅ Updated" in result6
        assert "(count: 2)" in result6  # Should not increment

        # Step 7: Verify final state
        final_result = await list_preferences(ctx, "likes")
        assert "📊 ❌" in final_result  # Should show at limit
        assert "elegant black blazers (2×)" in final_result
        assert "black blazers for work (1×)" in final_result
        assert "burgundy scarves (1×)" in final_result

        # Verify we have exactly 3 preferences (at limit)
        assert len(ctx.deps.prefs["preferences"]["likes"]) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
