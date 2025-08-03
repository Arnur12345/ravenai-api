import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'libs', 'shared-models'))

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.endpoints import get_transcript_internal, update_meeting_data
from shared_models.models import Meeting, User
from shared_models.schemas import Platform, MeetingUpdate, MeetingDataUpdate, TranscriptionSegment


class TestRedisPublishing:
    """Test suite for Redis publishing functionality in transcript endpoints."""

    @pytest.fixture
    def mock_redis_client(self):
        """Create a mock Redis client."""
        redis_mock = AsyncMock()
        redis_mock.publish = AsyncMock()
        return redis_mock

    @pytest.fixture
    def mock_request(self, mock_redis_client):
        """Create a mock FastAPI Request with Redis client."""
        request = MagicMock(spec=Request)
        request.app.state.redis_client = mock_redis_client
        return request

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def sample_meeting(self):
        """Create a sample meeting object."""
        from datetime import datetime
        meeting = Meeting(
            id=123,
            user_id=1,
            platform=Platform.GOOGLE_MEET,
            native_meeting_id="abc-def-ghi",
            status="active",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            data={"name": "Test Meeting"}
        )
        return meeting

    @pytest.fixture
    def sample_segments(self):
        """Create sample transcript segments."""
        from datetime import datetime
        return [
             TranscriptionSegment(
                 start=0.0,
                 end=3.0,
                 text="Hello everyone, welcome to the meeting.",
                 language="en",
                 created_at=datetime.now()
             ),
             TranscriptionSegment(
                 start=3.5,
                 end=6.0,
                 text="Thank you for joining us today.",
                 language="en",
                 created_at=datetime.now()
             )
         ]

    @pytest.fixture
    def sample_transcript_segments(self):
        """Sample transcript segments for testing"""
        from datetime import datetime
        return [
             TranscriptionSegment(
                 start=0.0,
                 end=5.0,
                 text="Hello, this is the first segment.",
                 language="en",
                 created_at=datetime.now()
             ),
             TranscriptionSegment(
                 start=5.0,
                 end=10.0,
                 text="This is the second segment.",
                 language="en",
                 created_at=datetime.now()
             ),
             TranscriptionSegment(
                 start=10.0,
                 end=15.0,
                 text="   ",  # Empty/whitespace segment
                 language="en",
                 created_at=datetime.now()
             )
         ]

    @pytest.mark.asyncio
    async def test_internal_transcript_publishes_to_correct_channel(self, mock_request, mock_db_session, sample_meeting, sample_segments):
        """Test that internal transcript endpoint publishes to rag_ingestion_queue channel."""
        # Setup
        mock_db_session.get.return_value = sample_meeting
        
        with patch('api.endpoints._get_full_transcript_segments', return_value=sample_segments):
            # Execute
            result = await get_transcript_internal(123, mock_request, mock_db_session)
            
            # Verify
            mock_request.app.state.redis_client.publish.assert_called_once()
            call_args = mock_request.app.state.redis_client.publish.call_args
            
            # Check channel name
            assert call_args[0][0] == "rag_ingestion_queue"
            
            # Check message format
            message = json.loads(call_args[0][1])
            assert "meeting_id" in message
            assert "transcript" in message
            assert message["meeting_id"] == 123
            assert "Hello everyone, welcome to the meeting. Thank you for joining us today." in message["transcript"]

    @pytest.mark.asyncio
    async def test_internal_transcript_correct_message_format(self, mock_request, mock_db_session, sample_meeting, sample_segments):
        """Test that the published message has the correct JSON format."""
        # Setup
        mock_db_session.get.return_value = sample_meeting
        
        with patch('api.endpoints._get_full_transcript_segments', return_value=sample_segments):
            # Execute
            await get_transcript_internal(123, mock_request, mock_db_session)
            
            # Verify message format
            call_args = mock_request.app.state.redis_client.publish.call_args
            message = json.loads(call_args[0][1])
            
            # Check required keys
            assert set(message.keys()) == {"meeting_id", "transcript"}
            assert isinstance(message["meeting_id"], int)
            assert isinstance(message["transcript"], str)
            assert len(message["transcript"]) > 0

    @pytest.mark.asyncio
    async def test_internal_transcript_no_publish_when_no_content(self, mock_request, mock_db_session, sample_meeting):
        """Test that no message is published when there's no transcript content."""
        # Setup - empty segments
        empty_segments = []
        mock_db_session.get.return_value = sample_meeting
        
        with patch('api.endpoints._get_full_transcript_segments', return_value=empty_segments):
            # Execute
            await get_transcript_internal(123, mock_request, mock_db_session)
            
            # Verify no publish call
            mock_request.app.state.redis_client.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_internal_transcript_handles_redis_error_gracefully(self, mock_request, mock_db_session, sample_meeting, sample_segments):
        """Test that Redis publishing errors don't break the endpoint."""
        # Setup
        mock_db_session.get.return_value = sample_meeting
        mock_request.app.state.redis_client.publish.side_effect = Exception("Redis connection failed")
        
        with patch('api.endpoints._get_full_transcript_segments', return_value=sample_segments):
            # Execute - should not raise exception
            result = await get_transcript_internal(123, mock_request, mock_db_session)
            
            # Verify endpoint still returns segments
            assert result == sample_segments

    @pytest.mark.asyncio
    async def test_patch_endpoint_publishes_after_update(self, mock_request, mock_db_session, sample_meeting, sample_segments):
        """Test that PATCH endpoint publishes transcript after successful update."""
        # Setup
        mock_user = User(id=1, email="test@example.com")
        meeting_update = MeetingUpdate(
            data=MeetingDataUpdate(name="Updated Meeting Name")
        )
        
        # Mock database operations
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = sample_meeting
        mock_db_session.execute.return_value = mock_result
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()
        
        with patch('api.endpoints._get_full_transcript_segments', return_value=sample_segments):
            # Execute
            result = await update_meeting_data(
            Platform.GOOGLE_MEET,
            "abc-def-ghi",
            meeting_update,
            mock_request,
            mock_user,
            mock_db_session
        )
            
            # Verify Redis publish was called
            mock_request.app.state.redis_client.publish.assert_called_once()
            call_args = mock_request.app.state.redis_client.publish.call_args
            
            # Check channel and message
            assert call_args[0][0] == "rag_ingestion_queue"
            message = json.loads(call_args[0][1])
            assert message["meeting_id"] == 123
            assert "transcript" in message

    @pytest.mark.asyncio
    async def test_patch_endpoint_no_redis_client(self, mock_db_session, sample_meeting):
        """Test that PATCH endpoint works when Redis client is not available."""
        # Setup request without Redis client
        request = MagicMock(spec=Request)
        request.app.state.redis_client = None
        
        mock_user = User(id=1, email="test@example.com")
        meeting_update = MeetingUpdate(
            data=MeetingDataUpdate(name="Updated Meeting Name")
        )
        
        # Mock database operations
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = sample_meeting
        mock_db_session.execute.return_value = mock_result
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()
        
        # Execute - should not raise exception
        result = await update_meeting_data(
            Platform.GOOGLE_MEET,
            "abc-def-ghi",
            meeting_update,
            request,
            mock_user,
            mock_db_session
        )
        
        # Verify endpoint still works
        assert result is not None

    @pytest.mark.asyncio
    async def test_internal_transcript_meeting_not_found(self, mock_request, mock_db_session):
        """Test that internal transcript endpoint handles missing meeting correctly."""
        # Setup
        mock_db_session.get.return_value = None
        
        # Execute and verify exception
        with pytest.raises(Exception):  # Should raise HTTPException
            await get_transcript_internal(999, mock_request, mock_db_session)
        
        # Verify no Redis publish attempt
        mock_request.app.state.redis_client.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_transcript_text_concatenation(self, mock_request, mock_db_session, sample_meeting):
        """Test that transcript segments are properly concatenated."""
        # Setup segments with various text content
        from datetime import datetime
        segments = [
             TranscriptionSegment(text="First segment.", start=0.0, end=1.0, speaker="Speaker 1", language="en", created_at=datetime.now()),
             TranscriptionSegment(text="", start=1.0, end=2.0, speaker="Speaker 1", language="en", created_at=datetime.now()),  # Empty text
             TranscriptionSegment(text="Second segment.", start=2.0, end=3.0, speaker="Speaker 2", language="en", created_at=datetime.now()),
             TranscriptionSegment(text="   ", start=3.0, end=4.0, speaker="Speaker 2", language="en", created_at=datetime.now()),  # Whitespace only
             TranscriptionSegment(text="Third segment.", start=4.0, end=5.0, speaker="Speaker 1", language="en", created_at=datetime.now())
         ]
        
        mock_db_session.get.return_value = sample_meeting
        
        with patch('api.endpoints._get_full_transcript_segments', return_value=segments):
            # Execute
            await get_transcript_internal(123, mock_request, mock_db_session)
            
            # Verify message content
            call_args = mock_request.app.state.redis_client.publish.call_args
            message = json.loads(call_args[0][1])
            
            # Current behavior: includes whitespace-only segments in join
            # The join logic uses 'if segment.text' which is True for whitespace-only strings
            expected_text = "First segment. Second segment.     Third segment."
            assert message["transcript"] == expected_text