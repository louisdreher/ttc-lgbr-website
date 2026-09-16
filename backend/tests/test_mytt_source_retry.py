import asyncio
from unittest.mock import AsyncMock

import pytest

from app.adapters.outbound.mytischtennis.source import MyTischtennisSource
from app.core.competition.application.sync.errors import SourceError


@pytest.mark.parametrize("code", [449, "449"])
def test_api_449_retries_same_request_until_success(code, caplog):
    pending = {"error": {"code": code, "message": "private provider response"}}
    ready = {"data": {"teampools": []}, "error": None}
    request = AsyncMock(side_effect=[pending, pending, pending, ready])
    sleep = AsyncMock()
    source = MyTischtennisSource(None, "1", sleep=sleep)

    result = asyncio.run(source._request(request, group_id=519001, round_filter="vr"))

    assert result == ready
    assert request.await_count == 4
    assert all(call.kwargs == {"group_id": 519001, "round_filter": "vr"}
               for call in request.await_args_list)
    assert [call.args[0] for call in sleep.await_args_list] == [2, 5, 10]
    assert "API 449" in caplog.text
    assert "private provider response" not in caplog.text


def test_persistent_449_exhausts_budget_without_enabling_outer_batch_retries():
    request = AsyncMock(return_value={"error": {"code": 449}})
    sleep = AsyncMock()
    source = MyTischtennisSource(None, "1", sleep=sleep)

    with pytest.raises(SourceError, match="API 449 nach vier") as error:
        asyncio.run(source._request(request))

    assert request.await_count == 4
    assert sleep.await_count == 3
    assert not error.value.retryable


@pytest.mark.parametrize("response", [
    {"data": {}, "error": None},
    {"error": {"code": 500}},
    {"error": "invalid"},
    {"error": {"message": "Please try again."}},
    [],
])
def test_other_responses_are_not_retried(response):
    request, sleep = AsyncMock(return_value=response), AsyncMock()
    source = MyTischtennisSource(None, "1", sleep=sleep)
    if isinstance(response, dict) and not response.get("error"):
        assert asyncio.run(source._request(request)) == response
    else:
        with pytest.raises(SourceError):
            asyncio.run(source._request(request))
    request.assert_awaited_once()
    sleep.assert_not_awaited()


def test_cancellation_during_backoff_stops_requests():
    request = AsyncMock(return_value={"error": {"code": 449}})
    sleep = AsyncMock(side_effect=asyncio.CancelledError)
    source = MyTischtennisSource(None, "1", sleep=sleep)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(source._request(request))
    request.assert_awaited_once()
