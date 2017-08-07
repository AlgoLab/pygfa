import sys
sys.path.insert(0, '../')

import copy
import unittest

import pygfa

gfa_file = "H\tVN:Z:1.0\n" + "S\t1\t*\tLN:i:6871\tRC:i:2200067\n" \
  + "S\t10\t*\tLN:i:251\tRC:i:82006\n" + "S\t11\t*\tLN:i:208\tRC:i:39533\n" \
  + "S\t12\t*\tLN:i:186\tRC:i:34457\n" + "S\t16\t*\tLN:i:157\tRC:i:15334\n" \
  + "S\t18\t*\tLN:i:145\tRC:i:55632\n" + "S\t19\t*\tLN:i:134\tRC:i:49274\n" \
  + "S\t2\t*\tLN:i:4589\tRC:i:6428225\n" + "S\t20\t*\tLN:i:134\tRC:i:20521\n" \
  + "S\t21\t*\tLN:i:133\tRC:i:28174\n" + "S\t22\t*\tLN:i:132\tRC:i:17846\n" \
  + "S\t23\t*\tLN:i:132\tRC:i:24658\n" + "S\t24\t*\tLN:i:107\tRC:i:22256\n" \
  + "S\t3\t*\tLN:i:2044\tRC:i:2727166\n" + "S\t4\t*\tLN:i:1744\tRC:i:1729157\n" \
  + "S\t5\t*\tLN:i:1378\tRC:i:1071246\n" + "S\t6\t*\tLN:i:1356\tRC:i:422793\n" \
  + "S\t7\t*\tLN:i:920\tRC:i:630822\n" + "S\t8\t*\tLN:i:876\tRC:i:794734\n" \
  + "S\t9\t*\tLN:i:255\tRC:i:40589\n" + "S\t25\t*\tLN:i:1000\n" \
  + "S\t26\t*\tLN:i:1000\n" + "S\t27\t*\tLN:i:1000\n" \
  + "S\t28\t*\tLN:i:1000\n" + "L\t25\t+\t26\t+\t10M\n" \
  + "L\t26\t+\t27\t+\t7M\n" + "L\t27\t+\t28\t+\t10M\n" \
  + "L\t28\t+\t25\t+\t5M\n" + "S\t13\t*\n" \
  + "S\t41\t*\n" + "C\t1\t+\t5\t+\t12\t120M\tID:Z:1_to_5\n" \
  + "P\t15\t41+,13+\t120M\n" + "L\t11\t+\t13\t+\t120M\tID:Z:11_to_13\n" \
  + "L\t1\t+\t2\t+\t10M\n" + "L\t1\t-\t19\t-\t10M\n" \
  + "L\t10\t+\t3\t-\t10M\n" + "L\t10\t-\t4\t+\t10M\n" \
  + "L\t11\t-\t6\t-\t10M\n" + "L\t11\t+\t9\t-\t10M\n" \
  + "L\t12\t+\t9\t+\t10M\n" + "L\t12\t-\t18\t+\t10M\n" \
  + "L\t16\t+\t20\t+\t10M\n" + "L\t16\t-\t22\t-\t10M\n" \
  + "L\t18\t+\t19\t+\t10M\n" + "L\t18\t-\t23\t+\t10M\n" \
  + "L\t2\t+\t5\t+\t10M\n" + "L\t2\t+\t5\t-\t10M\n" \
  + "L\t2\t-\t8\t+\t10M\n" + "L\t20\t+\t21\t+\t10M\n" \
  + "L\t21\t+\t23\t-\t10M\n" + "L\t22\t-\t6\t-\t10M\n" \
  + "L\t24\t+\t7\t+\t10M\n" + "L\t24\t-\t7\t+\t10M\n" \
  + "L\t3\t+\t4\t-\t10M\n" + "L\t3\t-\t6\t+\t10M\n" \
  + "L\t3\t-\t8\t-\t10M\n" + "L\t4\t-\t7\t-\t10M\n"

#
#
#                         [8_8_....     ...        ...          ...           ..8_8]
#            [5         /                                        [13]               \         [10_10]         [24
#    26       5 \      /                                             \               \       /       \        /24
#   /  \      5  [2_2_2]                          [12] --- [9] ------ [11]            [3_3_3]        /       / 24
#  25  27     5 /      \                         /                        \          /       \[4_4_4] --- [7]  24
#   \  /      5]        [1_1_1] --- [19] --- [18]                          [6_6_6_6]                         \ 24
#    28                                          \[23]-[21]-[20]-[16]-[22]/                                   \24]
#
#                 [41_41_41]
#

class TestLine (unittest.TestCase):

    graph = pygfa.gfa.GFA()
    graph.from_string(gfa_file)

    def test_dovetails_linear_path(self):
        self.assertTrue([
                        ("26", "27"),
                        ("27", "28"),
                        ("28", "25")]
                        or
                        [("26", "25"),
                        ("25", "27"),
                        ("27", "28")] == list(pygfa.dovetails_linear_path(self.graph,
                                                                    "26")))
        self.assertTrue([("12", "9")] == list(pygfa.dovetails_linear_path(self.graph,
                                                                    "12")))
        self.assertTrue([
                        ("23", "21"),
                        ("21", "20"),
                        ("20", "16"),
                        ("16", "22")] == list(pygfa.dovetails_linear_path(self.graph,
                                                                    "21")))
        self.assertTrue([("19", "1")] == list(pygfa.dovetails_linear_path(self.graph,
                                                                    "19")))
    def test_dovetails_linear_paths(self):
        self.assertTrue(len(list(pygfa.dovetails_linear_paths(self.graph))) == 4)

if  __name__ == '__main__':
    unittest.main()
