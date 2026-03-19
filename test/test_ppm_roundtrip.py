# test/test_ppm_roundtrip.py
from pygfa.encoding.ppm_coding import compress_string_ppm, decompress_string_ppm


def test_ppm_roundtrip_simple():
    data = "AAAACCCCGGGGTTTT"
    compressed = compress_string_ppm(data)
    # decompress_string_ppm expects (data, lengths); for single string, lengths=[len(data)]
    decompressed_list = decompress_string_ppm(compressed, [len(data.encode("utf-8"))])
    assert decompressed_list == [data.encode("utf-8")]


def test_ppm_roundtrip_dna():
    data = "GATTACAGAATTAC"
    compressed = compress_string_ppm(data)
    decompressed_list = decompress_string_ppm(compressed, [len(data.encode("utf-8"))])
    assert decompressed_list == [data.encode("utf-8")]


if __name__ == "__main__":
    test_ppm_roundtrip_simple()
    test_ppm_roundtrip_dna()
