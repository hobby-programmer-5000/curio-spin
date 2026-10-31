import random
import statistics
import time
import unittest

import core


class SimilarityTest(unittest.TestCase):
    def test_related_pairs_score_higher(self):
        s = core.similarity
        self.assertGreater(s("강아지 사료", "강아지 간식"), s("강아지 사료", "여름 휴가"))
        self.assertGreater(s("사과", "사과나무"), s("사과", "바나나"))
        self.assertGreater(s("고양이사료", "강아지사료"), s("고양이사료", "주식 투자"))
        self.assertGreater(s("Machine Learning", "machine-learning model"), s("Machine Learning", "pizza"))
        self.assertEqual(s("Python", " python "), 1.0)
        # sharing a name counts as similar even with particles or a different word order
        self.assertGreater(s("모차르트의 레퀴엠", "볼프강 아마데우스 모차르트"), 0.5)
        self.assertGreater(s("베토벤의 교향곡 9번 합창", "루트비히 판 베토벤"), 0.5)
        self.assertGreater(s("로베르트 슈만과 클라라 슈만", "슈만의 피아노 협주곡"), 0.5)
        self.assertLess(s("12사도", "12음 음렬주의"), 0.45)  # sharing only a number stays weak
        self.assertLess(s("아브라함과 이삭 그리고 야곱", "그리고 아무도 없었다"), 0.45)
        self.assertLess(s("바다", "컴퓨터"), 0.2)


class ArrangeTest(unittest.TestCase):
    WORDS = [
        "강아지 사료", "강아지 간식", "강아지 장난감", "강아지 산책",
        "고양이 사료", "고양이 간식", "고양이 모래", "고양이 장난감",
        "여름 휴가", "여름 바다", "여름 축제", "겨울 스키", "겨울 온천",
        "파이썬", "파이썬 기초", "자바스크립트", "리액트", "커피", "녹차", "홍차",
        "피자", "치킨", "떡볶이", "김밥", "라면",
    ]

    def test_is_permutation(self):
        order = core.arrange(self.WORDS, random.Random(1))
        self.assertEqual(sorted(order), sorted(self.WORDS))

    def test_reduces_clustering_vs_shuffle(self):
        rng = random.Random(7)
        shuffled, arranged = [], []
        for _ in range(20):
            w = self.WORDS[:]
            rng.shuffle(w)
            shuffled.append(core.neighbor_cost(w))
            arranged.append(core.neighbor_cost(core.arrange(self.WORDS, rng)))
        print(f"\n  neighbor cost: shuffle={statistics.mean(shuffled):.3f} arranged={statistics.mean(arranged):.3f}")
        self.assertLess(statistics.mean(arranged), statistics.mean(shuffled) * 0.7)

    def test_groups_spread_out(self):
        fields = ["역사", "문학", "미술", "과학", "음악", "철학", "종교"]
        words = [f"주제{i:03d}" for i in range(140)]  # keywords that are nearly identical as text
        groups = {w: fields[i % 7] for i, w in enumerate(words)}
        rng = random.Random(5)

        def same_adjacent(order):
            return sum(groups[order[i]] == groups[order[(i + 1) % len(order)]] for i in range(len(order)))

        shuffled = words[:]
        rng.shuffle(shuffled)
        arranged = core.arrange(words, rng, groups=groups)
        print(f"\n  same-group neighbors: shuffle={same_adjacent(shuffled)} arranged={same_adjacent(arranged)}")
        self.assertEqual(sorted(arranged), sorted(words))
        self.assertLessEqual(same_adjacent(arranged), 2)
        self.assertGreater(len({tuple(core.arrange(words, rng, groups=groups)) for _ in range(5)}), 4)

    def test_still_random(self):
        rng = random.Random()
        orders = {tuple(core.arrange(self.WORDS, rng)) for _ in range(10)}
        self.assertGreater(len(orders), 8)

    def test_small_and_large(self):
        for n in (0, 1, 2, 3, 4, 5):
            self.assertEqual(sorted(core.arrange(list("abcde")[:n])), sorted(list("abcde")[:n]))
        big = [f"키워드{i} 항목{i % 37}" for i in range(3000)]
        t = time.perf_counter()
        order = core.arrange(big)
        dt = time.perf_counter() - t
        print(f"\n  arrange(3000) took {dt:.2f}s")
        self.assertEqual(len(set(order)), 3000)
        self.assertLess(dt, 1.5)


