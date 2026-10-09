import json

import pytest

from src.image_id_ledger import ImageIdLedger


def _write_bytes(path, content: bytes):
    path.write_bytes(content)


class TestBasicAssignment:
    def test_first_image_gets_img_0001(self, tmp_path):
        ledger = ImageIdLedger(tmp_path / "ledger.json")
        img = tmp_path / "photo1.jpg"
        _write_bytes(img, b"fake jpeg bytes A")

        assert ledger.get_or_create(img) == "IMG_0001"

    def test_sequential_ids_for_different_images(self, tmp_path):
        ledger = ImageIdLedger(tmp_path / "ledger.json")
        img1 = tmp_path / "a.jpg"
        img2 = tmp_path / "b.jpg"
        _write_bytes(img1, b"content A")
        _write_bytes(img2, b"content B")

        assert ledger.get_or_create(img1) == "IMG_0001"
        assert ledger.get_or_create(img2) == "IMG_0002"

    def test_ids_are_four_digit_zero_padded(self, tmp_path):
        ledger = ImageIdLedger(tmp_path / "ledger.json")
        for i in range(12):
            img = tmp_path / f"img{i}.jpg"
            _write_bytes(img, f"content {i}".encode())
            ledger.get_or_create(img)
        last_img = tmp_path / "img11.jpg"
        assert ledger.get_or_create(last_img) == "IMG_0012"


class TestIdempotencyBySameContent:
    def test_same_file_processed_twice_keeps_same_id(self, tmp_path):
        ledger = ImageIdLedger(tmp_path / "ledger.json")
        img = tmp_path / "photo.jpg"
        _write_bytes(img, b"same bytes every time")

        first = ledger.get_or_create(img)
        second = ledger.get_or_create(img)
        assert first == second == "IMG_0001"

    def test_same_content_different_filename_gets_same_id(self, tmp_path):
        """Identity is by content hash, not filename -- a renamed/copied
        photo must resolve to its existing id."""
        ledger = ImageIdLedger(tmp_path / "ledger.json")
        original = tmp_path / "original_name.jpg"
        renamed = tmp_path / "renamed_copy.jpg"
        _write_bytes(original, b"identical content")
        _write_bytes(renamed, b"identical content")

        first_id = ledger.get_or_create(original)
        second_id = ledger.get_or_create(renamed)
        assert first_id == second_id

    def test_different_content_same_filename_gets_different_ids(self, tmp_path):
        """Two genuinely different photos must never collide just because
        they happen to share a filename (processed at different times)."""
        ledger_path = tmp_path / "ledger.json"
        img_path = tmp_path / "IMG_1234.jpg"

        ledger = ImageIdLedger(ledger_path)
        _write_bytes(img_path, b"first photo content")
        first_id = ledger.get_or_create(img_path)

        _write_bytes(img_path, b"completely different second photo")
        second_id = ledger.get_or_create(img_path)

        assert first_id != second_id


class TestPersistenceAcrossInstances:
    def test_ledger_reloaded_from_disk_preserves_ids(self, tmp_path):
        ledger_path = tmp_path / "ledger.json"
        img = tmp_path / "photo.jpg"
        _write_bytes(img, b"persistent content")

        ledger1 = ImageIdLedger(ledger_path)
        assigned_id = ledger1.get_or_create(img)

        # simulate a new process/run -- fresh instance, same file on disk
        ledger2 = ImageIdLedger(ledger_path)
        assert ledger2.get_or_create(img) == assigned_id

    def test_ledger_file_is_valid_json(self, tmp_path):
        ledger_path = tmp_path / "ledger.json"
        img = tmp_path / "photo.jpg"
        _write_bytes(img, b"content")
        ImageIdLedger(ledger_path).get_or_create(img)

        with open(ledger_path) as f:
            data = json.load(f)
        assert "entries" in data
        assert "next_id" in data

    def test_creates_parent_directories(self, tmp_path):
        ledger_path = tmp_path / "nested" / "dir" / "ledger.json"
        img = tmp_path / "photo.jpg"
        _write_bytes(img, b"content")
        ImageIdLedger(ledger_path).get_or_create(img)
        assert ledger_path.exists()


class TestNeverReuseOldIds:
    def test_removing_an_entry_does_not_free_its_id(self, tmp_path):
        """Core requirement: manually deleting an entry from the ledger
        must never allow its number to be issued again -- next_id is an
        independent monotonic counter, not derived from current entries."""
        ledger_path = tmp_path / "ledger.json"
        img1 = tmp_path / "a.jpg"
        img2 = tmp_path / "b.jpg"
        img3 = tmp_path / "c.jpg"
        _write_bytes(img1, b"content A")
        _write_bytes(img2, b"content B")

        ledger = ImageIdLedger(ledger_path)
        id1 = ledger.get_or_create(img1)  # IMG_0001
        id2 = ledger.get_or_create(img2)  # IMG_0002
        assert id1 == "IMG_0001"
        assert id2 == "IMG_0002"

        # Manually remove img1's entry from the ledger file, simulating
        # an operator deleting a record.
        with open(ledger_path) as f:
            data = json.load(f)
        img1_hash = next(h for h, v in data["entries"].items() if v["image_id"] == "IMG_0001")
        del data["entries"][img1_hash]
        with open(ledger_path, "w") as f:
            json.dump(data, f)

        # A brand new image must NOT get IMG_0001 back -- next_id was
        # untouched by the manual deletion.
        _write_bytes(img3, b"content C")
        ledger_reloaded = ImageIdLedger(ledger_path)
        id3 = ledger_reloaded.get_or_create(img3)
        assert id3 == "IMG_0003"
        assert id3 not in ("IMG_0001",)


class TestLookup:
    def test_lookup_returns_none_for_unknown_image(self, tmp_path):
        ledger = ImageIdLedger(tmp_path / "ledger.json")
        img = tmp_path / "never_processed.jpg"
        _write_bytes(img, b"unseen content")
        assert ledger.lookup(img) is None

    def test_lookup_does_not_create_an_entry(self, tmp_path):
        ledger = ImageIdLedger(tmp_path / "ledger.json")
        img = tmp_path / "photo.jpg"
        _write_bytes(img, b"content")

        assert ledger.lookup(img) is None
        assert len(ledger) == 0  # lookup must not have side effects

    def test_lookup_finds_existing_assignment(self, tmp_path):
        ledger = ImageIdLedger(tmp_path / "ledger.json")
        img = tmp_path / "photo.jpg"
        _write_bytes(img, b"content")
        assigned = ledger.get_or_create(img)
        assert ledger.lookup(img) == assigned


class TestLen:
    def test_len_reflects_entry_count(self, tmp_path):
        ledger = ImageIdLedger(tmp_path / "ledger.json")
        assert len(ledger) == 0
        img1, img2 = tmp_path / "a.jpg", tmp_path / "b.jpg"
        _write_bytes(img1, b"A")
        _write_bytes(img2, b"B")
        ledger.get_or_create(img1)
        assert len(ledger) == 1
        ledger.get_or_create(img2)
        assert len(ledger) == 2
        ledger.get_or_create(img1)  # repeat -- must not grow
        assert len(ledger) == 2
