from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
import hashlib
import pytest
from fastapi import HTTPException, UploadFile
from services.capture_chunks import append_capture_chunk


def writer(upload, target, *, current_size):
    data = upload.file.read()
    target.write_bytes(data)
    return len(data)


def send(root, index, data=b'video'):
    return append_capture_chunk(root, index, UploadFile(file=BytesIO(data)), writer)


@pytest.fixture
def root(tmp_path):
    (tmp_path / 'next_index.txt').write_text('0')
    return tmp_path


def test_lost_response_retry_13_expected_14(root):
    for i in range(14):
        send(root, i, bytes([i]))
    assert send(root, 13, bytes([13]))['duplicate']
    assert (root / 'capture.webm').read_bytes() == bytes(range(14))
    assert send(root, 14)['next_index'] == 15


def test_concurrent_retries_append_once(root):
    with ThreadPoolExecutor(max_workers=8) as pool:
        replies = list(pool.map(lambda _: send(root, 0), range(16)))
    assert sum(not r['duplicate'] for r in replies) == 1
    assert (root / 'capture.webm').read_bytes() == b'video'


def test_conflicting_and_missing_chunks_rejected(root):
    send(root, 0)
    for index, data in [(0, b'changed'), (2, b'future'), (-1, b'bad')]:
        with pytest.raises(HTTPException) as exc:
            send(root, index, data)
        assert exc.value.status_code == 409
    assert (root / 'capture.webm').read_bytes() == b'video'


def test_partial_append_recovery(root):
    send(root, 0)
    (root / 'chunk-1.json').write_text(json.dumps({'offset': 5, 'size': 4, 'sha256': hashlib.sha256(b'next').hexdigest()}))
    (root / 'capture.webm').write_bytes(b'videone')
    assert send(root, 1, b'next')['next_index'] == 2
    assert (root / 'capture.webm').read_bytes() == b'videonext'


def test_empty_chunk_keeps_counter(root):
    with pytest.raises(HTTPException):
        send(root, 0, b'')
    assert (root / 'next_index.txt').read_text() == '0'