class ParseTest(unittest.TestCase):
    def test_decode_cp949(self):
        text, enc = core.decode_bytes("키워드,점수\n사과,3\n".encode("cp949"))
        self.assertEqual(enc, "CP949")
        self.assertIn("사과", text)
        text, enc = core.decode_bytes("﻿키워드\n사과\n".encode("utf-8"))
        self.assertEqual(text.splitlines()[0], "키워드")

    def test_csv_with_title_header_and_noise_columns(self):
        csv_text = (
            "2026년 키워드 목록,,,\n"
            ",,,\n"
            "번호,키워드,검색량,등록일\n"
            "1,강아지 사료,1200,2026-01-02\n"
            "2,고양이 모래,\"3,400\",2026-01-03\n"
            "3,키워드,0,2026-01-04\n"
            "4,강아지 사료,5,2026-01-05\n"
            "5,여름 휴가,77,2026.01.06\n"
        )
        rows, delim = core.read_csv_rows(csv_text)
        self.assertEqual(delim, ",")
        lay = core.detect_layout(rows)
        self.assertEqual(lay.skip_top, 2)
        self.assertTrue(lay.has_header)
        self.assertEqual(lay.selected, [1])
        kws = core.extract_keywords(rows, lay.skip_top, lay.has_header, lay.selected)
        self.assertEqual(kws, ["강아지 사료", "고양이 모래", "여름 휴가"])

    def test_csv_without_hints(self):
        rows, _ = core.read_csv_rows("상품;가격\n사과;1000\n배;2000\n")
        lay = core.detect_layout(rows)
        self.assertTrue(lay.has_header)  # header on top of a numeric column
        self.assertEqual(lay.selected, [0])
        self.assertEqual(core.extract_keywords(rows, lay.skip_top, lay.has_header, lay.selected), ["사과", "배"])

    def test_group_column(self):
        rows, _ = core.read_csv_rows(
            "Idx,Keyword,Field\n1,알파벳,역사\n2,율리시스,문학\n3,복제,과학\n4,토라,종교\n"
            "5,함무라비 법전,역사\n6,오만과 편견,문학\n7,블랙홀,과학\n8,탈무드,종교\n")
        lay = core.detect_layout(rows)
        self.assertEqual((lay.selected, lay.group_col), ([1], 2))
        entries = core.extract_entries(rows, lay.skip_top, lay.has_header, lay.selected, group_col=lay.group_col)
        self.assertEqual(entries[:2], [("알파벳", "역사"), ("율리시스", "문학")])
        # without a hinted header, a column of short repeated values is guessed as the group
        rows, _ = core.read_csv_rows("".join(f"키워드{i},분야{i % 3}\n" for i in range(12)))
        lay = core.detect_layout(rows)
        self.assertEqual((lay.selected, lay.group_col), ([0], 1))
        # a single keyword column has no group
        self.assertIsNone(core.detect_layout(core.read_csv_rows("사과\n배\n포도\n감\n")[0]).group_col)

    def test_single_column_no_header(self):
        rows, _ = core.read_csv_rows("사과\n배\n포도\n")
        lay = core.detect_layout(rows)
        self.assertFalse(lay.has_header)
        self.assertEqual(core.extract_keywords(rows, 0, False, lay.selected), ["사과", "배", "포도"])

    def test_hint_class(self):
        self.assertEqual(core.hint_class("검색 키워드"), "kw")
        self.assertEqual(core.hint_class("키워드 검색량"), "other")
        self.assertEqual(core.hint_class("Keyword"), "kw")
        self.assertEqual(core.hint_class("No."), "other")
        self.assertIsNone(core.hint_class("사과"))

    def test_txt_and_manual(self):
        self.assertEqual(core.parse_txt("# 주석\n사과\n\n배\n사과\n"), ["사과", "배"])
        self.assertEqual(core.parse_txt("사과, 배, 포도"), ["사과", "배", "포도"])
        self.assertEqual(core.split_manual("사과, 배\n포도"), ["사과", "배", "포도"])
        self.assertEqual(core.split_manual("서울, 부산", split_commas=False), ["서울, 부산"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
